package ai.nyayaai.core.model

import kotlinx.datetime.LocalDate
import kotlinx.datetime.LocalTime

/**
 * The contract (B.1.5) says "all timestamps are ISO-8601 UTC". That is true of *moments*
 * and wrong for *calendar dates*, and the difference is the most dangerous bug in this app.
 *
 * A hearing on `2026-08-01` is a date on a court's cause list. It is not an instant. If it
 * is parsed as `2026-08-01T00:00:00Z` and rendered in any zone behind UTC, it displays as
 * **31 July** — a lawyer misses a hearing.
 *
 * So the domain has two kinds of time and they never mix:
 *
 *  - [kotlin.time.Instant] for genuine moments: `created_at`, `completed_at`,
 *    `last_synced_at`, `verified_at`, `started_at`, `read_at`.
 *  - [CourtDate] for calendar dates: `hearing.date`, `case.next_hearing_date`,
 *    `invoice.due_date`. These are **never** put through a timezone conversion.
 *
 * Filed against the contract for v1.2: these fields must be `format: date`, not
 * `format: date-time`, so generated DTOs get this right automatically.
 */
@JvmInline
value class CourtDate(
    val date: LocalDate,
) : Comparable<CourtDate> {
    override fun compareTo(other: CourtDate): Int = date.compareTo(other.date)

    override fun toString(): String = date.toString()

    companion object {
        /**
         * Accepts a bare `2026-08-01` and also tolerates a full date-time, from which it
         * takes the **date part only**. The server sending `2026-08-01T00:00:00Z` for a
         * hearing is a contract violation we report — but we display the right day
         * regardless.
         */
        fun parse(wire: String): CourtDate = CourtDate(LocalDate.parse(wire.substringBefore('T')))

        fun parseOrNull(wire: String?): CourtDate? =
            wire?.takeIf { it.isNotBlank() }?.let {
                runCatching { parse(it) }.getOrNull()
            }
    }
}

/** `hearing.time` is optional and, like the date, carries no zone of its own. */
@JvmInline
value class CourtTime(
    val time: LocalTime,
) {
    override fun toString(): String = time.toString()

    companion object {
        fun parseOrNull(wire: String?): CourtTime? =
            wire?.takeIf { it.isNotBlank() }?.let {
                runCatching { CourtTime(LocalTime.parse(it.substringBefore('+').trim())) }
                    .getOrNull()
            }
    }
}
