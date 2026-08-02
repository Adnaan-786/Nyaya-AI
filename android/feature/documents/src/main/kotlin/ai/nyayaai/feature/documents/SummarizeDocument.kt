package ai.nyayaai.feature.documents

import ai.nyayaai.core.designsystem.component.AiDisclaimerBanner
import ai.nyayaai.core.designsystem.theme.NyayaTheme
import ai.nyayaai.core.model.AiJob
import ai.nyayaai.core.model.AiJobId
import ai.nyayaai.core.model.AiJobStatus
import ai.nyayaai.core.model.DocumentId
import ai.nyayaai.core.network.api.ApiCaller
import ai.nyayaai.core.network.api.ApiResult
import ai.nyayaai.core.network.api.map
import ai.nyayaai.core.network.dto.SummarizeRequestDto
import ai.nyayaai.core.network.mapper.AiContent
import ai.nyayaai.core.network.mapper.toContent
import ai.nyayaai.core.network.mapper.toDomain
import ai.nyayaai.core.network.service.AiService
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject
import javax.inject.Singleton

/**
 * The result half of an [AiJob] fetch, kept alongside the job because the caller usually
 * wants both: the status to decide whether to keep polling, and the content once it lands.
 * Deliberately not the [ai.nyayaai.feature.ai] type of the same name — feature:documents
 * cannot depend on feature:ai (feature modules never depend on each other), so this is a
 * small, intentional duplicate of that shape, not a shared import.
 */
data class JobWithResult(
    val job: AiJob,
    val content: AiContent?,
)

/**
 * Wraps [AiService] directly — feature:documents cannot depend on feature:ai. Mirrors
 * [ai.nyayaai.feature.cases.TimeEntryRepository]'s relationship to `BillingService`: a
 * different feature's Retrofit service, injected straight from core:network instead of
 * routed through a cross-feature dependency that the build does not allow.
 */
@Singleton
class DocumentSummaryRepository
    @Inject
    constructor(
        private val service: AiService,
        private val caller: ApiCaller,
    ) {
        suspend fun summarize(documentId: DocumentId): ApiResult<AiJob> =
            caller.call { service.summarize(SummarizeRequestDto(documentId.value)) }.map { it.toDomain() }

        suspend fun job(id: AiJobId): ApiResult<JobWithResult> =
            caller.call { service.job(id.value) }.map { dto ->
                JobWithResult(dto.toDomain(), dto.result?.toContent())
            }
    }

/**
 * A job's lifecycle is a small, fixed set of mutually exclusive states, each carrying
 * different data (an estimate while polling, content when done, a message on failure) —
 * that shape is what `core:common`'s [ai.nyayaai.core.common.UiState] already uses a
 * sealed interface for, so this follows the same choice rather than a single flat data
 * class with a pile of nullable fields.
 */
sealed interface SummarizeState {
    data object Idle : SummarizeState

    data object Submitting : SummarizeState

    data class Polling(val estimatedSeconds: Int?) : SummarizeState

    data class Done(val content: AiContent) : SummarizeState

    /**
     * Covers both a real failure and the "still running after MAX_POLLS" timeout — the
     * message text is what tells them apart, exactly as [ai.nyayaai.feature.ai.AiViewModel]
     * does with its own `error` field.
     */
    data class Failed(val message: String) : SummarizeState
}

/**
 * A `@HiltViewModel` (not a bare `remember`-scoped holder) because summarization outlives a
 * single composition: the polling coroutine must survive the dialog's host recomposing
 * (e.g. on a configuration change) the same way [ai.nyayaai.feature.ai.AiViewModel] does for
 * the research flow. It is scoped per document id (see `hiltViewModel(key = ...)` at the
 * call site) so summarizing a second document does not resume the first one's state.
 */
