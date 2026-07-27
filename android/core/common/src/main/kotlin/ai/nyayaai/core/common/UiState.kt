package ai.nyayaai.core.common

/**
 * D.2: every screen renders exactly one of Loading / Content / Error / Empty.
 *
 * Empty is a **separate case rather than an empty Content list** on purpose. A lawyer with
 * no cases yet and a lawyer whose filter matched nothing need different words and
 * different next actions; collapsing them into `items.isEmpty()` is how screens end up
 * showing a bare "No data" with nowhere to go.
 */
sealed interface UiState<out T> {
    data object Loading : UiState<Nothing>

    data class Content<T>(
        val data: T,
        /** True while a pull-to-refresh runs over already-visible content. */
        val isRefreshing: Boolean = false,
    ) : UiState<T>

    data class Empty(
        val title: String,
        val description: String? = null,
    ) : UiState<Nothing>

    data class Error(
        val message: String,
        /** Null when the failure cannot be retried — a 403 must not offer "Try again". */
        val retryable: Boolean = true,
    ) : UiState<Nothing>
}

fun <T> UiState<T>.dataOrNull(): T? = (this as? UiState.Content)?.data
