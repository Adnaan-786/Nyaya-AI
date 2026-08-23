package ai.nyayaai.feature.billing

import ai.nyayaai.core.common.UiState
import ai.nyayaai.core.designsystem.component.EmptyState
import ai.nyayaai.core.designsystem.component.ErrorState
import ai.nyayaai.core.designsystem.component.LoadingList
import ai.nyayaai.core.designsystem.component.NyayaCard
import ai.nyayaai.core.designsystem.component.NyayaDropdownField
import ai.nyayaai.core.designsystem.component.SectionHeader
import ai.nyayaai.core.designsystem.theme.NyayaTheme
import ai.nyayaai.core.model.Case
import ai.nyayaai.core.model.CaseId
import ai.nyayaai.core.model.TimeEntry
import ai.nyayaai.core.network.api.ApiResult
import ai.nyayaai.core.network.api.isRetryable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarDuration
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlin.time.Clock
import javax.inject.Inject

data class TimeTrackerPickerState(
    val cases: List<Case> = emptyList(),
    val selectedCaseId: CaseId? = null,
    val isLoadingCases: Boolean = true,
)

/** D.9 billing/timer: case picker + start/stop, plus the "unbilled summary per case"
 * view alongside it — one screen, since both read from the same case list. */
@HiltViewModel
class TimeTrackerViewModel
    @Inject
    constructor(
        private val billingRepository: BillingRepository,
        private val repository: TimeTrackerRepository,
        val coordinator: TimeTrackerCoordinator,
    ) : ViewModel() {
        private val _pickerState = MutableStateFlow(TimeTrackerPickerState())
        val pickerState: StateFlow<TimeTrackerPickerState> = _pickerState.asStateFlow()

        private val _unbilledState = MutableStateFlow<UiState<List<TimeEntry>>>(UiState.Loading)
        val unbilledState: StateFlow<UiState<List<TimeEntry>>> = _unbilledState.asStateFlow()

        val timerState: StateFlow<TimeTrackerState> = coordinator.state

        init {
            viewModelScope.launch {
                val result = billingRepository.cases()
                _pickerState.update {
                    it.copy(
                        cases = (result as? ApiResult.Success)?.data.orEmpty(),
                        isLoadingCases = false,
                    )
                }
            }
            loadUnbilled()
        }

        fun onCaseSelected(id: CaseId) {
            _pickerState.update { it.copy(selectedCaseId = id) }
        }

        fun loadUnbilled() {
            viewModelScope.launch {
                _unbilledState.value = UiState.Loading
                _unbilledState.value =
                    when (val result = repository.unbilledTimeEntries()) {
                        is ApiResult.Failure -> UiState.Error(result.error.message, result.error.isRetryable)
                        is ApiResult.Success -> UiState.Content(result.data)
                    }
            }
        }

        fun start() {
            val current = _pickerState.value
            val case = current.cases.find { it.id == current.selectedCaseId } ?: return
            coordinator.start(case.id, case.title)
        }

        fun stop() = coordinator.stop()

        fun dismissMessage() = coordinator.clear()
    }

