package ai.nyayaai.core.network.mapper

import ai.nyayaai.core.model.AppConfig
import ai.nyayaai.core.model.Language
import ai.nyayaai.core.model.Session
import ai.nyayaai.core.model.TenantId
import ai.nyayaai.core.model.User
import ai.nyayaai.core.model.UserId
import ai.nyayaai.core.model.UserRole
import ai.nyayaai.core.network.dto.AppConfigDto
import ai.nyayaai.core.network.dto.TokenPairDto
import ai.nyayaai.core.network.dto.UserDto

fun UserDto.toDomain(): User =
    User(
        id = UserId(id.requiredString("user.id")),
        tenantId = TenantId(tenantId.requiredString("user.tenant_id")),
        name = name.requiredString("user.name"),
        phone = phone.requiredString("user.phone"),
        email = email,
        role = UserRole.from(role),
        language = Language.from(language),
        createdAt = createdAt.toInstantOrThrow("user.created_at"),
    )

fun TokenPairDto.toSession(): Session =
    Session(
        accessToken = accessToken.requiredString("access_token"),
        refreshToken = refreshToken.requiredString("refresh_token"),
        isNewUser = isNewUser,
    )

fun AppConfigDto.toDomain(): AppConfig =
    AppConfig(
        // A missing min_supported_version must not accidentally lock every user out, so it
        // defaults to "everything is supported" rather than throwing.
        minSupportedVersion = minSupportedVersion ?: 0,
        latestVersion = latestVersion ?: 0,
        featureFlags = featureFlags,
        statusBanner = statusBanner,
        supportPhone = supportPhone,
        supportEmail = supportEmail,
    )
