package ai.nyayaai.feature.cases

import ai.nyayaai.core.model.CaseId
import ai.nyayaai.core.model.TimeEntry
import ai.nyayaai.core.network.api.ApiCaller
import ai.nyayaai.core.network.api.ApiResult
import ai.nyayaai.core.network.api.map
import ai.nyayaai.core.network.dto.TimeEntryCreateDto
import ai.nyayaai.core.network.mapper.toDomain
import ai.nyayaai.core.network.service.BillingService
import kotlin.time.Instant
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Time entries live on [BillingService] — [feature:billing]'s service — not
 * [CaseService]. Feature modules never depend on each other, but each can inject the
 * same underlying Retrofit service from core:network; this mirrors ClientRepository's
 * relationship to CaseService from the previous sprint.
 */
@Singleton
class TimeEntryRepository
    @Inject
    constructor(
        private val service: BillingService,
        private val caller: ApiCaller,
    ) {
        suspend fun timeEntries(caseId: CaseId): ApiResult<List<TimeEntry>> =
            caller.call { service.timeEntries(caseId = caseId.value) }.map { list -> list.map { it.toDomain() } }

        suspend fun create(
            caseId: CaseId,
            startedAt: Instant,
            durationSeconds: Long,
            description: String?,
            billable: Boolean,
            ratePaise: Long?,
        ): ApiResult<TimeEntry> =
            caller
                .call {
                    service.createTimeEntry(
                        TimeEntryCreateDto(
                            caseId = caseId.value,
                            startedAt = startedAt.toString(), // ISO-8601, matches the contract
                            durationSeconds = durationSeconds,
                            description = description?.takeIf { it.isNotBlank() },
                            billable = billable,
                            ratePaise = ratePaise?.takeIf { it > 0 },
                        ),
                    )
                }.map { it.toDomain() }
    }
