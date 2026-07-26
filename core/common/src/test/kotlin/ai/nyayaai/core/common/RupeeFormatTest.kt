package ai.nyayaai.core.common

import ai.nyayaai.core.model.Paise
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * Money is integer paise (B.1.5) rendered with Indian lakh/crore grouping. Getting the
 * grouping wrong makes every invoice in the app look foreign to its reader.
 */
class RupeeFormatTest {
    @Test
    fun `formats the contract's own example`() {
        // B.1.5: "Rs. 1,500.50 = 150050"
        assertEquals("₹1,500.50", Paise(150_050).formatRupees())
    }

    @Test
    fun `groups lakhs the Indian way not the western way`() {
        assertEquals("₹1,50,000.00", Paise(15_000_000).formatRupees())
        assertEquals("₹10,00,000.00", Paise(100_000_000).formatRupees())
    }

    @Test
    fun `groups crores the Indian way`() {
        assertEquals("₹1,00,00,000.00", Paise(1_000_000_000).formatRupees())
    }

    @Test
    fun `handles small values and zero`() {
        assertEquals("₹0.00", Paise.ZERO.formatRupees())
        assertEquals("₹0.50", Paise(50).formatRupees())
        assertEquals("₹999.00", Paise(99_900).formatRupees())
    }

    @Test
    fun `handles negative values`() {
        assertEquals("-₹1,500.50", Paise(-150_050).formatRupees())
    }

    @Test
    fun `can omit symbol and paise`() {
        assertEquals("1,500", Paise(150_050).formatRupees(withSymbol = false, withPaise = false))
    }

    @Test
    fun `compact form uses lakh and crore units`() {
        assertEquals("₹1.5L", Paise(15_000_000).formatRupeesCompact())
        assertEquals("₹2.50Cr", Paise(2_500_000_000).formatRupeesCompact())
        assertEquals("₹1,500", Paise(150_050).formatRupeesCompact())
    }

    @Test
    fun `arithmetic stays in integer paise`() {
        val subtotal = Paise(150_050) + Paise(49_950)
        assertEquals(Paise(200_000), subtotal)
        assertEquals("₹2,000.00", subtotal.formatRupees())

        val lineTotal = Paise(75_000) * 3
        assertEquals("₹2,250.00", lineTotal.formatRupees())
    }
}
