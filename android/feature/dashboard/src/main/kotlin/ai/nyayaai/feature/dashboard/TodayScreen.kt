package ai.nyayaai.feature.dashboard

import ai.nyayaai.core.common.UiState
import ai.nyayaai.core.common.format12Hour
import ai.nyayaai.core.common.formatLong
import ai.nyayaai.core.common.isPast
import ai.nyayaai.core.designsystem.component.EmptyState
import ai.nyayaai.core.designsystem.component.ErrorState
import ai.nyayaai.core.designsystem.component.LoadingList
import ai.nyayaai.core.designsystem.component.StatusBadge
import ai.nyayaai.core.designsystem.component.StatusTone
import ai.nyayaai.core.designsystem.theme.NyayaTheme
import ai.nyayaai.core.model.CaseId
import ai.nyayaai.core.model.Task
import ai.nyayaai.core.network.mapper.TodayHearing
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle

@Composable
fun TodayRoute(
    onOpenCase: (CaseId) -> Unit,
    modifier: Modifier = Modifier,
    viewModel: TodayViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    TodayScreen(
        state = state,
        onOpenCase = onOpenCase,
        onRetry = { viewModel.load() },
        modifier = modifier,
    )
}

@Composable
fun TodayScreen(
    state: UiState<TodayContent>,
    onOpenCase: (CaseId) -> Unit,
    onRetry: () -> Unit,
    modifier: Modifier = Modifier,
) {
    when (state) {
        is UiState.Loading -> LoadingList(modifier = modifier)

        is UiState.Error ->
            ErrorState(
                message = state.message,
                onRetry = onRetry.takeIf { state.retryable },
                modifier = modifier,
            )

        is UiState.Empty -> EmptyState(title = state.title, description = state.description, modifier = modifier)

        is UiState.Content -> TodayContentList(state.data, onOpenCase, modifier)
    }
}

@Composable
private fun TodayContentList(
    content: TodayContent,
    onOpenCase: (CaseId) -> Unit,
    modifier: Modifier = Modifier,
) {
    val board = content.board

    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding =
            androidx.compose.foundation.layout
                .PaddingValues(NyayaTheme.spacing.md),
        verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.md),
    ) {
        item {
            Column {
                Text(
                    text = stringResource(R.string.today_greeting),
                    style = MaterialTheme.typography.headlineSmall,
                )
                Text(
                    // The date is rendered from the server's date-only field, formatted in
                    // IST. Never derived from a device clock that may be on another day.
                    text = board.date.formatLong(),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }

        if (board.overdueOutcomes.isNotEmpty()) {
            item {
                StatusBadge(
                    text = stringResource(R.string.today_outcomes_pending, board.overdueOutcomes.size),
                    tone = StatusTone.WARNING,
                )
            }
        }

        if (board.hearings.isEmpty()) {
            item {
                EmptyState(
                    title = stringResource(R.string.today_no_hearings),
                    description =
                        if (board.tomorrowCount > 0) {
                            stringResource(R.string.today_no_hearings_detail, board.tomorrowCount)
                        } else {
                            stringResource(R.string.today_no_hearings_free)
                        },
                )
            }
        } else {
            items(board.hearings, key = { it.id.value }) { hearing ->
                HearingCard(hearing, onClick = { onOpenCase(hearing.caseId) })
            }
        }

        if (content.tasks.isNotEmpty()) {
            item {
                Text(
                    text = stringResource(R.string.today_tasks),
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.padding(top = NyayaTheme.spacing.sm),
                )
            }
            items(content.tasks, key = { it.id.value }) { task -> TaskRow(task) }
        }
    }
}

@Composable
private fun HearingCard(
    hearing: TodayHearing,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier =
            modifier
                .fillMaxWidth()
                .clickable(onClick = onClick),
    ) {
        Row(
            modifier = Modifier.padding(NyayaTheme.spacing.md),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                // The time column is fixed-width so a list of hearings reads as a
                // schedule rather than as ragged prose.
                text = hearing.time?.format12Hour() ?: stringResource(R.string.today_time_unspecified),
                style = MaterialTheme.typography.titleSmall,
                modifier = Modifier.width(TIME_COLUMN_WIDTH),
            )
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = hearing.caseTitle,
                    style = MaterialTheme.typography.titleSmall,
                )
                val subtitle = listOfNotNull(hearing.courtroom, hearing.courtName).firstOrNull()
                if (subtitle != null) {
                    Text(
                        text = subtitle,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                hearing.purpose?.let {
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
private fun TaskRow(
    task: Task,
    modifier: Modifier = Modifier,
) {
    val overdue = task.dueDate?.isPast() == true

    Column(modifier = modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(vertical = NyayaTheme.spacing.sm),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Text(
                text = task.title,
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.weight(1f),
            )
            if (overdue) {
                StatusBadge(
                    text = stringResource(R.string.today_task_overdue),
                    tone = StatusTone.NEGATIVE,
                    modifier =
                        Modifier.semantics {
                            contentDescription = "Overdue task"
                        },
                )
            }
        }
        HorizontalDivider()
    }
}

private val TIME_COLUMN_WIDTH = 76.dp
