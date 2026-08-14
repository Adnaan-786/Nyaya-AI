package ai.nyayaai.feature.dashboard

import ai.nyayaai.core.common.UiState
import ai.nyayaai.core.common.format12Hour
import ai.nyayaai.core.common.formatLong
import ai.nyayaai.core.common.isPast
import ai.nyayaai.core.common.nextUpBy
import ai.nyayaai.core.designsystem.component.EmptyState
import ai.nyayaai.core.designsystem.component.ErrorState
import ai.nyayaai.core.designsystem.component.LoadingList
import ai.nyayaai.core.designsystem.component.NyayaCard
import ai.nyayaai.core.designsystem.component.SectionHeader
import ai.nyayaai.core.designsystem.component.Stat
import ai.nyayaai.core.designsystem.component.StatStrip
import ai.nyayaai.core.designsystem.component.StatusBadge
import ai.nyayaai.core.designsystem.component.StatusTone
import ai.nyayaai.core.designsystem.component.TimelineRail
import ai.nyayaai.core.designsystem.component.animatedListEntry
import ai.nyayaai.core.designsystem.theme.NyayaTheme
import ai.nyayaai.core.model.CaseId
import ai.nyayaai.core.model.Task
import ai.nyayaai.core.network.mapper.TodayHearing
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
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

        is UiState.Empty ->
            EmptyState(title = state.title, description = state.description, modifier = modifier)

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
        contentPadding = PaddingValues(NyayaTheme.spacing.md),
        verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.md),
    ) {
        item { Header(board.date.formatLong()) }

        item {
            StatStrip(
                stats =
                    listOf(
                        Stat(stringResource(R.string.today_stat_today), board.hearings.size.toString()),
                        Stat(stringResource(R.string.today_stat_tomorrow), board.tomorrowCount.toString()),
                        Stat(
                            stringResource(R.string.today_stat_tasks),
                            content.tasks.count { it.dueDate?.isPast() == true }.toString(),
                        ),
                    ),
            )
        }

        if (board.overdueOutcomes.isNotEmpty()) {
            item {
                StatusBadge(
                    text =
                        pluralStringResource(
                            R.plurals.today_outcomes_pending,
                            board.overdueOutcomes.size,
                            board.overdueOutcomes.size,
                        ),
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
            item {
                SectionHeader(title = stringResource(R.string.today_schedule))
            }

            itemsIndexed(board.hearings, key = { _, item -> item.id.value }) { index, hearing ->
                TimelineEntry(
                    hearing = hearing,
                    // The next hearing that has not started yet — what a lawyer glancing
                    // at the phone between listings actually wants marked.
                    isNow = hearing.id == board.hearings.nextUpBy { it.time }?.id,
                    isLast = index == board.hearings.lastIndex,
                    onClick = { onOpenCase(hearing.caseId) },
                    modifier = Modifier.animatedListEntry(index),
                )
            }
        }

        if (content.tasks.isNotEmpty()) {
            item { SectionHeader(title = stringResource(R.string.today_tasks)) }

            itemsIndexed(content.tasks, key = { _, item -> item.id.value }) { index, task ->
                TaskRow(task, modifier = Modifier.animatedListEntry(index))
            }
        }
    }
}

@Composable
private fun Header(
    dateLabel: String,
    modifier: Modifier = Modifier,
) {
    Column(modifier = modifier.padding(bottom = NyayaTheme.spacing.xs)) {
        Text(
            text = stringResource(R.string.today_greeting),
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.SemiBold,
        )
        Text(
            // The server's date-only field, formatted in IST — never derived from a
            // device clock that may be on another day. The counts live in the stat
            // strip below rather than being repeated here.
            text = dateLabel,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun TimelineEntry(
    hearing: TodayHearing,
    isNow: Boolean,
    isLast: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Row(modifier = modifier.height(IntrinsicSize.Min)) {
        TimelineRail(isNow = isNow, isLast = isLast)

        Column(
            modifier =
                Modifier
                    .width(TIME_COLUMN_WIDTH)
                    .padding(start = NyayaTheme.spacing.sm, top = NyayaTheme.spacing.xs),
        ) {
            Text(
                text = hearing.time?.format12Hour() ?: stringResource(R.string.today_time_unspecified),
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold,
                color =
                    if (isNow) {
                        MaterialTheme.colorScheme.onSurface
                    } else {
                        MaterialTheme.colorScheme.onSurfaceVariant
                    },
            )
        }

        NyayaCard(
            modifier = Modifier.weight(1f).padding(bottom = NyayaTheme.spacing.sm),
            onClick = onClick,
            // The next listing is tinted rather than merely bolder: on a screen read at
            // arm's length in a corridor, colour carries further than weight.
            containerColor =
                if (isNow) {
                    MaterialTheme.colorScheme.secondaryContainer
                } else {
                    MaterialTheme.colorScheme.surfaceContainerLowest
                },
        ) {
            // No avatar here, unlike the case list: the dot and the time already anchor
            // the row on the left, and a third element in that column only steals width
            // from a case title that needs it.
            Column(verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.xs)) {
                Text(
                    text = hearing.caseTitle,
                    style = MaterialTheme.typography.titleSmall,
                )
                hearing.purpose?.let {
                    Text(text = it, style = MaterialTheme.typography.bodyMedium)
                }
                listOfNotNull(hearing.courtroom, hearing.courtName).firstOrNull()?.let {
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
                style = MaterialTheme.typography.bodyLarge,
                modifier = Modifier.weight(1f),
            )
            if (overdue) {
                StatusBadge(
                    text = stringResource(R.string.today_task_overdue),
                    tone = StatusTone.NEGATIVE,
                    modifier = Modifier.semantics { contentDescription = "Overdue task" },
                )
            }
        }
        HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
    }
}

private val TIME_COLUMN_WIDTH = 84.dp
