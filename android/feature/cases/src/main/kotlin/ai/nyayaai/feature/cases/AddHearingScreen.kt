package ai.nyayaai.feature.cases

import ai.nyayaai.core.designsystem.component.FormScaffold
import ai.nyayaai.core.designsystem.component.NyayaDateField
import ai.nyayaai.core.designsystem.component.NyayaTextField
import ai.nyayaai.core.model.CaseId
import ai.nyayaai.core.model.CourtDate
import ai.nyayaai.core.model.CourtTime
import ai.nyayaai.core.network.api.ApiResult
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardCapitalization
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
import kotlinx.datetime.LocalTime
import javax.inject.Inject

/**
 * Reached from the FAB on [CaseDetailScreen]'s Hearings tab. [date] is the only field the
 * server requires; [time] is kept as free text (`HH:mm`) rather than a dedicated time picker
 * because the design system does not ship one yet — see [Form.kt].
 */
data class AddHearingUiState(
    val date: CourtDate? = null,
    val time: String = "",
    val purpose: String = "",
    val courtroom: String = "",
    val isSaving: Boolean = false,
    val error: String? = null,
    val created: Boolean = false,
) {
    val isValid: Boolean get() = date != null
}

@HiltViewModel
class AddHearingViewModel
    @Inject
    constructor(
        savedStateHandle: SavedStateHandle,
        private val repository: CaseRepository,
    ) : ViewModel() {
        private val caseId = CaseId(checkNotNull(savedStateHandle.get<String>(ARG_CASE_ID)))

        private val _state = MutableStateFlow(AddHearingUiState())
        val state: StateFlow<AddHearingUiState> = _state.asStateFlow()

        fun onDateChanged(value: CourtDate) {
            _state.update { it.copy(date = value, error = null) }
        }

        fun onTimeChanged(value: String) {
            _state.update { it.copy(time = value, error = null) }
        }

        fun onPurposeChanged(value: String) {
            _state.update { it.copy(purpose = value, error = null) }
        }

        fun onCourtroomChanged(value: String) {
            _state.update { it.copy(courtroom = value, error = null) }
        }

        fun save() {
            val current = _state.value
            val date = current.date
            if (!current.isValid || current.isSaving || date == null) return

            // A malformed HH:mm should be dropped rather than sent as garbage to the server.
            val time = current.time.takeIf { it.isNotBlank() }?.let { raw ->
                runCatching { CourtTime(LocalTime.parse(raw)) }.getOrNull()
            }

            _state.update { it.copy(isSaving = true, error = null) }
            viewModelScope.launch {
                when (
                    val result =
                        repository.addHearing(
                            caseId = caseId,
                            date = date,
                            time = time,
                            purpose = current.purpose,
                            courtroom = current.courtroom,
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
        }
    }

@Composable
fun AddHearingRoute(
    onHearingAdded: () -> Unit,
    modifier: Modifier = Modifier,
    viewModel: AddHearingViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    LaunchedEffect(state.created) {
        if (state.created) onHearingAdded()
    }

    FormScaffold(
        title = stringResource(R.string.hearing_add_title),
        submitLabel = stringResource(R.string.hearing_add_submit),
        canSubmit = state.isValid,
        isSubmitting = state.isSaving,
        onSubmit = viewModel::save,
        modifier = modifier,
        error = state.error,
    ) {
        NyayaDateField(
            value = state.date,
            onValueChange = viewModel::onDateChanged,
            label = stringResource(R.string.hearing_add_field_date),
        )

        NyayaTextField(
            value = state.time,
            onValueChange = viewModel::onTimeChanged,
            label = stringResource(R.string.hearing_add_field_time),
            helper = stringResource(R.string.hearing_add_field_time_helper),
            keyboardType = KeyboardType.Text,
            capitalization = KeyboardCapitalization.None,
        )

        NyayaTextField(
            value = state.purpose,
            onValueChange = viewModel::onPurposeChanged,
            label = stringResource(R.string.hearing_add_field_purpose),
        )

        NyayaTextField(
            value = state.courtroom,
            onValueChange = viewModel::onCourtroomChanged,
            label = stringResource(R.string.hearing_add_field_courtroom),
        )
    }
}
