package ai.nyayaai.feature.documents

import ai.nyayaai.core.network.NyayaJson
import ai.nyayaai.core.network.api.ApiCaller
import ai.nyayaai.core.network.api.ApiError
import ai.nyayaai.core.network.api.ApiResult
import ai.nyayaai.core.network.service.DocumentService
import kotlinx.coroutines.test.runTest
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.SocketPolicy
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import java.io.ByteArrayInputStream
import java.util.concurrent.TimeUnit

/**
 * The two things the AI-sync/Android audit flagged as untested (D.7/B.9): the 50 MB cap
 * is enforced before any network call, and a 403 on the PUT — an expired presigned URL,
 * per B.9's ~15 minute window — is retried once with a fresh ticket rather than failing
 * an upload the lawyer did nothing wrong on.
 *
 * Runs against a real [DocumentService] over [MockWebServer], the same style as
 * `core:network`'s `ApiCallerTest` — what is verified is the real Retrofit/OkHttp path,
 * not a hand-rolled fake of it.
 */
class ScanUploaderTest {
    private lateinit var server: MockWebServer
    private lateinit var uploader: ScanUploader

    @Before
    fun setUp() {
        server = MockWebServer().apply { start() }
        val service =
            Retrofit
                .Builder()
                .baseUrl(server.url("/v1/"))
                .client(
                    OkHttpClient
                        .Builder()
                        // Short and explicit: DISCONNECT_AT_START otherwise hangs on
                        // OkHttp's 10s default connect timeout before failing.
                        .connectTimeout(2, TimeUnit.SECONDS)
                        .readTimeout(2, TimeUnit.SECONDS)
                        .build(),
                )
                .addConverterFactory(NyayaJson.asConverterFactory("application/json".toMediaType()))
                .build()
                .create(DocumentService::class.java)
        uploader = ScanUploader(service, ApiCaller(NyayaJson))
    }

    @After
    fun tearDown() = server.shutdown()

    @Test
    fun `a scan over the 50MB limit is rejected before any network call`() =
        runTest {
            val result =
                uploader.upload(
                    name = "huge.pdf",
                    sizeBytes = MAX_UPLOAD_BYTES + 1,
                    caseId = null,
                    folder = null,
                ) { ByteArrayInputStream(ByteArray(0)) }

            assertTrue(result is ApiResult.Failure)
            assertTrue((result as ApiResult.Failure).error is ApiError.Validation)
            // The whole point: a file this large must never hold a connection open, not
            // even to ask for an upload URL.
            assertEquals(0, server.requestCount)
        }

    @Test
    fun `a scan exactly at the 50MB limit is allowed`() =
        runTest {
            server.enqueue(uploadUrlResponse("doc-1"))
            server.enqueue(MockResponse().setResponseCode(200))
            server.enqueue(confirmResponse("doc-1"))

            // Content-Length must match what is actually streamed, so the boundary check
            // (`>`, not `>=`) is proven with real bytes rather than a declared size the
            // body does not back up.
            val bytes = ByteArray(MAX_UPLOAD_BYTES.toInt())
            val result =
                uploader.upload(
                    name = "exact.pdf",
                    sizeBytes = bytes.size.toLong(),
                    caseId = null,
                    folder = null,
                ) { ByteArrayInputStream(bytes) }

            assertTrue(result is ApiResult.Success)
        }

    @Test
    fun `a 403 on the PUT is treated as an expired presigned URL and retried once`() =
        runTest {
            val bytes = "%PDF-1.4 scan bytes".toByteArray()

            server.enqueue(uploadUrlResponse("doc-1"))
            server.enqueue(MockResponse().setResponseCode(403)) // the presigned URL lapsed
            server.enqueue(uploadUrlResponse("doc-2")) // B.9: request a fresh ticket
            server.enqueue(MockResponse().setResponseCode(200))
            server.enqueue(confirmResponse("doc-2"))

            var opens = 0
            val result =
                uploader.upload(
                    name = "scan.pdf",
                    sizeBytes = bytes.size.toLong(),
                    caseId = null,
                    folder = null,
                ) {
                    opens++
                    ByteArrayInputStream(bytes)
                }

            assertTrue(result is ApiResult.Success)
            // Streamed fresh on the retry too — not replayed from an already-drained stream.
            assertEquals(2, opens)

            assertEquals(5, server.requestCount)
            assertEquals("/v1/documents/upload-url", server.takeRequest().path)
            assertEquals("/v1/uploads/doc-1", server.takeRequest().path?.substringBefore('?'))
            assertEquals("/v1/documents/upload-url", server.takeRequest().path)
            assertEquals("/v1/uploads/doc-2", server.takeRequest().path?.substringBefore('?'))
            assertEquals("/v1/documents/doc-2/confirm", server.takeRequest().path)
        }

    @Test
    fun `a second 403 is not retried again — one retry only`() =
        runTest {
            server.enqueue(uploadUrlResponse("doc-1"))
            server.enqueue(MockResponse().setResponseCode(403))
            server.enqueue(uploadUrlResponse("doc-2"))
            server.enqueue(MockResponse().setResponseCode(403))

            val result =
                uploader.upload(
                    name = "scan.pdf",
                    sizeBytes = 4,
                    caseId = null,
                    folder = null,
                ) { ByteArrayInputStream(byteArrayOf(1, 2, 3, 4)) }

            assertTrue(result is ApiResult.Failure)
            assertEquals(4, server.requestCount)
        }

    @Test
    fun `a dropped connection on the PUT is a Network failure, not a crash`() =
        runTest {
            server.enqueue(uploadUrlResponse("doc-1"))
            server.enqueue(MockResponse().setSocketPolicy(SocketPolicy.DISCONNECT_AT_START))

            val result =
                uploader.upload(
                    name = "scan.pdf",
                    sizeBytes = 4,
                    caseId = null,
                    folder = null,
                ) { ByteArrayInputStream(byteArrayOf(1, 2, 3, 4)) }

            assertTrue(result is ApiResult.Failure)
            assertTrue((result as ApiResult.Failure).error is ApiError.Network)
        }

    private fun uploadUrlResponse(documentId: String) =
        MockResponse()
            .setResponseCode(200)
            .setHeader("Content-Type", "application/json")
            .setBody(
                """
                {"success":true,
                 "data":{"upload_url":"/v1/uploads/$documentId","document_id":"$documentId","expires_in_seconds":900},
                 "error":null}
                """.trimIndent(),
            )

    private fun confirmResponse(documentId: String) =
        MockResponse()
            .setResponseCode(200)
            .setHeader("Content-Type", "application/json")
            .setBody(
                """
                {"success":true,
                 "data":{"id":"$documentId","name":"scan.pdf","size_bytes":4,
                          "created_at":"2026-07-23T10:30:00Z"},
                 "error":null}
                """.trimIndent(),
            )
}
