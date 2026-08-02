package ai.nyayaai.feature.portal

import ai.nyayaai.core.common.UiState
import ai.nyayaai.core.common.format12Hour
import ai.nyayaai.core.common.formatLong
import ai.nyayaai.core.common.isToday
import ai.nyayaai.core.designsystem.component.EmptyState
import ai.nyayaai.core.designsystem.component.ErrorState
import ai.nyayaai.core.designsystem.component.LoadingList
import ai.nyayaai.core.designsystem.component.NyayaCard
import ai.nyayaai.core.designsystem.component.SectionHeader
import ai.nyayaai.core.designsystem.component.StatusBadge
import ai.nyayaai.core.designsystem.component.StatusTone
import ai.nyayaai.core.designsystem.component.TimelineRail
import ai.nyayaai.core.designsystem.component.animatedListEntry
import ai.nyayaai.core.designsystem.theme.NyayaTheme
import ai.nyayaai.core.model.CaseId
import ai.nyayaai.core.network.api.ApiResult
import ai.nyayaai.core.network.api.isRetryable
import ai.nyayaai.core.network.mapper.PortalCase
import ai.nyayaai.core.network.mapper.PortalHearing
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

/**
 * D.10 client mode: a single case, read-only.
 *
 * This is a leaf screen — there is nowhere further to go from here. No hearing detail, no
 * document list, no sync button. Everything the client sees comes straight from
 * [PortalCase], which is already the sanitized, client-safe shape — nothing here re-derives
 * or reaches past it.
 */
@HiltViewModel
class PortalCaseDetailViewModel
    @Inject
    constructor(
        private val repository: PortalRepository,
        savedStateHandle: SavedStateHandle,
    ) : ViewModel() {
        private val caseId = CaseId(checkNotNull(savedStateHandle.get<String>(ARG_CASE_ID)))

        private val _state = MutableStateFlow<UiState<PortalCase>>(UiState.Loading)
        val state: StateFlow<UiState<PortalCase>> = _state.asStateFlow()

        init {
            load()
        }

        fun load() {
            viewModelScope.launch {
                _state.value = UiState.Loading

                _state.value =
                    when (val result = repository.case(caseId)) {
                        is ApiResult.Failure ->
                            UiState.Error(result.error.message, result.error.isRetryable)

                        is ApiResult.Success -> UiState.Content(result.data)
                    }
            }
        }

        companion object {
            const val ARG_CASE_ID = "portalCaseId"
        }
    }

@Composable
fun PortalCaseDetailRoute(
    modifier: Modifier = Modifier,
    viewModel: PortalCaseDetailViewModel = hiltViewModel(),
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
            PortalCaseDetailContent((state as UiState.Content<PortalCase>).data, modifier)
    }
}

@Composable
private fun PortalCaseDetailContent(
    case: PortalCase,
    modifier: Modifier = Modifier,
) {
    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = PaddingValues(NyayaTheme.spacing.md),
        verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.md),
    ) {
        item {
            NyayaCard {
                Column(verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.xs)) {
                    Text(text = case.title, style = MaterialTheme.typography.titleLarge)

                    case.courtName?.let {
                        Text(
                            text = it,
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }

                    if (case.statusLabel.isNotBlank()) {
                        StatusBadge(text = case.statusLabel, tone = StatusTone.NEUTRAL)
                    }

                    Text(
                        text =
                            case.nextHearingDate
                                ?.let { stringResource(R.string.portal_next_hearing, it.formatLong()) }
                                ?: stringResource(R.string.portal_no_next_hearing),
                        style = MaterialTheme.typography.bodyMedium,
                    )

                    case.judgeName?.let {
                        Text(
                            text = stringResource(R.string.portal_judge, it),
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                }
            }
        }

        item { SectionHeader(title = stringResource(R.string.portal_case_history)) }

        if (case.timeline.isEmpty()) {
            item { EmptyState(title = stringResource(R.string.portal_no_history)) }
        } else {
            itemsIndexed(case.timeline, key = { _, h -> h.id.value }) { index, hearing ->
                PortalHearingRow(
                    hearing = hearing,
                    isLast = index == case.timeline.lastIndex,
                    modifier = Modifier.animatedListEntry(index),
                )
            }
        }
    }
}

@Composable
private fun PortalHearingRow(
    hearing: PortalHearing,
    isLast: Boolean,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.sm),
    ) {
        TimelineRail(
            isNow = hearing.date.isToday(),
            isLast = isLast,
            modifier = Modifier,
        )

        NyayaCard(modifier = Modifier.weight(1f)) {
            Column(verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.xs)) {
                Row(
                    horizontalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.sm),
                ) {
                    Text(
                        text = hearing.date.formatLong(),
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

                hearing.purpose?.let {
                    Text(text = it, style = MaterialTheme.typography.bodyMedium)
                }
            }
        }
    }
}
