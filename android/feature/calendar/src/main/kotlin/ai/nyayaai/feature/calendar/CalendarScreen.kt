package ai.nyayaai.feature.calendar

import ai.nyayaai.core.common.UiState
import ai.nyayaai.core.common.format12Hour
import ai.nyayaai.core.common.formatLong
import ai.nyayaai.core.common.isToday
import ai.nyayaai.core.common.todayInIndia
import ai.nyayaai.core.designsystem.component.EmptyState
import ai.nyayaai.core.designsystem.component.ErrorState
import ai.nyayaai.core.designsystem.component.LoadingList
import ai.nyayaai.core.designsystem.component.NyayaCard
import ai.nyayaai.core.designsystem.component.animatedListEntry
import ai.nyayaai.core.designsystem.theme.NyayaTheme
import ai.nyayaai.core.model.CaseId
import ai.nyayaai.core.model.CourtDate
import ai.nyayaai.core.model.Hearing
import ai.nyayaai.core.network.api.ApiCaller
import ai.nyayaai.core.network.api.ApiResult
import ai.nyayaai.core.network.api.isRetryable
import ai.nyayaai.core.network.api.map
import ai.nyayaai.core.network.mapper.toDomain
import ai.nyayaai.core.network.service.CalendarService
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
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
import kotlinx.datetime.LocalDate
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class CalendarRepository
    @Inject
    constructor(
        private val service: CalendarService,
        private val caller: ApiCaller,
    ) {
        suspend fun hearings(
            from: String,
            to: String,
        ): ApiResult<List<Hearing>> = caller.call { service.range(from, to) }.map { list -> list.map { it.toDomain() } }
    }

/**
 * An **agenda**, not a month grid.
 *
 * A month grid shows a lawyer which squares have dots; an agenda shows what is actually
 * listed and when. With a handful of hearings a month, the grid is mostly empty cells,
 * and the thing worth seeing — the next date and what it is for — is what the agenda
 * puts first.
 */
@HiltViewModel
class CalendarViewModel
    @Inject
    constructor(
        private val repository: CalendarRepository,
    ) : ViewModel() {
        private val _state = MutableStateFlow<UiState<Map<CourtDate, List<Hearing>>>>(UiState.Loading)
        val state: StateFlow<UiState<Map<CourtDate, List<Hearing>>>> = _state.asStateFlow()

        init {
            load()
        }

        fun load() {
            viewModelScope.launch {
                _state.value = UiState.Loading

                // Anchored on the day in India, never the device's day. Epoch-day
                // arithmetic matches how core:common computes relative dates, and it
                // cannot drift through a timezone the way an Instant would.
                val today = todayInIndia()
                val from = LocalDate.fromEpochDays(today.toEpochDays() - PAST_WINDOW_DAYS)
                val to = LocalDate.fromEpochDays(today.toEpochDays() + FUTURE_WINDOW_DAYS)

                _state.value =
                    when (val result = repository.hearings(from.toString(), to.toString())) {
                        is ApiResult.Failure -> UiState.Error(result.error.message, result.error.isRetryable)
                        is ApiResult.Success ->
                            UiState.Content(result.data.groupBy { it.date }.toSortedMap())
                    }
            }
        }

        private companion object {
            const val PAST_WINDOW_DAYS = 30
            const val FUTURE_WINDOW_DAYS = 120
        }
    }

@Composable
fun CalendarRoute(
    onOpenCase: (CaseId) -> Unit,
    modifier: Modifier = Modifier,
    viewModel: CalendarViewModel = hiltViewModel(),
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

        is UiState.Content -> {
            val days = (state as UiState.Content<Map<CourtDate, List<Hearing>>>).data
            if (days.isEmpty()) {
                EmptyState(
                    title = stringResource(R.string.calendar_empty),
                    description = stringResource(R.string.calendar_empty_detail),
                    modifier = modifier,
                )
            } else {
                LazyColumn(
                    modifier = modifier.fillMaxSize(),
                    contentPadding = PaddingValues(NyayaTheme.spacing.md),
                    verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.md),
                ) {
                    days.forEach { (date, hearings) ->
                        item(key = date.toString()) { DayHeader(date) }

                        itemsIndexed(hearings, key = { _, h -> h.id.value }) { index, hearing ->
                            AgendaRow(
                                hearing = hearing,
                                onClick = { onOpenCase(hearing.caseId) },
                                modifier = Modifier.animatedListEntry(index),
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun DayHeader(
    date: CourtDate,
    modifier: Modifier = Modifier,
) {
    val isToday = date.isToday()

    Row(
        modifier = modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.sm),
    ) {
        Text(
            text = date.formatLong(),
            style = MaterialTheme.typography.titleSmall,
            color =
                if (isToday) {
                    MaterialTheme.colorScheme.primary
                } else {
                    MaterialTheme.colorScheme.onSurface
                },
        )
        if (isToday) {
            Text(
                text = stringResource(R.string.calendar_today),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onPrimaryContainer,
                modifier =
                    Modifier
                        .clip(MaterialTheme.shapes.extraSmall)
                        .background(MaterialTheme.colorScheme.primaryContainer)
                        .padding(horizontal = NyayaTheme.spacing.sm, vertical = NyayaTheme.spacing.xs),
            )
        }
    }
}

@Composable
private fun AgendaRow(
    hearing: Hearing,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    NyayaCard(modifier = modifier, onClick = onClick) {
        Column(verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.xs)) {
            Text(
                text = hearing.time?.format12Hour() ?: stringResource(R.string.calendar_no_time),
                style = MaterialTheme.typography.titleSmall,
            )
            hearing.purpose?.let {
                Text(text = it, style = MaterialTheme.typography.bodyMedium)
            }
            hearing.courtroom?.let {
                Text(
                    text = it,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}
