package ai.nyayaai.feature.billing

import ai.nyayaai.core.model.CaseId
import ai.nyayaai.core.model.TimeEntry
import ai.nyayaai.core.network.api.ApiResult
import android.content.Context
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlin.time.Clock
import kotlin.time.Instant
import javax.inject.Inject
import javax.inject.Singleton

/**
 * D.9's stopwatch, single source of truth for both [TimeTrackerService] (which only
 * keeps the OS foreground-alive and the notification ticking) and the Compose screen.
 *
 * Same shape as [PaymentCoordinator]: the thing that actually starts/stops matters (a
 * notification action, an in-app button) lives outside the composition, so something
 * outside it has to hold the running state. Persistence goes through the same
 * `time-entries` endpoint [ai.nyayaai.feature.cases.AddTimeEntryScreen]'s manual form
 * uses — see [TimeTrackerRepository].
 */
@Singleton
class TimeTrackerCoordinator
    @Inject
    constructor(
        @ApplicationContext private val context: Context,
        private val repository: TimeTrackerRepository,
    ) {
        private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)

        private val _state = MutableStateFlow<TimeTrackerState>(TimeTrackerState.Idle)
        val state: StateFlow<TimeTrackerState> = _state.asStateFlow()

        fun start(
            caseId: CaseId,
            caseTitle: String,
        ) {
            if (_state.value is TimeTrackerState.Running) return

            val startedAt = Clock.System.now()
            _state.value = TimeTrackerState.Running(caseId, caseTitle, startedAt)
            TimeTrackerService.start(context, caseTitle, startedAt)
        }

        /**
         * The single path both the in-app Stop button and the notification's Stop action
         * converge on — [TimeTrackerService] holds no business logic of its own, it just
         * forwards its Stop action here. A second call while already saving/idle is a
         * harmless no-op rather than a double-submit.
         */
        fun stop() {
            val running = _state.value as? TimeTrackerState.Running ?: return

            _state.value = TimeTrackerState.Saving
            TimeTrackerService.stop(context)

            scope.launch {
                val elapsedSeconds = (Clock.System.now() - running.startedAt).inWholeSeconds.coerceAtLeast(1)
                val result =
                    repository.create(
                        caseId = running.caseId,
                        startedAt = running.startedAt,
                        durationSeconds = elapsedSeconds,
                        description = null,
                        billable = true,
                        ratePaise = null,
                    )
                _state.value =
                    when (result) {
                        is ApiResult.Success -> TimeTrackerState.Saved(result.data)
                        is ApiResult.Failure -> TimeTrackerState.Failed(result.error.message)
                    }
            }
        }

        /** Dismisses a Saved/Failed banner, same as [PaymentCoordinator.clear]. */
        fun clear() {
            if (_state.value !is TimeTrackerState.Running) {
                _state.value = TimeTrackerState.Idle
            }
        }
    }

sealed interface TimeTrackerState {
    data object Idle : TimeTrackerState

    data class Running(
        val caseId: CaseId,
        val caseTitle: String,
        val startedAt: Instant,
    ) : TimeTrackerState

    data object Saving : TimeTrackerState

    data class Saved(
        val entry: TimeEntry,
    ) : TimeTrackerState

    data class Failed(
        val message: String?,
    ) : TimeTrackerState
}
