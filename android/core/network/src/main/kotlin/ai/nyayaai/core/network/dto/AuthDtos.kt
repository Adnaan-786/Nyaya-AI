package ai.nyayaai.core.network.dto

import kotlinx.serialization.Serializable

/**
 * DTOs are deliberately **liberal**: every field is nullable with a default, because the
 * server's optional-vs-absent-vs-null policy is not defined by the contract (filed for
 * v1.2). Mappers are the strict layer — they decide whether a missing field is a sensible
 * default or a reportable contract violation, so domain models stay honest.
 *
 * Property names are camelCase; `NyayaJson`'s snake_case naming strategy handles the wire
 * format, so no @SerialName annotations are needed.
 */

@Serializable
data class OtpRequestDto(
    val phone: String,
)

@Serializable
data class OtpVerifyRequestDto(
    val phone: String,
    val otp: String,
)

@Serializable
data class RefreshRequestDto(
    val refreshToken: String,
)

@Serializable
data class TokenPairDto(
    val accessToken: String? = null,
    val refreshToken: String? = null,
    val isNewUser: Boolean = false,
    val user: UserDto? = null,
)

@Serializable
data class OnboardRequestDto(
    val name: String,
    val roleHint: String,
    val firmName: String? = null,
    val barCouncilId: String? = null,
    val language: String = "en",
)

@Serializable
data class UserDto(
    val id: String? = null,
    val tenantId: String? = null,
    val name: String? = null,
    val phone: String? = null,
    val email: String? = null,
    val role: String? = null,
    val language: String? = null,
    val createdAt: String? = null,
)

@Serializable
data class DeviceRegistrationDto(
    val fcmToken: String,
    val platform: String = "android",
    val appVersion: String,
)

@Serializable
data class DeviceDto(
    val id: String? = null,
)

@Serializable
data class AppConfigDto(
    val minSupportedVersion: Int? = null,
    val latestVersion: Int? = null,
    val featureFlags: Map<String, Boolean> = emptyMap(),
    val statusBanner: String? = null,
    val supportPhone: String? = null,
    val supportEmail: String? = null,
)

@Serializable
data class NotificationDto(
    val id: String? = null,
    val type: String? = null,
    val title: String? = null,
    val body: String? = null,
    val deepLink: String? = null,
    val readAt: String? = null,
    val createdAt: String? = null,
)

/** `PATCH /users/{id}` (B.6 team management) — the only role a firm admin can hand out here. */
@Serializable
data class UserRoleUpdateDto(
    val role: String,
)
