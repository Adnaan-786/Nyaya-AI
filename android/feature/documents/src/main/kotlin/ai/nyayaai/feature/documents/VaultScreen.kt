package ai.nyayaai.feature.documents

import ai.nyayaai.core.common.UiState
import ai.nyayaai.core.common.todayInIndia
import ai.nyayaai.core.designsystem.component.EmptyState
import ai.nyayaai.core.designsystem.component.ErrorState
import ai.nyayaai.core.designsystem.component.LoadingList
import ai.nyayaai.core.designsystem.component.NyayaCard
import ai.nyayaai.core.designsystem.component.StatusBadge
import ai.nyayaai.core.designsystem.component.StatusTone
import ai.nyayaai.core.designsystem.component.animatedListEntry
import ai.nyayaai.core.designsystem.theme.NyayaTheme
import ai.nyayaai.core.model.Document
import ai.nyayaai.core.model.DocumentId
import ai.nyayaai.core.model.OcrStatus
import ai.nyayaai.core.network.api.ApiCaller
import ai.nyayaai.core.network.api.ApiResult
import ai.nyayaai.core.network.api.isRetryable
import ai.nyayaai.core.network.api.map
import ai.nyayaai.core.network.mapper.toDomain
import ai.nyayaai.core.network.service.DocumentService
import android.net.Uri
import android.widget.Toast
import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Article
import androidx.compose.material.icons.filled.DocumentScanner
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.zIndex
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import androidx.work.WorkInfo
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class DocumentRepository
    @Inject
    constructor(
        private val service: DocumentService,
        private val caller: ApiCaller,
    ) {
        suspend fun documents(folder: String? = null): ApiResult<List<Document>> =
            caller.call { service.documents(folder = folder) }.map { list -> list.map { it.toDomain() } }
    }

private val ACTIVE_WORK_STATES = setOf(WorkInfo.State.ENQUEUED, WorkInfo.State.RUNNING, WorkInfo.State.BLOCKED)

@HiltViewModel
class VaultViewModel
    @Inject
    constructor(
        private val repository: DocumentRepository,
        private val uploadQueue: ScanUploadQueue,
    ) : ViewModel() {
        private val _state = MutableStateFlow<UiState<List<Document>>>(UiState.Loading)
        val state: StateFlow<UiState<List<Document>>> = _state.asStateFlow()

        // D.7's WorkManager queue survives this ViewModel, so "is anything uploading"
        // is read straight off WorkManager rather than tracked locally — it is correct
        // even for an upload that was queued before the app was last killed.
        val uploading: StateFlow<Boolean> =
            uploadQueue
                .uploads()
                .map { infos -> infos.any { it.state in ACTIVE_WORK_STATES } }
                .stateIn(viewModelScope, SharingStarted.WhileSubscribed(UPLOAD_FLOW_TIMEOUT_MS), false)

        private val _message = MutableStateFlow<String?>(null)
        val message: StateFlow<String?> = _message.asStateFlow()

        private val _folder = MutableStateFlow<String?>(null)
        val folder: StateFlow<String?> = _folder.asStateFlow()

        // WorkInfo for a finished job keeps re-emitting in WorkManager's own history until
        // it is pruned, so each terminal id is handled once rather than reloading the list
        // or re-showing a toast on every recomposition-triggered collection.
        private val handledWork = mutableSetOf<UUID>()

        init {
            load()
            uploadQueue
                .uploads()
                .onEach(::onWorkInfosChanged)
                .launchIn(viewModelScope)
        }

        private fun onWorkInfosChanged(infos: List<WorkInfo>) {
            infos.forEach { info ->
                if (info.id in handledWork) return@forEach
                when (info.state) {
                    WorkInfo.State.SUCCEEDED -> {
                        handledWork += info.id
                        // Reload rather than prepending locally: OCR status is decided
                        // server-side and the row should show what the server actually has.
                        load()
                    }

                    WorkInfo.State.FAILED -> {
                        handledWork += info.id
                        _message.value =
                            info.outputData.getString(ScanUploadWorker.KEY_ERROR_MESSAGE)
                                ?: "The upload did not complete."
                    }

                    else -> Unit
                }
            }
        }

        fun onFolderChanged(value: String?) {
            _folder.value = value
            load()
        }

        fun load() {
            viewModelScope.launch {
                _state.value = UiState.Loading
                _state.value =
                    when (val result = repository.documents(_folder.value)) {
                        is ApiResult.Failure -> UiState.Error(result.error.message, result.error.isRetryable)
                        is ApiResult.Success -> UiState.Content(result.data)
                    }
            }
        }

        /** D.7: a finished scan goes straight into the B.9 upload flow, queued durably so
         * it survives the app being killed before the PUT lands. */
        fun uploadScan(
            uri: Uri,
            pageCount: Int,
        ) {
            viewModelScope.launch {
                // Named by day and page count so a vault full of scans is still
                // scannable by eye before OCR has run.
                val pages = if (pageCount == 1) "1 page" else "$pageCount pages"
                val name = "Scan ${todayInIndia()} ($pages).pdf"

                when (val result = uploadQueue.enqueue(uri, name, caseId = null, folder = _folder.value)) {
                    is QueueResult.Enqueued -> Unit // uploading/state update comes from the WorkInfo flow above.
                    is QueueResult.Rejected -> _message.value = result.message
                }
            }
        }

        fun clearMessage() {
            _message.value = null
        }

        private companion object {
            const val UPLOAD_FLOW_TIMEOUT_MS = 5000L
        }
    }

