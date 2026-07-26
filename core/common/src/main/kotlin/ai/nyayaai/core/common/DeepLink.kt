package ai.nyayaai.core.common

/**
 * B.8 deep links. Every push notification routes through one of these.
 *
 * Parsed here rather than in the notification handler because the same links arrive from
 * three places — an FCM data message, a cold-start intent, and an in-app notification
 * inbox tap — and all three must land on the same screen.
 *
 * Unknown or malformed links resolve to `null`, and the caller opens Today. A push
 * referencing a screen this app version does not have must never crash it (B.13 allows the
 * server to ship new push types ahead of a client release).
 */
sealed interface DeepLink {
    data class Case(
        val caseId: String,
    ) : DeepLink

    data class Job(
        val jobId: String,
    ) : DeepLink

    data class Invoice(
        val invoiceId: String,
    ) : DeepLink

    data class Task(
        val taskId: String,
    ) : DeepLink

    data object Today : DeepLink

    companion object {
        const val SCHEME = "nyayaai"

        private const val HOST_CASE = "case"
        private const val HOST_JOB = "job"
        private const val HOST_INVOICE = "invoice"
        private const val HOST_TASK = "task"
        private const val HOST_TODAY = "today"

        /**
         * Accepts `nyayaai://case/{id}`, `nyayaai://today`, and so on.
         *
         * Deliberately string-based rather than `android.net.Uri`-based so it is unit
         * testable on the JVM — this is exactly the kind of routing that should not need an
         * emulator to verify.
         */
        fun parse(raw: String?): DeepLink? {
            val uri = raw?.trim().orEmpty()
            if (!uri.startsWith("$SCHEME://")) return null

            val body = uri.removePrefix("$SCHEME://").substringBefore('?').trim('/')
            if (body.isEmpty()) return null

            val host = body.substringBefore('/')
            val id = body.substringAfter('/', missingDelimiterValue = "").trim()

            return when (host) {
                HOST_TODAY -> Today
                HOST_CASE -> id.takeIf(String::isNotEmpty)?.let(::Case)
                HOST_JOB -> id.takeIf(String::isNotEmpty)?.let(::Job)
                HOST_INVOICE -> id.takeIf(String::isNotEmpty)?.let(::Invoice)
                HOST_TASK -> id.takeIf(String::isNotEmpty)?.let(::Task)
                else -> null
            }
        }
    }
}

/** The inverse, for building links in tests and for the in-app notification inbox. */
fun DeepLink.toUri(): String =
    when (this) {
        is DeepLink.Case -> "${DeepLink.SCHEME}://case/$caseId"
        is DeepLink.Job -> "${DeepLink.SCHEME}://job/$jobId"
        is DeepLink.Invoice -> "${DeepLink.SCHEME}://invoice/$invoiceId"
        is DeepLink.Task -> "${DeepLink.SCHEME}://task/$taskId"
        DeepLink.Today -> "${DeepLink.SCHEME}://today"
    }