@HiltViewModel
class SummarizeViewModel
    @Inject
    constructor(
        private val repository: DocumentSummaryRepository,
    ) : ViewModel() {
        private val _state = MutableStateFlow<SummarizeState>(SummarizeState.Idle)
        val state: StateFlow<SummarizeState> = _state.asStateFlow()

        private var started = false

        /** Idempotent: recomposition of the hosting dialog must not resubmit the job. */
        fun start(documentId: DocumentId) {
            if (started) return
            started = true

            _state.value = SummarizeState.Submitting
            viewModelScope.launch {
                when (val submitted = repository.summarize(documentId)) {
                    is ApiResult.Failure -> _state.value = SummarizeState.Failed(submitted.error.message)

                    is ApiResult.Success -> {
                        _state.value = SummarizeState.Polling(submitted.data.estimatedSeconds)
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
                        _state.value = SummarizeState.Failed(result.error.message)
                        return
                    }

                    is ApiResult.Success -> {
                        val (job, content) = result.data
                        if (job.status.isTerminal) {
                            _state.value =
                                when {
                                    job.status == AiJobStatus.FAILED ->
                                        SummarizeState.Failed(job.error ?: GENERIC_ERROR)
                                    content != null -> SummarizeState.Done(content)
                                    else -> SummarizeState.Failed(GENERIC_ERROR)
                                }
                            return
                        }
                        _state.value = SummarizeState.Polling(job.estimatedSeconds)
                    }
                }
            }

            // Giving up quietly would leave a spinner forever. The job is still running
            // server-side, so this is not an error — say exactly that, matching
            // AiViewModel's copy for the identical situation.
            _state.value = SummarizeState.Failed(TIMEOUT_MESSAGE)
        }

        private companion object {
            const val POLL_INTERVAL_MS = 1_500L
            const val MAX_POLLS = 40
            const val TIMEOUT_MESSAGE =
                "This is taking longer than usual. It will appear under recent results when it finishes."
            const val GENERIC_ERROR = "Summarization failed. Please try again."
        }
    }

/**
 * D.7's per-document summarize action. Modal rather than a new screen — this app has no
 * bottom-sheet component, and [AlertDialog] is the one established way here to show a
 * transient result over the vault (see `SettingsScreen`'s logout confirmation).
 */
@Composable
fun SummarizeDialog(
    documentId: DocumentId,
    onDismiss: () -> Unit,
    modifier: Modifier = Modifier,
    viewModel: SummarizeViewModel = hiltViewModel(key = "summarize-${documentId.value}"),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    LaunchedEffect(documentId) { viewModel.start(documentId) }

    AlertDialog(
        onDismissRequest = onDismiss,
        modifier = modifier,
        title = { Text(stringResource(R.string.vault_summarize_title)) },
        text = {
            Column(
                modifier =
                    Modifier
                        .heightIn(max = DIALOG_MAX_HEIGHT)
                        .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.sm),
            ) {
                when (val current = state) {
                    is SummarizeState.Idle, is SummarizeState.Submitting -> ProgressRow(
                        text = stringResource(R.string.vault_summarize_submitting),
                    )

                    is SummarizeState.Polling ->
                        ProgressRow(
                            text =
                                current.estimatedSeconds?.let {
                                    stringResource(R.string.vault_summarize_progress_estimate, it)
                                } ?: stringResource(R.string.vault_summarize_progress),
                        )

                    is SummarizeState.Done -> {
                        // B.11, mandatory on every AI surface — this dialog renders an
                        // AI-generated result, so it is not optional here either.
                        AiDisclaimerBanner()

                        current.content.docTypeDetected?.let {
                            Text(
                                text = stringResource(R.string.vault_summarize_doc_type, it),
                                style = MaterialTheme.typography.labelLarge,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }

                        current.content.summaryMarkdown?.let {
                            Text(text = it, style = MaterialTheme.typography.bodyMedium)
                        }

                        if (current.content.keyPoints.isNotEmpty()) {
                            Column(verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.xs)) {
                                current.content.keyPoints.forEach { point ->
                                    Row(horizontalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.xs)) {
                                        Text(text = "•", style = MaterialTheme.typography.bodyMedium)
                                        Text(text = point, style = MaterialTheme.typography.bodyMedium)
                                    }
                                }
                            }
                        }
                    }

                    is SummarizeState.Failed ->
                        Text(text = current.message, color = MaterialTheme.colorScheme.error)
                }
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss) { Text(stringResource(R.string.vault_summarize_close)) }
        },
    )
}

@Composable
private fun ProgressRow(text: String) {
    Row(
        horizontalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.sm),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        CircularProgressIndicator(modifier = Modifier.size(PROGRESS_SPINNER))
        Text(text = text, style = MaterialTheme.typography.bodyMedium)
    }
}

private val PROGRESS_SPINNER = 20.dp
private val DIALOG_MAX_HEIGHT = 400.dp