/** D.7 document vault. Upload and the ML Kit scanner arrive with Sprint A5. */
@Composable
fun VaultRoute(
    onOpenDocument: (Document) -> Unit,
    modifier: Modifier = Modifier,
    viewModel: VaultViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val folder by viewModel.folder.collectAsStateWithLifecycle()
    val uploading by viewModel.uploading.collectAsStateWithLifecycle()
    val context = LocalContext.current

    // Presentation-only: which document (if any) has its summary dialog open. This is
    // not list state, so it does not belong in VaultViewModel, which owns the document
    // list, not a transient modal.
    var summarizingDocumentId by remember { mutableStateOf<DocumentId?>(null) }

    val startScan =
        rememberDocumentScanner(
            onScanned = { result ->
                result.pdf?.let { pdf ->
                    viewModel.uploadScan(pdf.uri, pdf.pageCount)
                }
            },
            // No Play Services, or the module could not download. Saying so beats a
            // button that silently does nothing.
            onUnavailable = { Toast.makeText(context, R.string.vault_scan_unavailable, Toast.LENGTH_LONG).show() },
        )

    Box(modifier = modifier.fillMaxSize()) {
        FloatingActionButton(
            onClick = startScan,
            modifier =
                Modifier
                    .align(Alignment.BottomEnd)
                    .padding(NyayaTheme.spacing.lg)
                    .zIndex(1f),
        ) {
            if (uploading) {
                CircularProgressIndicator(modifier = Modifier.size(FAB_SPINNER))
            } else {
                Icon(
                    Icons.Default.DocumentScanner,
                    contentDescription = stringResource(R.string.vault_scan),
                )
            }
        }

        Column(modifier = Modifier.fillMaxSize()) {
            LazyRow(
                // Vertical padding so the chips are not wedged between the app bar and the
                // first card. The horizontal padding is what lets a partially scrolled
                // chip peek at the edge, which is the only hint that the row scrolls.
                contentPadding =
                    PaddingValues(
                        horizontal = NyayaTheme.spacing.md,
                        vertical = NyayaTheme.spacing.sm,
                    ),
                horizontalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.sm),
            ) {
                items(FOLDERS) { option ->
                    FilterChip(
                        selected = option.wire == folder,
                        onClick = { viewModel.onFolderChanged(option.wire) },
                        label = { Text(stringResource(option.labelRes)) },
                    )
                }
            }

            when (state) {
                is UiState.Loading -> LoadingList()

                is UiState.Error -> {
                    val error = state as UiState.Error
                    ErrorState(message = error.message, onRetry = viewModel::load.takeIf { error.retryable })
                }

                is UiState.Empty -> EmptyState(title = (state as UiState.Empty).title)

                is UiState.Content -> {
                    val documents = (state as UiState.Content<List<Document>>).data
                    if (documents.isEmpty()) {
                        EmptyState(
                            title = stringResource(R.string.vault_empty),
                            description = stringResource(R.string.vault_empty_detail),
                        )
                    } else {
                        LazyColumn(
                            contentPadding =
                                PaddingValues(
                                    start = NyayaTheme.spacing.md,
                                    end = NyayaTheme.spacing.md,
                                    top = NyayaTheme.spacing.md,
                                    // Clears the FAB, which floats over this list rather than beside it.
                                    bottom = NyayaTheme.spacing.fabClearance,
                                ),
                            verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.sm),
                        ) {
                            itemsIndexed(documents, key = { _, d -> d.id.value }) { index, document ->
                                DocumentCard(
                                    document = document,
                                    onClick = { onOpenDocument(document) },
                                    onSummarize = { summarizingDocumentId = document.id },
                                    modifier = Modifier.animatedListEntry(index),
                                )
                            }
                        }
                    }
                }
            }
        }
    }

    summarizingDocumentId?.let { documentId ->
        SummarizeDialog(
            documentId = documentId,
            onDismiss = { summarizingDocumentId = null },
        )
    }
}

