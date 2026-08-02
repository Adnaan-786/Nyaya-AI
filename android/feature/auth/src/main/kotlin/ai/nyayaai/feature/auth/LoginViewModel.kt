package ai.nyayaai.feature.auth

import ai.nyayaai.core.model.Language
import ai.nyayaai.core.model.User
import ai.nyayaai.core.network.api.ApiError
import ai.nyayaai.core.network.api.ApiResult
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

/**
 * D.2: every screen is a single [LoginUiState] rendered from a StateFlow. The step field
 * drives navigation within the flow rather than a separate nav graph, because phone entry
 * and OTP entry are one user task.
 */
data class LoginUiState(
    val step: Step = Step.PHONE,
    val phone: String = "",
    val otp: String = "",
    val isSubmitting: Boolean = false,
    val error: String? = null,
    val signedInUser: User? = null,
    val onboardName: String = "",
    val onboardRole: OnboardRole = OnboardRole.LAWYER,
    val onboardFirmName: String = "",
    val onboardBarCouncilId: String = "",
    val onboardLanguage: Language = Language.EN,
) {
    enum class Step { PHONE, OTP, ONBOARDING, SIGNED_IN }

    /** Indian mobile numbers are 10 digits; the +91 prefix is added on submit (D.6). */
    val isPhoneValid: Boolean get() = phone.length == PHONE_LENGTH && phone.all(Char::isDigit)

    val isOtpValid: Boolean get() = otp.length == OTP_LENGTH && otp.all(Char::isDigit)

    /**
     * `role_hint` always carries a valid default from the dropdown, so name is the only
     * field the server actually requires (`POST /auth/onboard`).
     */
    val isOnboardingValid: Boolean get() = onboardName.isNotBlank()

    companion object {
        const val PHONE_LENGTH = 10
        const val OTP_LENGTH = 6
        const val COUNTRY_CODE = "+91"
    }
}

/**
 * The server's `role_hint` is regex-validated to only `"lawyer"` or `"firm_admin"` — narrower
 * than [ai.nyayaai.core.model.UserRole], which also covers roles nobody picks at sign-up
 * (intern, client are assigned later by a firm admin, not chosen by the new user themselves).
 */
enum class OnboardRole(val wire: String) {
    LAWYER("lawyer"),
    FIRM_ADMIN("firm_admin"),
}

@HiltViewModel
class LoginViewModel
    @Inject
    constructor(
        private val repository: AuthRepository,
    ) : ViewModel() {
        private val _state = MutableStateFlow(LoginUiState())
        val state: StateFlow<LoginUiState> = _state.asStateFlow()

        fun onPhoneChanged(value: String) {
            _state.update {
                it.copy(phone = value.filter(Char::isDigit).take(LoginUiState.PHONE_LENGTH), error = null)
            }
        }

        fun onOtpChanged(value: String) {
            _state.update {
                it.copy(otp = value.filter(Char::isDigit).take(LoginUiState.OTP_LENGTH), error = null)
            }
        }

        fun requestOtp() {
            val current = _state.value
            if (!current.isPhoneValid || current.isSubmitting) return

            _state.update { it.copy(isSubmitting = true, error = null) }
            viewModelScope.launch {
                when (val result = repository.requestOtp(LoginUiState.COUNTRY_CODE + current.phone)) {
                    is ApiResult.Success ->
                        _state.update {
                            it.copy(isSubmitting = false, step = LoginUiState.Step.OTP)
                        }

                    is ApiResult.Failure ->
                        _state.update { it.copy(isSubmitting = false, error = result.error.display()) }
                }
            }
        }

        fun verifyOtp() {
            val current = _state.value
            if (!current.isOtpValid || current.isSubmitting) return

            _state.update { it.copy(isSubmitting = true, error = null) }
            viewModelScope.launch {
                val verified =
                    repository.verifyOtp(
                        phone = LoginUiState.COUNTRY_CODE + current.phone,
                        otp = current.otp,
                    )

                when (verified) {
                    is ApiResult.Failure ->
                        _state.update { it.copy(isSubmitting = false, error = verified.error.display()) }

                    is ApiResult.Success -> {
                        if (verified.data.isNewUser) {
                            // The placeholder user the server created has an empty name — skip
                            // `me()` until onboarding actually sets one, otherwise the app would
                            // briefly show a signed-in user with no name.
                            _state.update {
                                it.copy(isSubmitting = false, step = LoginUiState.Step.ONBOARDING)
                            }
                        } else {
                            // Proves the token was stored and the auth interceptor works: this
                            // call is authenticated, and it is the same round-trip the splash
                            // screen makes.
                            val me = repository.me()
                            _state.update {
                                when (me) {
                                    is ApiResult.Success ->
                                        it.copy(
                                            isSubmitting = false,
                                            step = LoginUiState.Step.SIGNED_IN,
                                            signedInUser = me.data,
                                        )

                                    is ApiResult.Failure ->
                                        it.copy(isSubmitting = false, error = me.error.display())
                                }
                            }
                        }
                    }
                }
            }
        }

        fun onOnboardNameChanged(value: String) {
            _state.update { it.copy(onboardName = value, error = null) }
        }

        fun onOnboardRoleChanged(value: OnboardRole) {
            _state.update { it.copy(onboardRole = value, error = null) }
        }

        fun onOnboardFirmNameChanged(value: String) {
            _state.update { it.copy(onboardFirmName = value, error = null) }
        }

        fun onOnboardBarCouncilIdChanged(value: String) {
            _state.update { it.copy(onboardBarCouncilId = value, error = null) }
        }

        fun onOnboardLanguageChanged(value: Language) {
            _state.update { it.copy(onboardLanguage = value, error = null) }
        }

        fun submitOnboarding() {
            val current = _state.value
            if (!current.isOnboardingValid || current.isSubmitting) return

            _state.update { it.copy(isSubmitting = true, error = null) }
            viewModelScope.launch {
                val onboarded =
                    repository.onboard(
                        name = current.onboardName,
                        roleHint = current.onboardRole.wire,
                        firmName = current.onboardFirmName,
                        barCouncilId = current.onboardBarCouncilId,
                        language = current.onboardLanguage.wire,
                    )

                when (onboarded) {
                    is ApiResult.Failure ->
                        _state.update { it.copy(isSubmitting = false, error = onboarded.error.display()) }

                    is ApiResult.Success ->
                        // Same round-trip verifyOtp makes for an existing user — proves the
                        // onboarded profile actually persisted before the app treats them as
                        // signed in.
                        _state.update {
                            it.copy(
                                isSubmitting = false,
                                step = LoginUiState.Step.SIGNED_IN,
                                signedInUser = onboarded.data,
                            )
                        }
                }
            }
        }

        fun back() {
            _state.update { it.copy(step = LoginUiState.Step.PHONE, otp = "", error = null) }
        }

        fun logout() {
            repository.logout()
            _state.value = LoginUiState()
        }

        /**
         * Temporary: B.3 error text belongs in string resources keyed by code, which arrives
         * with the design system in Sprint A2. Until then the server's message is shown, which
         * is at least always contract-shaped.
         */
        private fun ApiError.display(): String = message.ifBlank { "Something went wrong." }
    }
