package ai.nyayaai.core.network.api

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

inline fun <T, R> ApiResult<T>.map(transform: (T) -> R): ApiResult<R> =
    when (this) {
        is ApiResult.Success -> ApiResult.Success(transform(data), meta)
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
