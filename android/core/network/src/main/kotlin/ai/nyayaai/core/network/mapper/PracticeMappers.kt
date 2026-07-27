package ai.nyayaai.core.network.mapper

import ai.nyayaai.core.model.AiJob
import ai.nyayaai.core.model.AiJobId
import ai.nyayaai.core.model.AiJobStatus
import ai.nyayaai.core.model.AiJobType
import ai.nyayaai.core.model.Case
import ai.nyayaai.core.model.CaseId
import ai.nyayaai.core.model.CaseStatus
import ai.nyayaai.core.model.Client
import ai.nyayaai.core.model.ClientId
import ai.nyayaai.core.model.Document
import ai.nyayaai.core.model.DocumentId
import ai.nyayaai.core.model.Hearing
import ai.nyayaai.core.model.HearingId
import ai.nyayaai.core.model.HearingSource
import ai.nyayaai.core.model.Invoice
import ai.nyayaai.core.model.InvoiceId
import ai.nyayaai.core.model.InvoiceLineItem
import ai.nyayaai.core.model.InvoiceStatus
import ai.nyayaai.core.model.OcrStatus
import ai.nyayaai.core.model.Paise
import ai.nyayaai.core.model.ResearchConfidence
import ai.nyayaai.core.model.Task
import ai.nyayaai.core.model.TaskId
import ai.nyayaai.core.model.TaskStatus
import ai.nyayaai.core.model.TimeEntry
import ai.nyayaai.core.model.TimeEntryId
import ai.nyayaai.core.model.UserId
import ai.nyayaai.core.network.dto.AiJobDto
import ai.nyayaai.core.network.dto.AiResultDto
import ai.nyayaai.core.network.dto.CaseDto
import ai.nyayaai.core.network.dto.CitationDto
import ai.nyayaai.core.network.dto.ClientDto
import ai.nyayaai.core.network.dto.CnrPreviewDto
import ai.nyayaai.core.network.dto.DocumentDto
import ai.nyayaai.core.network.dto.HearingDto
import ai.nyayaai.core.network.dto.InvoiceDto
import ai.nyayaai.core.network.dto.InvoiceLineItemDto
import ai.nyayaai.core.network.dto.PortalCaseDto
import ai.nyayaai.core.network.dto.PortalHearingDto
import ai.nyayaai.core.network.dto.PortalInvoiceDto
import ai.nyayaai.core.network.dto.TaskDto
import ai.nyayaai.core.network.dto.TimeEntryDto
import ai.nyayaai.core.network.dto.TodayDto
import ai.nyayaai.core.network.dto.TodayHearingDto

fun ClientDto.toDomain(): Client =
    Client(
        id = ClientId(id.requiredString("client.id")),
        name = name.requiredString("client.name"),
        phone = phone.requiredString("client.phone"),
        email = email,
        address = address,
        notes = notes,
        tags = tags,
        createdAt = createdAt.toInstantOrThrow("client.created_at"),
    )

fun CaseDto.toDomain(): Case =
    Case(
        id = CaseId(id.requiredString("case.id")),
        cnr = cnr,
        title = title.requiredString("case.title"),
        caseNumber = caseNumber,
        courtName = courtName,
        courtType = courtType,
        judgeName = judgeName,
        caseType = caseType,
        stage = stage,
        status = CaseStatus.from(status),
        clientId = clientId?.let(::ClientId),
        assignedUserIds = assignedUserIds.map(::UserId),
        // Date-only, never routed through a timezone.
        nextHearingDate = nextHearingDate.toCourtDateOrNull(),
        ecourtsSynced = ecourtsSynced,
        lastSyncedAt = lastSyncedAt.toInstantOrNull(),
        createdAt = createdAt.toInstantOrThrow("case.created_at"),
    )

fun HearingDto.toDomain(): Hearing =
    Hearing(
        id = HearingId(id.requiredString("hearing.id")),
        caseId = CaseId(caseId.requiredString("hearing.case_id")),
        date = date.toCourtDateOrThrow("hearing.date"),
        time = time.toCourtTimeOrNull(),
        purpose = purpose,
        courtroom = courtroom,
        outcomeNotes = outcomeNotes,
        source = HearingSource.from(source),
    )

