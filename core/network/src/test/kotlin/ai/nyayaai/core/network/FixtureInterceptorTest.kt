package ai.nyayaai.core.network

import ai.nyayaai.core.network.api.ApiCaller
import ai.nyayaai.core.network.api.ApiError
import ai.nyayaai.core.network.api.ApiResult
import ai.nyayaai.core.network.fixture.FixtureInterceptor
import ai.nyayaai.core.network.fixture.FixtureSource
import ai.nyayaai.core.network.interceptor.IdempotencyInterceptor
import ai.nyayaai.core.network.service.AuthService
import kotlinx.coroutines.test.runTest
import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory

/**
 * The mock flavor must exercise the **real** stack, not bypass it. These tests assert that
 * a fixture-backed request still goes through JSON parsing, the idempotency interceptor
 * and error mapping — which is what makes "works on mock" evidence that the app will work
 * against Part 1's server.
 */
class FixtureInterceptorTest {
    @Test
    fun `request paths map to fixture names with ids collapsed`() {
        val name = FixtureInterceptor::fixtureName

        assertEquals("post_auth_otp_verify", name("POST", "/v1/auth/otp/verify"))
        assertEquals("get_me", name("GET", "/v1/me"))
        assertEquals(
            "get_cases_id",
            name("GET", "/v1/cases/6f1c8d20-9a3b-4c5d-8e7f-0a1b2c3d4e5f"),
        )
        assertEquals(
            "get_cases_id_hearings",
            name("GET", "/v1/cases/6f1c8d20-9a3b-4c5d-8e7f-0a1b2c3d4e5f/hearings"),
        )
    }

    @Test
    fun `a fixture response is parsed by the same code that parses the server`() =
        runTest {
            val service =
                serviceWith(
                    fixtures =
                        mapOf(
                            "get_me" to
                                """
                                {"success":true,
                                 "data":{"id":"0b7f6c1e-3c2a-4a1e-9c3d-1f2a5b6c7d8e",
                                         "tenant_id":"9a1d2e3f-4b5c-4d6e-8f90-1a2b3c4d5e6f",
                                         "name":"Adv. Meera Raghavan","phone":"+919812345678",
                                         "role":"lawyer","language":"hi",
                                         "created_at":"2026-02-11T05:20:00Z"},
                                 "error":null}
                                """.trimIndent(),
                        ),
                )

            val result = ApiCaller(NyayaJson).call { service.me() }

            assertTrue(result is ApiResult.Success)
            assertEquals("Adv. Meera Raghavan", (result as ApiResult.Success).data.name)
        }

    @Test
    fun `scenario fixtures drive the B3 error paths`() =
        runTest {
            val service =
                serviceWith(
                    fixtures =
                        mapOf(
                            "get_me__upstream_unavailable" to
                                """
                                {"success":false,"data":null,
                                 "error":{"code":"UPSTREAM_UNAVAILABLE",
                                          "message":"eCourts is not responding.","details":{}}}
                                """.trimIndent(),
                        ),
                    scenario = "upstream_unavailable",
                )

            val result = ApiCaller(NyayaJson).call { service.me() }

            // Comes back through the full error-mapping path with the right HTTP status.
            assertTrue((result as ApiResult.Failure).error is ApiError.UpstreamUnavailable)
        }

    @Test
    fun `a missing fixture yields a contract-shaped error not a crash`() =
        runTest {
            val service = serviceWith(fixtures = emptyMap())

            val result = ApiCaller(NyayaJson).call { service.me() }

            val error = (result as ApiResult.Failure).error
            assertTrue(error is ApiError.Unknown)
            // The message names the file to create, so the fix is obvious.
            assertTrue((error as ApiError.Unknown).message.contains("get_me.json"))
        }

    @Test
    fun `mutating calls still get an idempotency key before reaching the fixture`() =
        runTest {
            val seen = mutableListOf<String?>()
            val service =
                serviceWith(
                    fixtures =
                        mapOf(
                            "post_auth_otp_request" to """{"success":true,"data":{"ok":true},"error":null}""",
                        ),
                    spy = { chain ->
                        seen += chain.request().header(IdempotencyInterceptor.HEADER)
                        chain.proceed(chain.request())
                    },
                )

            ApiCaller(NyayaJson).call {
                service.requestOtp(
                    ai.nyayaai.core.network.dto
                        .OtpRequestDto("+919812345678"),
                )
            }

            // Proves the fixture path does not short-circuit the interceptors above it.
            assertNotNull(seen.single())
        }

    private fun serviceWith(
        fixtures: Map<String, String>,
        scenario: String? = null,
        spy: Interceptor? = null,
    ): AuthService {
        val source =
            object : FixtureSource {
                override fun read(name: String): String? = fixtures[name]
            }

        val client =
            OkHttpClient
                .Builder()
                .addInterceptor(IdempotencyInterceptor())
                .apply {
                    if (scenario != null) {
                        addInterceptor { chain ->
                            chain.proceed(
                                chain
                                    .request()
                                    .newBuilder()
                                    .header(FixtureInterceptor.SCENARIO_HEADER, scenario)
                                    .build(),
                            )
                        }
                    }
                    spy?.let(::addInterceptor)
                }.addInterceptor(FixtureInterceptor(source))
                .build()

        return Retrofit
            .Builder()
            .baseUrl("http://localhost/v1/")
            .client(client)
            .addConverterFactory(NyayaJson.asConverterFactory("application/json".toMediaType()))
            .build()
            .create(AuthService::class.java)
    }
}
