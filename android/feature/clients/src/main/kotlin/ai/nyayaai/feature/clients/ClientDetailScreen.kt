package ai.nyayaai.feature.clients

import ai.nyayaai.core.common.UiState
import ai.nyayaai.core.designsystem.component.EmptyState
import ai.nyayaai.core.designsystem.component.ErrorState
import ai.nyayaai.core.designsystem.component.LoadingList
import ai.nyayaai.core.designsystem.component.NyayaCard
import ai.nyayaai.core.designsystem.component.SectionHeader
import ai.nyayaai.core.designsystem.component.animatedListEntry
import ai.nyayaai.core.designsystem.theme.NyayaTheme
import ai.nyayaai.core.model.Case
import ai.nyayaai.core.model.CaseId
import ai.nyayaai.core.model.Client
import ai.nyayaai.core.model.ClientId
import ai.nyayaai.core.network.api.ApiResult
import ai.nyayaai.core.network.api.isRetryable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
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
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

/**
 * The result of a portal invite, kept out of a plain `String?` so the screen can
 * localize the success line rather than the ViewModel guessing at UI copy. Rendered as a
 * plain inline [Text] rather than a snackbar — no snackbar host exists anywhere in this
 * codebase, and building one for a single button is not worth the plumbing.
 */
sealed interface InviteResult {
    data object Sent : InviteResult

    data class Failed(
        val message: String,
    ) : InviteResult
}

/** A client plus the cases they are party to, loaded together (see [ClientDetailViewModel.load]). */
data class ClientDetail(
    val client: Client,
    val cases: List<Case>,
    val isInviting: Boolean = false,
    val inviteResult: InviteResult? = null,
)

@HiltViewModel
class ClientDetailViewModel
    @Inject
    constructor(
        private val repository: ClientRepository,
        savedStateHandle: SavedStateHandle,
    ) : ViewModel() {
        private val clientId = ClientId(checkNotNull(savedStateHandle.get<String>(ARG_CLIENT_ID)))

        private val _state = MutableStateFlow<UiState<ClientDetail>>(UiState.Loading)
        val state: StateFlow<UiState<ClientDetail>> = _state.asStateFlow()

        init {
            load()
        }

        fun load() {
            viewModelScope.launch {
                _state.value = UiState.Loading

                val clientCall = async { repository.client(clientId) }
                val casesCall = async { repository.cases(clientId) }

                _state.value =
                    when (val client = clientCall.await()) {
                        is ApiResult.Failure ->
                            UiState.Error(client.error.message, client.error.isRetryable)

                        // A cases failure must not hide the client's own details — the
                        // contact information is still useful on its own.
                        is ApiResult.Success ->
                            UiState.Content(
                                ClientDetail(
                                    client = client.data,
                                    cases = (casesCall.await() as? ApiResult.Success)?.data.orEmpty(),
                                ),
                            )
                    }
            }
        }

        /** The server's invite endpoint is safe to call again, so no "already invited" guard is needed here. */
        fun invite() {
            val current = _state.value as? UiState.Content ?: return
            if (current.data.isInviting) return

            _state.update { UiState.Content(current.data.copy(isInviting = true, inviteResult = null)) }

            viewModelScope.launch {
                val result: InviteResult =
                    when (val call = repository.invite(clientId)) {
                        is ApiResult.Success -> InviteResult.Sent
                        is ApiResult.Failure -> InviteResult.Failed(call.error.message)
                    }
                _state.update {
                    UiState.Content((it as UiState.Content).data.copy(isInviting = false, inviteResult = result))
                }
            }
        }

        fun dismissInviteMessage() {
            val current = _state.value as? UiState.Content ?: return
            _state.value = UiState.Content(current.data.copy(inviteResult = null))
        }

        companion object {
            const val ARG_CLIENT_ID = "clientId"
        }
    }

@Composable
fun ClientDetailRoute(
    onOpenCase: (CaseId) -> Unit,
    modifier: Modifier = Modifier,
    viewModel: ClientDetailViewModel = hiltViewModel(),
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
            ClientDetailContent(
                detail = (state as UiState.Content<ClientDetail>).data,
                onOpenCase = onOpenCase,
                onInvite = viewModel::invite,
                modifier = modifier,
            )
    }
}

@Composable
private fun ClientDetailContent(
    detail: ClientDetail,
    onOpenCase: (CaseId) -> Unit,
    onInvite: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val client = detail.client

    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = PaddingValues(NyayaTheme.spacing.md),
        verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.md),
    ) {
        item {
            Text(text = client.name, style = MaterialTheme.typography.headlineSmall)
        }

        item {
            NyayaCard {
                Column(verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.xs)) {
                    DetailRow(stringResource(R.string.client_phone), client.phone)
                    DetailRow(stringResource(R.string.client_email), client.email)
                    DetailRow(stringResource(R.string.client_address), client.address)
                    DetailRow(stringResource(R.string.client_notes), client.notes)
                }
            }
        }

        item {
            Column(verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.sm)) {
                OutlinedButton(
                    onClick = onInvite,
                    enabled = !detail.isInviting,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(stringResource(R.string.client_invite))
                }
                when (val result = detail.inviteResult) {
                    null -> Unit
                    is InviteResult.Sent ->
                        Text(
                            text = stringResource(R.string.client_invite_sent),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )

                    is InviteResult.Failed ->
                        Text(
                            text = result.message,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.error,
                        )
                }
            }
        }

        item {
            SectionHeader(title = stringResource(R.string.client_cases_header))
        }

        if (detail.cases.isEmpty()) {
            item { EmptyState(title = stringResource(R.string.client_no_cases)) }
        } else {
            itemsIndexed(detail.cases, key = { _, case -> case.id.value }) { index, case ->
                NyayaCard(
                    modifier = Modifier.animatedListEntry(index),
                    onClick = { onOpenCase(case.id) },
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
                }
            }
        }
    }
}

@Composable
private fun DetailRow(
    label: String,
    value: String?,
) {
    if (value.isNullOrBlank()) return

    Column(modifier = Modifier.fillMaxWidth().padding(vertical = NyayaTheme.spacing.xs)) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(text = value, style = MaterialTheme.typography.bodyMedium)
    }
}
