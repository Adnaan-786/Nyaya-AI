package ai.nyayaai.feature.tasks

import ai.nyayaai.core.common.UiState
import ai.nyayaai.core.common.formatShort
import ai.nyayaai.core.common.isPast
import ai.nyayaai.core.designsystem.component.EmptyState
import ai.nyayaai.core.designsystem.component.ErrorState
import ai.nyayaai.core.designsystem.component.LoadingList
import ai.nyayaai.core.designsystem.component.StatusBadge
import ai.nyayaai.core.designsystem.component.StatusTone
import ai.nyayaai.core.designsystem.theme.NyayaTheme
import ai.nyayaai.core.model.Task
import ai.nyayaai.core.model.TaskId
import ai.nyayaai.core.model.TaskStatus
import ai.nyayaai.core.network.api.ApiCaller
import ai.nyayaai.core.network.api.ApiResult
import ai.nyayaai.core.network.api.isRetryable
import ai.nyayaai.core.network.api.map
import ai.nyayaai.core.network.dto.TaskCreateDto
import ai.nyayaai.core.network.mapper.toDomain
import ai.nyayaai.core.network.service.CalendarService
import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextDecoration
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class TaskRepository
    @Inject
    constructor(
        private val service: CalendarService,
        private val caller: ApiCaller,
    ) {
        suspend fun tasks(status: String? = null): ApiResult<List<Task>> =
            caller.call { service.tasks(status) }.map { list -> list.map { it.toDomain() } }

        suspend fun create(title: String): ApiResult<Task> =
            caller.call { service.createTask(TaskCreateDto(title = title)) }.map { it.toDomain() }

        suspend fun setStatus(
            id: TaskId,
            status: TaskStatus,
        ): ApiResult<Task> =
            caller
                .call { service.updateTask(id.value, mapOf("status" to status.name.lowercase())) }
                .map { it.toDomain() }
    }

@HiltViewModel
class TasksViewModel
    @Inject
    constructor(
        private val repository: TaskRepository,
    ) : ViewModel() {
        private val _state = MutableStateFlow<UiState<List<Task>>>(UiState.Loading)
        val state: StateFlow<UiState<List<Task>>> = _state.asStateFlow()

        init {
            load()
        }

        fun load() {
            viewModelScope.launch {
                _state.value = UiState.Loading
                _state.value =
                    when (val result = repository.tasks()) {
                        is ApiResult.Failure -> UiState.Error(result.error.message, result.error.isRetryable)
                        is ApiResult.Success -> UiState.Content(result.data)
                    }
            }
        }

        /**
         * Ticking a task updates the list optimistically, then reconciles.
         *
         * A checkbox that waits for a round trip before moving feels broken on a patchy
         * connection; if the call fails the reload puts the true state back.
         */
        fun toggle(task: Task) {
            val current = (_state.value as? UiState.Content)?.data ?: return
            val next = if (task.status == TaskStatus.DONE) TaskStatus.OPEN else TaskStatus.DONE

            _state.value =
                UiState.Content(
                    current.map { if (it.id == task.id) it.copy(status = next) else it },
                )

            viewModelScope.launch {
                if (repository.setStatus(task.id, next) is ApiResult.Failure) load()
            }
        }
    }

@Composable
fun TasksRoute(
    modifier: Modifier = Modifier,
    viewModel: TasksViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    when (state) {
        is UiState.Loading -> LoadingList(modifier = modifier)

        is UiState.Error -> {
            val error = state as UiState.Error
            ErrorState(
                message = error.message,
                onRetry = viewModel::load.takeIf { error.retryable },
                modifier = modifier,
            )
        }

        is UiState.Empty -> EmptyState(title = (state as UiState.Empty).title, modifier = modifier)

        is UiState.Content -> {
            val tasks = (state as UiState.Content<List<Task>>).data
            if (tasks.isEmpty()) {
                EmptyState(
                    title = stringResource(R.string.tasks_empty),
                    description = stringResource(R.string.tasks_empty_detail),
                    modifier = modifier,
                )
            } else {
                LazyColumn(
                    modifier = modifier.fillMaxSize(),
                    contentPadding = PaddingValues(NyayaTheme.spacing.md),
                    verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.sm),
                ) {
                    items(tasks, key = { it.id.value }) { task ->
                        TaskCard(task, onToggle = { viewModel.toggle(task) })
                    }
                }
            }
        }
    }
}

@Composable
private fun TaskCard(
    task: Task,
    onToggle: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val done = task.status == TaskStatus.DONE
    val overdue = !done && task.dueDate?.isPast() == true

    Card(modifier = modifier.fillMaxWidth().animateContentSize()) {
        Row(
            modifier = Modifier.padding(end = NyayaTheme.spacing.md),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Checkbox(checked = done, onCheckedChange = { onToggle() })

            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = task.title,
                    style = MaterialTheme.typography.bodyLarge,
                    textDecoration = if (done) TextDecoration.LineThrough else null,
                    color =
                        if (done) {
                            MaterialTheme.colorScheme.onSurfaceVariant
                        } else {
                            MaterialTheme.colorScheme.onSurface
                        },
                )
                task.dueDate?.let {
                    Text(
                        text = stringResource(R.string.tasks_due, it.formatShort()),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }

            if (overdue) {
                StatusBadge(
                    text = stringResource(R.string.tasks_overdue),
                    tone = StatusTone.NEGATIVE,
                )
            }
        }
    }
}
