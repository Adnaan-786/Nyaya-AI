package ai.nyayaai.core.common

import ai.nyayaai.core.model.CourtDate
import ai.nyayaai.core.model.CourtTime
import kotlinx.datetime.LocalDate
import kotlinx.datetime.LocalDateTime
import kotlinx.datetime.LocalTime
import kotlinx.datetime.TimeZone
import kotlinx.datetime.toLocalDateTime
import kotlinx.datetime.todayIn
import kotlin.time.Clock
import kotlin.time.Instant

/**
 * D.9: the app renders IST regardless of the device timezone. A lawyer travelling, or a
 * device with a wrong zone set, must still see the court's day.
 */
val IndiaTimeZone: TimeZone = TimeZone.of("Asia/Kolkata")

fun todayInIndia(clock: Clock = Clock.System): LocalDate = clock.todayIn(IndiaTimeZone)

/** Converts a genuine moment into the IST calendar day it fell on. */
fun Instant.toIndiaDate(): LocalDate = toIndiaDateTime().date

fun Instant.toIndiaDateTime(): LocalDateTime = toLocalDateTime(IndiaTimeZone)

/**
 * Days from today (IST) to this court date. Negative is in the past.
 *
 * Note this deliberately operates on [LocalDate] arithmetic, never on instant
 * subtraction — "3 days away" must not change because the user opened the app at 11pm.
 */
fun CourtDate.daysFromToday(clock: Clock = Clock.System): Int =
    (date.toEpochDays() - todayInIndia(clock).toEpochDays()).toInt()

fun CourtDate.isToday(clock: Clock = Clock.System): Boolean = daysFromToday(clock) == 0

fun CourtDate.isPast(clock: Clock = Clock.System): Boolean = daysFromToday(clock) < 0

/** `2026-08-01` -> `01 Aug 2026`. */
fun CourtDate.formatLong(): String {
    val d = date
    return "%02d %s %d".format(d.day, MONTH_ABBREVIATIONS[d.month.ordinal], d.year)
}

/** `2026-08-01` -> `01 Aug`. Used where the year is obvious from context. */
fun CourtDate.formatShort(): String {
    val d = date
    return "%02d %s".format(d.day, MONTH_ABBREVIATIONS[d.month.ordinal])
}

/** 24h `14:30` -> `2:30 PM`. Courts list times in both forms; users expect 12h. */
fun CourtTime.format12Hour(): String {
    val h = time.hour
    val suffix = if (h < NOON) "AM" else "PM"
    val hour12 =
        when {
            h == 0 -> 12
            h > NOON -> h - NOON
            else -> h
        }
    return "%d:%02d %s".format(hour12, time.minute, suffix)
}

private const val NOON = 12

private val MONTH_ABBREVIATIONS =
    listOf(
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    )

/** The wall-clock time in India right now. */
fun nowTimeInIndia(clock: Clock = Clock.System): LocalTime = clock.now().toIndiaDateTime().time

/**
 * The next entry that has not started yet, or the last one once the day is over.
 *
 * Lives here rather than in a screen because "which one am I on" is a question about the
 * clock in India, and answering it from a device clock is the same bug class as parsing
 * a hearing date as an instant.
 */
fun <T> List<T>.nextUpBy(
    clock: Clock = Clock.System,
    time: (T) -> CourtTime?,
): T? {
    val now = nowTimeInIndia(clock)
    return firstOrNull { entry ->
        val at = time(entry)
        at == null || at.time >= now
    } ?: lastOrNull()
}
