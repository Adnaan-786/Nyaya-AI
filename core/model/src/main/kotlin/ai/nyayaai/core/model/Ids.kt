package ai.nyayaai.core.model

/**
 * Contract rule B.1.5: every ID is a UUIDv4 **string**. Wrapping them stops the classic
 * mistake of passing a client id where a case id is expected — the compiler catches it,
 * and it costs nothing at runtime.
 */
@JvmInline value class TenantId(
    val value: String,
)

@JvmInline value class UserId(
    val value: String,
)

@JvmInline value class ClientId(
    val value: String,
)

@JvmInline value class CaseId(
    val value: String,
)

@JvmInline value class HearingId(
    val value: String,
)

@JvmInline value class DocumentId(
    val value: String,
)

@JvmInline value class AiJobId(
    val value: String,
)

@JvmInline value class ConversationId(
    val value: String,
)

@JvmInline value class InvoiceId(
    val value: String,
)

@JvmInline value class TimeEntryId(
    val value: String,
)

@JvmInline value class ExpenseId(
    val value: String,
)

@JvmInline value class TaskId(
    val value: String,
)

@JvmInline value class NotificationId(
    val value: String,
)

@JvmInline value class DeviceId(
    val value: String,
)

@JvmInline value class TemplateId(
    val value: String,
)

@JvmInline value class PlanId(
    val value: String,
)
