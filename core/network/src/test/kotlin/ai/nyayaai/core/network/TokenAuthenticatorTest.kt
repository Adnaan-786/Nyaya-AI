package ai.nyayaai.core.network

import ai.nyayaai.core.network.auth.SessionEvents
import ai.nyayaai.core.network.auth.TokenAuthenticator
import ai.nyayaai.core.network.auth.TokenStore
import ai.nyayaai.core.network.interceptor.AuthInterceptor
import ai.nyayaai.core.network.service.AuthRefreshService
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.mockwebserver.Dispatcher
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.RecordedRequest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger

/**
 * B.4.4 refresh, under the conditions it actually meets in production.
 *
 * The Today screen issues several requests at once on cold start. When the 30-minute
 * access token has expired they all 401 together — and because refresh tokens **rotate**,
 * a second refresh call would invalidate the first one's result and log the user out.
 * "Single-flight" is therefore a correctness requirement, not an optimisation.
 */
class TokenAuthenticatorTest {
    private lateinit var server: MockWebServer
    private lateinit var tokenStore: FakeTokenStore
    private lateinit var sessionEvents: SessionEvents
    private lateinit var client: OkHttpClient

    private val refreshCount = AtomicInteger(0)

    @Before
    fun setUp() {
        server = MockWebServer().apply { start() }
        tokenStore = FakeTokenStore(access = EXPIRED_TOKEN, refresh = REFRESH_TOKEN)
        sessionEvents = SessionEvents()

        val refreshService =
            Retrofit
                .Builder()
                .baseUrl(server.url("/v1/"))
                .client(OkHttpClient())
                .addConverterFactory(NyayaJson.asConverterFactory(JSON.toMediaType()))
                .build()
                .create(AuthRefreshService::class.java)

        val authenticator =
            TokenAuthenticator(
                tokenStore = tokenStore,
                refreshService = { refreshService },
                sessionEvents = sessionEvents,
                json = NyayaJson,
            )

        client =
            OkHttpClient
                .Builder()
                .addInterceptor(AuthInterceptor(tokenStore))
                .authenticator(authenticator)
                .build()
    }

    @After
    fun tearDown() = server.shutdown()

    @Test
    fun `concurrent 401s trigger exactly one refresh`() {
        server.dispatcher = expiredUntilRefreshed()

        val parallel = 8
        val pool = Executors.newFixedThreadPool(parallel)
        val start = CountDownLatch(1)
        val done = CountDownLatch(parallel)
        val codes = ConcurrentHashMap<Int, Int>()

        repeat(parallel) {
            pool.execute {
                start.await()
                try {
                    client.newCall(get("cases")).execute().use { response ->
                        codes.merge(response.code, 1, Int::plus)
                    }
                } finally {
                    done.countDown()
                }
            }
        }
        start.countDown()
        assertTrue("requests did not finish", done.await(TIMEOUT_SECONDS, TimeUnit.SECONDS))
        pool.shutdown()

        // The whole point: one refresh, not eight.
        assertEquals(1, refreshCount.get())
        assertEquals(parallel, codes[200])
        assertEquals(FRESH_TOKEN, tokenStore.accessToken)
    }

    @Test
    fun `the rotated refresh token replaces the old one`() {
        server.dispatcher = expiredUntilRefreshed()

        client.newCall(get("cases")).execute().use { assertEquals(200, it.code) }

        // B.4.4: refresh rotates; keeping the old token would fail the next refresh.
        assertEquals(FRESH_TOKEN, tokenStore.accessToken)
        assertEquals(ROTATED_REFRESH_TOKEN, tokenStore.refreshToken)
    }

    @Test
    fun `a failed refresh wipes the session and signals a forced logout`() {
        server.dispatcher =
            object : Dispatcher() {
                override fun dispatch(request: RecordedRequest): MockResponse =
                    if (request.path.orEmpty().endsWith("auth/refresh")) {
                        refreshCount.incrementAndGet()
                        // The 30-day refresh token has expired or was rotated out.
                        body(401, errorEnvelope("UNAUTHENTICATED"))
                    } else {
                        body(401, errorEnvelope("TOKEN_EXPIRED"))
                    }
            }

        client.newCall(get("cases")).execute().use { assertEquals(401, it.code) }

        assertFalse(tokenStore.isLoggedIn.value)
        assertEquals(null, tokenStore.accessToken)
        assertNotNull(runBlocking { sessionEvents.forcedLogout.first() })
    }

    @Test
    fun `a plain UNAUTHENTICATED does not attempt a refresh`() {
        server.dispatcher =
            object : Dispatcher() {
                override fun dispatch(request: RecordedRequest): MockResponse {
                    if (request.path.orEmpty().endsWith("auth/refresh")) {
                        refreshCount.incrementAndGet()
                    }
                    return body(401, errorEnvelope("UNAUTHENTICATED"))
                }
            }

        client.newCall(get("cases")).execute().use { assertEquals(401, it.code) }

        // Only TOKEN_EXPIRED is refreshable; retrying anything else just fails slower.
        assertEquals(0, refreshCount.get())
    }

    /** 401s every protected call until a refresh happens, then serves 200s. */
    private fun expiredUntilRefreshed() =
        object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.path.orEmpty()
                return when {
                    path.endsWith("auth/refresh") -> {
                        refreshCount.incrementAndGet()
                        // Deliberately slow, so the other threads pile up on the mutex —
                        // without single-flight this is where the extra refreshes happen.
                        Thread.sleep(REFRESH_DELAY_MS)
                        body(
                            200,
                            """
                            {"success":true,
                             "data":{"access_token":"$FRESH_TOKEN",
                                     "refresh_token":"$ROTATED_REFRESH_TOKEN"},
                             "error":null}
                            """.trimIndent(),
                        )
                    }

                    request.getHeader("Authorization") == "Bearer $FRESH_TOKEN" ->
                        body(200, """{"success":true,"data":{},"error":null}""")

                    else -> body(401, errorEnvelope("TOKEN_EXPIRED"))
                }
            }
        }

    private fun get(path: String) =
        Request
            .Builder()
            .url(server.url("/v1/$path"))
            .build()

    private fun body(
        code: Int,
        json: String,
    ) = MockResponse()
        .setResponseCode(code)
        .setHeader("Content-Type", JSON)
        .setBody(json)

    private fun errorEnvelope(code: String) =
        """{"success":false,"data":null,
            "error":{"code":"$code","message":"m","details":{}}}"""

    private class FakeTokenStore(
        access: String?,
        refresh: String?,
    ) : TokenStore {
        private val _isLoggedIn = MutableStateFlow(access != null)
        override val isLoggedIn: StateFlow<Boolean> = _isLoggedIn.asStateFlow()

        @Volatile override var accessToken: String? = access
            private set

        @Volatile override var refreshToken: String? = refresh
            private set

        override fun save(
            accessToken: String,
            refreshToken: String,
        ) {
            this.accessToken = accessToken
            this.refreshToken = refreshToken
            _isLoggedIn.value = true
        }

        override fun clear() {
            accessToken = null
            refreshToken = null
            _isLoggedIn.value = false
        }
    }

    private companion object {
        const val JSON = "application/json"
        const val EXPIRED_TOKEN = "expired-access-token"
        const val FRESH_TOKEN = "fresh-access-token"
        const val REFRESH_TOKEN = "refresh-token"
        const val ROTATED_REFRESH_TOKEN = "rotated-refresh-token"
        const val REFRESH_DELAY_MS = 250L
        const val TIMEOUT_SECONDS = 20L
    }
}
