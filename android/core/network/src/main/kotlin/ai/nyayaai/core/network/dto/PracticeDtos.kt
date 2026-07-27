package ai.nyayaai.core.network.dto

import kotlinx.serialization.Serializable

/**
 * DTOs for cases, hearings, billing, AI and the client portal.
 *
 * Same rule as [AuthDtos.kt]: liberal here, strict in the mappers. Every field is
 * nullable with a default so an additive server change (B.13) can never crash decoding,
 * and `NyayaJson`'s snake_case strategy means no `@SerialName` anywhere.
 */

@Serializable
data class ClientDto(
    val id: String? = null,
    val name: String? = null,
    val phone: String? = null,
    val email: String? = null,
    val address: String? = null,
    val notes: String? = null,
    val tags: List<String> = emptyList(),
    val createdAt: String? = null,
)

@Serializable
data class ClientCreateDto(
    val name: String,
    val phone: String,
    val email: String? = null,
    val address: String? = null,
    val notes: String? = null,
    val tags: List<String> = emptyList(),
)

@Serializable
data class CaseDto(
    val id: String? = null,
    val cnr: String? = null,
    val title: String? = null,
    val caseNumber: String? = null,
    val courtName: String? = null,
    val courtType: String? = null,
    val judgeName: String? = null,
    val caseType: String? = null,
    val stage: String? = null,
    val status: String? = null,
    val clientId: String? = null,
    val assignedUserIds: List<String> = emptyList(),
    // Date-only. See CourtDate — parsing this as an instant is what shows a lawyer the
    // wrong hearing day.
    val nextHearingDate: String? = null,
    val ecourtsSynced: Boolean = false,
    val lastSyncedAt: String? = null,
    val createdAt: String? = null,
)

@Serializable
data class CaseCreateDto(
    val title: String,
    val clientId: String? = null,
    val cnr: String? = null,
    val caseNumber: String? = null,
    val courtName: String? = null,
    val caseType: String? = null,
    val stage: String? = null,
)

@Serializable
data class CnrLookupRequestDto(
    val cnr: String,
)

@Serializable
data class CnrPreviewDto(
    val cnr: String? = null,
    val title: String? = null,
    val caseNumber: String? = null,
    val courtName: String? = null,
    val courtType: String? = null,
    val judgeName: String? = null,
    val caseType: String? = null,
    val stage: String? = null,
    val parties: List<String> = emptyList(),
    val nextHearingDate: String? = null,
)

@Serializable
data class CaseFromCnrRequestDto(
    val cnr: String,
    val clientId: String? = null,
)

@Serializable
data class HearingDto(
    val id: String? = null,
    val caseId: String? = null,
    val date: String? = null,
    val time: String? = null,
    val purpose: String? = null,
    val courtroom: String? = null,
    val outcomeNotes: String? = null,
    val source: String? = null,
)

@Serializable
data class HearingCreateDto(
    val date: String,
    val time: String? = null,
    val purpose: String? = null,
    val courtroom: String? = null,
)

/** `GET /calendar/today` — the payload behind the Today screen (D.4). */
@Serializable
data class TodayDto(
    val date: String? = null,
    val hearings: List<TodayHearingDto> = emptyList(),
    val tomorrowCount: Int = 0,
    val unreadNotifications: Int = 0,
    // A list, not a count: the server sends the actual hearings so the nudge can link
    // straight to the one that needs an outcome recorded.
    val overdueOutcomes: List<TodayHearingDto> = emptyList(),
)

@Serializable
data class TodayHearingDto(
    val id: String? = null,
    val caseId: String? = null,
    val caseTitle: String? = null,
    val outcomeNotes: String? = null,
    val courtName: String? = null,
    val date: String? = null,
    val time: String? = null,
    val purpose: String? = null,
    val courtroom: String? = null,
)

@Serializable
data class TaskDto(
    val id: String? = null,
    val caseId: String? = null,
    val title: String? = null,
    val assigneeId: String? = null,
    val dueDate: String? = null,
    val status: String? = null,
    val createdBy: String? = null,
)

@Serializable
data class TaskCreateDto(
    val title: String,
    val caseId: String? = null,
    val dueDate: String? = null,
)

@Serializable
data class DocumentDto(
    val id: String? = null,
    val caseId: String? = null,
    val clientId: String? = null,
    val name: String? = null,
    val folder: String? = null,
    val mimeType: String? = null,
    val sizeBytes: Long = 0,
    val ocrStatus: String? = null,
    val downloadUrl: String? = null,
    val uploadedBy: String? = null,
    val createdAt: String? = null,
)

