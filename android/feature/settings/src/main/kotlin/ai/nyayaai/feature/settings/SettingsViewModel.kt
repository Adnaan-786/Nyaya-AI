package ai.nyayaai.feature.settings

import ai.nyayaai.core.model.Language
import ai.nyayaai.core.network.api.ApiCaller
import ai.nyayaai.core.network.auth.TokenStore
import ai.nyayaai.core.network.service.AuthService
import androidx.appcompat.app.AppCompatDelegate
import androidx.core.os.LocaleListCompat
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull
import javax.inject.Inject

@HiltViewModel
class SettingsViewModel
    @Inject
    constructor(
        // Injected directly rather than through feature:auth — features must not depend
        // on each other (D.2), and clearing the session is a core:network concern.
        private val tokenStore: TokenStore,
        private val authService: AuthService,
        private val caller: ApiCaller,
    ) : ViewModel() {
        /**
         * D.11.4: logout wipes the token pair. Room and cached files are wiped here too
         * once offline caching lands — a shared device must not leave one lawyer's
         * privileged case data readable by the next person to sign in.
         *
         * Unregistering this device first (`DELETE /devices/{id}`) stops the outgoing
         * lawyer's pushes from following the next person who signs in on a shared handset.
         * It is best-effort: the call needs a valid access token, so it must run and settle
         * before [TokenStore.clear] wipes the one it needs — but a slow or unreachable
         * server must never meaningfully delay sign-out, so it is capped at two seconds.
         * Worst case the device row is orphaned server-side, which is harmless.
         */
        fun logout(onComplete: () -> Unit) {
            viewModelScope.launch {
                withTimeoutOrNull(LOGOUT_UNREGISTER_TIMEOUT_MS) {
                    tokenStore.deviceId?.let { id ->
                        runCatching { caller.call { authService.unregisterDevice(id) } }
                    }
                }
                tokenStore.clear()
                onComplete()
            }
        }

        fun setLanguage(language: Language) {
            // Per-app language: the OS remembers it across launches and it does not
            // change the device locale for anything else.
            AppCompatDelegate.setApplicationLocales(
                LocaleListCompat.forLanguageTags(language.wire),
            )
        }

        private companion object {
            const val LOGOUT_UNREGISTER_TIMEOUT_MS = 2_000L
        }
    }
