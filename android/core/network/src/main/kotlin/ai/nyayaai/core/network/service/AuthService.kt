package ai.nyayaai.core.network.service

import ai.nyayaai.core.network.api.ApiEnvelope
import ai.nyayaai.core.network.api.EmptyBody
import ai.nyayaai.core.network.dto.AppConfigDto
import ai.nyayaai.core.network.dto.DeviceDto
import ai.nyayaai.core.network.dto.DeviceRegistrationDto
import ai.nyayaai.core.network.dto.EmailOtpRequestDto
import ai.nyayaai.core.network.dto.EmailOtpVerifyRequestDto
import ai.nyayaai.core.network.dto.OnboardRequestDto
import ai.nyayaai.core.network.dto.OtpRequestDto
import ai.nyayaai.core.network.dto.OtpVerifyRequestDto
import ai.nyayaai.core.network.dto.RefreshRequestDto
import ai.nyayaai.core.network.dto.TokenPairDto
import ai.nyayaai.core.network.dto.UserDto
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path

/** B.6 "Auth and profile", plus the unauthenticated `GET /app/config` from B.14. */
interface AuthService {
    @POST("auth/otp/request")
    suspend fun requestOtp(
        @Body body: OtpRequestDto,
    ): ApiEnvelope<EmptyBody>

    @POST("auth/otp/verify")
    suspend fun verifyOtp(
        @Body body: OtpVerifyRequestDto,
    ): ApiEnvelope<TokenPairDto>

    @POST("auth/email/request")
    suspend fun requestEmailOtp(
        @Body body: EmailOtpRequestDto,
    ): ApiEnvelope<EmptyBody>

    @POST("auth/email/verify")
    suspend fun verifyEmailOtp(
        @Body body: EmailOtpVerifyRequestDto,
    ): ApiEnvelope<TokenPairDto>

    @POST("auth/onboard")
    suspend fun onboard(
        @Body body: OnboardRequestDto,
    ): ApiEnvelope<UserDto>

    @GET("me")
    suspend fun me(): ApiEnvelope<UserDto>

    /**
     * B.4.6: called after every login and after every FCM token refresh. Pulled into
     * Sprint A1 because IC-1 (W6) requires a hearing reminder push to arrive.
     */
    @POST("devices")
    suspend fun registerDevice(
        @Body body: DeviceRegistrationDto,
    ): ApiEnvelope<DeviceDto>

    @DELETE("devices/{id}")
    suspend fun unregisterDevice(
        @Path("id") id: String,
    ): ApiEnvelope<EmptyBody>

    @GET("app/config")
    suspend fun appConfig(): ApiEnvelope<AppConfigDto>
}

/**
 * Refresh lives on its own service, bound to an OkHttp client that has **no**
 * [ai.nyayaai.core.network.auth.TokenAuthenticator] attached. Sharing the main client
 * would let a failing refresh trigger another refresh, recursively.
 */
interface AuthRefreshService {
    @POST("auth/refresh")
    suspend fun refresh(
        @Body body: RefreshRequestDto,
    ): ApiEnvelope<TokenPairDto>
}
