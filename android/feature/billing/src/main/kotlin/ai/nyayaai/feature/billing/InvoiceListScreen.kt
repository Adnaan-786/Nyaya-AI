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
import ai.nyayaai.core.designsystem.component.animatedListEntry
import ai.nyayaai.core.designsystem.theme.NyayaTheme
import ai.nyayaai.core.model.Invoice
import ai.nyayaai.core.model.InvoiceId
import ai.nyayaai.core.model.InvoiceStatus
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle

@Composable
fun InvoiceListRoute(
    modifier: Modifier = Modifier,
    viewModel: InvoiceListViewModel = hiltViewModel(),
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
            val invoices = (state as UiState.Content<List<Invoice>>).data
            if (invoices.isEmpty()) {
                EmptyState(
                    title = stringResource(R.string.billing_empty_title),
                    description = stringResource(R.string.billing_empty_detail),
                    modifier = modifier,
                )
            } else {
                LazyColumn(
                    modifier = modifier.fillMaxSize(),
                    contentPadding = PaddingValues(NyayaTheme.spacing.md),
                    verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.sm),
                ) {
                    itemsIndexed(invoices, key = { _, item -> item.id.value }) { index, invoice ->
                        InvoiceCard(
                            invoice = invoice,
                            onSend = { viewModel.send(it) },
                            modifier = Modifier.animatedListEntry(index),
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun InvoiceCard(
    invoice: Invoice,
    onSend: (InvoiceId) -> Unit,
    modifier: Modifier = Modifier,
) {
    NyayaCard(modifier = modifier) {
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

            HorizontalDivider(modifier = Modifier.padding(vertical = NyayaTheme.spacing.xs))

            AmountRow(stringResource(R.string.billing_subtotal), invoice.subtotalPaise.formatRupees())

            // A zero GST line with a non-zero rate is the reverse charge case: the
            // advocate charges no GST and the client's accounts team needs to see why.
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

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Text(
                    text = stringResource(R.string.billing_total),
                    style = MaterialTheme.typography.titleSmall,
                )
                Text(
                    // Indian grouping: 1,50,000.00 rather than 150,000.00. Formatted from
                    // integer paise, so what shows here is exactly what the PDF prints.
                    text = invoice.totalPaise.formatRupees(),
                    style = MaterialTheme.typography.titleSmall,
                )
            }

            if (invoice.status == InvoiceStatus.DRAFT) {
                TextButton(onClick = { onSend(invoice.id) }) {
                    Text(stringResource(R.string.billing_send))
                }
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

private fun InvoiceStatus.labelRes(): Int =
    when (this) {
        InvoiceStatus.DRAFT -> R.string.billing_status_draft
        InvoiceStatus.SENT -> R.string.billing_status_sent
        InvoiceStatus.PAID -> R.string.billing_status_paid
        InvoiceStatus.OVERDUE -> R.string.billing_status_overdue
        InvoiceStatus.UNKNOWN -> R.string.billing_status_draft
    }

private fun InvoiceStatus.tone(): StatusTone =
    when (this) {
        InvoiceStatus.PAID -> StatusTone.POSITIVE
        InvoiceStatus.OVERDUE -> StatusTone.NEGATIVE
        InvoiceStatus.SENT -> StatusTone.NEUTRAL
        InvoiceStatus.DRAFT, InvoiceStatus.UNKNOWN -> StatusTone.NEUTRAL
    }
