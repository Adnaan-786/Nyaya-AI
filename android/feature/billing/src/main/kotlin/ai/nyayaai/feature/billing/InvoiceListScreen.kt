package ai.nyayaai.feature.billing

import ai.nyayaai.core.common.UiState
import ai.nyayaai.core.common.formatRupees
import ai.nyayaai.core.common.formatShort
import ai.nyayaai.core.designsystem.component.EmptyState
import ai.nyayaai.core.designsystem.component.ErrorState
import ai.nyayaai.core.designsystem.component.HeroAmount
import ai.nyayaai.core.designsystem.component.LoadingList
import ai.nyayaai.core.designsystem.component.NyayaCard
import ai.nyayaai.core.designsystem.component.StatusBadge
import ai.nyayaai.core.designsystem.component.StatusTone
import ai.nyayaai.core.designsystem.component.animatedListEntry
import ai.nyayaai.core.designsystem.theme.NyayaTheme
import ai.nyayaai.core.model.Invoice
import ai.nyayaai.core.model.InvoiceId
import ai.nyayaai.core.model.InvoiceStatus
import ai.nyayaai.core.model.sum
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
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarDuration
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle

@Composable
fun InvoiceListRoute(
    firmName: String,
    onOpenInvoice: (InvoiceId) -> Unit,
    onAddInvoice: () -> Unit,
    modifier: Modifier = Modifier,
    viewModel: InvoiceListViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val payment by viewModel.paymentCoordinator.state.collectAsStateWithLifecycle()
    val message by viewModel.message.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val snackbarHostState = remember { SnackbarHostState() }

    // Keyed on `payment` so a state change (e.g. Verifying -> Settled) cancels whatever
    // this coroutine was doing before — an indefinite "Verifying…" snackbar is dismissed
    // for free the moment the server actually decides, no manual bookkeeping needed.
    LaunchedEffect(payment) {
        when (val current = payment) {
            is PaymentState.Verifying ->
                snackbarHostState.showSnackbar(
                    message = context.getString(R.string.billing_payment_verifying),
                    duration = SnackbarDuration.Indefinite,
                )

            // The list refreshes when the server settles a payment, so the status badge
            // shows what the server decided rather than what Checkout claimed.
            is PaymentState.Settled -> {
                viewModel.load()
                viewModel.paymentCoordinator.clear()
            }

            is PaymentState.Failed ->
                snackbarHostState.showSnackbar(
                    message = current.message ?: context.getString(R.string.billing_payment_failed),
                    duration = SnackbarDuration.Long,
                )

            PaymentState.Idle, PaymentState.InProgress -> Unit
        }
    }

    LaunchedEffect(message) {
        message?.let {
            snackbarHostState.showSnackbar(message = it, duration = SnackbarDuration.Short)
            viewModel.clearMessage()
        }
    }

    // The FAB lives at the Scaffold level, present in every state — a lawyer with zero
    // invoices, or whose list failed to load, still needs a way to create the first one.
    Scaffold(
        modifier = modifier,
        snackbarHost = { SnackbarHost(snackbarHostState) },
        floatingActionButton = {
            FloatingActionButton(onClick = onAddInvoice) {
                Icon(
                    imageVector = Icons.Filled.Add,
                    contentDescription = stringResource(R.string.billing_add_title),
                )
            }
        },
    ) { innerPadding ->
        val contentModifier = Modifier.padding(innerPadding)

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
                val invoices = (state as UiState.Content<List<Invoice>>).data
                if (invoices.isEmpty()) {
                    EmptyState(
                        title = stringResource(R.string.billing_empty_title),
                        description = stringResource(R.string.billing_empty_detail),
                        modifier = contentModifier,
                    )
                } else {
                    LazyColumn(
                        modifier = contentModifier.fillMaxSize(),
                        contentPadding =
                            PaddingValues(
                                start = NyayaTheme.spacing.md,
                                end = NyayaTheme.spacing.md,
                                top = NyayaTheme.spacing.md,
                                // Clears the FAB, which floats over this list rather than beside it.
                                bottom = NyayaTheme.spacing.fabClearance,
                            ),
                        verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.sm),
                    ) {
                        item { OutstandingHeader(invoices) }

                        itemsIndexed(invoices, key = { _, item -> item.id.value }) { index, invoice ->
                            InvoiceCard(
                                invoice = invoice,
                                onOpen = onOpenInvoice,
                                onSend = { viewModel.send(it) },
                                onPay = { target ->
                                    val activity = context.findActivity() ?: return@InvoiceCard
                                    viewModel.pay(target) { order ->
                                        CheckoutLauncher.start(
                                            activity = activity,
                                            request =
                                                CheckoutRequest(
                                                    keyId = order.keyId,
                                                    orderId = order.orderId,
                                                    amountPaise = order.amountPaise,
                                                    invoiceNumber = target.number,
                                                    firmName = firmName,
                                                ),
                                        )
                                    }
                                },
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
private fun InvoiceCard(
    invoice: Invoice,
    onOpen: (InvoiceId) -> Unit,
    onSend: (InvoiceId) -> Unit,
    onPay: (Invoice) -> Unit,
    modifier: Modifier = Modifier,
) {
    NyayaCard(modifier = modifier, onClick = { onOpen(invoice.id) }) {
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

            when (invoice.status) {
                InvoiceStatus.DRAFT ->
                    TextButton(onClick = { onSend(invoice.id) }) {
                        Text(stringResource(R.string.billing_send))
                    }

                // Paid invoices offer nothing: the money is in, and B.10 makes the
                // server the only thing that can say so.
                InvoiceStatus.SENT, InvoiceStatus.OVERDUE ->
                    TextButton(onClick = { onPay(invoice) }) {
                        Text(stringResource(R.string.billing_pay))
                    }

                InvoiceStatus.PAID, InvoiceStatus.UNKNOWN -> Unit
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
        InvoiceStatus.UNKNOWN -> R.string.billing_status_unknown
    }

private fun InvoiceStatus.tone(): StatusTone =
    when (this) {
        InvoiceStatus.PAID -> StatusTone.POSITIVE
        InvoiceStatus.OVERDUE -> StatusTone.NEGATIVE
        InvoiceStatus.SENT -> StatusTone.NEUTRAL
        InvoiceStatus.DRAFT, InvoiceStatus.UNKNOWN -> StatusTone.NEUTRAL
    }

/** Razorpay Checkout needs the hosting Activity, which a composable only sees through
 *  its Context chain. */
private fun android.content.Context.findActivity(): android.app.Activity? {
    var current = this
    while (current is android.content.ContextWrapper) {
        if (current is android.app.Activity) return current
        current = current.baseContext
    }
    return null
}

/**
 * What a lawyer opens billing to find out, answered before they read a single row.
 *
 * Outstanding deliberately excludes drafts as well as paid invoices: a draft is money
 * not yet asked for, and counting it would overstate what is actually owed.
 */
@Composable
private fun OutstandingHeader(
    invoices: List<Invoice>,
    modifier: Modifier = Modifier,
) {
    val unpaid =
        invoices.filter { it.status != InvoiceStatus.PAID && it.status != InvoiceStatus.DRAFT }
    val overdue = invoices.count { it.status == InvoiceStatus.OVERDUE }

    HeroAmount(
        label = stringResource(R.string.billing_outstanding),
        value = unpaid.map { it.totalPaise }.sum().formatRupees(),
        caption = pluralStringResource(R.plurals.billing_awaiting, overdue, overdue),
        modifier = modifier.padding(vertical = NyayaTheme.spacing.md),
    )
}
