package ai.nyayaai.core.network.api

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

/**
 * B.3: every response — success or failure — uses this envelope. B.1.4 makes it a contract
 * violation for the server to return anything else on any `/v1` route, including errors.
 *
 * Nothing outside this package should ever see an envelope: [ApiCaller] unwraps it.
 */
@Serializable
data class ApiEnvelope<T>(
    val success: Boolean = false,
    val data: T? = null,
    val error: ApiErrorBody? = null,
    val meta: PageMeta? = null,
)

@Serializable
data class ApiErrorBody(
    val code: String = "",
    val message: String = "",
    val details: JsonObject? = null,
)

/** Present only on paginated lists (`?page=1&limit=20`, max limit 100). */
@Serializable
data class PageMeta(
    val page: Int = 1,
    val limit: Int = DEFAULT_LIMIT,
    val total: Int = 0,
) {
    val hasMore: Boolean get() = page * limit < total

    companion object {
        const val DEFAULT_LIMIT = 20
        const val MAX_LIMIT = 100
    }
}

/** A page of results plus the metadata needed to request the next one. */
data class Paged<T>(
    val items: List<T>,
    val page: Int,
    val limit: Int,
    val total: Int,
) {
    val hasMore: Boolean get() = page * limit < total
}

@Serializable
data class EmptyBody(
    @SerialName("ok") val ok: Boolean = true,
)
