package ai.nyayaai.core.model

import kotlin.time.Instant

/**
 * Domain models for the contract entities in B.5.
 *
 * Nullability here is the **contract's** nullability, not defensive nullability. The DTO
 * layer in `core:network` is liberal (everything optional); its mappers are the single
 * place that decides whether a missing field is a default or a reported contract
 * violation. By the time a model reaches a ViewModel it is trustworthy.
 */

data class User(
    val id: UserId,
    val tenantId: TenantId,
    val name: String,
    // Nullable since the email OTP channel landed: an account created by email has no
    // phone until its owner adds one. Treating it as required here is not a stricter
    // contract, it is a wrong one — the mapper would reject the very accounts that
    // channel creates.
    val phone: String?,
    val email: String?,
    val role: UserRole,
    val language: Language,
    val createdAt: Instant,
)

/**
 * A firm's team roster (`GET /users`), deliberately smaller than [User]. The server's
 * response here carries no `tenant_id` — every row is already implicitly the caller's own
 * firm, so echoing it back would be a field with no use — and this type follows that shape
 * exactly rather than forcing every roster row through [User]'s stricter contract.
 */
data class TeamMember(
    val id: UserId,
    val name: String,
    /** Null for a colleague who signed up by email — see [User.phone]. */
    val phone: String?,
    val email: String?,
    val role: UserRole,
    val language: Language,
    val createdAt: Instant,
)

data class Client(
    val id: ClientId,
    val name: String,
    val phone: String,
    val email: String?,
    val address: String?,
    val notes: String?,
    val tags: List<String>,
    val createdAt: Instant,
)

data class Case(
    val id: CaseId,
    val cnr: String?,
    val title: String,
    val caseNumber: String?,
    val courtName: String?,
    val courtType: String?,
    val judgeName: String?,
    val caseType: String?,
    val stage: String?,
    val status: CaseStatus,
    val clientId: ClientId?,
    val assignedUserIds: List<UserId>,
    val nextHearingDate: CourtDate?,
    val ecourtsSynced: Boolean,
    val lastSyncedAt: Instant?,
    val createdAt: Instant,
)

data class Hearing(
    val id: HearingId,
    val caseId: CaseId,
    val date: CourtDate,
    val time: CourtTime?,
    val purpose: String?,
    val courtroom: String?,
    val outcomeNotes: String?,
    val source: HearingSource,
)

data class Document(
    val id: DocumentId,
    val caseId: CaseId?,
    val clientId: ClientId?,
    val name: String,
    val folder: String?,
    val mimeType: String,
    val sizeBytes: Long,
    val ocrStatus: OcrStatus,
    /** Presigned, valid ~15 min (B.5). Never cache this; re-fetch the document instead. */
    val downloadUrl: String?,
    val uploadedBy: UserId?,
    val createdAt: Instant,
)

data class AiJob(
    val id: AiJobId,
    val type: AiJobType,
    val status: AiJobStatus,
    val inputRef: String?,
    val error: String?,
    val createdAt: Instant,
    val completedAt: Instant?,
    val estimatedSeconds: Int?,
)

data class InvoiceLineItem(
    val description: String,
    val quantity: Int,
    val ratePaise: Paise,
    val amountPaise: Paise,
)

data class Invoice(
    val id: InvoiceId,
    val clientId: ClientId,
    val caseId: CaseId?,
    val number: String,
    val lineItems: List<InvoiceLineItem>,
    val subtotalPaise: Paise,
    /** Percent, e.g. 18 for 18% GST. */
    val gstRate: Int,
    val gstPaise: Paise,
    val totalPaise: Paise,
    val status: InvoiceStatus,
    val dueDate: CourtDate?,
    val description: String?,
    val pdfUrl: String?,
    val paymentLink: String?,
)

data class TimeEntry(
    val id: TimeEntryId,
    val caseId: CaseId,
    val userId: UserId,
    val startedAt: Instant,
    val durationSeconds: Long,
    val description: String?,
    val billable: Boolean,
    val ratePaise: Paise?,
)

data class Task(
    val id: TaskId,
    val caseId: CaseId?,
    val title: String,
    val assigneeId: UserId?,
    val dueDate: CourtDate?,
    val description: String?,
    val status: TaskStatus,
    val createdBy: UserId?,
)

data class AppNotification(
    val id: NotificationId,
    val type: PushType,
    val title: String,
    val body: String,
    val deepLink: String?,
    val readAt: Instant?,
    val createdAt: Instant,
)

/**
 * B.14. Fetched unauthenticated on every cold start and cached 6 h. The app must respect
 * all three of these: a blocking update screen, remote feature kill switches, and a
 * dismissible status banner.
 */
data class AppConfig(
    val minSupportedVersion: Int,
    val latestVersion: Int,
    val featureFlags: Map<String, Boolean>,
    val statusBanner: String?,
    val supportPhone: String?,
    val supportEmail: String?,
) {
    fun isSupported(currentVersionCode: Int): Boolean = currentVersionCode >= minSupportedVersion

    fun isEnabled(flag: String): Boolean = featureFlags[flag] ?: true
}

data class Session(
    val accessToken: String,
    val refreshToken: String,
    val isNewUser: Boolean,
)

@JvmInline
value class CaseNoteId(val value: String)

data class CaseNote(
    val id: CaseNoteId,
    val caseId: CaseId,
    val authorId: UserId,
    val text: String,
    val createdAt: kotlinx.datetime.Instant,
)
