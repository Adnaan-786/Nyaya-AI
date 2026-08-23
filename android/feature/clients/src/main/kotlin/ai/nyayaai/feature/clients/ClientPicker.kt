package ai.nyayaai.feature.clients

import ai.nyayaai.core.common.UiState
import ai.nyayaai.core.designsystem.component.EmptyState
import ai.nyayaai.core.designsystem.component.ErrorState
import ai.nyayaai.core.designsystem.component.LoadingList
import ai.nyayaai.core.designsystem.theme.NyayaTheme
import ai.nyayaai.core.model.Client
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ClientPickerBottomSheet(
    onClientSelected: (Client) -> Unit,
    onDismissRequest: () -> Unit,
    modifier: Modifier = Modifier,
    viewModel: ClientListViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val query by viewModel.query.collectAsStateWithLifecycle()

    ModalBottomSheet(
        onDismissRequest = onDismissRequest,
        modifier = modifier
    ) {
        Column {
            OutlinedTextField(
                value = query,
                onValueChange = viewModel::onQueryChanged,
                label = { Text(stringResource(R.string.clients_search_hint)) },
                singleLine = true,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(NyayaTheme.spacing.md),
            )
            
            when (state) {
                is UiState.Loading -> LoadingList()
                is UiState.Error -> {
                    val error = state as UiState.Error
                    ErrorState(message = error.message, onRetry = viewModel::load)
                }
                is UiState.Empty -> EmptyState(title = (state as UiState.Empty).title)
                is UiState.Content -> {
                    val clients = (state as UiState.Content<List<Client>>).data
                    if (clients.isEmpty()) {
                        EmptyState(title = stringResource(R.string.clients_empty_search))
                    } else {
                        LazyColumn(
                            contentPadding = PaddingValues(NyayaTheme.spacing.md),
                            verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.sm)
                        ) {
                            items(clients) { client ->
                                ClientCard(
                                    client = client,
                                    onClick = { onClientSelected(client) }
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}
