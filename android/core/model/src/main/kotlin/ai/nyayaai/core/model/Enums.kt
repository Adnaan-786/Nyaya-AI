package ai.nyayaai.core.model

/**
 * Every contract enum decodes through [from], which falls back to `UNKNOWN` instead of
 * throwing.
 *
 * B.13 lets the server add values additively after the contract freeze — a new case
 * `stage` or job `type` shipped server-side must never crash an installed app that
 * predates it. Screens render `UNKNOWN` as the raw string with neutral styling.
 */
private inline fun <reified T : Enum<T>> decode(
    wire: String?,
    fallback: T,
): T =
    enumValues<T>().firstOrNull { it.name.equals(wire?.replace('-', '_'), ignoreCase = true) }
        ?: fallback

enum class UserRole {
    FIRM_ADMIN,
    LAWYER,
    INTERN,
    CLIENT,
    UNKNOWN,
    ;

    /** True for the reduced client-mode app shell (D.10). */
    val isClient: Boolean get() = this == CLIENT

    companion object {
        fun from(wire: String?): UserRole = decode(wire, UNKNOWN)
    }
}

enum class Language {
    EN,
    HI,
    ;

    val wire: String get() = name.lowercase()

    companion object {
        fun from(wire: String?): Language = decode(wire, EN)
    }
}

enum class CaseStatus {
    ACTIVE,
    DISPOSED,
    ARCHIVED,
    UNKNOWN,
    ;

    companion object {
        fun from(wire: String?): CaseStatus = decode(wire, UNKNOWN)
    }
}

enum class HearingSource {
    ECOURTS,
    MANUAL,
    UNKNOWN,
    ;

    companion object {
        fun from(wire: String?): HearingSource = decode(wire, UNKNOWN)
    }
}

enum class OcrStatus {
    PENDING,
    DONE,
    FAILED,
    UNKNOWN,
    ;

    companion object {
        fun from(wire: String?): OcrStatus = decode(wire, UNKNOWN)
    }
}

enum class AiJobType {
    SUMMARIZE,
    RESEARCH,
    DRAFT,
    RISK_REVIEW,
    UNKNOWN,
    ;

    companion object {
        fun from(wire: String?): AiJobType = decode(wire, UNKNOWN)
    }
}

enum class AiJobStatus {
    QUEUED,
    RUNNING,
    DONE,
    FAILED,
    UNKNOWN,
    ;

    val isTerminal: Boolean get() = this == DONE || this == FAILED

    companion object {
        fun from(wire: String?): AiJobStatus = decode(wire, UNKNOWN)
    }
}

/** B.7: `insufficient` must render a distinct "no reliable authority found" state. */
enum class ResearchConfidence {
    HIGH,
    MEDIUM,
    INSUFFICIENT,
    UNKNOWN,
    ;

    companion object {
        fun from(wire: String?): ResearchConfidence = decode(wire, UNKNOWN)
    }
}

enum class RiskSeverity {
    HIGH,
    MEDIUM,
    LOW,
    UNKNOWN,
    ;

    companion object {
        fun from(wire: String?): RiskSeverity = decode(wire, UNKNOWN)
    }
}

enum class InvoiceStatus {
    DRAFT,
    SENT,
    PAID,
    OVERDUE,
    UNKNOWN,
    ;

    companion object {
        fun from(wire: String?): InvoiceStatus = decode(wire, UNKNOWN)
    }
}

enum class TaskStatus {
    OPEN,
    IN_PROGRESS,
    DONE,
    UNKNOWN,
    ;

    companion object {
        fun from(wire: String?): TaskStatus = decode(wire, UNKNOWN)
    }
}

/** B.8 push types. `UNKNOWN` pushes are dropped silently rather than crashing. */
enum class PushType {
    HEARING_REMINDER,
    DAILY_DIGEST,
    CASE_UPDATE,
    AI_JOB_COMPLETE,
    PAYMENT_RECEIVED,
    TASK_ASSIGNED,
    UNKNOWN,
    ;

    companion object {
        fun from(wire: String?): PushType = decode(wire, UNKNOWN)
    }
}
