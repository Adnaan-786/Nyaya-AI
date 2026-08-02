package ai.nyayaai.feature.auth

import ai.nyayaai.core.model.User
import ai.nyayaai.core.network.api.ApiCaller
import ai.nyayaai.core.network.api.ApiResult
import ai.nyayaai.core.network.api.map
import ai.nyayaai.core.network.auth.TokenStore
import ai.nyayaai.core.network.dto.OnboardRequestDto
import ai.nyayaai.core.network.dto.OtpRequestDto
import ai.nyayaai.core.network.dto.OtpVerifyRequestDto
import ai.nyayaai.core.network.mapper.toDomain
import ai.nyayaai.core.network.mapper.toSession
import ai.nyayaai.core.network.service.AuthService
import javax.inject.Inject
import javax.inject.Singleton

/**
 * B.4 phone-OTP login.
 *
 * Everything network-shaped stops here: the ViewModel receives domain models and typed
 * errors, never DTOs or HTTP.
 */
@Singleton
class AuthRepository
    @Inject
    constructor(
        private val service: AuthService,
        private val caller: ApiCaller,
        private val tokenStore: TokenStore,
    ) {
        /** B.4.1: 6-digit OTP, 5-minute validity, max 3/hour per phone (server-enforced). */
        suspend fun requestOtp(phone: String): ApiResult<Unit> =
            caller.call { service.requestOtp(OtpRequestDto(phone)) }.map { }

        /**
         * B.4.2. On success the token pair is persisted before returning, so any call made
         * immediately afterwards is already authenticated.
         */
        suspend fun verifyOtp(
            phone: String,
            otp: String,
        ): ApiResult<VerifiedLogin> =
            caller
                .call { service.verifyOtp(OtpVerifyRequestDto(phone, otp)) }
                .map { dto ->
                    val session = dto.toSession()
                    tokenStore.save(session.accessToken, session.refreshToken)
                    VerifiedLogin(
                        isNewUser = session.isNewUser,
                        user = dto.user?.toDomain(),
                    )
                }

        suspend fun me(): ApiResult<User> = caller.call { service.me() }.map { it.toDomain() }

        /**
         * B.6 onboarding. Only reachable for a brand-new user (see [VerifiedLogin.isNewUser]) —
         * finishes the placeholder profile the server created at OTP verification so the name
         * and tenant it returns are no longer empty / "Pending setup".
         */
        suspend fun onboard(
            name: String,
            roleHint: String,
            firmName: String?,
            barCouncilId: String?,
            language: String,
        ): ApiResult<User> =
            caller
                .call {
                    service.onboard(
                        OnboardRequestDto(
                            name = name,
                            roleHint = roleHint,
                            firmName = firmName?.takeIf { it.isNotBlank() },
                            barCouncilId = barCouncilId?.takeIf { it.isNotBlank() },
                            language = language,
                        ),
                    )
                }.map { it.toDomain() }

        fun logout() = tokenStore.clear()
    }

/**
 * [isNewUser] decides whether the app goes to the onboarding wizard or straight to Today
 * (B.4.2 / D.6).
 */
data class VerifiedLogin(
    val isNewUser: Boolean,
    val user: User?,
)
