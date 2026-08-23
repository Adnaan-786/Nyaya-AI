package ai.nyayaai.feature.billing

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
 * D.9's stopwatch persists through the exact same `time-entries` endpoint the manual
 * entry form (`feature:cases.TimeEntryRepository`) already uses — feature modules never
 * depend on each other, so this reuses the shared [BillingService]/DTOs rather than the
 * sibling module's repository class, same convention that repository's own doc comment
 * describes for its relationship to `feature:cases.CaseService`.
 */
@Singleton
class TimeTrackerRepository
    @Inject
    constructor(
        private val service: BillingService,
        private val caller: ApiCaller,
    ) {
        suspend fun unbilledTimeEntries(): ApiResult<List<TimeEntry>> =
            caller.call { service.timeEntries(unbilledOnly = true) }.map { list -> list.map { it.toDomain() } }

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
                            startedAt = startedAt.toString(),
                            durationSeconds = durationSeconds,
                            description = description?.takeIf { it.isNotBlank() },
                            billable = billable,
                            ratePaise = ratePaise?.takeIf { it > 0 },
                        ),
                    )
                }.map { it.toDomain() }
    }
