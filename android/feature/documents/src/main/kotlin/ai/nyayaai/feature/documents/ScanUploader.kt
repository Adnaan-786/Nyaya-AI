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
import android.content.Context
import android.net.Uri
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import javax.inject.Inject
import javax.inject.Singleton

private const val PDF_MIME = "application/pdf"

/**
 * B.9 upload, all three steps: reserve, PUT, confirm.
 *
 * The confirm step is not optional. Without it the server holds a row claiming a file
 * that may never have been written, and only confirmed documents appear in listings —
 * so an upload that dies after the PUT is invisible rather than silently corrupt.
 */
@Singleton
class ScanUploader
    @Inject
    constructor(
        private val service: DocumentService,
        private val caller: ApiCaller,
    ) {
        suspend fun upload(
            context: Context,
            uri: Uri,
            name: String,
            caseId: CaseId?,
            folder: String?,
        ): ApiResult<Document> {
            val bytes =
                runCatching {
                    context.contentResolver.openInputStream(uri)?.use { it.readBytes() }
                }.getOrNull()
                    ?: return ApiResult.Failure(
                        ApiError.Validation("The scan could not be read.", emptyMap()),
                    )

            val issued =
                caller.call {
                    service.createUploadUrl(
                        UploadUrlRequestDto(
                            name = name,
                            mimeType = PDF_MIME,
                            sizeBytes = bytes.size.toLong(),
                            caseId = caseId?.value,
                            folder = folder,
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

            val put =
                runCatching {
                    service.uploadBytes(uploadUrl, bytes.toRequestBody(PDF_MIME.toMediaType()))
                }.getOrNull()

            // A 403 here is usually an expired signature rather than a real denial. A5
            // turns this into a re-request and resume inside the WorkManager queue; for
            // now the user is told plainly instead of seeing a silent no-op.
            return if (put?.isSuccessful != true) {
                ApiResult.Failure(
                    ApiError.Network("The upload did not complete. Please try again.", null),
                )
            } else {
                caller.call { service.confirmUpload(documentId) }.map { it.toDomain() }
            }
        }
    }
