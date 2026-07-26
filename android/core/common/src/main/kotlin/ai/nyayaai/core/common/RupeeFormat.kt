package ai.nyayaai.core.common

import ai.nyayaai.core.model.Paise
import kotlin.math.absoluteValue

/**
 * Formats paise as rupees using the **Indian digit grouping** (lakh/crore), not the
 * Western thousands grouping:
 *
 *   150050    -> ₹1,500.50
 *   15000000  -> ₹1,50,000.00      (one lakh fifty thousand — NOT ₹150,000.00)
 *   1000000000 -> ₹1,00,00,000.00  (one crore)
 *
 * `NumberFormat.getCurrencyInstance(Locale("en","IN"))` does produce this, but it also
 * drags in the locale's currency symbol placement and rounding behaviour, and it takes a
 * `double`. We are not putting money through a double (see [Paise]), so we group the
 * digits ourselves.
 */
fun Paise.formatRupees(
    withSymbol: Boolean = true,
    withPaise: Boolean = true,
): String {
    val negative = value < 0
    val absolute = value.absoluteValue
    val rupees = absolute / Paise.PAISE_PER_RUPEE
    val remainder = (absolute % Paise.PAISE_PER_RUPEE).toInt()

    val builder = StringBuilder()
    if (negative) builder.append('-')
    if (withSymbol) builder.append('₹')
    builder.append(groupIndian(rupees))
    if (withPaise) builder.append('.').append("%02d".format(remainder))
    return builder.toString()
}

/**
 * Compact form for dense lists: ₹1.5L, ₹2.50Cr. The full value stays on the detail screen.
 *
 * Deliberately does **not** abbreviate below one lakh: "₹1.5K" is both less readable and
 * less idiomatic in India than "₹1,500", and invoice amounts cluster in exactly that range.
 */
fun Paise.formatRupeesCompact(): String {
    val rupees = value.absoluteValue / Paise.PAISE_PER_RUPEE
    val sign = if (value < 0) "-" else ""
    return when {
        rupees >= CRORE -> "$sign₹%.2fCr".format(rupees.toDouble() / CRORE)
        rupees >= LAKH -> "$sign₹%.1fL".format(rupees.toDouble() / LAKH)
        else -> formatRupees(withPaise = false)
    }
}

/**
 * Indian grouping: last three digits, then pairs.
 * 10000000 -> "1,00,00,000"
 */
private fun groupIndian(value: Long): String {
    val digits = value.toString()
    if (digits.length <= LAST_GROUP) return digits

    val lastThree = digits.takeLast(LAST_GROUP)
    val rest = digits.dropLast(LAST_GROUP)

    val grouped = StringBuilder()
    var index = rest.length
    while (index > PAIR) {
        grouped.insert(0, "," + rest.substring(index - PAIR, index))
        index -= PAIR
    }
    grouped.insert(0, rest.substring(0, index))
    return "$grouped,$lastThree"
}

private const val LAST_GROUP = 3
private const val PAIR = 2
private const val LAKH = 100_000L
private const val CRORE = 10_000_000L