fun DocumentDto.toDomain(): Document =
    Document(
        id = DocumentId(id.requiredString("document.id")),
        caseId = caseId?.let(::CaseId),
        clientId = clientId?.let(::ClientId),
        name = name.requiredString("document.name"),
        folder = folder,
        mimeType = mimeType ?: "application/octet-stream",
        sizeBytes = sizeBytes,
        ocrStatus = OcrStatus.from(ocrStatus),
        downloadUrl = downloadUrl,
        uploadedBy = uploadedBy?.let(::UserId),
        createdAt = createdAt.toInstantOrThrow("document.created_at"),
    )

fun TaskDto.toDomain(): Task =
    Task(
        id = TaskId(id.requiredString("task.id")),
        caseId = caseId?.let(::CaseId),
        title = title.requiredString("task.title"),
        assigneeId = assigneeId?.let(::UserId),
        dueDate = dueDate.toCourtDateOrNull(),
        status = TaskStatus.from(status),
        createdBy = createdBy?.let(::UserId),
    )

fun InvoiceLineItemDto.toDomain(): InvoiceLineItem =
    InvoiceLineItem(
        description = description ?: "",
        quantity = quantity,
        ratePaise = Paise(ratePaise),
        // Recomputed rather than trusted: if the server ever disagrees with
        // quantity x rate, the line and the total on screen must still add up.
        amountPaise = Paise(if (amountPaise != 0L) amountPaise else quantity * ratePaise),
    )

fun InvoiceDto.toDomain(): Invoice =
    Invoice(
        id = InvoiceId(id.requiredString("invoice.id")),
        clientId = ClientId(clientId.requiredString("invoice.client_id")),
        caseId = caseId?.let(::CaseId),
        number = number.requiredString("invoice.number"),
        lineItems = lineItems.map { it.toDomain() },
        subtotalPaise = Paise(subtotalPaise),
        gstRate = gstRate,
        gstPaise = Paise(gstPaise),
        totalPaise = Paise(totalPaise),
        status = InvoiceStatus.from(status),
        dueDate = dueDate.toCourtDateOrNull(),
        pdfUrl = pdfUrl,
        paymentLink = paymentLink,
    )

fun TimeEntryDto.toDomain(): TimeEntry =
    TimeEntry(
        id = TimeEntryId(id.requiredString("time_entry.id")),
        caseId = CaseId(caseId.requiredString("time_entry.case_id")),
        userId = UserId(userId.requiredString("time_entry.user_id")),
        startedAt = startedAt.toInstantOrThrow("time_entry.started_at"),
        durationSeconds = durationSeconds,
        description = description,
        billable = billable,
        ratePaise = ratePaise?.let(::Paise),
    )

fun AiJobDto.toDomain(): AiJob =
    AiJob(
        // Submission returns `job_id` (B.7) while the job resource returns `id`. Accepting
        // either keeps one model for both, instead of a second near-identical type.
        id = AiJobId((id ?: jobId).requiredString("ai_job.id")),
        type = AiJobType.from(type),
        status = AiJobStatus.from(status),
        inputRef = input["document_id"] ?: input["query"],
        error = error,
        createdAt =
            createdAt.toInstantOrNull() ?: kotlin.time.Clock.System
                .now(),
        completedAt = completedAt.toInstantOrNull(),
        estimatedSeconds = estimatedSeconds,
    )

/**
 * AI result content, kept out of [AiJob] because the domain model describes the *job*
 * while this describes what came back. Screens render one or the other by job type.
 */
data class AiContent(
    val summaryMarkdown: String?,
    val keyPoints: List<String>,
    val parties: List<String>,
    val sectionsInvoked: List<String>,
    val docTypeDetected: String?,
    val answerMarkdown: String?,
    val confidence: ResearchConfidence,
    val citations: List<Citation>,
)

data class Citation(
    val title: String,
    val court: String?,
    val year: Int?,
    val citation: String?,
    val sourceUrl: String?,
    val snippet: String?,
)

fun AiResultDto.toContent(): AiContent =
    AiContent(
        summaryMarkdown = summaryMarkdown,
        keyPoints = keyPoints,
        parties = parties,
        sectionsInvoked = sectionsInvoked,
        docTypeDetected = docTypeDetected,
        answerMarkdown = answerMarkdown,
        confidence = ResearchConfidence.from(confidence),
        citations = citations.map { it.toDomain() },
    )

fun CitationDto.toDomain(): Citation =
    Citation(
        title = title ?: "Untitled authority",
        court = court,
        year = year,
        citation = citation,
        sourceUrl = sourceUrl,
        snippet = snippet,
    )

