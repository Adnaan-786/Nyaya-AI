package ai.nyayaai.core.common

import ai.nyayaai.core.model.CourtDate
import kotlinx.datetime.LocalDate
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import kotlin.time.Clock
import kotlin.time.Instant
import java.util.TimeZone as JavaTimeZone

/**
 * Guards the single most dangerous bug class in this app: a hearing rendering on the wrong
 * calendar day because a date was treated as an instant, or because the device is not in
 * IST.
 *
 * Every test here runs with the JVM default timezone forced to **America/Los_Angeles**
 * (UTC-7/-8) — the zone where a naive `2026-08-01T00:00:00Z` renders as 31 July.
 */
class IndiaTimeTest {
    private lateinit var originalZone: JavaTimeZone

    @Before
    fun forceNonIndianDeviceTimeZone() {
        originalZone = JavaTimeZone.getDefault()
        JavaTimeZone.setDefault(JavaTimeZone.getTimeZone("America/Los_Angeles"))
    }

    @After
    fun restoreTimeZone() {
        JavaTimeZone.setDefault(originalZone)
    }

    @Test
    fun `court date keeps its calendar day on a device behind UTC`() {
        val hearing = CourtDate.parse("2026-08-01")

        assertEquals(LocalDate(2026, 8, 1), hearing.date)
        assertEquals("01 Aug 2026", hearing.formatLong())
        assertEquals("01 Aug", hearing.formatShort())
    }

    @Test
    fun `court date parsed from a full timestamp keeps the date part`() {
        // A contract violation we report — but the user must still see the right day.
        val hearing = CourtDate.parse("2026-08-01T00:00:00Z")

        assertEquals(LocalDate(2026, 8, 1), hearing.date)
    }

    @Test
    fun `today is the IST day even when the device day is still yesterday`() {
        // 2026-07-31 20:00 UTC == 2026-08-01 01:30 IST, but 2026-07-31 13:00 in LA.
        val clock = fixedClock("2026-07-31T20:00:00Z")

        assertEquals(LocalDate(2026, 8, 1), todayInIndia(clock))
    }

    @Test
    fun `days until a hearing does not shift with the device timezone`() {
        // 2026-08-01 02:00 UTC == 2026-08-01 07:30 IST; in LA it is still 31 July 19:00.
        val clock = fixedClock("2026-08-01T02:00:00Z")

        assertEquals(0, CourtDate.parse("2026-08-01").daysFromToday(clock))
        assertEquals(1, CourtDate.parse("2026-08-02").daysFromToday(clock))
        assertEquals(-1, CourtDate.parse("2026-07-31").daysFromToday(clock))
        assertTrue(CourtDate.parse("2026-08-01").isToday(clock))
        assertTrue(CourtDate.parse("2026-07-31").isPast(clock))
    }

    @Test
    fun `late evening IST does not roll the hearing countdown forward`() {
        // 23:30 IST on 1 Aug. "in 3 days" must not become "in 2 days" because the UTC
        // instant has already ticked over to the 2nd.
        val clock = fixedClock("2026-08-01T18:00:00Z")

        assertEquals(3, CourtDate.parse("2026-08-04").daysFromToday(clock))
    }

    @Test
    fun `instants are rendered in IST regardless of device zone`() {
        val syncedAt = Instant.parse("2026-08-01T18:00:00Z")

        // 18:00 UTC is 23:30 IST on the same day — not 11:00 the same morning in LA.
        assertEquals(LocalDate(2026, 8, 1), syncedAt.toIndiaDate())
        assertEquals(23, syncedAt.toIndiaDateTime().hour)
        assertEquals(30, syncedAt.toIndiaDateTime().minute)
    }

    private fun fixedClock(iso: String): Clock =
        object : Clock {
            private val fixed = Instant.parse(iso)

            override fun now(): Instant = fixed
        }
}
