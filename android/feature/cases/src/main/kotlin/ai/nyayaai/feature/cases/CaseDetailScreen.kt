package ai.nyayaai.feature.cases

import ai.nyayaai.core.common.UiState
import ai.nyayaai.core.common.format12Hour
import ai.nyayaai.core.common.formatLong
import ai.nyayaai.core.common.formatShort
import ai.nyayaai.core.designsystem.component.EmptyState
import ai.nyayaai.core.designsystem.component.ErrorState
import ai.nyayaai.core.designsystem.component.LoadingList
import ai.nyayaai.core.designsystem.component.NyayaCard
import ai.nyayaai.core.designsystem.component.SectionHeader
import ai.nyayaai.core.designsystem.component.Stat
import ai.nyayaai.core.designsystem.component.StatStrip
import ai.nyayaai.core.designsystem.component.StatusBadge
import ai.nyayaai.core.designsystem.component.StatusTone
import ai.nyayaai.core.designsystem.component.animatedListEntry
import ai.nyayaai.core.designsystem.theme.NyayaTheme
import ai.nyayaai.core.model.Document
import ai.nyayaai.core.model.Hearing
import ai.nyayaai.core.model.OcrStatus
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle

@Composable
fun CaseDetailRoute(
    onAddHearing: () -> Unit,
    modifier: Modifier = Modifier,
    viewModel: CaseDetailViewModel = hiltViewModel(),
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

        is UiState.Content ->
            CaseDetailContent(
                detail = (state as UiState.Content<CaseDetail>).data,
                onSync = viewModel::sync,
                onAddHearing = onAddHearing,
                modifier = modifier,
            )
    }
}

@Composable
private fun CaseDetailContent(
    detail: CaseDetail,
    onSync: () -> Unit,
    onAddHearing: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var tab by remember { mutableIntStateOf(0) }
    val case = detail.case

    Scaffold(
        modifier = modifier.fillMaxSize(),
        floatingActionButton = {
            if (tab == 1) {
                FloatingActionButton(onClick = onAddHearing) {
                    Icon(
                        imageVector = Icons.Filled.Add,
                        contentDescription = stringResource(R.string.hearing_add_title),
                    )
                }
            }
        },
    ) { innerPadding ->
        Column(modifier = Modifier.fillMaxSize().padding(innerPadding)) {
            Column(modifier = Modifier.padding(NyayaTheme.spacing.md)) {
                Text(text = case.title, style = MaterialTheme.typography.titleLarge)
                case.courtName?.let {
                    Text(
                        text = it,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }

            TabRow(selectedTabIndex = tab) {
                TAB_LABELS.forEachIndexed { index, label ->
                    Tab(
                        selected = tab == index,
                        onClick = { tab = index },
                        text = { Text(stringResource(label)) },
                    )
                }
            }

            when (tab) {
                0 -> OverviewTab(detail, onSync)
                1 -> HearingsTab(detail.hearings)
                else -> DocumentsTab(detail.documents)
            }
        }
    }
}

@Composable
private fun OverviewTab(
    detail: CaseDetail,
    onSync: () -> Unit,
) {
    val case = detail.case

    LazyColumn(
        contentPadding = PaddingValues(NyayaTheme.spacing.md),
        verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.md),
    ) {
        item {
            StatStrip(
                stats =
                    listOf(
                        Stat(stringResource(R.string.case_tab_hearings), detail.hearings.size.toString()),
                        Stat(stringResource(R.string.case_tab_documents), detail.documents.size.toString()),
                    ),
            )
        }

        item {
            NyayaCard {
                Column(verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.xs)) {
                    DetailRow(stringResource(R.string.case_number), case.caseNumber)
                    DetailRow(stringResource(R.string.case_cnr), case.cnr)
                    DetailRow(stringResource(R.string.case_court), case.courtName)
                    DetailRow(stringResource(R.string.case_judge), case.judgeName)
                    DetailRow(stringResource(R.string.case_type), case.caseType)
                    DetailRow(stringResource(R.string.case_stage), case.stage)
                    DetailRow(
                        stringResource(R.string.case_next_hearing),
                        case.nextHearingDate?.formatLong(),
                    )
                }
            }
        }

        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.sm),
            ) {
                OutlinedButton(onClick = onSync, enabled = !detail.isSyncing) {
                    Text(stringResource(R.string.case_sync))
                }
                detail.syncMessage?.let {
                    Text(
                        text = it,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }
}

@Composable
private fun HearingsTab(hearings: List<Hearing>) {
    if (hearings.isEmpty()) {
        EmptyState(title = stringResource(R.string.case_no_hearings))
        return
    }

    LazyColumn(
        contentPadding = PaddingValues(NyayaTheme.spacing.md),
        verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.sm),
    ) {
        itemsIndexed(hearings, key = { _, h -> h.id.value }) { index, hearing ->
            NyayaCard(modifier = Modifier.animatedListEntry(index)) {
                Column(verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.xs)) {
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.sm),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            text = hearing.date.formatShort(),
                            style = MaterialTheme.typography.titleSmall,
                        )
                        hearing.time?.let {
                            Text(
                                text = it.format12Hour(),
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                    hearing.purpose?.let { Text(text = it, style = MaterialTheme.typography.bodyMedium) }
                    hearing.outcomeNotes?.let {
                        Text(
                            text = "${stringResource(R.string.case_hearing_outcome)}: $it",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun DocumentsTab(documents: List<Document>) {
    if (documents.isEmpty()) {
        EmptyState(title = stringResource(R.string.case_no_documents))
        return
    }

    LazyColumn(
        contentPadding = PaddingValues(NyayaTheme.spacing.md),
        verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.sm),
    ) {
        itemsIndexed(documents, key = { _, d -> d.id.value }) { index, document ->
            NyayaCard(modifier = Modifier.animatedListEntry(index)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(text = document.name, style = MaterialTheme.typography.bodyMedium)
                        document.folder?.let {
                            Text(
                                text = it,
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                    StatusBadge(text = document.ocrStatus.name, tone = document.ocrStatus.tone())
                }
            }
        }
    }
}

/** A failed OCR is a real limitation the lawyer should see, not a silent gap. */
private fun OcrStatus.tone(): StatusTone =
    when (this) {
        OcrStatus.DONE -> StatusTone.POSITIVE
        OcrStatus.PENDING -> StatusTone.NEUTRAL
        OcrStatus.FAILED -> StatusTone.NEGATIVE
        OcrStatus.UNKNOWN -> StatusTone.NEUTRAL
    }

@Composable
private fun DetailRow(
    label: String,
    value: String?,
) {
    if (value.isNullOrBlank()) return

    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = NyayaTheme.spacing.xs),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(text = value, style = MaterialTheme.typography.bodyMedium)
    }
}

private val TAB_LABELS =
    listOf(
        R.string.case_tab_overview,
        R.string.case_tab_hearings,
        R.string.case_tab_documents,
    )
