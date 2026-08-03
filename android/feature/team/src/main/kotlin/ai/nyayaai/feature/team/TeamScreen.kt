package ai.nyayaai.feature.team

import ai.nyayaai.core.common.UiState
import ai.nyayaai.core.designsystem.component.EmptyState
import ai.nyayaai.core.designsystem.component.ErrorState
import ai.nyayaai.core.designsystem.component.InitialAvatar
import ai.nyayaai.core.designsystem.component.LoadingList
import ai.nyayaai.core.designsystem.component.NyayaCard
import ai.nyayaai.core.designsystem.component.NyayaDropdownField
import ai.nyayaai.core.designsystem.component.StatusBadge
import ai.nyayaai.core.designsystem.component.StatusTone
import ai.nyayaai.core.designsystem.component.animatedListEntry
import ai.nyayaai.core.designsystem.theme.NyayaTheme
import ai.nyayaai.core.model.TeamMember
import ai.nyayaai.core.model.UserId
import ai.nyayaai.core.model.UserRole
import ai.nyayaai.core.network.api.ApiResult
import ai.nyayaai.core.network.api.isRetryable
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateContentSize
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
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

@HiltViewModel
class TeamViewModel
    @Inject
    constructor(
        private val repository: TeamRepository,
    ) : ViewModel() {
        private val _state = MutableStateFlow<UiState<List<TeamMember>>>(UiState.Loading)
        val state: StateFlow<UiState<List<TeamMember>>> = _state.asStateFlow()

        // Same shape as InvoiceListViewModel's `_message` (feature:billing) — a plain,
        // dismissible error line rather than a snackbar, since no snackbar host exists
        // anywhere in this codebase.
        private val _message = MutableStateFlow<String?>(null)
        val message: StateFlow<String?> = _message.asStateFlow()

        init {
            load()
        }

        fun load() {
            viewModelScope.launch {
                _state.value = UiState.Loading
                _state.value =
                    when (val result = repository.members()) {
                        is ApiResult.Failure ->
                            UiState.Error(result.error.message, result.error.isRetryable)

                        is ApiResult.Success -> UiState.Content(result.data)
                    }
            }
        }

        fun changeRole(
            member: TeamMember,
            role: AssignableRole,
        ) {
            viewModelScope.launch {
                when (val result = repository.updateRole(member.id, role.wire)) {
                    is ApiResult.Success -> load()
                    is ApiResult.Failure -> _message.value = result.error.message
                }
            }
        }

        fun removeMember(member: TeamMember) {
            viewModelScope.launch {
                when (val result = repository.remove(member.id)) {
                    is ApiResult.Success -> load()
                    is ApiResult.Failure -> _message.value = result.error.message
                }
            }
        }

        fun clearMessage() {
            _message.value = null
        }
    }

/**
 * The firm's roster. [currentUserId] and [isAdmin] arrive from the caller rather than a
 * fresh `/me` call — the signed-in session already knows both, and re-fetching them here
 * would just be a second source of truth for values the app already has.
 */