private val FAB_SPINNER = 20.dp

@Composable
private fun DocumentCard(
    document: Document,
    onClick: () -> Unit,
    onSummarize: () -> Unit,
    modifier: Modifier = Modifier,
) {
    NyayaCard(modifier = modifier.animateContentSize(), onClick = onClick) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.sm),
        ) {
            Column(modifier = Modifier.weight(1f)) {
                // Bounded, because a court filing's name is routinely long enough to wrap
                // three or four times ("Written statement on behalf of respondent no. 2
                // dated 14.03.2026.pdf"). Unbounded, it stretched the row and left the
                // status badge floating in the middle of a wall of text. Two lines keeps
                // the part that distinguishes one filing from another.
                Text(
                    text = document.name,
                    style = MaterialTheme.typography.bodyLarge,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )

                val meta =
                    listOfNotNull(document.folder, document.sizeBytes.asFileSize())
                        .joinToString(" · ")
                Text(
                    text = meta,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            StatusBadge(
                text = stringResource(document.ocrStatus.labelRes()),
                tone = document.ocrStatus.tone(),
            )

            // The server requires OCR text before it can summarize a document, so the
            // action is disabled rather than hidden — the lawyer sees it exists and why
            // it isn't available yet.
            IconButton(onClick = onSummarize, enabled = document.ocrStatus == OcrStatus.DONE) {
                Icon(
                    imageVector = Icons.AutoMirrored.Filled.Article,
                    contentDescription = stringResource(R.string.vault_summarize),
                )
            }
        }
    }
}

/**
 * A failed OCR is shown, not hidden. It means the document is not searchable and the
 * summarizer cannot read it — the lawyer needs to know that before relying on a search
 * that silently missed it.
 */
private fun OcrStatus.tone(): StatusTone =
    when (this) {
        OcrStatus.DONE -> StatusTone.POSITIVE
        OcrStatus.PENDING -> StatusTone.NEUTRAL
        OcrStatus.FAILED -> StatusTone.NEGATIVE
        OcrStatus.UNKNOWN -> StatusTone.NEUTRAL
    }

private fun OcrStatus.labelRes(): Int =
    when (this) {
        OcrStatus.DONE -> R.string.vault_ocr_done
        OcrStatus.PENDING -> R.string.vault_ocr_pending
        OcrStatus.FAILED -> R.string.vault_ocr_failed
        OcrStatus.UNKNOWN -> R.string.vault_ocr_pending
    }

private fun Long.asFileSize(): String =
    when {
        this >= MB -> "${this / MB} MB"
        this >= KB -> "${this / KB} KB"
        else -> "$this B"
    }

private const val KB = 1024L
private const val MB = KB * 1024L

private data class FolderOption(
    val wire: String?,
    val labelRes: Int,
)

private val FOLDERS =
    listOf(
        FolderOption(null, R.string.vault_folder_all),
        FolderOption("Pleadings", R.string.vault_folder_pleadings),
        FolderOption("Evidence", R.string.vault_folder_evidence),
        FolderOption("Orders", R.string.vault_folder_orders),
        FolderOption("Correspondence", R.string.vault_folder_correspondence),
    )
