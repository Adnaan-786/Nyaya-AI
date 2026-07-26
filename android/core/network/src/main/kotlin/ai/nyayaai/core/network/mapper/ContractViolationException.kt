package ai.nyayaai.core.network.mapper

import ai.nyayaai.core.model.CourtDate
import ai.nyayaai.core.model.CourtTime
import kotlin.time.Instant

/**
 * Thrown by mappers when a response is well-formed JSON but breaks the contract — a
 * required field is absent, or a value cannot be interpreted.
 *
 * D.13 requires any staging response that differs from the contract to be filed as a
 * blocking bug against the server repo the same day. Giving this its own exception type
 * (rather than letting it surface as a generic parse failure) is what makes those reports
 * specific enough to act on.
 */
class ContractViolationException(
    val field: String,
    val detail: String,
) : IllegalStateException("Contract violation on '$field': $detail")

/** Requires a field the contract marks as always present. */
internal fun <T : Any> T?.required(field: String): T =
    this ?: throw ContractViolationException(field, "was null or missing")

internal fun String?.requiredString(field: String): String =
    this?.takeIf { it.isNotBlank() }
        ?: throw ContractViolationException(field, "was null, missing, or blank")

/** Parses an ISO-8601 UTC instant (B.1.5) for genuine moments only. */
internal fun String?.toInstantOrThrow(field: String): Instant =
    this?.let { raw -> runCatching { Instant.parse(raw) }.getOrNull() }
        ?: throw ContractViolationException(field, "not an ISO-8601 instant: $this")

internal fun String?.toInstantOrNull(): Instant? =
    this
        ?.takeIf {
            it.isNotBlank()
        }?.let { runCatching { Instant.parse(it) }.getOrNull() }

/**
 * Parses a **calendar date**. Never routed through a timezone — see [CourtDate] for why
 * this is the difference between showing a hearing on the right day and the wrong one.
 */
internal fun String?.toCourtDateOrThrow(field: String): CourtDate =
    CourtDate.parseOrNull(this)
        ?: throw ContractViolationException(field, "not a calendar date: $this")

internal fun String?.toCourtDateOrNull(): CourtDate? = CourtDate.parseOrNull(this)

internal fun String?.toCourtTimeOrNull(): CourtTime? = CourtTime.parseOrNull(this)
