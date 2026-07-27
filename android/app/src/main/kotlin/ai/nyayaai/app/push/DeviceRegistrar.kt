package ai.nyayaai.app.push

import ai.nyayaai.core.network.api.ApiCaller
import ai.nyayaai.core.network.api.ApiResult
import ai.nyayaai.core.network.auth.TokenStore
import ai.nyayaai.core.network.dto.DeviceRegistrationDto
import ai.nyayaai.core.network.service.AuthService
import android.util.Log
import com.google.firebase.messaging.FirebaseMessaging
import kotlinx.coroutines.tasks.await
import javax.inject.Inject
import javax.inject.Singleton

/**
 * B.4.6: `POST /devices` after every login and after every FCM token refresh.
 *
 * All Firebase access in the app funnels through here, which is what lets the app run
 * with **no** `google-services.json` at all: every call is guarded, and a missing
 * Firebase config degrades to "no push" rather than to a crash on startup. That matters
 * because the demo has to work before anyone has created a Firebase project.
 */
@Singleton
class DeviceRegistrar
    @Inject
    constructor(
        private val service: AuthService,
        private val caller: ApiCaller,
        private val tokenStore: TokenStore,
    ) {
        /** Fetches the current FCM token and registers it. Safe to call repeatedly. */
        suspend fun registerCurrentToken(appVersion: String) {
            val token = currentToken() ?: return
            register(token, appVersion)
        }

        suspend fun register(
            fcmToken: String,
            appVersion: String = UNKNOWN_VERSION,
        ) {
            // Registering while logged out would attach this device to nobody; the
            // login flow calls us again once there is a session.
            if (tokenStore.accessToken == null) return

            val result =
                caller.call {
                    service.registerDevice(
                        DeviceRegistrationDto(fcmToken = fcmToken, appVersion = appVersion),
                    )
                }

            if (result is ApiResult.Failure) {
                // Not fatal: the user simply gets no push until the next attempt. Failing
                // login over a notification token would be the wrong trade.
                Log.w(TAG, "device registration failed: ${result.error.message}")
            }
        }

        private suspend fun currentToken(): String? =
            runCatching { FirebaseMessaging.getInstance().token.await() }
                .onFailure { Log.i(TAG, "FCM unavailable (no google-services.json?): ${it.message}") }
                .getOrNull()

        private companion object {
            const val TAG = "DeviceRegistrar"
            const val UNKNOWN_VERSION = "0"
        }
    }
