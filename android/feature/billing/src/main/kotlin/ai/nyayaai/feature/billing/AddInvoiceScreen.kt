package ai.nyayaai.feature.billing

import ai.nyayaai.core.designsystem.component.FormScaffold
import ai.nyayaai.core.designsystem.component.NyayaDropdownField
import ai.nyayaai.core.designsystem.component.NyayaMoneyField
import ai.nyayaai.core.designsystem.component.NyayaTextField
import ai.nyayaai.core.designsystem.theme.NyayaTheme
import ai.nyayaai.core.model.Case
import ai.nyayaai.core.model.CaseId
import ai.nyayaai.core.model.Client
import ai.nyayaai.core.model.ClientId
import ai.nyayaai.core.model.InvoiceId
import ai.nyayaai.core.network.api.ApiResult
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.hilt.navigation.compose.hiltViewModel
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

/** India's GST slabs — a fixed list rather than a server lookup, since these do not change. */
private val GST_RATES = listOf(0, 5, 12, 18, 28)

/**
 * B.5's invoice creation form. A client is mandatory (the server's `client_id` is
 * required); a case is optional, since not every billable engagement is tied to a
 * specific matter.
 */
data class AddInvoiceUiState(
    val clientId: ClientId? = null,
    val clients: List<Client> = emptyList(),
    val caseId: CaseId? = null,
    val cases: List<Case> = emptyList(),
    val lineItems: List<InvoiceLineItemInput> = listOf(InvoiceLineItemInput()),
    val gstRate: Int = 18,
    val reverseCharge: Boolean = false,
    val importUnbilledTime: Boolean = false,
    val isLoadingPickers: Boolean = true,
    val isSaving: Boolean = false,
    val error: String? = null,
    val createdInvoiceId: InvoiceId? = null,
) {
    // A blank description or a zero rate is a degenerate line the server would accept
    // (rate_paise >= 0) but that is never what the lawyer meant to bill.
    val isValid: Boolean
        get() =
            clientId != null &&
                lineItems.isNotEmpty() &&
                lineItems.all { it.description.isNotBlank() && it.ratePaise > 0 }
}

@HiltViewModel
class AddInvoiceViewModel
    @Inject
    constructor(
        private val repository: BillingRepository,
    ) : ViewModel() {
        private val _state = MutableStateFlow(AddInvoiceUiState())
        val state: StateFlow<AddInvoiceUiState> = _state.asStateFlow()

        init {
            loadPickers()
        }

        /**
         * Clients and cases load concurrently, same as [ai.nyayaai.feature.dashboard.TodayViewModel] —
         * a lawyer filling this in should not wait on one list before the other appears. A
         * picker failure surfaces as [AddInvoiceUiState.error] rather than blocking the
         * form: the fields below are still fillable, the user just sees why a dropdown
         * came up empty.
         */
        private fun loadPickers() {
            viewModelScope.launch {
                val clientsCall = async { repository.clients() }
                val casesCall = async { repository.cases() }
                val clientsResult = clientsCall.await()
                val casesResult = casesCall.await()

                val errors =
                    listOfNotNull(
                        (clientsResult as? ApiResult.Failure)?.error?.message,
                        (casesResult as? ApiResult.Failure)?.error?.message,
                    )

                _state.update {
                    it.copy(
                        clients = (clientsResult as? ApiResult.Success)?.data.orEmpty(),
                        cases = (casesResult as? ApiResult.Success)?.data.orEmpty(),
                        isLoadingPickers = false,
                        error = errors.firstOrNull(),
                    )
                }
            }
        }

        fun onClientSelected(id: ClientId) {
            _state.update { it.copy(clientId = id, error = null) }
        }

        fun onCaseSelected(id: CaseId?) {
            _state.update { it.copy(caseId = id, error = null) }
        }

        fun onGstRateChanged(rate: Int) {
            _state.update { it.copy(gstRate = rate, error = null) }
        }

        fun onReverseChargeChanged(value: Boolean) {
            _state.update { it.copy(reverseCharge = value, error = null) }
        }

        fun onImportUnbilledTimeChanged(value: Boolean) {
            _state.update { it.copy(importUnbilledTime = value, error = null) }
        }

        fun addLineItem() {
            _state.update { it.copy(lineItems = it.lineItems + InvoiceLineItemInput(), error = null) }
        }

        /** A no-op below one row: the server requires at least one line item. */
        fun removeLineItem(index: Int) {
            _state.update {
                if (it.lineItems.size <= 1) {
                    it
                } else {
                    it.copy(lineItems = it.lineItems.filterIndexed { i, _ -> i != index }, error = null)
                }
            }
        }

        fun updateLineItem(
            index: Int,
            updated: InvoiceLineItemInput,
        ) {
            _state.update {
                it.copy(
                    lineItems = it.lineItems.mapIndexed { i, line -> if (i == index) updated else line },
                    error = null,
                )
            }
        }

        fun save() {
            val current = _state.value
            if (!current.isValid || current.isSaving) return

            _state.update { it.copy(isSaving = true, error = null) }
            viewModelScope.launch {
                when (
                    val result =
                        repository.createInvoice(
                            clientId = checkNotNull(current.clientId),
                            caseId = current.caseId,
                            lineItems = current.lineItems,
                            gstRate = current.gstRate,
                            reverseCharge = current.reverseCharge,
                            importUnbilledTime = current.importUnbilledTime,
                        )
                ) {
                    is ApiResult.Success ->
                        _state.update { it.copy(isSaving = false, createdInvoiceId = result.data.id) }

                    is ApiResult.Failure ->
                        _state.update { it.copy(isSaving = false, error = result.error.message) }
                }
            }
        }
    }

