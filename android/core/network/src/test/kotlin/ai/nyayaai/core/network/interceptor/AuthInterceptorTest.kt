package ai.nyayaai.core.network.interceptor

import ai.nyayaai.core.network.auth.TokenStore
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test

class AuthInterceptorTest {

    private class FakeTokenStore : TokenStore {
        override val isLoggedIn = kotlinx.coroutines.flow.MutableStateFlow(true)
        override var accessToken: String? = "fake_token"
        override var refreshToken: String? = "fake_refresh"
        override var deviceId: String? = "fake_device"
        override fun save(access: String, refresh: String) {}
        override fun clear() {}
    }

    private val server = MockWebServer()
    private lateinit var client: OkHttpClient

    @Before
    fun setUp() {
        server.start()
        client = OkHttpClient.Builder()
            .addInterceptor(AuthInterceptor(FakeTokenStore()))
            .build()
    }

    @After
    fun tearDown() = server.shutdown()

    @Test
    fun `attaches Bearer token to normal requests`() {
        server.enqueue(MockResponse())
        
        val request = Request.Builder()
            .url(server.url("/v1/uploads/123"))
            .build()
            
        client.newCall(request).execute().use { it.close() }
        
        val recorded = server.takeRequest()
        assertEquals("Bearer fake_token", recorded.getHeader("Authorization"))
    }

    @Test
    fun `skips Bearer token for public paths`() {
        server.enqueue(MockResponse())
        
        val request = Request.Builder()
            .url(server.url("/auth/login"))
            .build()
            
        client.newCall(request).execute().use { it.close() }
        
        val recorded = server.takeRequest()
        assertNull(recorded.getHeader("Authorization"))
    }

    @Test
    fun `skips Bearer token for S3 presigned URLs`() {
        server.enqueue(MockResponse())
        
        val request = Request.Builder()
            .url(server.url("/my-bucket/obj?X-Amz-Signature=12345"))
            .build()
            
        client.newCall(request).execute().use { it.close() }
        
        val recorded = server.takeRequest()
        assertNull(recorded.getHeader("Authorization"))
    }
}
