package ai.nyayaai.core.network.api

import ai.nyayaai.core.network.mapper.ContractViolationException

/**
 * What every network call returns. There is no `Loading` case — that belongs to the
 * screen's UiState, not to the transport.
 */
sealed interface ApiResult<out T> {
    data class Success<T>(
        val data: T,
        val meta: PageMeta? = null,
    ) : ApiResult<T>

    data class Failure(
        val error: ApiError,
    ) : ApiResult<Nothing>
}

/**
 * Every repository in the app calls this as `caller.call { service.x() }.map { it.toDomain() }`
 * — `transform` is where a DTO becomes a domain model, and every one of those mappers throws
 * [ContractViolationException] on a missing or malformed required field (see
 * `core/network/mapper/ContractViolationException.kt`). [ApiCaller]'s own try/catch only
 * wraps the network call itself, not this chained `.map` step, so without a catch here that
 * exception used to escape uncaught out of `viewModelScope.launch` and crash the whole app —
 * on real data, not just a contrived test, since a single unexpected field in one row is
 * enough. Converting it to a [ApiError.ContractViolation] failure is exactly what the
 * exception already exists to communicate; this is the one place that translation needs to
 * happen for it to protect every caller at once.
 */
inline fun <T, R> ApiResult<T>.map(transform: (T) -> R): ApiResult<R> =
    when (this) {
        is ApiResult.Success ->
            try {
                ApiResult.Success(transform(data), meta)
            } catch (e: ContractViolationException) {
                ApiResult.Failure(
                    ApiError.ContractViolation(
                        message = "The server sent an unexpected response.",
                        detail = "Contract violation on '${e.field}': ${e.detail}",
                        cause = e,
                    ),
                )
            }

        is ApiResult.Failure -> this
    }

inline fun <T> ApiResult<T>.onSuccess(action: (T) -> Unit): ApiResult<T> =
    apply {
        if (this is ApiResult.Success) action(data)
    }

inline fun <T> ApiResult<T>.onFailure(action: (ApiError) -> Unit): ApiResult<T> =
    apply {
        if (this is ApiResult.Failure) action(error)
    }

fun <T> ApiResult<T>.getOrNull(): T? = (this as? ApiResult.Success)?.data

fun <T> ApiResult<T>.errorOrNull(): ApiError? = (this as? ApiResult.Failure)?.error