/** The Today screen's own shape (D.4) — a hearing plus the case context it needs. */
data class TodayBoard(
    val date: ai.nyayaai.core.model.CourtDate,
    val hearings: List<TodayHearing>,
    val tomorrowCount: Int,
    val unreadNotifications: Int,
    val overdueOutcomes: List<TodayHearing>,
)

data class TodayHearing(
    val id: HearingId,
    val caseId: CaseId,
    val caseTitle: String,
    val courtName: String?,
    val time: ai.nyayaai.core.model.CourtTime?,
    val purpose: String?,
    val courtroom: String?,
)

fun TodayDto.toDomain(): TodayBoard =
    TodayBoard(
        date = date.toCourtDateOrThrow("today.date"),
        hearings = hearings.map { it.toDomain() },
        tomorrowCount = tomorrowCount,
        unreadNotifications = unreadNotifications,
        overdueOutcomes = overdueOutcomes.map { it.toDomain() },
    )

fun TodayHearingDto.toDomain(): TodayHearing =
    TodayHearing(
        id = HearingId(id.requiredString("today.hearing.id")),
        caseId = CaseId(caseId.requiredString("today.hearing.case_id")),
        caseTitle = caseTitle.requiredString("today.hearing.case_title"),
        courtName = courtName,
        time = time.toCourtTimeOrNull(),
        purpose = purpose,
        courtroom = courtroom,
    )

data class CnrPreview(
    val cnr: String,
    val title: String,
    val caseNumber: String?,
    val courtName: String?,
    val judgeName: String?,
    val caseType: String?,
    val stage: String?,
    val parties: List<String>,
    val nextHearingDate: ai.nyayaai.core.model.CourtDate?,
)

fun CnrPreviewDto.toDomain(): CnrPreview =
    CnrPreview(
        cnr = cnr.requiredString("cnr_preview.cnr"),
        title = title.requiredString("cnr_preview.title"),
        caseNumber = caseNumber,
        courtName = courtName,
        judgeName = judgeName,
        caseType = caseType,
        stage = stage,
        parties = parties,
        nextHearingDate = nextHearingDate.toCourtDateOrNull(),
    )

/**
 * Client-mode models (D.10).
 *
 * Separate types from [Case] and [Invoice] on purpose. If the portal reused the staff
 * models, every field added to those would become a field the client screens could
 * accidentally render — the type system is doing the same allow-listing the server does.
 */
data class PortalCase(
    val id: CaseId,
    val title: String,
    val caseNumber: String?,
    val courtName: String?,
    val statusLabel: String,
    val nextHearingDate: ai.nyayaai.core.model.CourtDate?,
    val judgeName: String?,
    val timeline: List<PortalHearing>,
)

data class PortalHearing(
    val id: HearingId,
    val date: ai.nyayaai.core.model.CourtDate,
    val time: ai.nyayaai.core.model.CourtTime?,
    val purpose: String?,
    val isUpcoming: Boolean,
)

data class PortalInvoice(
    val id: InvoiceId,
    val number: String,
    val totalPaise: Paise,
    val status: InvoiceStatus,
    val dueDate: ai.nyayaai.core.model.CourtDate?,
    val paymentLink: String?,
)

fun PortalCaseDto.toDomain(): PortalCase =
    PortalCase(
        id = CaseId(id.requiredString("portal.case.id")),
        title = title.requiredString("portal.case.title"),
        caseNumber = caseNumber,
        courtName = courtName,
        // Already plain language from the server; shown as-is rather than re-mapped,
        // so the client never sees an internal status string.
        statusLabel = status ?: "",
        nextHearingDate = nextHearingDate.toCourtDateOrNull(),
        judgeName = judgeName,
        timeline = timeline.map { it.toDomain() },
    )

fun PortalHearingDto.toDomain(): PortalHearing =
    PortalHearing(
        id = HearingId(id.requiredString("portal.hearing.id")),
        date = date.toCourtDateOrThrow("portal.hearing.date"),
        time = time.toCourtTimeOrNull(),
        purpose = purpose,
        isUpcoming = isUpcoming,
    )

fun PortalInvoiceDto.toDomain(): PortalInvoice =
    PortalInvoice(
        id = InvoiceId(id.requiredString("portal.invoice.id")),
        number = number.requiredString("portal.invoice.number"),
        totalPaise = Paise(totalPaise),
        status = InvoiceStatus.from(status),
        dueDate = dueDate.toCourtDateOrNull(),
        paymentLink = paymentLink,
    )
