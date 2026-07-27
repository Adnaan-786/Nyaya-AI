package ai.nyayaai.feature.cases

import ai.nyayaai.core.common.UiState
import ai.nyayaai.core.designsystem.component.EmptyState
import ai.nyayaai.core.designsystem.component.ErrorState
import ai.nyayaai.core.designsystem.component.HearingChip
import ai.nyayaai.core.designsystem.component.LoadingList
import ai.nyayaai.core.designsystem.component.StatusBadge
import ai.nyayaai.core.designsystem.component.StatusTone
import ai.nyayaai.core.designsystem.theme.NyayaTheme
import ai.nyayaai.core.model.Case
import ai.nyayaai.core.model.CaseId
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle

@Composable
fun CaseListRoute(
    onOpenCase: (CaseId) -> Unit,
    onAddCase: () -> Unit,
    modifier: Modifier = Modifier,
    viewModel: CaseListViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val query by viewModel.query.collectAsStateWithLifecycle()
    val filter by viewModel.filter.collectAsStateWithLifecycle()

    Column(modifier = modifier.fillMaxSize()) {
        OutlinedTextField(
            value = query,
            onValueChange = viewModel::onQueryChanged,
            label = { Text(stringResource(R.string.cases_search_hint)) },
            singleLine = true,
            modifier =
                Modifier
                    .fillMaxWidth()
                    .padding(NyayaTheme.spacing.md),
        )

        Row(
            modifier = Modifier.padding(horizontal = NyayaTheme.spacing.md),
            horizontalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.sm),
        ) {
            CaseFilter.entries.forEach { option ->
                FilterChip(
                    selected = option == filter,
                    onClick = { viewModel.onFilterChanged(option) },
                    label = { Text(stringResource(option.labelRes())) },
                )
            }
        }

        when (state) {
            is UiState.Loading -> LoadingList()

            is UiState.Error -> {
                val error = state as UiState.Error
                ErrorState(
                    message = error.message,
                    onRetry = viewModel::load.takeIf { error.retryable },
                )
            }

            is UiState.Empty -> EmptyState(title = (state as UiState.Empty).title)

            is UiState.Content -> {
                val cases = (state as UiState.Content<List<Case>>).data
                if (cases.isEmpty()) {
                    // The query decides which of the two empty states applies (see
                    // CaseListViewModel) — one offers an add button, one does not.
                    if (query.isBlank()) {
                        EmptyState(
                            title = stringResource(R.string.cases_empty_title),
                            description = stringResource(R.string.cases_empty_detail),
                            action = {
                                Button(onClick = onAddCase) {
                                    Text(stringResource(R.string.cases_add))
                                }
                            },
                        )
                    } else {
                        EmptyState(title = stringResource(R.string.cases_empty_search))
                    }
                } else {
                    LazyColumn(
                        contentPadding = PaddingValues(NyayaTheme.spacing.md),
                        verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.sm),
                    ) {
                        items(cases, key = { it.id.value }) { case ->
                            CaseCard(case, onClick = { onOpenCase(case.id) })
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun CaseFilter.labelRes(): Int =
    when (this) {
        CaseFilter.ALL -> R.string.cases_filter_all
        CaseFilter.ACTIVE -> R.string.cases_filter_active
        CaseFilter.DISPOSED -> R.string.cases_filter_disposed
    }

@Composable
internal fun CaseCard(
    case: Case,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier =
            modifier
                .fillMaxWidth()
                .clickable(onClick = onClick),
    ) {
        Column(
            modifier = Modifier.padding(NyayaTheme.spacing.md),
            verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.xs),
        ) {
            Text(text = case.title, style = MaterialTheme.typography.titleSmall)

            val subtitle = listOfNotNull(case.caseNumber, case.courtName).joinToString(" · ")
            if (subtitle.isNotBlank()) {
                Text(
                    text = subtitle,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            Row(
                horizontalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.sm),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                case.nextHearingDate?.let { HearingChip(date = it) }

                case.stage?.let { StatusBadge(text = it, tone = StatusTone.NEUTRAL) }

                // A case with no CNR was entered by hand — worth showing, because it is
                // the one that will never update itself from eCourts.
                if (case.cnr == null) {
                    StatusBadge(
                        text = stringResource(R.string.cases_manual_badge),
                        tone = StatusTone.WARNING,
                    )
                }
            }
        }
    }
}
