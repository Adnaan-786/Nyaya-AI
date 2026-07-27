package ai.nyayaai.core.network.service

import ai.nyayaai.core.network.api.ApiEnvelope
import ai.nyayaai.core.network.api.EmptyBody
import ai.nyayaai.core.network.dto.AiJobDto
import ai.nyayaai.core.network.dto.CaseCreateDto
import ai.nyayaai.core.network.dto.CaseDto
import ai.nyayaai.core.network.dto.CaseFromCnrRequestDto
import ai.nyayaai.core.network.dto.ClientCreateDto
import ai.nyayaai.core.network.dto.ClientDto
import ai.nyayaai.core.network.dto.CnrLookupRequestDto
import ai.nyayaai.core.network.dto.CnrPreviewDto
import ai.nyayaai.core.network.dto.DocumentDto
import ai.nyayaai.core.network.dto.HearingCreateDto
import ai.nyayaai.core.network.dto.HearingDto
import ai.nyayaai.core.network.dto.InvoiceCreateDto
import ai.nyayaai.core.network.dto.InvoiceDto
import ai.nyayaai.core.network.dto.PaymentOrderDto
import ai.nyayaai.core.network.dto.PaymentOrderRequestDto
import ai.nyayaai.core.network.dto.PaymentVerifyDto
import ai.nyayaai.core.network.dto.PaymentVerifyRequestDto
import ai.nyayaai.core.network.dto.PortalCaseDto
import ai.nyayaai.core.network.dto.PortalInvoiceDto
import ai.nyayaai.core.network.dto.ResearchRequestDto
import ai.nyayaai.core.network.dto.SummarizeRequestDto
import ai.nyayaai.core.network.dto.TaskCreateDto
import ai.nyayaai.core.network.dto.TaskDto
import ai.nyayaai.core.network.dto.TimeEntryCreateDto
import ai.nyayaai.core.network.dto.TimeEntryDto
import ai.nyayaai.core.network.dto.TodayDto
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

/** B.6 cases, hearings, clients and the timeline. */
interface CaseService {
    @GET("cases")
    suspend fun cases(
        @Query("status") status: String? = null,
        @Query("q") query: String? = null,
        @Query("page") page: Int = 1,
        @Query("limit") limit: Int = 20,
    ): ApiEnvelope<List<CaseDto>>

    @GET("cases/{id}")
    suspend fun case(
        @Path("id") id: String,
    ): ApiEnvelope<CaseDto>

    @POST("cases")
    suspend fun createCase(
        @Body body: CaseCreateDto,
    ): ApiEnvelope<CaseDto>

    /**
     * D.5's "wow moment": the lawyer types 16 characters and gets a real case back.
     * A 422 CNR_INVALID or a 503 from eCourts both surface as typed errors, and the
     * screen offers manual entry rather than a dead end.
     */
    @POST("cases/lookup-cnr")
    suspend fun lookupCnr(
        @Body body: CnrLookupRequestDto,
    ): ApiEnvelope<CnrPreviewDto>

    @POST("cases/from-cnr")
    suspend fun createFromCnr(
        @Body body: CaseFromCnrRequestDto,
    ): ApiEnvelope<CaseDto>

    /** Rate-limited to 1/hour server-side; the UI shows "Synced 2 h ago" instead of retrying. */
    @POST("cases/{id}/sync")
    suspend fun sync(
        @Path("id") id: String,
    ): ApiEnvelope<CaseDto>

    @GET("cases/{id}/hearings")
    suspend fun hearings(
        @Path("id") id: String,
    ): ApiEnvelope<List<HearingDto>>

    @POST("cases/{id}/hearings")
    suspend fun addHearing(
        @Path("id") id: String,
        @Body body: HearingCreateDto,
    ): ApiEnvelope<HearingDto>

    @GET("cases/{id}/documents")
    suspend fun caseDocuments(
        @Path("id") id: String,
    ): ApiEnvelope<List<DocumentDto>>

    @GET("clients")
    suspend fun clients(
        @Query("page") page: Int = 1,
        @Query("limit") limit: Int = 50,
    ): ApiEnvelope<List<ClientDto>>

    @POST("clients")
    suspend fun createClient(
        @Body body: ClientCreateDto,
    ): ApiEnvelope<ClientDto>
}

