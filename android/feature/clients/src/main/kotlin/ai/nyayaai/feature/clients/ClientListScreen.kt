package ai.nyayaai.feature.clients

import ai.nyayaai.core.common.UiState
import ai.nyayaai.core.designsystem.component.EmptyState
import ai.nyayaai.core.designsystem.component.ErrorState
import ai.nyayaai.core.designsystem.component.InitialAvatar
import ai.nyayaai.core.designsystem.component.LoadingList
import ai.nyayaai.core.designsystem.component.NyayaCard
import ai.nyayaai.core.designsystem.component.animatedListEntry
import ai.nyayaai.core.designsystem.theme.NyayaTheme
import ai.nyayaai.core.model.Client
import ai.nyayaai.core.model.ClientId
import ai.nyayaai.core.network.api.ApiResult
import ai.nyayaai.core.network.api.isRetryable
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
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
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
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.debounce
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

@OptIn(FlowPreview::class)
@HiltViewModel
class ClientListViewModel
    @Inject
    constructor(
        private val repository: ClientRepository,
    ) : ViewModel() {
        private val _state = MutableStateFlow<UiState<List<Client>>>(UiState.Loading)
        val state: StateFlow<UiState<List<Client>>> = _state.asStateFlow()

        private val _query = MutableStateFlow("")
        val query: StateFlow<String> = _query.asStateFlow()

        init {
            viewModelScope.launch {
                // Same debounce as CaseListViewModel (D.5): one request per pause in
                // typing, not one per keystroke, on what is often mobile data.
                _query
                    .debounce(SEARCH_DEBOUNCE_MS)
                    .distinctUntilChanged()
                    .collect { load() }
            }
        }

        fun onQueryChanged(value: String) {
            _query.value = value
        }

        fun load() {
            viewModelScope.launch {
                _state.update { if (it is UiState.Content) it.copy(isRefreshing = true) else UiState.Loading }

                _state.value =
                    when (val result = repository.clients(_query.value)) {
                        is ApiResult.Failure -> UiState.Error(result.error.message, result.error.isRetryable)
                        is ApiResult.Success -> UiState.Content(result.data)
                    }
            }
        }

        private companion object {
            const val SEARCH_DEBOUNCE_MS = 300L
        }
    }

/**
 * The FAB is a sibling of the `when` inside [Scaffold], exactly as in `TasksRoute` — a
 * lawyer needs to add a client from an empty list, an error banner or mid-load, not only
 * once clients already exist.
 */
@Composable
fun ClientListRoute(
    onOpenClient: (ClientId) -> Unit,
    onAddClient: () -> Unit,
    modifier: Modifier = Modifier,
    viewModel: ClientListViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val query by viewModel.query.collectAsStateWithLifecycle()

    Scaffold(
        modifier = modifier,
        floatingActionButton = {
            FloatingActionButton(onClick = onAddClient) {
                Icon(Icons.Default.Add, contentDescription = stringResource(R.string.clients_add))
            }
        },
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .padding(innerPadding)
                .fillMaxSize(),
        ) {
            OutlinedTextField(
                value = query,
                onValueChange = viewModel::onQueryChanged,
                label = { Text(stringResource(R.string.clients_search_hint)) },
                singleLine = true,
                modifier =
                    Modifier
                        .fillMaxWidth()
                        .padding(NyayaTheme.spacing.md),
            )

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
                    val clients = (state as UiState.Content<List<Client>>).data
                    if (clients.isEmpty()) {
                        if (query.isBlank()) {
                            EmptyState(
                                title = stringResource(R.string.clients_empty_title),
                                description = stringResource(R.string.clients_empty_detail),
                            )
                        } else {
                            EmptyState(title = stringResource(R.string.clients_empty_search))
                        }
                    } else {
                        LazyColumn(
                            contentPadding = PaddingValues(NyayaTheme.spacing.md),
                            verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.sm),
                        ) {
                            itemsIndexed(clients, key = { _, item -> item.id.value }) { index, client ->
                                ClientCard(
                                    client = client,
                                    onClick = { onOpenClient(client.id) },
                                    modifier = Modifier.animatedListEntry(index),
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
internal fun ClientCard(
    client: Client,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    NyayaCard(modifier = modifier, onClick = onClick) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            InitialAvatar(name = client.name)

            Column(
                modifier = Modifier.padding(start = NyayaTheme.spacing.md),
                verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.xs),
            ) {
                Text(text = client.name, style = MaterialTheme.typography.titleMedium)
                Text(
                    text = client.phone,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}
