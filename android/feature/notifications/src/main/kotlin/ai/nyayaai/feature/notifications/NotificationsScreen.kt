package ai.nyayaai.feature.notifications

import ai.nyayaai.core.common.UiState
import ai.nyayaai.core.designsystem.component.EmptyState
import ai.nyayaai.core.designsystem.component.ErrorState
import ai.nyayaai.core.designsystem.component.LoadingList
import ai.nyayaai.core.designsystem.component.NyayaCard
import ai.nyayaai.core.designsystem.component.SectionHeader
import ai.nyayaai.core.designsystem.component.animatedListEntry
import ai.nyayaai.core.designsystem.theme.NyayaTheme
import ai.nyayaai.core.model.AppNotification
import ai.nyayaai.core.model.NotificationId
import ai.nyayaai.core.model.PushType
import ai.nyayaai.core.network.api.ApiCaller
import ai.nyayaai.core.network.api.ApiResult
import ai.nyayaai.core.network.api.isRetryable
import ai.nyayaai.core.network.api.map
import ai.nyayaai.core.network.mapper.toDomain
import ai.nyayaai.core.network.service.NotificationService
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Article
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Circle
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Payments
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
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
import kotlin.time.Clock
import kotlin.time.Instant

/** B.6 notifications — always scoped to the signed-in staff user, never the whole firm. */
@Singleton
class NotificationRepository
    @Inject
    constructor(
        private val service: NotificationService,
        private val caller: ApiCaller,
    ) {
        suspend fun notifications(unreadOnly: Boolean = false): ApiResult<List<AppNotification>> =
            caller.call { service.notifications(unreadOnly = unreadOnly) }.map { list -> list.map { it.toDomain() } }

        suspend fun markRead(id: NotificationId): ApiResult<AppNotification> =
            caller.call { service.markRead(id.value) }.map { it.toDomain() }

        suspend fun markAllRead(): ApiResult<Int> =
            caller.call { service.markAllRead() }.map { it["updated"] ?: 0 }
    }

@HiltViewModel
class NotificationsViewModel
    @Inject
    constructor(
        private val repository: NotificationRepository,
    ) : ViewModel() {
        private val _state = MutableStateFlow<UiState<List<AppNotification>>>(UiState.Loading)
        val state: StateFlow<UiState<List<AppNotification>>> = _state.asStateFlow()

        private val _unreadOnly = MutableStateFlow(false)
        val unreadOnly: StateFlow<Boolean> = _unreadOnly.asStateFlow()

        init {
            load()
        }

        /** Switching the filter is a fresh fetch, not a client-side re-slice — the server,
         * not this screen, decides what "unread" means for pagination. */
        fun setUnreadOnly(value: Boolean) {
            _unreadOnly.value = value
            load()
        }

        fun load() {
            viewModelScope.launch {
                _state.value = UiState.Loading
                _state.value =
                    when (val result = repository.notifications(_unreadOnly.value)) {
                        is ApiResult.Failure -> UiState.Error(result.error.message, result.error.isRetryable)
                        is ApiResult.Success -> UiState.Content(result.data)
                    }
            }
        }

        /**
         * Tapping an unread notification marks it read immediately in local state, exactly
         * like [ai.nyayaai.feature.tasks.TasksViewModel.toggle] — a lawyer clearing ten
         * reminders in a row should not watch each dot wait on a round trip before it
         * disappears. The `markRead` call runs after, and a failure reconciles via [load]
         * rather than trying to undo the optimistic edit by hand.
         *
         * The deep link, if any, is handed to [onOpenDeepLink] as the raw string the server
         * sent — this screen does not parse it. [ai.nyayaai.core.common.DeepLink.parse] is
         * the single place that turns that string into a destination, the same code path a
         * push notification tap already goes through, so a link opened from this inbox and
         * one opened from a system notification always land in the same place.
         */
        fun onTap(
            notification: AppNotification,
            onOpenDeepLink: (String) -> Unit,
        ) {
            if (notification.readAt == null) {
                val current = (_state.value as? UiState.Content)?.data
                if (current != null) {
                    _state.value =
                        UiState.Content(
                            current.map {
                                if (it.id == notification.id) it.copy(readAt = Clock.System.now()) else it
                            },
                        )
                }

                viewModelScope.launch {
                    if (repository.markRead(notification.id) is ApiResult.Failure) load()
                }
            }

            notification.deepLink?.let(onOpenDeepLink)
        }

        /**
         * No optimistic path here, unlike [onTap] — this clears every unread row at once,
         * so there is nothing smaller than a full [load] to reconcile against, and the
         * round trip is a single call rather than one per row.
         */
        fun onMarkAllRead() {
            viewModelScope.launch {
                if (repository.markAllRead() is ApiResult.Success) load()
            }
        }
    }

