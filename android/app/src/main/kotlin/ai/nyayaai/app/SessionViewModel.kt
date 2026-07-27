package ai.nyayaai.app

import ai.nyayaai.core.model.User
import ai.nyayaai.core.network.api.ApiCaller
import ai.nyayaai.core.network.api.ApiResult
import ai.nyayaai.core.network.api.map
import ai.nyayaai.core.network.auth.TokenStore
import ai.nyayaai.core.network.mapper.toDomain
import ai.nyayaai.core.network.service.AuthService
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

/**
 * Restores the signed-in user on cold start.
 *
 * Without this the app held the session in `remember` only, so every cold start showed
 * the login screen even though a valid 30-day refresh token was sitting in encrypted
 * storage. That is bad on its own — it costs an OTP, and B.4 rate-limits those to three
 * an hour — but it also broke push entirely: tapping a hearing reminder opened the login
 * screen instead of the case, which is the one moment the notification exists for.
 */
@HiltViewModel
class SessionViewModel
    @Inject
    constructor(
        private val service: AuthService,
        private val caller: ApiCaller,
        private val tokenStore: TokenStore,
    ) : ViewModel() {
        private val _state = MutableStateFlow<SessionState>(SessionState.Restoring)
        val state: StateFlow<SessionState> = _state.asStateFlow()

        init {
            restore()
        }

        private fun restore() {
            if (tokenStore.accessToken == null) {
                _state.value = SessionState.SignedOut
                return
            }

            viewModelScope.launch {
                // A stored token is not proof of a live session — it may have expired, or
                // the account may be gone. `GET /me` is the cheapest way to find out, and
                // the Authenticator refreshes underneath it if the access token is stale.
                when (val me = caller.call { service.me() }.map { it.toDomain() }) {
                    is ApiResult.Success -> _state.value = SessionState.SignedIn(me.data)

                    is ApiResult.Failure -> {
                        // Anything that reaches here after the refresh attempt means the
                        // session is genuinely unusable. Clearing prevents a loop where
                        // every launch retries a token that will never work again.
                        tokenStore.clear()
                        _state.value = SessionState.SignedOut
                    }
                }
            }
        }

        fun onSignedIn(user: User) {
            _state.value = SessionState.SignedIn(user)
        }

        fun onSignedOut() {
            _state.value = SessionState.SignedOut
        }
    }

sealed interface SessionState {
    /** Held only for as long as `GET /me` takes; the splash theme covers it. */
    data object Restoring : SessionState

    data object SignedOut : SessionState

    data class SignedIn(
        val user: User,
    ) : SessionState
}
