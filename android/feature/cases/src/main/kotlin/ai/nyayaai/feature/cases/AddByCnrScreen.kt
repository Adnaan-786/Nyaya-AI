package ai.nyayaai.feature.cases

import ai.nyayaai.core.common.formatLong
import ai.nyayaai.core.designsystem.component.NyayaCard
import ai.nyayaai.core.designsystem.theme.NyayaTheme
import ai.nyayaai.core.model.CaseId
import ai.nyayaai.core.network.api.ApiError
import ai.nyayaai.core.network.api.ApiResult
import ai.nyayaai.core.network.mapper.CnrPreview
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.style.TextAlign
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

private const val CNR_LENGTH = 16

data class AddByCnrUiState(
    val cnr: String = "",
    val isFetching: Boolean = false,
    val isSaving: Boolean = false,
    val preview: CnrPreview? = null,
    val error: String? = null,
    /**
     * D.5: when eCourts is unreachable the screen must offer manual entry rather than a
     * dead end. A lawyer standing in a corridor cannot wait for someone else's uptime.
     */
    val offerManualEntry: Boolean = false,
    val createdCaseId: CaseId? = null,
) {
    val isCnrComplete: Boolean get() = cnr.length == CNR_LENGTH
}

@HiltViewModel
class AddByCnrViewModel
    @Inject
    constructor(
        private val repository: CaseRepository,
    ) : ViewModel() {
        private val _state = MutableStateFlow(AddByCnrUiState())
        val state: StateFlow<AddByCnrUiState> = _state.asStateFlow()

        fun onCnrChanged(value: String) {
            _state.update {
                it.copy(
                    cnr = value.filter(Char::isLetterOrDigit).uppercase().take(CNR_LENGTH),
                    error = null,
                    preview = null,
                    offerManualEntry = false,
                )
            }
        }

        fun lookup() {
            val current = _state.value
            if (!current.isCnrComplete || current.isFetching) return

            _state.update { it.copy(isFetching = true, error = null, offerManualEntry = false) }
            viewModelScope.launch {
                when (val result = repository.lookupCnr(current.cnr)) {
                    is ApiResult.Success ->
                        _state.update { it.copy(isFetching = false, preview = result.data) }

                    is ApiResult.Failure ->
                        _state.update {
                            it.copy(
                                isFetching = false,
                                error = result.error.message,
                                // Only an upstream failure justifies the manual escape
                                // hatch. A malformed CNR should be corrected, not
                                // worked around.
                                offerManualEntry = result.error is ApiError.UpstreamUnavailable,
                            )
                        }
                }
            }
        }

        fun confirm() {
            val current = _state.value
            val preview = current.preview ?: return
            if (current.isSaving) return

            _state.update { it.copy(isSaving = true, error = null) }
            viewModelScope.launch {
                when (val result = repository.createFromCnr(preview.cnr, clientId = null)) {
                    is ApiResult.Success ->
                        _state.update { it.copy(isSaving = false, createdCaseId = result.data.id) }

                    is ApiResult.Failure ->
                        _state.update { it.copy(isSaving = false, error = result.error.message) }
                }
            }
        }
    }

@Composable
fun AddByCnrRoute(
    onCaseCreated: (CaseId) -> Unit,
    onManualEntry: () -> Unit,
    modifier: Modifier = Modifier,
    viewModel: AddByCnrViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    state.createdCaseId?.let { onCaseCreated(it) }

    Column(
        modifier = modifier.fillMaxWidth().padding(NyayaTheme.spacing.md),
        verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.md),
    ) {
        Text(
            text = stringResource(R.string.cnr_title),
            style = MaterialTheme.typography.headlineSmall,
        )

        OutlinedTextField(
            value = state.cnr,
            onValueChange = viewModel::onCnrChanged,
            label = { Text(stringResource(R.string.cnr_hint)) },
            supportingText = {
                Text(
                    if (state.cnr.isNotEmpty() && !state.isCnrComplete) {
                        stringResource(R.string.cnr_length_error)
                    } else {
                        stringResource(R.string.cnr_help)
                    },
                )
            },
            isError = state.cnr.isNotEmpty() && !state.isCnrComplete,
            singleLine = true,
            keyboardOptions =
                androidx.compose.foundation.text.KeyboardOptions(
                    capitalization = KeyboardCapitalization.Characters,
                ),
            modifier = Modifier.fillMaxWidth(),
        )

        if (state.isFetching) {
            Column(
                modifier = Modifier.fillMaxWidth(),
                horizontalAlignment = androidx.compose.ui.Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.sm),
            ) {
                CircularProgressIndicator()
                Text(
                    text = stringResource(R.string.cnr_fetching),
                    style = MaterialTheme.typography.bodyMedium,
                    textAlign = TextAlign.Center,
                )
            }
        } else {
            Button(
                onClick = viewModel::lookup,
                enabled = state.isCnrComplete,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(stringResource(R.string.cnr_fetch))
            }
        }

        state.error?.let { message ->
            Text(
                text = message,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.error,
            )
            if (state.offerManualEntry) {
                TextButton(onClick = onManualEntry) {
                    Text(stringResource(R.string.cnr_manual_instead))
                }
            }
        }

        state.preview?.let { preview ->
            PreviewCard(preview)
            Button(
                onClick = viewModel::confirm,
                enabled = !state.isSaving,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(stringResource(R.string.cnr_confirm))
            }
        }
    }
}

@Composable
private fun PreviewCard(
    preview: CnrPreview,
    modifier: Modifier = Modifier,
) {
    NyayaCard(modifier = modifier) {
        Column(verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.xs)) {
            Text(text = preview.title, style = MaterialTheme.typography.titleSmall)

            listOfNotNull(preview.caseNumber, preview.courtName, preview.judgeName)
                .forEach {
                    Text(
                        text = it,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }

            preview.nextHearingDate?.let {
                Text(
                    text = "${stringResource(R.string.case_next_hearing)}: ${it.formatLong()}",
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
        }
    }
}
