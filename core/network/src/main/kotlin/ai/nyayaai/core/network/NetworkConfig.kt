package ai.nyayaai.core.network

/**
 * Supplied by `:app` from the flavor's BuildConfig (B.2 environments).
 *
 * `core:network` deliberately has no flavors of its own — propagating three flavors across
 * sixteen modules buys nothing, and keeping the environment as injected data means the
 * whole stack can be exercised in unit tests by handing it a MockWebServer URL.
 */
data class NetworkConfig(
    val baseUrl: String,
    /**
     * Mock flavor only. Serves recorded JSON **through the real OkHttp stack** rather than
     * short-circuiting to in-memory objects, so JSON parsing, the auth interceptor, the
     * authenticator and error mapping are all exercised in daily development. Mock and
     * staging then differ only by base URL — which is the only thing that makes "works on
     * mock" evidence that the app will work against Part 1.
     */
    val useFixtures: Boolean,
    val appVersionCode: Int,
    val appVersionName: String,
    val enableHttpLogging: Boolean,
)