@Composable
fun TeamRoute(
    currentUserId: UserId,
    isAdmin: Boolean,
    modifier: Modifier = Modifier,
    viewModel: TeamViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val message by viewModel.message.collectAsStateWithLifecycle()

    Column(modifier = modifier.fillMaxSize().animateContentSize()) {
        AnimatedVisibility(
            visible = message != null,
            enter = fadeIn(tween(200)),
            exit = fadeOut(tween(200)),
        ) {
            message?.let { text ->
                Row(
                    modifier = Modifier.fillMaxWidth().padding(NyayaTheme.spacing.md),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    Text(
                        text = text,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                        modifier = Modifier.weight(1f),
                    )
                    IconButton(onClick = viewModel::clearMessage) {
                        Icon(Icons.Default.Close, contentDescription = stringResource(R.string.team_dismiss_message))
                    }
                }
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
                val members = (state as UiState.Content<List<TeamMember>>).data
                if (members.isEmpty()) {
                    EmptyState(title = stringResource(R.string.team_empty_title))
                } else {
                    LazyColumn(
                        contentPadding = PaddingValues(NyayaTheme.spacing.md),
                        verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.sm),
                    ) {
                        itemsIndexed(members, key = { _, member -> member.id.value }) { index, member ->
                            TeamMemberCard(
                                member = member,
                                // The server blocks a self-role-change and any action
                                // against a client-role account (see TeamRepository's
                                // KDoc) — hiding the controls here means this screen
                                // never offers a tap the server would 403 or 422 on.
                                canManage = isAdmin && member.id != currentUserId && member.role != UserRole.CLIENT,
                                onChangeRole = { role -> viewModel.changeRole(member, role) },
                                onRemove = { viewModel.removeMember(member) },
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
internal fun TeamMemberCard(
    member: TeamMember,
    canManage: Boolean,
    onChangeRole: (AssignableRole) -> Unit,
    onRemove: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var showRoleDialog by remember { mutableStateOf(false) }
    var showRemoveDialog by remember { mutableStateOf(false) }

    NyayaCard(modifier = modifier) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            InitialAvatar(name = member.name)

            Column(
                modifier =
                    Modifier
                        .padding(start = NyayaTheme.spacing.md)
                        .weight(1f),
                verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.xs),
            ) {
                Text(text = member.name, style = MaterialTheme.typography.titleMedium)
                Text(
                    text = member.phone,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                StatusBadge(text = stringResource(member.role.labelRes()), tone = member.role.tone())
            }

            if (canManage) {
                IconButton(onClick = { showRoleDialog = true }) {
                    Icon(Icons.Default.Edit, contentDescription = stringResource(R.string.team_change_role_cd))
                }
                IconButton(onClick = { showRemoveDialog = true }) {
                    Icon(Icons.Default.Delete, contentDescription = stringResource(R.string.team_remove_cd))
                }
            }
        }
    }

    if (showRoleDialog) {
        ChangeRoleDialog(
            current = member.role,
            onConfirm = { role ->
                showRoleDialog = false
                onChangeRole(role)
            },
            onDismiss = { showRoleDialog = false },
        )
    }

    if (showRemoveDialog) {
        AlertDialog(
            onDismissRequest = { showRemoveDialog = false },
            title = { Text(stringResource(R.string.team_remove_title)) },
            text = { Text(stringResource(R.string.team_remove_body, member.name)) },
            confirmButton = {
                TextButton(
                    onClick = {
                        showRemoveDialog = false
                        onRemove()
                    },
                ) {
                    Text(stringResource(R.string.team_remove_confirm))
                }
            },
            dismissButton = {
                TextButton(onClick = { showRemoveDialog = false }) {
                    Text(stringResource(R.string.team_cancel))
                }
            },
        )
    }
}

@Composable
private fun ChangeRoleDialog(
    current: UserRole,
    onConfirm: (AssignableRole) -> Unit,
    onDismiss: () -> Unit,
) {
    var selected by remember { mutableStateOf(current.toAssignableRoleOrDefault()) }

    // `optionLabel` in NyayaDropdownField is a plain (T) -> String, not @Composable, so
    // every label is resolved up front here rather than calling stringResource() inside
    // the lambda.
    val roleLabels = AssignableRole.entries.associateWith { stringResource(it.labelRes()) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(R.string.team_change_role_title)) },
        text = {
            NyayaDropdownField(
                value = selected,
                options = AssignableRole.entries,
                onSelect = { selected = it },
                label = stringResource(R.string.team_change_role_label),
                optionLabel = { roleLabels.getValue(it) },
            )
        },
        confirmButton = {
            TextButton(onClick = { onConfirm(selected) }) {
                Text(stringResource(R.string.team_change_role_confirm))
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text(stringResource(R.string.team_cancel))
            }
        },
    )
}

/** Falls back to LAWYER for a role the picker cannot represent (UNKNOWN, CLIENT). */
private fun UserRole.toAssignableRoleOrDefault(): AssignableRole =
    when (this) {
        UserRole.FIRM_ADMIN -> AssignableRole.FIRM_ADMIN
        UserRole.LAWYER -> AssignableRole.LAWYER
        UserRole.INTERN -> AssignableRole.INTERN
        UserRole.CLIENT, UserRole.UNKNOWN -> AssignableRole.LAWYER
    }

private fun UserRole.labelRes(): Int =
    when (this) {
        UserRole.FIRM_ADMIN -> R.string.team_role_firm_admin
        UserRole.LAWYER -> R.string.team_role_lawyer
        UserRole.INTERN -> R.string.team_role_intern
        UserRole.CLIENT -> R.string.team_role_client
        UserRole.UNKNOWN -> R.string.team_role_unknown
    }

private fun UserRole.tone(): StatusTone =
    when (this) {
        UserRole.FIRM_ADMIN -> StatusTone.POSITIVE
        UserRole.LAWYER -> StatusTone.NEUTRAL
        UserRole.INTERN -> StatusTone.WARNING
        UserRole.CLIENT -> StatusTone.NEUTRAL
        UserRole.UNKNOWN -> StatusTone.NEGATIVE
    }

private fun AssignableRole.labelRes(): Int =
    when (this) {
        AssignableRole.FIRM_ADMIN -> R.string.team_role_firm_admin
        AssignableRole.LAWYER -> R.string.team_role_lawyer
        AssignableRole.INTERN -> R.string.team_role_intern
    }
