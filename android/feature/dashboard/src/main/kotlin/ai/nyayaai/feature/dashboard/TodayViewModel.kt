package ai.nyayaai.feature.dashboard

import ai.nyayaai.core.common.UiState
import ai.nyayaai.core.model.Task
import ai.nyayaai.core.network.api.ApiCaller
import ai.nyayaai.core.network.api.ApiResult
import ai.nyayaai.core.network.api.isRetryable
import ai.nyayaai.core.network.api.map
import ai.nyayaai.core.network.mapper.TodayBoard
import ai.nyayaai.core.network.mapper.toDomain
import ai.nyayaai.core.network.service.CalendarService
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class TodayRepository
    @Inject
    constructor(
        private val service: CalendarService,
        private val caller: ApiCaller,
    ) {
        suspend fun today(): ApiResult<TodayBoard> = caller.call { service.today() }.map { it.toDomain() }

        suspend fun openTasks(): ApiResult<List<Task>> =
            caller.call { service.tasks(status = "open") }.map { list -> list.map { it.toDomain() } }
    }

data class TodayContent(
    val board: TodayBoard,
    val tasks: List<Task>,
)

/**
 * D.4's Today screen — the retention screen, and the one a lawyer opens in the corridor
 * outside a courtroom.
 *
 * The two calls run **concurrently**: a lawyer checking the day's list before walking in
 * should not wait for hearings and then tasks in sequence.
 */
@HiltViewModel
class TodayViewModel
    @Inject
    constructor(
        private val repository: TodayRepository,
    ) : ViewModel() {
        private val _state = MutableStateFlow<UiState<TodayContent>>(UiState.Loading)
        val state: StateFlow<UiState<TodayContent>> = _state.asStateFlow()

        init {
            load()
        }

        fun load(isRefresh: Boolean = false) {
            viewModelScope.launch {
                if (isRefresh) {
                    val current = _state.value
                    if (current is UiState.Content) {
                        _state.value = current.copy(isRefreshing = true)
                    }
                } else {
                    _state.value = UiState.Loading
                }

                val boardCall = async { repository.today() }
                val tasksCall = async { repository.openTasks() }
                val board = boardCall.await()
                val tasks = tasksCall.await()

                _state.value =
                    when (board) {
                        is ApiResult.Failure ->
                            UiState.Error(board.error.message, board.error.isRetryable)

                        is ApiResult.Success -> {
                            // A failed task list must not blank out the hearings — the
                            // hearings are the reason this screen exists.
                            val taskList = (tasks as? ApiResult.Success)?.data.orEmpty()
                            UiState.Content(TodayContent(board.data, taskList))
                        }
                    }
            }
        }
    }
