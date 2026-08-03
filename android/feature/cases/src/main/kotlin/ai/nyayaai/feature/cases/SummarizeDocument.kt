package ai.nyayaai.feature.cases

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
import androidx.compose.animation.Crossfade
import androidx.compose.animation.animateContentSize
import androidx.compose.animation.core.tween
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
 * Duplicated from `feature:documents`' type of the same name — feature modules never
 * depend on each other, so Case Detail's Documents tab gets its own copy of the small
 * job+content pairing rather than a shared import.
 */
data class JobWithResult(
    val job: AiJob,
    val content: AiContent?,
)

/**
 * A second, independent wrapper around [AiService] for Case Detail's Documents tab.
 * feature:cases cannot depend on feature:documents any more than it can depend on
 * feature:ai, so this mirrors [ai.nyayaai.feature.documents.DocumentSummaryRepository]
 * exactly rather than sharing it — the same duplication [TimeEntryRepository] already
 * accepts for `BillingService`.
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

/** See `feature:documents`' `SummarizeState` for why this is a sealed interface. */
sealed interface SummarizeState {
    data object Idle : SummarizeState

    data object Submitting : SummarizeState

    data class Polling(val estimatedSeconds: Int?) : SummarizeState

    data class Done(val content: AiContent) : SummarizeState

    data class Failed(val message: String) : SummarizeState
}

/** Case Detail's copy of the summarize job lifecycle — see `feature:documents`' twin. */
@HiltViewModel
class SummarizeViewModel
    @Inject
    constructor(
        private val repository: DocumentSummaryRepository,
    ) : ViewModel() {
        private val _state = MutableStateFlow<SummarizeState>(SummarizeState.Idle)
        val state: StateFlow<SummarizeState> = _state.asStateFlow()

        private var started = false

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

            // Still running server-side, not a failure — matches AiViewModel's copy.
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

/** Case Detail's mirror of the vault's summarize dialog — same shape, same `AlertDialog` use. */
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
        title = { Text(stringResource(R.string.case_summarize_title)) },
        text = {
            Column(
                modifier =
                    Modifier
                        .heightIn(max = DIALOG_MAX_HEIGHT)
                        .verticalScroll(rememberScrollState())
                        // Smoothly resizes the dialog as content height changes (e.g. a
                        // spinner giving way to a multi-paragraph answer) instead of a jump-cut.
                        .animateContentSize(),
                verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.sm),
            ) {
                Crossfade(
                    targetState = state,
                    animationSpec = tween(CROSSFADE_MS),
                    label = "summarize-state",
                ) { current ->
                    when (current) {
                        is SummarizeState.Idle, is SummarizeState.Submitting ->
                            ProgressRow(
                                text = stringResource(R.string.case_summarize_submitting),
                            )

                        is SummarizeState.Polling ->
                            ProgressRow(
                                text =
                                    current.estimatedSeconds?.let {
                                        stringResource(R.string.case_summarize_progress_estimate, it)
                                    } ?: stringResource(R.string.case_summarize_progress),
                            )

                        is SummarizeState.Done -> {
                            Column(verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.sm)) {
                                AiDisclaimerBanner()

                                current.content.docTypeDetected?.let {
                                    Text(
                                        text = stringResource(R.string.case_summarize_doc_type, it),
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
                                            Row(
                                                horizontalArrangement =
                                                    Arrangement.spacedBy(NyayaTheme.spacing.xs),
                                            ) {
                                                Text(text = "•", style = MaterialTheme.typography.bodyMedium)
                                                Text(text = point, style = MaterialTheme.typography.bodyMedium)
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        is SummarizeState.Failed ->
                            Text(text = current.message, color = MaterialTheme.colorScheme.error)
                    }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss) { Text(stringResource(R.string.case_summarize_close)) }
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
private const val CROSSFADE_MS = 260
