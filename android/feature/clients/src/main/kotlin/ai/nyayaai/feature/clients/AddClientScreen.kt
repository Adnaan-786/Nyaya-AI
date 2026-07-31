package ai.nyayaai.feature.clients

import ai.nyayaai.core.designsystem.component.FormScaffold
import ai.nyayaai.core.designsystem.component.NyayaTextField
import ai.nyayaai.core.model.ClientId
import ai.nyayaai.core.network.api.ApiResult
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

/**
 * The only client intake form in the app (D.6-shaped): a flat, boolean-flag state, matching
 * `AddByCnrUiState` rather than the shared `UiState` — there is nothing to load here, only
 * something to submit.
 */
data class AddClientUiState(
    val name: String = "",
    val phone: String = "",
    val email: String = "",
    val address: String = "",
    val notes: String = "",
    val isSaving: Boolean = false,
    val error: String? = null,
    val createdClientId: ClientId? = null,
) {
    /** Indian mobile numbers are 10 digits — same rule `LoginUiState.isPhoneValid` uses at sign-in. */
    val isValid: Boolean get() = name.isNotBlank() && phone.length == PHONE_LENGTH && phone.all(Char::isDigit)

    companion object {
        const val PHONE_LENGTH = 10
    }
}

@HiltViewModel
class AddClientViewModel
    @Inject
    constructor(
        private val repository: ClientRepository,
    ) : ViewModel() {
        private val _state = MutableStateFlow(AddClientUiState())
        val state: StateFlow<AddClientUiState> = _state.asStateFlow()

        fun onNameChanged(value: String) {
            _state.update { it.copy(name = value, error = null) }
        }

        fun onPhoneChanged(value: String) {
            _state.update {
                it.copy(phone = value.filter(Char::isDigit).take(AddClientUiState.PHONE_LENGTH), error = null)
            }
        }

        fun onEmailChanged(value: String) {
            _state.update { it.copy(email = value, error = null) }
        }

        fun onAddressChanged(value: String) {
            _state.update { it.copy(address = value, error = null) }
        }

        fun onNotesChanged(value: String) {
            _state.update { it.copy(notes = value, error = null) }
        }

        fun submit() {
            val current = _state.value
            if (!current.isValid || current.isSaving) return

            _state.update { it.copy(isSaving = true, error = null) }
            viewModelScope.launch {
                when (
                    val result =
                        repository.create(
                            name = current.name,
                            phone = current.phone,
                            email = current.email.takeIf { it.isNotBlank() },
                            address = current.address.takeIf { it.isNotBlank() },
                            notes = current.notes.takeIf { it.isNotBlank() },
                        )
                ) {
                    is ApiResult.Success ->
                        _state.update { it.copy(isSaving = false, createdClientId = result.data.id) }

                    is ApiResult.Failure ->
                        _state.update { it.copy(isSaving = false, error = result.error.message) }
                }
            }
        }
    }

@Composable
fun AddClientRoute(
    onClientCreated: (ClientId) -> Unit,
    modifier: Modifier = Modifier,
    viewModel: AddClientViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    // A LaunchedEffect, not a call in the composition body — firing navigation directly
    // while composing re-fires on every recomposition, not just the one where the id
    // first appeared.
    LaunchedEffect(state.createdClientId) {
        state.createdClientId?.let(onClientCreated)
    }

    FormScaffold(
        title = stringResource(R.string.add_client_title),
        submitLabel = stringResource(R.string.add_client_submit),
        canSubmit = state.isValid,
        isSubmitting = state.isSaving,
        onSubmit = viewModel::submit,
        error = state.error,
        modifier = modifier,
    ) {
        NyayaTextField(
            value = state.name,
            onValueChange = viewModel::onNameChanged,
            label = stringResource(R.string.add_client_name),
            enabled = !state.isSaving,
        )

        NyayaTextField(
            value = state.phone,
            onValueChange = viewModel::onPhoneChanged,
            label = stringResource(R.string.add_client_phone),
            keyboardType = KeyboardType.Phone,
            enabled = !state.isSaving,
            helper = stringResource(R.string.add_client_phone_helper),
        )

        NyayaTextField(
            value = state.email,
            onValueChange = viewModel::onEmailChanged,
            label = stringResource(R.string.add_client_email),
            keyboardType = KeyboardType.Email,
            enabled = !state.isSaving,
        )

        NyayaTextField(
            value = state.address,
            onValueChange = viewModel::onAddressChanged,
            label = stringResource(R.string.add_client_address),
            singleLine = false,
            maxLines = 3,
            enabled = !state.isSaving,
        )

        NyayaTextField(
            value = state.notes,
            onValueChange = viewModel::onNotesChanged,
            label = stringResource(R.string.add_client_notes),
            singleLine = false,
            maxLines = 4,
            enabled = !state.isSaving,
        )
    }
}
