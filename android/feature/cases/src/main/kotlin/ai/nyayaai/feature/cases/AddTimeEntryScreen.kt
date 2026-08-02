package ai.nyayaai.feature.cases

import ai.nyayaai.core.designsystem.component.FormScaffold
import ai.nyayaai.core.designsystem.component.NyayaMoneyField
import ai.nyayaai.core.designsystem.component.NyayaTextField
import ai.nyayaai.core.model.CaseId
import ai.nyayaai.core.network.api.ApiResult
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlin.time.Clock
import javax.inject.Inject

/**
 * Reached from the FAB on [CaseDetailScreen]'s Time tab. [durationMinutes] is the only
 * field the lawyer must fill in; it is entered in minutes (how a lawyer actually thinks
 * about billable work) and converted to seconds for the wire. [startedAt] is not
 * user-entered in this first cut — it is stamped with "now" at save time, since a
 * retroactive "when did this work happen" picker is a reasonable future enhancement but
 * out of scope here.
 */
data class AddTimeEntryUiState(
    val durationMinutes: String = "",
    val description: String = "",
    val billable: Boolean = true,
    val ratePaise: Long = 0,
    val isSaving: Boolean = false,
    val error: String? = null,
    val created: Boolean = false,
) {
    val isValid: Boolean get() = durationMinutes.toIntOrNull()?.let { it > 0 } == true
}

@HiltViewModel
class AddTimeEntryViewModel
    @Inject
    constructor(
        savedStateHandle: SavedStateHandle,
        private val repository: TimeEntryRepository,
    ) : ViewModel() {
        private val caseId = CaseId(checkNotNull(savedStateHandle.get<String>(ARG_CASE_ID)))

        private val _state = MutableStateFlow(AddTimeEntryUiState())
        val state: StateFlow<AddTimeEntryUiState> = _state.asStateFlow()

        fun onDurationMinutesChanged(value: String) {
            _state.update { it.copy(durationMinutes = value, error = null) }
        }

        fun onDescriptionChanged(value: String) {
            _state.update { it.copy(description = value, error = null) }
        }

        fun onBillableChanged(value: Boolean) {
            _state.update { it.copy(billable = value, error = null) }
        }

        fun onRatePaiseChanged(value: Long) {
            _state.update { it.copy(ratePaise = value, error = null) }
        }

        fun save() {
            val current = _state.value
            val minutes = current.durationMinutes.toIntOrNull()
            if (!current.isValid || current.isSaving || minutes == null) return

            _state.update { it.copy(isSaving = true, error = null) }
            viewModelScope.launch {
                when (
                    val result =
                        repository.create(
                            caseId = caseId,
                            startedAt = Clock.System.now(),
                            durationSeconds = minutes.toLong() * SECONDS_PER_MINUTE,
                            description = current.description,
                            billable = current.billable,
                            ratePaise = current.ratePaise.takeIf { it > 0 },
                        )
                ) {
                    is ApiResult.Success ->
                        _state.update { it.copy(isSaving = false, created = true) }

                    is ApiResult.Failure ->
                        _state.update { it.copy(isSaving = false, error = result.error.message) }
                }
            }
        }

        companion object {
            const val ARG_CASE_ID = "caseId"
            private const val SECONDS_PER_MINUTE = 60L
        }
    }

@Composable
fun AddTimeEntryRoute(
    onTimeEntryAdded: () -> Unit,
    modifier: Modifier = Modifier,
    viewModel: AddTimeEntryViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    LaunchedEffect(state.created) {
        if (state.created) onTimeEntryAdded()
    }

    FormScaffold(
        title = stringResource(R.string.time_entry_add_title),
        submitLabel = stringResource(R.string.time_entry_add_submit),
        canSubmit = state.isValid,
        isSubmitting = state.isSaving,
        onSubmit = viewModel::save,
        modifier = modifier,
        error = state.error,
    ) {
        NyayaTextField(
            value = state.durationMinutes,
            onValueChange = viewModel::onDurationMinutesChanged,
            label = stringResource(R.string.time_entry_add_field_duration),
            keyboardType = KeyboardType.Number,
        )

        NyayaTextField(
            value = state.description,
            onValueChange = viewModel::onDescriptionChanged,
            label = stringResource(R.string.time_entry_add_field_description),
        )

        // The design system has no dedicated toggle component (see AddHearingScreen's
        // note on the same gap for time), so a raw M3 widget is the correct call here,
        // mirroring TasksScreen's inline Checkbox usage.
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Checkbox(checked = state.billable, onCheckedChange = viewModel::onBillableChanged)
            Text(
                text = stringResource(R.string.time_entry_add_field_billable),
                style = MaterialTheme.typography.bodyMedium,
            )
        }

        NyayaMoneyField(
            paise = state.ratePaise,
            onValueChange = viewModel::onRatePaiseChanged,
            label = stringResource(R.string.time_entry_add_field_rate),
            helper = stringResource(R.string.time_entry_add_field_rate_helper),
        )
    }
}
