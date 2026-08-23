package ai.nyayaai.feature.cases

import ai.nyayaai.core.model.Case
import ai.nyayaai.core.model.CaseId
import ai.nyayaai.core.model.Client
import ai.nyayaai.core.model.ClientId
import ai.nyayaai.core.model.CourtDate
import ai.nyayaai.core.model.CourtTime
import ai.nyayaai.core.model.Document
import ai.nyayaai.core.model.Hearing
import ai.nyayaai.core.network.api.ApiCaller
import ai.nyayaai.core.network.api.ApiResult
import ai.nyayaai.core.network.api.map
import ai.nyayaai.core.network.dto.CaseCreateDto
import ai.nyayaai.core.network.dto.CaseFromCnrRequestDto
import ai.nyayaai.core.network.dto.CnrLookupRequestDto
import ai.nyayaai.core.network.dto.HearingCreateDto
import ai.nyayaai.core.network.mapper.CnrPreview
import ai.nyayaai.core.network.mapper.toDomain
import ai.nyayaai.core.network.service.CaseService
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class CaseRepository
    @Inject
    constructor(
        private val service: CaseService,
        private val calendarService: ai.nyayaai.core.network.service.CalendarService,
        private val caller: ApiCaller,
    ) {
        suspend fun cases(
            query: String? = null,
            status: String? = null,
        ): ApiResult<List<Case>> =
            caller
                .call { service.cases(status = status, query = query?.takeIf { it.isNotBlank() }) }
                .map { list -> list.map { it.toDomain() } }

        suspend fun case(id: CaseId): ApiResult<Case> = caller.call { service.case(id.value) }.map { it.toDomain() }

        suspend fun hearings(id: CaseId): ApiResult<List<Hearing>> =
            caller.call { service.hearings(id.value) }.map { list -> list.map { it.toDomain() } }

        suspend fun documents(id: CaseId): ApiResult<List<Document>> =
            caller.call { service.caseDocuments(id.value) }.map { list -> list.map { it.toDomain() } }

        suspend fun clients(): ApiResult<List<Client>> =
            caller.call { service.clients() }.map { list -> list.map { it.toDomain() } }

        /** D.5: 422 CNR_INVALID and 503 UPSTREAM_UNAVAILABLE both arrive here as typed errors. */
        suspend fun lookupCnr(cnr: String): ApiResult<CnrPreview> =
            caller.call { service.lookupCnr(CnrLookupRequestDto(cnr)) }.map { it.toDomain() }

        suspend fun createFromCnr(
            cnr: String,
            clientId: ClientId,
        ): ApiResult<Case> =
            caller
                .call { service.createFromCnr(CaseFromCnrRequestDto(cnr, clientId.value)) }
                .map { it.toDomain() }

        /**
         * Server-side rate limit is 1/hour. The case-list badge (CaseListScreen.CaseCard)
         * reads [Case.lastSyncedAt] from the returned case rather than this call retrying.
         */
        suspend fun sync(id: CaseId): ApiResult<Case> = caller.call { service.sync(id.value) }.map { it.toDomain() }

        /** Manual intake (D.6): every field but [title] is optional, and blank means absent on the wire. */
        suspend fun createCase(
            title: String,
            clientId: ClientId,
            caseNumber: String?,
            courtName: String?,
            courtType: String?,
            judgeName: String?,
            caseType: String?,
            stage: String?,
            nextHearingDate: CourtDate?,
        ): ApiResult<Case> =
            caller
                .call {
                    service.createCase(
                        CaseCreateDto(
                            title = title,
                            clientId = clientId.value,
                            caseNumber = caseNumber?.takeIf { it.isNotBlank() },
                            courtName = courtName?.takeIf { it.isNotBlank() },
                            courtType = courtType?.takeIf { it.isNotBlank() },
                            judgeName = judgeName?.takeIf { it.isNotBlank() },
                            caseType = caseType?.takeIf { it.isNotBlank() },
                            stage = stage?.takeIf { it.isNotBlank() },
                            nextHearingDate = nextHearingDate?.toString(),
                        ),
                    )
                }.map { it.toDomain() }

        /** Manual hearing entry from the case detail screen's Hearings tab FAB. */
        suspend fun addHearing(
            caseId: CaseId,
            date: CourtDate,
            time: CourtTime?,
            purpose: String?,
            courtroom: String?,
        ): ApiResult<Hearing> =
            caller
                .call {
                    service.addHearing(
                        caseId.value,
                        HearingCreateDto(
                            date = date.toString(),
                            time = time?.toString(),
                            purpose = purpose?.takeIf { it.isNotBlank() },
                            courtroom = courtroom?.takeIf { it.isNotBlank() },
                        ),
                    )
                }.map { it.toDomain() }
    
        suspend fun notes(caseId: CaseId): ApiResult<List<ai.nyayaai.core.model.CaseNote>> =
            caller.call { service.timeline(caseId.value) }.map { list -> 
                list.filter { it.type == "note" }
                    .map { 
                        // The JSON element needs to be decoded to CaseNoteDto
                        val dto = kotlinx.serialization.json.Json.decodeFromJsonElement(
                            ai.nyayaai.core.network.dto.CaseNoteDto.serializer(), 
                            it.data
                        )
                        dto.toDomain() 
                    }
            }

        suspend fun addNote(caseId: CaseId, text: String): ApiResult<ai.nyayaai.core.model.CaseNote> =
            caller.call { service.addNote(caseId.value, ai.nyayaai.core.network.dto.CaseNoteCreateDto(text)) }
                .map { it.toDomain() }

        // INTERIM: The server lacks a case-scoped task retrieval endpoint (e.g. GET /cases/{id}/tasks).
        // Fetching all tasks and filtering by case_id client-side for now.
        // Once the m1-module1 gap is closed, this should switch to a case-scoped GET or a case_id query parameter.
        suspend fun tasks(caseId: CaseId): ApiResult<List<ai.nyayaai.core.model.Task>> =
            caller.call { calendarService.tasks(status = null) }
                .map { list -> list.map { it.toDomain() }.filter { it.caseId == caseId } }

        suspend fun addTask(
            caseId: CaseId, 
            title: String, 
            description: String?, 
            dueDate: CourtDate?
        ): ApiResult<ai.nyayaai.core.model.Task> =
            caller.call { 
                calendarService.createTask(
                    ai.nyayaai.core.network.dto.TaskCreateDto(
                        title = title,
                        caseId = caseId.value,
                        dueDate = dueDate?.toString(),
                        description = description?.takeIf { it.isNotBlank() }
                    )
                ) 
            }.map { it.toDomain() }
}
