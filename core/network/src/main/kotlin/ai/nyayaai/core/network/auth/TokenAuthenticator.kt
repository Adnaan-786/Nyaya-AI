package ai.nyayaai.core.network.auth

import ai.nyayaai.core.network.api.ApiEnvelope
import ai.nyayaai.core.network.api.ApiError
import ai.nyayaai.core.network.dto.RefreshRequestDto
import ai.nyayaai.core.network.dto.TokenPairDto
import ai.nyayaai.core.network.service.AuthRefreshService
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.serialization.json.Json
import okhttp3.Authenticator
import okhttp3.Request
import okhttp3.Response
import okhttp3.Route
import javax.inject.Inject
import javax.inject.Provider
import javax.inject.Singleton

/**
 * B.4.4 token refresh, with **single-flight** semantics.
 *
 * The Today screen fires several requests at once on cold start. When the 30-minute access
 * token has expired they all come back 401 together. Refreshing once per 401 would burn
 * the rotated refresh token on the first call and log the user out on the rest — so every
 * caller queues on one mutex, and whoever loses the race simply retries with the token the
 * winner already fetched.
 */
@Singleton
class TokenAuthenticator
    @Inject
    constructor(
        private val tokenStore: TokenStore,
        private val refreshService: Provider<AuthRefreshService>,
        private val sessionEvents: SessionEvents,
        private val json: Json,
    ) : Authenticator {
        private val mutex = Mutex()

        override fun authenticate(
            route: Route?,
            response: Response,
        ): Request? {
            val failedToken =
                response.request
                    .header(HEADER_AUTH)
                    ?.removePrefix(BEARER)
                    ?: return null // Unauthenticated route; nothing to refresh.

            // Give up rather than loop if the refreshed token is also rejected.
            if (response.priorResponseCount() >= MAX_ATTEMPTS) {
                forceLogout()
                return null
            }

            // Only TOKEN_EXPIRED is refreshable. A plain UNAUTHENTICATED means the session is
            // genuinely invalid and retrying would just fail again more slowly.
            if (!response.isTokenExpired()) return null

            return runBlocking {
                mutex.withLock {
                    val current = tokenStore.accessToken

                    // Someone else refreshed while we waited for the lock — reuse their token.
                    if (current != null && current != failedToken) {
                        return@withLock response.request.withToken(current)
                    }

                    val refreshToken =
                        tokenStore.refreshToken ?: run {
                            forceLogout()
                            return@withLock null
                        }

                    val refreshed =
                        runCatching {
                            refreshService.get().refresh(RefreshRequestDto(refreshToken))
                        }.getOrNull()

                    val pair: TokenPairDto? = refreshed?.takeIf { it.success }?.data
                    if (pair?.accessToken == null || pair.refreshToken == null) {
                        // B.4.4: refresh tokens rotate, so a failure here is terminal.
                        forceLogout()
                        return@withLock null
                    }

                    tokenStore.save(pair.accessToken, pair.refreshToken)
                    response.request.withToken(pair.accessToken)
                }
            }
        }

        private fun forceLogout() {
            tokenStore.clear()
            sessionEvents.notifyForcedLogout()
        }

        private fun Request.withToken(token: String): Request =
            newBuilder().header(HEADER_AUTH, "$BEARER$token").build()

        private fun Response.priorResponseCount(): Int {
            var count = 1
            var prior = priorResponse
            while (prior != null) {
                count++
                prior = prior.priorResponse
            }
            return count
        }

        /** Peeks the error envelope without consuming the body the caller still needs. */
        private fun Response.isTokenExpired(): Boolean {
            val snapshot = runCatching { peekBody(PEEK_BYTES).string() }.getOrNull() ?: return false
            val code =
                runCatching {
                    json
                        .decodeFromString(
                            ApiEnvelope.serializer(
                                kotlinx.serialization.json.JsonObject
                                    .serializer(),
                            ),
                            snapshot,
                        ).error
                        ?.code
                }.getOrNull()
            return code == ApiError.CODE_TOKEN_EXPIRED
        }

        private companion object {
            const val HEADER_AUTH = "Authorization"
            const val BEARER = "Bearer "
            const val MAX_ATTEMPTS = 2
            const val PEEK_BYTES = 4096L
        }
    }
