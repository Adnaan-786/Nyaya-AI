package ai.nyayaai.feature.billing

import ai.nyayaai.core.common.UiState
import ai.nyayaai.core.common.formatRupees
import ai.nyayaai.core.common.formatShort
import ai.nyayaai.core.designsystem.component.EmptyState
import ai.nyayaai.core.designsystem.component.ErrorState
import ai.nyayaai.core.designsystem.component.LoadingList
import ai.nyayaai.core.designsystem.component.NyayaCard
import ai.nyayaai.core.designsystem.component.StatusBadge
import ai.nyayaai.core.designsystem.component.StatusTone
import ai.nyayaai.core.designsystem.theme.NyayaTheme
import ai.nyayaai.core.model.Invoice
import ai.nyayaai.core.model.InvoiceId
import ai.nyayaai.core.model.InvoiceLineItem
import ai.nyayaai.core.model.InvoiceStatus
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
import androidx.compose.material3.Button
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
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

@HiltViewModel
class InvoiceDetailViewModel
    @Inject
    constructor(
        private val repository: BillingRepository,
        savedStateHandle: SavedStateHandle,
    ) : ViewModel() {
        private val invoiceId = InvoiceId(checkNotNull(savedStateHandle.get<String>(ARG_INVOICE_ID)))

        private val _state = MutableStateFlow<UiState<Invoice>>(UiState.Loading)
        val state: StateFlow<UiState<Invoice>> = _state.asStateFlow()

        init {
            load()
        }

        fun load() {
            viewModelScope.launch {
                _state.value = UiState.Loading
                _state.value =
                    when (val result = repository.invoice(invoiceId)) {
                        is ApiResult.Failure ->
                            UiState.Error(result.error.message, result.error.isRetryable)

                        is ApiResult.Success -> UiState.Content(result.data)
                    }
            }
        }

        companion object {
            const val ARG_INVOICE_ID = "invoiceId"
        }
    }

/**
 * B.5's single-invoice view — opened from a row on [InvoiceListRoute]. [onOpenPdf] hands
 * back the invoice's `pdfUrl` rather than opening it itself: this module has no opinion on
 * how an external URL is launched, and wiring that to the app's actual opener happens in a
 * later navigation step.
 */
@Composable
fun InvoiceDetailRoute(
    onOpenPdf: (String) -> Unit,
    modifier: Modifier = Modifier,
    viewModel: InvoiceDetailViewModel = hiltViewModel(),
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
            InvoiceDetailContent(
                invoice = (state as UiState.Content<Invoice>).data,
                onOpenPdf = onOpenPdf,
                modifier = modifier,
            )
    }
}

@Composable
private fun InvoiceDetailContent(
    invoice: Invoice,
    onOpenPdf: (String) -> Unit,
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
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(text = invoice.number, style = MaterialTheme.typography.titleMedium)
                        StatusBadge(
                            text = stringResource(invoice.status.labelRes()),
                            tone = invoice.status.tone(),
                        )
                    }

                    invoice.dueDate?.let {
                        Text(
                            text = stringResource(R.string.billing_due, it.formatShort()),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
        }

        item {
            Text(
                text = stringResource(R.string.billing_line_items),
                style = MaterialTheme.typography.titleSmall,
            )
        }

        itemsIndexed(invoice.lineItems, key = { index, _ -> index }) { _, line ->
            LineItemCard(line)
        }

        item {
            NyayaCard {
                Column(verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.xs)) {
                    AmountRow(stringResource(R.string.billing_subtotal), invoice.subtotalPaise.formatRupees())

                    // Same reverse-charge handling as InvoiceCard on the list screen: a
                    // zero GST line with a non-zero rate means the recipient owes the tax,
                    // not that the invoice is somehow GST-free.
                    if (invoice.gstPaise.isZero && invoice.gstRate > 0) {
                        Text(
                            text = stringResource(R.string.billing_reverse_charge),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    } else {
                        AmountRow(
                            stringResource(R.string.billing_gst, invoice.gstRate),
                            invoice.gstPaise.formatRupees(),
                        )
                    }

                    HorizontalDivider(modifier = Modifier.padding(vertical = NyayaTheme.spacing.xs))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                    ) {
                        Text(
                            text = stringResource(R.string.billing_total),
                            style = MaterialTheme.typography.titleSmall,
                        )
                        Text(
                            text = invoice.totalPaise.formatRupees(),
                            style = MaterialTheme.typography.titleSmall,
                        )
                    }
                }
            }
        }

        invoice.pdfUrl?.let { url ->
            item {
                Button(
                    onClick = { onOpenPdf(url) },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(stringResource(R.string.billing_view_pdf))
                }
            }
        }
    }
}

@Composable
private fun LineItemCard(line: InvoiceLineItem) {
    NyayaCard {
        Column(verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.xs)) {
            Text(text = line.description, style = MaterialTheme.typography.bodyMedium)
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Text(
                    text =
                        stringResource(
                            R.string.billing_line_item_quantity_rate,
                            line.quantity,
                            line.ratePaise.formatRupees(),
                        ),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(text = line.amountPaise.formatRupees(), style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}

@Composable
private fun AmountRow(
    label: String,
    amount: String,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(text = amount, style = MaterialTheme.typography.bodyMedium)
    }
}

// Duplicated from InvoiceListScreen.kt rather than shared: both functions are ~12 lines
// and `private`, and this module otherwise has no cross-file "shared internals" convention
// to hang them on — a little repetition here beats fighting Kotlin file visibility.
private fun InvoiceStatus.labelRes(): Int =
    when (this) {
        InvoiceStatus.DRAFT -> R.string.billing_status_draft
        InvoiceStatus.SENT -> R.string.billing_status_sent
        InvoiceStatus.PAID -> R.string.billing_status_paid
        InvoiceStatus.OVERDUE -> R.string.billing_status_overdue
        InvoiceStatus.UNKNOWN -> R.string.billing_status_unknown
    }

private fun InvoiceStatus.tone(): StatusTone =
    when (this) {
        InvoiceStatus.PAID -> StatusTone.POSITIVE
        InvoiceStatus.OVERDUE -> StatusTone.NEGATIVE
        InvoiceStatus.SENT -> StatusTone.NEUTRAL
        InvoiceStatus.DRAFT, InvoiceStatus.UNKNOWN -> StatusTone.NEUTRAL
    }