interface CalendarService {
    @GET("calendar/today")
    suspend fun today(): ApiEnvelope<TodayDto>

    @GET("calendar")
    suspend fun range(
        @Query("from") from: String,
        @Query("to") to: String,
    ): ApiEnvelope<List<HearingDto>>

    @GET("tasks")
    suspend fun tasks(
        @Query("status") status: String? = null,
    ): ApiEnvelope<List<TaskDto>>

    @POST("tasks")
    suspend fun createTask(
        @Body body: TaskCreateDto,
    ): ApiEnvelope<TaskDto>

    @PATCH("tasks/{id}")
    suspend fun updateTask(
        @Path("id") id: String,
        @Body body: Map<String, String>,
    ): ApiEnvelope<TaskDto>
}

interface DocumentService {
    @GET("documents")
    suspend fun documents(
        @Query("folder") folder: String? = null,
        @Query("page") page: Int = 1,
        @Query("limit") limit: Int = 30,
    ): ApiEnvelope<List<DocumentDto>>

    @GET("documents/{id}")
    suspend fun document(
        @Path("id") id: String,
    ): ApiEnvelope<DocumentDto>
}

interface BillingService {
    @GET("invoices")
    suspend fun invoices(
        @Query("status") status: String? = null,
        @Query("page") page: Int = 1,
        @Query("limit") limit: Int = 20,
    ): ApiEnvelope<List<InvoiceDto>>

    @GET("invoices/{id}")
    suspend fun invoice(
        @Path("id") id: String,
    ): ApiEnvelope<InvoiceDto>

    @POST("invoices")
    suspend fun createInvoice(
        @Body body: InvoiceCreateDto,
    ): ApiEnvelope<InvoiceDto>

    @POST("invoices/{id}/send")
    suspend fun sendInvoice(
        @Path("id") id: String,
    ): ApiEnvelope<InvoiceDto>

    @GET("time-entries")
    suspend fun timeEntries(
        @Query("case_id") caseId: String? = null,
        @Query("unbilled_only") unbilledOnly: Boolean = false,
    ): ApiEnvelope<List<TimeEntryDto>>

    @POST("time-entries")
    suspend fun createTimeEntry(
        @Body body: TimeEntryCreateDto,
    ): ApiEnvelope<TimeEntryDto>

    @POST("payments/order")
    suspend fun createOrder(
        @Body body: PaymentOrderRequestDto,
    ): ApiEnvelope<PaymentOrderDto>

    /** B.10 step 4. The response's invoice status is the truth, not the SDK callback. */
    @POST("payments/verify")
    suspend fun verifyPayment(
        @Body body: PaymentVerifyRequestDto,
    ): ApiEnvelope<PaymentVerifyDto>
}

/**
 * B.7: submission returns 202 with a job id, and the app polls (or waits for the
 * `ai_job_complete` push). Nothing here blocks on the model.
 */
interface AiService {
    @POST("ai/summarize")
    suspend fun summarize(
        @Body body: SummarizeRequestDto,
    ): ApiEnvelope<AiJobDto>

    @POST("ai/research")
    suspend fun research(
        @Body body: ResearchRequestDto,
    ): ApiEnvelope<AiJobDto>

    @GET("ai/jobs/{id}")
    suspend fun job(
        @Path("id") id: String,
    ): ApiEnvelope<AiJobDto>

    @GET("ai/jobs")
    suspend fun jobs(
        @Query("type") type: String? = null,
        @Query("page") page: Int = 1,
        @Query("limit") limit: Int = 20,
    ): ApiEnvelope<List<AiJobDto>>
}

/** D.10. Everything a `role=client` login is allowed to see, and nothing else. */
interface PortalService {
    @GET("portal/cases")
    suspend fun cases(): ApiEnvelope<List<PortalCaseDto>>

    @GET("portal/cases/{id}")
    suspend fun case(
        @Path("id") id: String,
    ): ApiEnvelope<PortalCaseDto>

    @GET("portal/invoices")
    suspend fun invoices(): ApiEnvelope<List<PortalInvoiceDto>>
}

/** Kept for symmetry with the auth service's [EmptyBody] responses. */
internal typealias Ack = ApiEnvelope<EmptyBody>