@Composable
fun TimeTrackerRoute(
    modifier: Modifier = Modifier,
    viewModel: TimeTrackerViewModel = hiltViewModel(),
) {
    val picker by viewModel.pickerState.collectAsStateWithLifecycle()
    val unbilled by viewModel.unbilledState.collectAsStateWithLifecycle()
    val timer by viewModel.timerState.collectAsStateWithLifecycle()
    val snackbarHostState = remember { SnackbarHostState() }
    val context = LocalContext.current

    // Same shape as InvoiceListRoute's payment-state handling: react to the terminal
    // states, leave Idle/Running/Saving alone (the stopwatch card already reflects those).
    LaunchedEffect(timer) {
        when (val current = timer) {
            is TimeTrackerState.Saved -> {
                snackbarHostState.showSnackbar(
                    message = context.getString(R.string.timer_saved),
                    duration = SnackbarDuration.Short,
                )
                viewModel.loadUnbilled()
                viewModel.dismissMessage()
            }

            is TimeTrackerState.Failed -> {
                snackbarHostState.showSnackbar(
                    message = current.message ?: context.getString(R.string.timer_failed),
                    duration = SnackbarDuration.Long,
                )
                viewModel.dismissMessage()
            }

            TimeTrackerState.Idle, TimeTrackerState.Saving, is TimeTrackerState.Running -> Unit
        }
    }

    Scaffold(
        modifier = modifier,
        snackbarHost = { SnackbarHost(snackbarHostState) },
    ) { innerPadding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(innerPadding),
            contentPadding = PaddingValues(NyayaTheme.spacing.md),
            verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.md),
        ) {
            item {
                StopwatchCard(
                    picker = picker,
                    timer = timer,
                    onCaseSelected = viewModel::onCaseSelected,
                    onStart = viewModel::start,
                    onStop = viewModel::stop,
                )
            }

            item { SectionHeader(title = stringResource(R.string.timer_unbilled_title)) }

            when (val state = unbilled) {
                is UiState.Loading -> item { LoadingList() }

                is UiState.Error ->
                    item {
                        ErrorState(
                            message = state.message,
                            onRetry = viewModel::loadUnbilled.takeIf { state.retryable },
                        )
                    }

                is UiState.Empty -> item { EmptyState(title = state.title) }

                is UiState.Content -> {
                    val entries = state.data
                    if (entries.isEmpty()) {
                        item { EmptyState(title = stringResource(R.string.timer_unbilled_empty)) }
                    } else {
                        val byCase = entries.groupBy { it.caseId }
                        val caseTitles = picker.cases.associateBy({ it.id }, { it.title })

                        byCase.forEach { (caseId, caseEntries) ->
                            item(key = caseId.value) {
                                UnbilledCaseRow(
                                    caseTitle = caseTitles[caseId] ?: caseId.value,
                                    totalSeconds = caseEntries.sumOf { it.durationSeconds },
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun StopwatchCard(
    picker: TimeTrackerPickerState,
    timer: TimeTrackerState,
    onCaseSelected: (CaseId) -> Unit,
    onStart: () -> Unit,
    onStop: () -> Unit,
) {
    NyayaCard {
        Column(verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.sm)) {
            when (timer) {
                is TimeTrackerState.Running -> {
                    Text(text = timer.caseTitle, style = MaterialTheme.typography.titleMedium)
                    Text(
                        text = stringResource(R.string.timer_running),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    ElapsedTime(startedAtMillis = timer.startedAt.toEpochMilliseconds())
                    OutlinedButton(onClick = onStop, modifier = Modifier.fillMaxWidth()) {
                        Text(stringResource(R.string.timer_stop))
                    }
                }

                else -> {
                    val selected = picker.selectedCaseId
                    NyayaDropdownField(
                        value = picker.cases.find { it.id == selected },
                        options = picker.cases,
                        onSelect = { onCaseSelected(it.id) },
                        label = stringResource(R.string.timer_case_label),
                        optionLabel = { it.title },
                        enabled = !picker.isLoadingCases && timer !is TimeTrackerState.Saving,
                    )
                    Button(
                        onClick = onStart,
                        enabled = selected != null && timer !is TimeTrackerState.Saving,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(stringResource(R.string.timer_start))
                    }
                }
            }
        }
    }
}

/** Recomposes once a second purely to redraw the label — the notification's own
 * chronometer (`TimeTrackerService`) is what actually keeps the timer alive; this is
 * just the in-app mirror of the same `startedAt`. */
@Composable
private fun ElapsedTime(startedAtMillis: Long) {
    var elapsedSeconds by remember(startedAtMillis) { mutableLongStateOf(0L) }

    LaunchedEffect(startedAtMillis) {
        while (true) {
            elapsedSeconds = (Clock.System.now().toEpochMilliseconds() - startedAtMillis) / MILLIS_PER_SECOND
            delay(MILLIS_PER_SECOND)
        }
    }

    Text(text = elapsedSeconds.formatDuration(), style = MaterialTheme.typography.headlineMedium)
}

@Composable
private fun UnbilledCaseRow(
    caseTitle: String,
    totalSeconds: Long,
) {
    NyayaCard {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(text = caseTitle, style = MaterialTheme.typography.bodyLarge)
            Text(text = totalSeconds.formatDuration(), style = MaterialTheme.typography.bodyMedium)
        }
    }
}

/** Same rendering as `CaseDetailScreen`'s private time-entry formatter — duplicated
 * rather than shared, same reasoning as this module's own `InvoiceStatus` label/tone
 * functions: a few lines of `private fun` beats fighting Kotlin file visibility across
 * feature modules that are not allowed to depend on each other anyway. */
private fun Long.formatDuration(): String {
    val hours = this / SECONDS_PER_HOUR
    val minutes = (this % SECONDS_PER_HOUR) / SECONDS_PER_MINUTE
    val seconds = this % SECONDS_PER_MINUTE
    return if (hours > 0) {
        "%d:%02d:%02d".format(hours, minutes, seconds)
    } else {
        "%d:%02d".format(minutes, seconds)
    }
}

private const val MILLIS_PER_SECOND = 1000L
private const val SECONDS_PER_MINUTE = 60L
private const val SECONDS_PER_HOUR = 3600L