@Serializable
data class InvoiceLineItemDto(
    val description: String? = null,
    val quantity: Int = 1,
    val ratePaise: Long = 0,
    val amountPaise: Long = 0,
)

@Serializable
data class InvoiceDto(
    val id: String? = null,
    val clientId: String? = null,
    val caseId: String? = null,
    val number: String? = null,
    val lineItems: List<InvoiceLineItemDto> = emptyList(),
    // Money is integer paise on the wire, always. Never a decimal.
    val subtotalPaise: Long = 0,
    val gstRate: Int = 0,
    val gstPaise: Long = 0,
    val totalPaise: Long = 0,
    val status: String? = null,
    val dueDate: String? = null,
    val pdfUrl: String? = null,
    val paymentLink: String? = null,
    val createdAt: String? = null,
)

@Serializable
data class InvoiceCreateDto(
    val clientId: String,
    val caseId: String? = null,
    val lineItems: List<InvoiceLineItemDto>,
    val gstRate: Int = 18,
    val importUnbilledTime: Boolean = false,
    val reverseCharge: Boolean = false,
)

@Serializable
data class TimeEntryCreateDto(
    val caseId: String,
    val startedAt: String,
    val durationSeconds: Long,
    val description: String? = null,
    val billable: Boolean = true,
    val ratePaise: Long? = null,
)

@Serializable
data class TimeEntryDto(
    val id: String? = null,
    val caseId: String? = null,
    val userId: String? = null,
    val startedAt: String? = null,
    val durationSeconds: Long = 0,
    val description: String? = null,
    val billable: Boolean = true,
    val ratePaise: Long? = null,
    val invoicedAt: String? = null,
)

@Serializable
data class PaymentOrderRequestDto(
    val invoiceId: String,
)

@Serializable
data class PaymentOrderDto(
    val razorpayOrderId: String? = null,
    val amountPaise: Long = 0,
    val keyId: String? = null,
)

@Serializable
data class PaymentVerifyRequestDto(
    val orderId: String,
    val paymentId: String,
    val signature: String,
)

/**
 * B.10: the app reads `invoiceStatus`, never its own Checkout SDK result. The server is
 * the only thing that decides an invoice is paid.
 */
@Serializable
data class PaymentVerifyDto(
    val invoiceId: String? = null,
    val invoiceStatus: String? = null,
    val verified: Boolean = false,
)

@Serializable
data class AiJobDto(
    val id: String? = null,
    val jobId: String? = null,
    val type: String? = null,
    val status: String? = null,
    val input: Map<String, String> = emptyMap(),
    val error: String? = null,
    val estimatedSeconds: Int? = null,
    val createdAt: String? = null,
    val completedAt: String? = null,
    val result: AiResultDto? = null,
)

/**
 * Both AI result shapes in one type — summarise fills the top half, research the bottom.
 * Keeping them together avoids a polymorphic decoder for a difference the UI already
 * knows from the job type.
 */
@Serializable
data class AiResultDto(
    val summaryMarkdown: String? = null,
    val keyPoints: List<String> = emptyList(),
    val parties: List<String> = emptyList(),
    val sectionsInvoked: List<String> = emptyList(),
    val dates: List<String> = emptyList(),
    val docTypeDetected: String? = null,
    val answerMarkdown: String? = null,
    val confidence: String? = null,
    val citations: List<CitationDto> = emptyList(),
)

@Serializable
data class CitationDto(
    val title: String? = null,
    val court: String? = null,
    val year: Int? = null,
    val citation: String? = null,
    val sourceUrl: String? = null,
    val snippet: String? = null,
)

@Serializable
data class SummarizeRequestDto(
    val documentId: String,
    val docTypeHint: String? = null,
)

@Serializable
data class ResearchRequestDto(
    val query: String,
    val language: String = "en",
    val conversationId: String? = null,
)

/** D.10 client mode. A deliberately smaller shape than [CaseDto] — see PortalMappers. */
@Serializable
data class PortalCaseDto(
    val id: String? = null,
    val title: String? = null,
    val caseNumber: String? = null,
    val courtName: String? = null,
    val status: String? = null,
    val nextHearingDate: String? = null,
    val judgeName: String? = null,
    val timeline: List<PortalHearingDto> = emptyList(),
)

@Serializable
data class PortalHearingDto(
    val id: String? = null,
    val date: String? = null,
    val time: String? = null,
    val purpose: String? = null,
    val isUpcoming: Boolean = false,
)

@Serializable
data class PortalInvoiceDto(
    val id: String? = null,
    val number: String? = null,
    val totalPaise: Long = 0,
    val status: String? = null,
    val dueDate: String? = null,
    val pdfUrl: String? = null,
    val paymentLink: String? = null,
    val createdAt: String? = null,
)
