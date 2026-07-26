package ai.nyayaai.core.network

import ai.nyayaai.core.network.api.ApiCaller
import ai.nyayaai.core.network.api.ApiEnvelope
import ai.nyayaai.core.network.api.ApiError
import ai.nyayaai.core.network.api.ApiResult
import ai.nyayaai.core.network.dto.UserDto
import ai.nyayaai.core.network.service.AuthService
import kotlinx.coroutines.test.runTest
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory

/**
 * B.3 says the app must handle **every** error code. These run against a real
 * MockWebServer through a real Retrofit/OkHttp stack, so what is verified is the same path
 * the app takes against staging — not a mocked-out approximation of it.
 */
class ApiCallerTest {
    private lateinit var server: MockWebServer
    private lateinit var service: AuthService
    private val caller = ApiCaller(NyayaJson)

    @Before
    fun setUp() {
        server = MockWebServer().apply { start() }
        service =
            Retrofit
                .Builder()
                .baseUrl(server.url("/v1/"))
                .client(OkHttpClient())
                .addConverterFactory(NyayaJson.asConverterFactory("application/json".toMediaType()))
                .build()
                .create(AuthService::class.java)
    }

    @After
    fun tearDown() = server.shutdown()

    @Test
    fun `success envelope is unwrapped to its data`() =
        runTest {
            server.enqueue(
                json(
                    200,
                    """
                {"success":true,
                 "data":{"id":"11111111-1111-4111-8111-111111111111",
                         "tenant_id":"22222222-2222-4222-8222-222222222222",
                         "name":"Adv. Meera Raghavan","phone":"+919812345678",
                         "role":"lawyer","language":"hi",
                         "created_at":"2026-07-23T10:30:00Z"},
                 "error":null}
                """,
                ),
            )

            val result = caller.call { service.me() }

            assertTrue(result is ApiResult.Success)
            assertEquals("Adv. Meera Raghavan", (result as ApiResult.Success).data.name)
        }

    @Test
    fun `quota exceeded carries the paywall details from B14`() =
        runTest {
            server.enqueue(
                json(
                    402,
                    """
                {"success":false,"data":null,
                 "error":{"code":"QUOTA_EXCEEDED",
                          "message":"You have used all 20 AI jobs today.",
                          "details":{"limit":"20","plan":"solo","upgrade_to":"firm"}}}
                """,
                ),
            )

            val error = failureOf { service.me() }

            assertTrue(error is ApiError.QuotaExceeded)
            with(error as ApiError.QuotaExceeded) {
                assertEquals(20, limit)
                assertEquals("solo", plan)
                // B.14: the paywall opens with this plan preselected.
                assertEquals("firm", upgradeTo)
            }
        }

    @Test
    fun `not found codes expose which resource was missing`() =
        runTest {
            server.enqueue(
                json(
                    404,
                    """
                {"success":false,"data":null,
                 "error":{"code":"CASE_NOT_FOUND",
                          "message":"No case with this ID in your firm.","details":{}}}
                """,
                ),
            )

            val error = failureOf { service.me() }

            assertTrue(error is ApiError.NotFound)
            assertEquals("case", (error as ApiError.NotFound).resource)
        }

    @Test
    fun `cnr invalid is a distinct type so the field can show it inline`() =
        runTest {
            server.enqueue(
                json(
                    422,
                    """
                {"success":false,"data":null,
                 "error":{"code":"CNR_INVALID","message":"CNR must be 16 characters.",
                          "details":{}}}
                """,
                ),
            )

            assertTrue(failureOf { service.me() } is ApiError.CnrInvalid)
        }

    @Test
    fun `every remaining B3 code maps to its own type`() =
        runTest {
            val cases =
                listOf(
                    Triple(400, "VALIDATION_ERROR", ApiError.Validation::class),
                    Triple(401, "UNAUTHENTICATED", ApiError.Unauthenticated::class),
                    Triple(401, "TOKEN_EXPIRED", ApiError.TokenExpired::class),
                    Triple(403, "FORBIDDEN_ROLE", ApiError.ForbiddenRole::class),
                    Triple(409, "DUPLICATE_RESOURCE", ApiError.DuplicateResource::class),
                    Triple(426, "UPGRADE_REQUIRED", ApiError.UpgradeRequired::class),
                    Triple(429, "RATE_LIMITED", ApiError.RateLimited::class),
                    Triple(500, "INTERNAL_ERROR", ApiError.InternalError::class),
                    Triple(503, "UPSTREAM_UNAVAILABLE", ApiError.UpstreamUnavailable::class),
                )

            cases.forEach { (status, code, expected) ->
                server.enqueue(
                    json(
                        status,
                        """{"success":false,"data":null,
                        "error":{"code":"$code","message":"m","details":{}}}""",
                    ),
                )
                assertEquals(code, expected, failureOf { service.me() }!!::class)
            }
        }

    @Test
    fun `an unrecognised code falls back to Unknown rather than throwing`() =
        runTest {
            server.enqueue(
                json(
                    418,
                    """{"success":false,"data":null,
                    "error":{"code":"TEAPOT_ON_FIRE","message":"?","details":{}}}""",
                ),
            )

            val error = failureOf { service.me() }

            assertTrue(error is ApiError.Unknown)
            assertEquals("TEAPOT_ON_FIRE", (error as ApiError.Unknown).code)
        }

    @Test
    fun `a non-envelope error body is reported as a contract violation`() =
        runTest {
            // B.1.4 forbids this. When it happens we must be able to name it in a bug report.
            server.enqueue(
                MockResponse()
                    .setResponseCode(502)
                    .setHeader("Content-Type", "text/html")
                    .setBody("<html><body>502 Bad Gateway</body></html>"),
            )

            val error = failureOf { service.me() }

            assertTrue(error is ApiError.ContractViolation)
            assertTrue((error as ApiError.ContractViolation).detail.contains("502"))
        }

    @Test
    fun `success true with a null body is a contract violation not an empty screen`() =
        runTest {
            server.enqueue(json(200, """{"success":true,"data":null,"error":null}"""))

            assertTrue(failureOf { service.me() } is ApiError.ContractViolation)
        }

    @Test
    fun `a dropped connection becomes a Network error not a crash`() =
        runTest {
            server.shutdown()

            val error = failureOf { service.me() }

            assertTrue(error is ApiError.Network)
        }

    private suspend fun failureOf(block: suspend () -> ApiEnvelope<UserDto>): ApiError? =
        (caller.call(block) as? ApiResult.Failure)?.error

    private fun json(
        code: Int,
        body: String,
    ) = MockResponse()
        .setResponseCode(code)
        .setHeader("Content-Type", "application/json")
        .setBody(body.trimIndent())
}
