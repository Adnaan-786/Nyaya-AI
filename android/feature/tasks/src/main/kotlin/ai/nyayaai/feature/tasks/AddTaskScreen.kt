package ai.nyayaai.feature.tasks

import ai.nyayaai.core.designsystem.component.FormScaffold
import ai.nyayaai.core.designsystem.component.NyayaDateField
import ai.nyayaai.core.designsystem.component.NyayaTextField
import ai.nyayaai.core.model.CourtDate
import ai.nyayaai.core.network.api.ApiResult
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
 * A standalone task, not tied to a case. Case-scoped "add task from case detail" is a
 * separate, future screen — keeping the case picker out of this one keeps the common path
 * (a quick reminder to self) to two fields.
 */
data class AddTaskUiState(
    val title: String = "",
    val dueDate: CourtDate? = null,
    val isSaving: Boolean = false,
    val error: String? = null,
    val created: Boolean = false,
) {
    val isValid: Boolean get() = title.isNotBlank()
}

@HiltViewModel
class AddTaskViewModel
    @Inject
    constructor(
        private val repository: TaskRepository,
    ) : ViewModel() {
        private val _state = MutableStateFlow(AddTaskUiState())
        val state: StateFlow<AddTaskUiState> = _state.asStateFlow()

        fun onTitleChanged(value: String) {
            _state.update { it.copy(title = value, error = null) }
        }

        fun onDueDateChanged(value: CourtDate) {
            _state.update { it.copy(dueDate = value) }
        }

        fun save() {
            val current = _state.value
            if (!current.isValid || current.isSaving) return

            _state.update { it.copy(isSaving = true, error = null) }
            viewModelScope.launch {
                when (val result = repository.create(title = current.title, dueDate = current.dueDate)) {
                    is ApiResult.Success -> _state.update { it.copy(isSaving = false, created = true) }
                    is ApiResult.Failure ->
                        _state.update { it.copy(isSaving = false, error = result.error.message) }
                }
            }
        }
    }

@Composable
fun AddTaskRoute(
    onTaskCreated: () -> Unit,
    modifier: Modifier = Modifier,
    viewModel: AddTaskViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    // Fired from an effect, not the composable body: calling onTaskCreated() directly while
    // composing runs it once per recomposition of a still-true state, not once per creation.
    LaunchedEffect(state.created) {
        if (state.created) onTaskCreated()
    }

    FormScaffold(
        title = stringResource(R.string.tasks_add_title),
        submitLabel = stringResource(R.string.tasks_add_save),
        canSubmit = state.isValid,
        isSubmitting = state.isSaving,
        onSubmit = viewModel::save,
        modifier = modifier,
        error = state.error,
    ) {
        NyayaTextField(
            value = state.title,
            onValueChange = viewModel::onTitleChanged,
            label = stringResource(R.string.tasks_add_title_label),
        )

        NyayaDateField(
            value = state.dueDate,
            onValueChange = viewModel::onDueDateChanged,
            label = stringResource(R.string.tasks_add_due_date_label),
        )
    }
}
