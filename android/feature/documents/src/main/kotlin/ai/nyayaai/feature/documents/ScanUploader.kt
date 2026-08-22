package ai.nyayaai.feature.documents

import ai.nyayaai.core.model.CaseId
import ai.nyayaai.core.model.Document
import ai.nyayaai.core.network.api.ApiCaller
import ai.nyayaai.core.network.api.ApiError
import ai.nyayaai.core.network.api.ApiResult
import ai.nyayaai.core.network.api.map
import ai.nyayaai.core.network.dto.UploadUrlRequestDto
import ai.nyayaai.core.network.mapper.toDomain
import ai.nyayaai.core.network.service.DocumentService
import okhttp3.MediaType
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody
import okio.Buffer
import okio.BufferedSink
import okio.buffer
import okio.source
import java.io.InputStream
import java.net.HttpURLConnection
import javax.inject.Inject
import javax.inject.Singleton

private const val PDF_MIME = "application/pdf"

/** B.9's cap. Enforced here — before any network call — not just relied on server-side. */
const val MAX_UPLOAD_BYTES = 50L * 1024 * 1024

/**
 * B.9 upload, all three steps: reserve, PUT, confirm.
 *
 * The confirm step is not optional. Without it the server holds a row claiming a file
 * that may never have been written, and only confirmed documents appear in listings —
 * so an upload that dies after the PUT is invisible rather than silently corrupt.
 *
 * Takes an `openStream` factory rather than a `Context`/`Uri` so it stays plain Kotlin —
 * testable against a real [DocumentService] over MockWebServer — and so it can run
 * unchanged inside [ScanUploadWorker], which reads from a staged file rather than the
 * original scanner `Uri` (see [ScanUploadQueue] for why).
 */
@Singleton
class ScanUploader
    @Inject
    constructor(
        private val service: DocumentService,
        private val caller: ApiCaller,
    ) {
        suspend fun upload(
            name: String,
            sizeBytes: Long,
            caseId: CaseId?,
            folder: String?,
            mimeType: String = PDF_MIME,
            onProgress: (bytesSent: Long) -> Unit = {},
            openStream: () -> InputStream,
        ): ApiResult<Document> {
            // B.9's limit, checked before the server is even asked for an upload URL — a
            // file this large must never reach the point of holding a network connection
            // open (or, before streaming, risking an OOM reading it into memory).
            if (sizeBytes > MAX_UPLOAD_BYTES) {
                return ApiResult.Failure(
                    ApiError.Validation(
                        "This scan is larger than the 50 MB upload limit.",
                        mapOf("size_bytes" to sizeBytes.toString()),
                    ),
                )
            }

            val target = PendingUpload(name, sizeBytes, mimeType, caseId, folder, onProgress, openStream)
            return reserveAndPut(target, retryOnExpiredUrl = true)
        }

        private suspend fun reserveAndPut(
            target: PendingUpload,
            retryOnExpiredUrl: Boolean,
        ): ApiResult<Document> {
            val issued =
                caller.call {
                    service.createUploadUrl(
                        UploadUrlRequestDto(
                            name = target.name,
                            mimeType = target.mimeType,
                            sizeBytes = target.sizeBytes,
                            caseId = target.caseId?.value,
                            folder = target.folder,
                        ),
                    )
                }

            val ticket =
                when (issued) {
                    is ApiResult.Failure -> return issued
                    is ApiResult.Success -> issued.data
                }

            val uploadUrl = ticket.uploadUrl
            val documentId = ticket.documentId
            if (uploadUrl == null || documentId == null) {
                return ApiResult.Failure(
                    ApiError.ContractViolation(
                        message = "The server did not return an upload URL.",
                        detail = "upload_url or document_id was missing",
                        cause = null,
                    ),
                )
            }

            val body =
                StreamingRequestBody(
                    target.sizeBytes,
                    target.mimeType.toMediaType(),
                    target.onProgress,
                    target.openStream,
                )
            val put = runCatching { service.uploadBytes(uploadUrl, body) }.getOrNull()

            return when {
                put?.isSuccessful == true ->
                    caller.call { service.confirmUpload(documentId) }.map { it.toDomain() }

                // The presigned URL is good for ~15 minutes (B.9); a 403 here almost always
                // means it lapsed while the PUT was in flight or queued offline, not a real
                // denial. One retry with a fresh ticket recovers an upload that would
                // otherwise fail for no reason the lawyer caused.
                put?.code() == HttpURLConnection.HTTP_FORBIDDEN && retryOnExpiredUrl ->
                    reserveAndPut(target, retryOnExpiredUrl = false)

                else ->
                    ApiResult.Failure(
                        ApiError.Network("The upload did not complete. Please try again.", null),
                    )
            }
        }

        private class PendingUpload(
            val name: String,
            val sizeBytes: Long,
            val mimeType: String,
            val caseId: CaseId?,
            val folder: String?,
            val onProgress: (bytesSent: Long) -> Unit,
            val openStream: () -> InputStream,
        )
    }

/**
 * Streams `openStream()`'s bytes straight to the sink instead of holding the whole file
 * in memory — the plain `ByteArray` this replaced risked OOM on a large scan and made the
 * 50 MB check moot for anything that got past it. `onProgress` reports cumulative bytes
 * written, which [ScanUploadWorker] turns into the upload notification's percentage.
 */
private class StreamingRequestBody(
    private val length: Long,
    private val mediaType: MediaType,
    private val onProgress: (bytesSent: Long) -> Unit,
    private val openStream: () -> InputStream,
) : RequestBody() {
    override fun contentType(): MediaType = mediaType

    override fun contentLength(): Long = length

    override fun writeTo(sink: BufferedSink) {
        openStream().source().buffer().use { source ->
            val buffer = Buffer()
            var sent = 0L
            var read: Long
            while (source.read(buffer, SEGMENT_SIZE).also { read = it } != -1L) {
                sink.write(buffer, read)
                sent += read
                onProgress(sent)
            }
        }
    }

    private companion object {
        const val SEGMENT_SIZE = 8192L
    }
}
