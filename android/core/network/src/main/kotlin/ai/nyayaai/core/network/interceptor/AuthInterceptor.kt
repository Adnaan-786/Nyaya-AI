package ai.nyayaai.core.network.interceptor

import ai.nyayaai.core.network.auth.TokenStore
import okhttp3.Interceptor
import okhttp3.Request
import okhttp3.Response
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Attaches `Authorization: Bearer <token>` (B.4.3).
 *
 * The `/auth` paths and `/app/config` are unauthenticated per B.6 — sending a stale token to the
 * refresh endpoint in particular would make token rotation fail in confusing ways.
 */
@Singleton
class AuthInterceptor
    @Inject
    constructor(
        private val tokenStore: TokenStore,
    ) : Interceptor {
        override fun intercept(chain: Interceptor.Chain): Response {
            val request = chain.request()
            if (isPublic(request)) return chain.proceed(request)

            val token = tokenStore.accessToken ?: return chain.proceed(request)

            return chain.proceed(
                request
                    .newBuilder()
                    .header("Authorization", "Bearer $token")
                    .build(),
            )
        }

        private fun isPublic(request: Request): Boolean {
            val path = request.url.encodedPath
            return PUBLIC_PATHS.any { path.contains(it) }
        }

        private companion object {
            val PUBLIC_PATHS = listOf("/auth/", "/app/config", "/legal/consent-text")
        }
    }
