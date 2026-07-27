package ai.nyayaai.feature.documents

import ai.nyayaai.core.common.UiState
import ai.nyayaai.core.designsystem.component.EmptyState
import ai.nyayaai.core.designsystem.component.ErrorState
import ai.nyayaai.core.designsystem.component.LoadingList
import ai.nyayaai.core.designsystem.component.StatusBadge
import ai.nyayaai.core.designsystem.component.StatusTone
import ai.nyayaai.core.designsystem.theme.NyayaTheme
import ai.nyayaai.core.model.Document
import ai.nyayaai.core.model.OcrStatus
import ai.nyayaai.core.network.api.ApiCaller
import ai.nyayaai.core.network.api.ApiResult
import ai.nyayaai.core.network.api.isRetryable
import ai.nyayaai.core.network.api.map
import ai.nyayaai.core.network.mapper.toDomain
import ai.nyayaai.core.network.service.DocumentService
import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
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
import kotlinx.coroutines.launch
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

@HiltViewModel
class VaultViewModel
    @Inject
    constructor(
        private val repository: DocumentRepository,
    ) : ViewModel() {
        private val _state = MutableStateFlow<UiState<List<Document>>>(UiState.Loading)
        val state: StateFlow<UiState<List<Document>>> = _state.asStateFlow()

        private val _folder = MutableStateFlow<String?>(null)
        val folder: StateFlow<String?> = _folder.asStateFlow()

        init {
            load()
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

    Column(modifier = modifier.fillMaxSize()) {
        LazyRow(
            contentPadding = PaddingValues(horizontal = NyayaTheme.spacing.md),
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
                        contentPadding = PaddingValues(NyayaTheme.spacing.md),
                        verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.sm),
                    ) {
                        items(documents, key = { it.id.value }) { document ->
                            DocumentCard(document, onClick = { onOpenDocument(document) })
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun DocumentCard(
    document: Document,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier =
            modifier
                .fillMaxWidth()
                .animateContentSize()
                .clickable(onClick = onClick),
    ) {
        Row(
            modifier = Modifier.padding(NyayaTheme.spacing.md),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.sm),
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(text = document.name, style = MaterialTheme.typography.bodyLarge)

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
