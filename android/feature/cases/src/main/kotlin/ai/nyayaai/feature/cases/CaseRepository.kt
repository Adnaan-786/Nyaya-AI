package ai.nyayaai.feature.cases

import ai.nyayaai.core.model.Case
import ai.nyayaai.core.model.CaseId
import ai.nyayaai.core.model.Client
import ai.nyayaai.core.model.ClientId
import ai.nyayaai.core.model.Document
import ai.nyayaai.core.model.Hearing
import ai.nyayaai.core.network.api.ApiCaller
import ai.nyayaai.core.network.api.ApiResult
import ai.nyayaai.core.network.api.map
import ai.nyayaai.core.network.dto.CaseFromCnrRequestDto
import ai.nyayaai.core.network.dto.CnrLookupRequestDto
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
            clientId: ClientId?,
        ): ApiResult<Case> =
            caller
                .call { service.createFromCnr(CaseFromCnrRequestDto(cnr, clientId?.value)) }
                .map { it.toDomain() }

        /** Server-side rate limit is 1/hour; the UI shows "Synced N ago" rather than retrying. */
        suspend fun sync(id: CaseId): ApiResult<Case> = caller.call { service.sync(id.value) }.map { it.toDomain() }
    }
