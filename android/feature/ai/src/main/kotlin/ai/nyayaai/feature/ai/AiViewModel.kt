package ai.nyayaai.feature.ai

import ai.nyayaai.core.model.AiJob
import ai.nyayaai.core.model.AiJobId
import ai.nyayaai.core.model.AiJobStatus
import ai.nyayaai.core.network.api.ApiCaller
import ai.nyayaai.core.network.api.ApiResult
import ai.nyayaai.core.network.api.map
import ai.nyayaai.core.network.dto.ResearchRequestDto
import ai.nyayaai.core.network.dto.SummarizeRequestDto
import ai.nyayaai.core.network.mapper.AiContent
import ai.nyayaai.core.network.mapper.toContent
import ai.nyayaai.core.network.mapper.toDomain
import ai.nyayaai.core.network.service.AiService
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject
import javax.inject.Singleton

data class JobWithResult(
    val job: AiJob,
    val content: AiContent?,
)

@Singleton
class AiRepository
    @Inject
    constructor(
        private val service: AiService,
        private val caller: ApiCaller,
    ) {
        suspend fun research(
            query: String,
            language: String,
        ): ApiResult<AiJob> =
            caller.call { service.research(ResearchRequestDto(query, language)) }.map { it.toDomain() }

        suspend fun summarize(documentId: String): ApiResult<AiJob> =
            caller.call { service.summarize(SummarizeRequestDto(documentId)) }.map { it.toDomain() }

        suspend fun job(id: AiJobId): ApiResult<JobWithResult> =
            caller.call { service.job(id.value) }.map { dto ->
                JobWithResult(dto.toDomain(), dto.result?.toContent())
            }

        suspend fun recentJobs(): ApiResult<List<AiJob>> =
            caller.call { service.jobs() }.map { list -> list.map { it.toDomain() } }
    }

data class AiUiState(
    val query: String = "",
    val isSubmitting: Boolean = false,
    /** Drives the "about 30 seconds" copy on the progress card (B.7). */
    val estimatedSeconds: Int? = null,
    val activeJob: AiJob? = null,
    val content: AiContent? = null,
    val recent: List<AiJob> = emptyList(),
    val error: String? = null,
    /** Set on 402; the screen routes to the paywall with this plan preselected (B.14). */
    val upgradeTo: String? = null,
)

/**
 * B.7's async job pattern: submit, get a job id back immediately, then poll.
 *
 * Polling is the fallback path — the primary completion signal is the `ai_job_complete`
 * push. It exists because a lawyer who backgrounds the app mid-job and returns must still
 * see the result, and because push delivery on Indian budget devices is not guaranteed.
 */
@HiltViewModel
class AiViewModel
    @Inject
    constructor(
        private val repository: AiRepository,
    ) : ViewModel() {
        private val _state = MutableStateFlow(AiUiState())
        val state: StateFlow<AiUiState> = _state.asStateFlow()

        init {
            loadRecent()
        }

        fun onQueryChanged(value: String) {
            _state.update { it.copy(query = value, error = null) }
        }

        fun ask(language: String = "en") {
            val current = _state.value
            if (current.query.isBlank() || current.isSubmitting) return

            _state.update { it.copy(isSubmitting = true, error = null, content = null, upgradeTo = null) }

            viewModelScope.launch {
                when (val submitted = repository.research(current.query, language)) {
                    is ApiResult.Failure -> {
                        val error = submitted.error
                        _state.update {
                            it.copy(
                                isSubmitting = false,
                                error = error.message,
                                upgradeTo =
                                    (error as? ai.nyayaai.core.network.api.ApiError.QuotaExceeded)?.upgradeTo,
                            )
                        }
                    }

                    is ApiResult.Success -> {
                        _state.update {
                            it.copy(
                                activeJob = submitted.data,
                                estimatedSeconds = submitted.data.estimatedSeconds,
                            )
                        }
                        poll(submitted.data.id)
                    }
                }
            }
        }

        private suspend fun poll(id: AiJobId) {
            repeat(MAX_POLLS) {
                delay(POLL_INTERVAL_MS)

                when (val result = repository.job(id)) {
                    is ApiResult.Failure -> {
                        _state.update { it.copy(isSubmitting = false, error = result.error.message) }
                        return
                    }

                    is ApiResult.Success -> {
                        val (job, content) = result.data
                        if (job.status.isTerminal) {
                            _state.update {
                                it.copy(
                                    isSubmitting = false,
                                    activeJob = job,
                                    content = content,
                                    error = job.error.takeIf { _ -> job.status == AiJobStatus.FAILED },
                                )
                            }
                            loadRecent()
                            return
                        }
                        _state.update { it.copy(activeJob = job) }
                    }
                }
            }

            // Giving up quietly would leave a spinner forever. The job is still running
            // server-side and will appear under recent results, so say exactly that.
            _state.update { it.copy(isSubmitting = false, error = TIMEOUT_MESSAGE) }
        }

        fun loadRecent() {
            viewModelScope.launch {
                (repository.recentJobs() as? ApiResult.Success)?.let { result ->
                    _state.update { it.copy(recent = result.data) }
                }
            }
        }

        private companion object {
            const val POLL_INTERVAL_MS = 3_000L
            const val MAX_POLLS = 100
            const val TIMEOUT_MESSAGE =
                "This is taking longer than usual. It will appear under recent results when it finishes."
        }
    }
