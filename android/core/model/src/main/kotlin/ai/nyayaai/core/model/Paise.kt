package ai.nyayaai.core.model

/**
 * Contract rule B.1.5: money is **integer paise** (Rs. 1,500.50 == 150050).
 *
 * There is deliberately no `Double`/`Float` conversion anywhere in this class. Floating
 * point money in a billing product produces invoices that are off by a paisa and clients
 * who do not pay them.
 */
@JvmInline
value class Paise(
    val value: Long,
) {
    operator fun plus(other: Paise): Paise = Paise(value + other.value)

    operator fun minus(other: Paise): Paise = Paise(value - other.value)

    operator fun times(quantity: Int): Paise = Paise(value * quantity)

    operator fun compareTo(other: Paise): Int = value.compareTo(other.value)

    val isZero: Boolean get() = value == 0L

    /** Whole rupees, truncated. Use the formatter in `core:common` for display. */
    val rupees: Long get() = value / PAISE_PER_RUPEE

    /** The 0..99 paise remainder. */
    val remainderPaise: Int get() = (value % PAISE_PER_RUPEE).toInt()

    companion object {
        const val PAISE_PER_RUPEE = 100L
        val ZERO = Paise(0)

        fun ofRupees(rupees: Long): Paise = Paise(rupees * PAISE_PER_RUPEE)
    }
}

fun Iterable<Paise>.sum(): Paise = fold(Paise.ZERO) { acc, p -> acc + p }