/** The binary choice between "all" and "unread" — a segmented toggle, not a filter row of
 * N chips like the vault's folders, because there are exactly two options. */
private enum class NotificationFilter(
    val unreadOnly: Boolean,
    val labelRes: Int,
) {
    ALL(unreadOnly = false, labelRes = R.string.notifications_filter_all),
    UNREAD(unreadOnly = true, labelRes = R.string.notifications_filter_unread),
}

@Composable
fun NotificationsRoute(
    onOpenDeepLink: (String) -> Unit,
    modifier: Modifier = Modifier,
    viewModel: NotificationsViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val unreadOnly by viewModel.unreadOnly.collectAsStateWithLifecycle()

    val hasUnread = (state as? UiState.Content)?.data?.any { it.readAt == null } == true

    Column(modifier = modifier.fillMaxSize()) {
        SectionHeader(
            title = stringResource(R.string.notifications_title),
            actionLabel = stringResource(R.string.notifications_mark_all_read).takeIf { hasUnread },
            onAction = viewModel::onMarkAllRead.takeIf { hasUnread },
            modifier =
                Modifier
                    .fillMaxWidth()
                    .padding(horizontal = NyayaTheme.spacing.md, vertical = NyayaTheme.spacing.sm),
        )

        SingleChoiceSegmentedButtonRow(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .padding(horizontal = NyayaTheme.spacing.md),
        ) {
            NotificationFilter.entries.forEachIndexed { index, option ->
                SegmentedButton(
                    selected = option.unreadOnly == unreadOnly,
                    onClick = { viewModel.setUnreadOnly(option.unreadOnly) },
                    shape = SegmentedButtonDefaults.itemShape(index, NotificationFilter.entries.size),
                ) {
                    Text(stringResource(option.labelRes))
                }
            }
        }

        val contentModifier = Modifier.padding(top = NyayaTheme.spacing.sm)

        when (state) {
            is UiState.Loading -> LoadingList(modifier = contentModifier)

            is UiState.Error -> {
                val error = state as UiState.Error
                ErrorState(
                    message = error.message,
                    onRetry = viewModel::load.takeIf { error.retryable },
                    modifier = contentModifier,
                )
            }

            is UiState.Empty -> EmptyState(title = (state as UiState.Empty).title, modifier = contentModifier)

            is UiState.Content -> {
                val notifications = (state as UiState.Content<List<AppNotification>>).data
                if (notifications.isEmpty()) {
                    EmptyState(
                        title =
                            stringResource(
                                if (unreadOnly) R.string.notifications_empty_unread_title else R.string.notifications_empty_all_title,
                            ),
                        description =
                            stringResource(
                                if (unreadOnly) {
                                    R.string.notifications_empty_unread_detail
                                } else {
                                    R.string.notifications_empty_all_detail
                                },
                            ),
                        modifier = contentModifier,
                    )
                } else {
                    LazyColumn(
                        modifier = contentModifier.fillMaxSize(),
                        contentPadding = PaddingValues(NyayaTheme.spacing.md),
                        verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.sm),
                    ) {
                        itemsIndexed(notifications, key = { _, item -> item.id.value }) { index, notification ->
                            NotificationCard(
                                notification = notification,
                                onClick = { viewModel.onTap(notification, onOpenDeepLink) },
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
private fun NotificationCard(
    notification: AppNotification,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val unread = notification.readAt == null

    NyayaCard(modifier = modifier, onClick = onClick) {
        Row(horizontalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.sm)) {
            Icon(
                imageVector = notification.type.icon(),
                contentDescription = null,
                tint =
                    if (unread) {
                        MaterialTheme.colorScheme.primary
                    } else {
                        MaterialTheme.colorScheme.onSurfaceVariant
                    },
            )

            Column(modifier = Modifier.weight(1f)) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.xs),
                ) {
                    Text(
                        text = notification.title,
                        style = MaterialTheme.typography.bodyLarge,
                        fontWeight = if (unread) FontWeight.SemiBold else FontWeight.Normal,
                        color =
                            if (unread) {
                                MaterialTheme.colorScheme.onSurface
                            } else {
                                MaterialTheme.colorScheme.onSurfaceVariant
                            },
                        modifier = Modifier.weight(1f, fill = false),
                    )
                    if (unread) {
                        Icon(
                            imageVector = Icons.Filled.Circle,
                            contentDescription = stringResource(R.string.notifications_unread_dot),
                            tint = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.size(UNREAD_DOT_SIZE),
                        )
                    }
                }

                Text(
                    text = notification.body,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )

                Text(
                    text = notification.createdAt.timeAgoLabel(),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

/** A leading icon per push type, reusing the exact icons the rest of the app already uses
 * for the same concept — the bottom nav's calendar for hearings, its check circle for
 * tasks — so a notification about a hearing looks like the Calendar tab, not like a
 * fresh icon invented just for this inbox. */
private fun PushType.icon(): ImageVector =
    when (this) {
        PushType.HEARING_REMINDER -> Icons.Filled.CalendarMonth
        PushType.DAILY_DIGEST -> Icons.Filled.Notifications
        PushType.CASE_UPDATE -> Icons.AutoMirrored.Filled.Article
        PushType.AI_JOB_COMPLETE -> Icons.Filled.AutoAwesome
        PushType.PAYMENT_RECEIVED -> Icons.Filled.Payments
        PushType.TASK_ASSIGNED -> Icons.Filled.CheckCircle
        PushType.UNKNOWN -> Icons.Filled.Notifications
    }

/**
 * A short "N ago" label for a genuine moment.
 *
 * [ai.nyayaai.core.common.IndiaTime] has no equivalent — `CourtDate.formatShort`/
 * `formatLong` work in calendar days because a hearing date has no time-of-day meaning,
 * but a notification's `createdAt` is a real instant, and stretching the court-date API
 * to cover it would be the wrong fit rather than reuse.
 */
@Composable
private fun Instant.timeAgoLabel(clock: Clock = Clock.System): String {
    val totalSeconds = (clock.now() - this).inWholeSeconds.coerceAtLeast(0)
    val minutes = totalSeconds / SECONDS_PER_MINUTE
    val hours = minutes / MINUTES_PER_HOUR
    val days = hours / HOURS_PER_DAY

    return when {
        minutes < 1 -> stringResource(R.string.notifications_time_just_now)
        hours < 1 -> stringResource(R.string.notifications_time_minutes, minutes)
        days < 1 -> stringResource(R.string.notifications_time_hours, hours)
        else -> stringResource(R.string.notifications_time_days, days)
    }
}

private val UNREAD_DOT_SIZE = 8.dp
private const val SECONDS_PER_MINUTE = 60L
private const val MINUTES_PER_HOUR = 60L
private const val HOURS_PER_DAY = 24L