@Composable
fun AddInvoiceRoute(
    onInvoiceCreated: (InvoiceId) -> Unit,
    modifier: Modifier = Modifier,
    viewModel: AddInvoiceViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    LaunchedEffect(state.createdInvoiceId) {
        state.createdInvoiceId?.let(onInvoiceCreated)
    }

    val noCaseLabel = stringResource(R.string.billing_add_no_case)

    FormScaffold(
        title = stringResource(R.string.billing_add_title),
        submitLabel = stringResource(R.string.billing_add_submit),
        canSubmit = state.isValid,
        isSubmitting = state.isSaving,
        onSubmit = viewModel::save,
        modifier = modifier,
        error = state.error,
    ) {
        NyayaDropdownField(
            value = state.clients.find { it.id == state.clientId },
            options = state.clients,
            onSelect = { viewModel.onClientSelected(it.id) },
            label = stringResource(R.string.billing_add_client),
            optionLabel = { it.name },
            enabled = !state.isLoadingPickers,
        )

        // The dropdown's own text field shows a blank when [value] is null, same as any
        // other cleared field — the synthetic "No case" row only needs to exist in the
        // menu so the user has something to tap to get back to that cleared state.
        NyayaDropdownField(
            value = state.cases.find { it.id == state.caseId },
            options = listOf<Case?>(null) + state.cases,
            onSelect = { viewModel.onCaseSelected(it?.id) },
            label = stringResource(R.string.billing_add_case),
            optionLabel = { it?.title ?: noCaseLabel },
            enabled = !state.isLoadingPickers,
        )

        NyayaDropdownField(
            value = state.gstRate,
            options = GST_RATES,
            onSelect = viewModel::onGstRateChanged,
            label = stringResource(R.string.billing_add_gst_rate),
            optionLabel = { "$it%" },
        )

        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Checkbox(checked = state.reverseCharge, onCheckedChange = viewModel::onReverseChargeChanged)
            Text(stringResource(R.string.billing_add_reverse_charge))
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Checkbox(checked = state.importUnbilledTime, onCheckedChange = viewModel::onImportUnbilledTimeChanged)
            Text(stringResource(R.string.billing_add_import_unbilled))
        }

        Text(
            text = stringResource(R.string.billing_line_items),
            style = MaterialTheme.typography.titleSmall,
        )

        state.lineItems.forEachIndexed { index, line ->
            LineItemFields(
                line = line,
                canRemove = state.lineItems.size > 1,
                onChange = { viewModel.updateLineItem(index, it) },
                onRemove = { viewModel.removeLineItem(index) },
            )
        }

        OutlinedButton(onClick = viewModel::addLineItem, modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(R.string.billing_add_line_item))
        }
    }
}

@Composable
private fun LineItemFields(
    line: InvoiceLineItemInput,
    canRemove: Boolean,
    onChange: (InvoiceLineItemInput) -> Unit,
    onRemove: () -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.xs)) {
        NyayaTextField(
            value = line.description,
            onValueChange = { onChange(line.copy(description = it)) },
            label = stringResource(R.string.billing_add_line_description),
        )

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.sm),
        ) {
            NyayaTextField(
                value = if (line.quantity == 0) "" else line.quantity.toString(),
                onValueChange = { input ->
                    val digitsOnly = input.filter(Char::isDigit)
                    onChange(line.copy(quantity = digitsOnly.toIntOrNull() ?: 0))
                },
                label = stringResource(R.string.billing_add_line_quantity),
                keyboardType = KeyboardType.Number,
                modifier = Modifier.weight(1f),
            )

            NyayaMoneyField(
                paise = line.ratePaise,
                onValueChange = { onChange(line.copy(ratePaise = it)) },
                label = stringResource(R.string.billing_add_line_rate),
                modifier = Modifier.weight(1f),
            )
        }

        TextButton(onClick = onRemove, enabled = canRemove) {
            Text(stringResource(R.string.billing_add_line_remove))
        }
    }
}
