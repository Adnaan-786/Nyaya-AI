package ai.nyayaai.feature.cases

import ai.nyayaai.core.designsystem.component.FormScaffold
import ai.nyayaai.core.designsystem.component.NyayaDateField
import ai.nyayaai.core.designsystem.component.NyayaTextField
import ai.nyayaai.core.model.CaseId
import ai.nyayaai.core.model.CourtDate
import ai.nyayaai.core.network.api.ApiResult
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

/**
 * D.6: the manual escape hatch for when eCourts has nothing (a filed-but-not-yet-numbered
 * case, an upstream outage) or the lawyer just wants to skip the CNR lookup. [title] is the
 * only field the server requires (`min_length=1`); everything else travels as `null` rather
 * than an empty string when left blank, same convention as [CaseRepository.createCase].
 */
data class AddCaseUiState(
    val title: String = "",
    val clientId: ai.nyayaai.core.model.ClientId? = null,
    val clientName: String? = null,
    val showClientPicker: Boolean = false,
    val caseNumber: String = "",
    val courtName: String = "",
    val courtType: String = "",
    val judgeName: String = "",
    val caseType: String = "",
    val stage: String = "",
    val nextHearingDate: CourtDate? = null,
    val isSaving: Boolean = false,
    val error: String? = null,
    val createdCaseId: CaseId? = null,
) {
    val isValid: Boolean get() = title.isNotBlank() && clientId != null
}

@HiltViewModel
class AddCaseViewModel
    @Inject
    constructor(
        private val repository: CaseRepository,
    ) : ViewModel() {
        private val _state = MutableStateFlow(AddCaseUiState())
        val state: StateFlow<AddCaseUiState> = _state.asStateFlow()

        fun onTitleChanged(value: String) {
            _state.update { it.copy(title = value, error = null) }
        }

        fun onClientSelected(client: ai.nyayaai.core.model.Client) {
            _state.update { it.copy(clientId = client.id, clientName = client.name, showClientPicker = false, error = null) }
        }

        fun setClientPickerVisible(visible: Boolean) {
            _state.update { it.copy(showClientPicker = visible) }
        }

        fun onCaseNumberChanged(value: String) {
            _state.update { it.copy(caseNumber = value, error = null) }
        }

        fun onCourtNameChanged(value: String) {
            _state.update { it.copy(courtName = value, error = null) }
        }

        fun onCourtTypeChanged(value: String) {
            _state.update { it.copy(courtType = value, error = null) }
        }

        fun onJudgeNameChanged(value: String) {
            _state.update { it.copy(judgeName = value, error = null) }
        }

        fun onCaseTypeChanged(value: String) {
            _state.update { it.copy(caseType = value, error = null) }
        }

        fun onStageChanged(value: String) {
            _state.update { it.copy(stage = value, error = null) }
        }

        fun onNextHearingDateChanged(value: CourtDate) {
            _state.update { it.copy(nextHearingDate = value, error = null) }
        }

        fun save() {
            val current = _state.value
            if (!current.isValid || current.isSaving) return

            _state.update { it.copy(isSaving = true, error = null) }
            viewModelScope.launch {
                when (
                    val result =
                        repository.createCase(
                            title = current.title,
                            clientId = current.clientId!!,
                            caseNumber = current.caseNumber,
                            courtName = current.courtName,
                            courtType = current.courtType,
                            judgeName = current.judgeName,
                            caseType = current.caseType,
                            stage = current.stage,
                            nextHearingDate = current.nextHearingDate,
                        )
                ) {
                    is ApiResult.Success ->
                        _state.update { it.copy(isSaving = false, createdCaseId = result.data.id) }

                    is ApiResult.Failure ->
                        _state.update { it.copy(isSaving = false, error = result.error.message) }
                }
            }
        }
    }

@Composable
fun AddCaseRoute(
    onCaseCreated: (CaseId) -> Unit,
    modifier: Modifier = Modifier,
    viewModel: AddCaseViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    LaunchedEffect(state.createdCaseId) {
        state.createdCaseId?.let(onCaseCreated)
    }

    FormScaffold(
        title = stringResource(R.string.case_add_manual_title),
        submitLabel = stringResource(R.string.case_add_manual_submit),
        canSubmit = state.isValid,
        isSubmitting = state.isSaving,
        onSubmit = viewModel::save,
        modifier = modifier,
        error = state.error,
    ) {
        Box(modifier = Modifier.fillMaxWidth().clickable { viewModel.setClientPickerVisible(true) }) {
            OutlinedTextField(
                value = state.clientName ?: "",
                onValueChange = {},
                readOnly = true,
                enabled = false,
                label = { Text(stringResource(ai.nyayaai.feature.clients.R.string.clients_title)) },
                modifier = Modifier.fillMaxWidth(),
                placeholder = { Text(stringResource(ai.nyayaai.feature.clients.R.string.clients_search_hint)) },
                colors = androidx.compose.material3.OutlinedTextFieldDefaults.colors(
                    disabledTextColor = androidx.compose.material3.MaterialTheme.colorScheme.onSurface,
                    disabledBorderColor = androidx.compose.material3.MaterialTheme.colorScheme.outline,
                    disabledLabelColor = androidx.compose.material3.MaterialTheme.colorScheme.onSurfaceVariant,
                )
            )
        }

        if (state.showClientPicker) {
            ai.nyayaai.feature.clients.ClientPickerBottomSheet(
                onClientSelected = viewModel::onClientSelected,
                onDismissRequest = { viewModel.setClientPickerVisible(false) },
            )
        }

        NyayaTextField(
            value = state.title,
            onValueChange = viewModel::onTitleChanged,
            label = stringResource(R.string.case_add_manual_field_title),
        )

        NyayaTextField(
            value = state.caseNumber,
            onValueChange = viewModel::onCaseNumberChanged,
            label = stringResource(R.string.case_number),
        )

        NyayaTextField(
            value = state.courtName,
            onValueChange = viewModel::onCourtNameChanged,
            label = stringResource(R.string.case_court),
        )

        NyayaTextField(
            value = state.courtType,
            onValueChange = viewModel::onCourtTypeChanged,
            label = stringResource(R.string.case_add_manual_field_court_type),
        )

        NyayaTextField(
            value = state.judgeName,
            onValueChange = viewModel::onJudgeNameChanged,
            label = stringResource(R.string.case_judge),
        )

        NyayaTextField(
            value = state.caseType,
            onValueChange = viewModel::onCaseTypeChanged,
            label = stringResource(R.string.case_type),
        )

        NyayaTextField(
            value = state.stage,
            onValueChange = viewModel::onStageChanged,
            label = stringResource(R.string.case_stage),
        )

        NyayaDateField(
            value = state.nextHearingDate,
            onValueChange = viewModel::onNextHearingDateChanged,
            label = stringResource(R.string.case_next_hearing),
        )
    }
}
