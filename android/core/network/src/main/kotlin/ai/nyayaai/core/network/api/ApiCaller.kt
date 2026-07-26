package ai.nyayaai.core.network.api

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import retrofit2.HttpException
import java.io.IOException
import javax.inject.Inject
import javax.inject.Singleton

/**
 * The single place the envelope is unwrapped and B.3 error codes become [ApiError]s.
 *
 * Repositories call `apiCaller.call { service.getCases() }` and receive an [ApiResult].
 * No feature module ever sees an [ApiEnvelope], an [HttpException], or a raw JSON body —
 * D.2 requires envelope handling and error mapping to live in `core:network` exactly once.
 */
@Singleton
class ApiCaller
    @Inject
    constructor(
        private val json: Json,
    ) {
        suspend fun <T> call(block: suspend () -> ApiEnvelope<T>): ApiResult<T> =
            try {
                unwrap(block())
            } catch (e: HttpException) {
                ApiResult.Failure(mapHttpException(e))
            } catch (e: IOException) {
                ApiResult.Failure(
                    ApiError.Network(e.message ?: "No internet connection", e),
                )
            } catch (e: kotlinx.serialization.SerializationException) {
                // The server answered with something that is not the contract's shape at all.
                ApiResult.Failure(
                    ApiError.ContractViolation(
                        message = "The server sent an unexpected response.",
                        detail = "Response body did not deserialize: ${e.message}",
                        cause = e,
                    ),
                )
            }

        /** For endpoints whose success body is empty (204-style, wrapped in the envelope). */
        suspend fun callUnit(block: suspend () -> ApiEnvelope<EmptyBody>): ApiResult<Unit> = call(block).map { }

        private fun <T> unwrap(envelope: ApiEnvelope<T>): ApiResult<T> =
            when {
                envelope.success && envelope.data != null ->
                    ApiResult.Success(envelope.data, envelope.meta)

                // success:true with a null body is a contract violation, not an empty result —
                // report it rather than silently rendering a blank screen.
                envelope.success ->
                    ApiResult.Failure(
                        ApiError.ContractViolation(
                            message = "The server sent an empty response.",
                            detail = "success=true but data was null",
                        ),
                    )

                envelope.error != null -> ApiResult.Failure(toApiError(envelope.error))

                else ->
                    ApiResult.Failure(
                        ApiError.ContractViolation(
                            message = "The server sent an unexpected response.",
                            detail = "success=false but error was null",
                        ),
                    )
            }

        private fun mapHttpException(e: HttpException): ApiError {
            val raw = runCatching { e.response()?.errorBody()?.string() }.getOrNull()
            val body =
                raw?.takeIf { it.isNotBlank() }?.let { text ->
                    runCatching {
                        json.decodeFromString(ApiEnvelope.serializer(EmptyBody.serializer()), text).error
                    }.getOrNull()
                }

            return body?.let(::toApiError) ?: ApiError.ContractViolation(
                message = "The server sent an unexpected response.",
                detail = "HTTP ${e.code()} with a non-envelope body: ${raw?.take(ERROR_SNIPPET)}",
                cause = e,
            )
        }

        private fun toApiError(body: ApiErrorBody): ApiError =
            when (body.code) {
                ApiError.CODE_VALIDATION -> body.toValidation()
                ApiError.CODE_TOKEN_EXPIRED -> ApiError.TokenExpired(body.message)
                ApiError.CODE_UNAUTHENTICATED -> ApiError.Unauthenticated(body.message)
                ApiError.CODE_QUOTA_EXCEEDED -> body.toQuotaExceeded()
                ApiError.CODE_FORBIDDEN_ROLE -> ApiError.ForbiddenRole(body.message)
                ApiError.CODE_DUPLICATE -> ApiError.DuplicateResource(body.message)
                ApiError.CODE_CNR_INVALID -> ApiError.CnrInvalid(body.message)
                ApiError.CODE_UPGRADE_REQUIRED -> ApiError.UpgradeRequired(body.message)
                ApiError.CODE_INTERNAL -> ApiError.InternalError(body.message)
                ApiError.CODE_UPSTREAM_UNAVAILABLE -> ApiError.UpstreamUnavailable(body.message)
                ApiError.CODE_RATE_LIMITED ->
                    ApiError.RateLimited(body.message, body.intDetail("retry_after_seconds"))

                // `*_NOT_FOUND` is a family of codes, not one, so it cannot be an equality
                // branch — and anything still unmatched is B.3's generic fallback.
                else -> body.toNotFoundOrUnknown()
            }

        private fun ApiErrorBody.toValidation() =
            ApiError.Validation(
                message = message,
                fieldErrors =
                    details
                        ?.jsonObject
                        ?.mapValues { it.value.jsonPrimitive.content }
                        .orEmpty(),
            )

        private fun ApiErrorBody.toQuotaExceeded() =
            ApiError.QuotaExceeded(
                message = message,
                limit = intDetail("limit"),
                plan = stringDetail("plan"),
                // B.14: always present, and the paywall preselects it.
                upgradeTo = stringDetail("upgrade_to"),
            )

        private fun ApiErrorBody.toNotFoundOrUnknown(): ApiError =
            if (code.endsWith(ApiError.NOT_FOUND_SUFFIX)) {
                ApiError.NotFound(
                    message = message,
                    resource = code.removeSuffix(ApiError.NOT_FOUND_SUFFIX).lowercase(),
                )
            } else {
                ApiError.Unknown(message, code)
            }

        private fun ApiErrorBody.intDetail(key: String): Int? = stringDetail(key)?.toIntOrNull()

        private fun ApiErrorBody.stringDetail(key: String): String? = details?.get(key)?.jsonPrimitive?.content

        private companion object {
            const val ERROR_SNIPPET = 200
        }
    }
