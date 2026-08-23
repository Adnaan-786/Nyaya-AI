package ai.nyayaai.feature.portal

import ai.nyayaai.core.common.UiState
import ai.nyayaai.core.common.formatLong
import ai.nyayaai.core.common.formatRupees
import ai.nyayaai.core.common.formatShort
import ai.nyayaai.core.designsystem.component.EmptyState
import ai.nyayaai.core.designsystem.component.ErrorState
import ai.nyayaai.core.designsystem.component.InitialAvatar
import ai.nyayaai.core.designsystem.component.LoadingList
import ai.nyayaai.core.designsystem.component.NyayaCard
import ai.nyayaai.core.designsystem.component.SectionHeader
import ai.nyayaai.core.designsystem.component.StatusBadge
import ai.nyayaai.core.designsystem.component.StatusTone
import ai.nyayaai.core.designsystem.component.animatedListEntry
import ai.nyayaai.core.designsystem.theme.NyayaTheme
import ai.nyayaai.core.model.CaseId
import ai.nyayaai.core.model.InvoiceStatus
import ai.nyayaai.core.network.mapper.PortalCase
import ai.nyayaai.core.network.mapper.PortalInvoice
import ai.nyayaai.core.model.InvoiceId
import ai.nyayaai.feature.billing.CheckoutLauncher
import ai.nyayaai.feature.billing.CheckoutRequest
import ai.nyayaai.feature.billing.PaymentState
import android.app.Activity
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarDuration
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.platform.LocalContext
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
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

/**
 * The whole of client mode: cases and bills. No AI, no vault, no team, no timers.
 *
 * The copy here is deliberately plain — "Next date" rather than "next hearing date",
 * "bills" rather than "invoices". The reader is the person the case is *about*, not a
 * lawyer, and legalese in a client-facing screen is a failure of the product.
 */
@Composable
fun PortalRoute(
    userName: String,
    onOpenCase: (CaseId) -> Unit,
    modifier: Modifier = Modifier,
    viewModel: PortalViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val payment by viewModel.paymentCoordinator.state.collectAsStateWithLifecycle()
    val message by viewModel.message.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(payment) {
        when (val current = payment) {
            is PaymentState.Verifying ->
                snackbarHostState.showSnackbar(
                    message = context.getString(R.string.portal_payment_verifying),
                    duration = SnackbarDuration.Indefinite,
                )

            is PaymentState.Settled -> {
                viewModel.load()
                viewModel.paymentCoordinator.clear()
            }

            is PaymentState.Failed ->
                snackbarHostState.showSnackbar(
                    message = current.message ?: context.getString(R.string.portal_payment_failed),
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

    Scaffold(
        modifier = modifier,
        snackbarHost = { SnackbarHost(snackbarHostState) },
    ) { padding ->
        when (state) {
            is UiState.Loading -> LoadingList(modifier = Modifier.padding(padding))

            is UiState.Error -> {
                val error = state as UiState.Error
                ErrorState(
                    message = error.message,
                    onRetry = viewModel::load.takeIf { error.retryable },
                    modifier = Modifier.padding(padding),
                )
            }

            is UiState.Empty -> EmptyState(title = (state as UiState.Empty).title, modifier = Modifier.padding(padding))

            is UiState.Content ->
                PortalContentList(
                    content = (state as UiState.Content<PortalContent>).data,
                    userName = userName,
                    onPay = { invoiceId ->
                        viewModel.pay(invoiceId) { order ->
                            CheckoutLauncher.start(
                                activity = context as Activity,
                                request = CheckoutRequest(
                                    keyId = order.keyId,
                                    orderId = order.orderId,
                                    amountPaise = order.amountPaise,
                                    invoiceNumber = (state as UiState.Content<PortalContent>).data.invoices.first { it.id == invoiceId }.number,
                                    firmName = userName,
                                ),
                            )
                        }
                    },
                    onOpenCase = onOpenCase,
                    modifier = Modifier.padding(padding),
                )
        }
    }
}

@Composable
private fun PortalContentList(
    content: PortalContent,
    userName: String,
    onPay: (InvoiceId) -> Unit,
    onOpenCase: (CaseId) -> Unit,
    modifier: Modifier = Modifier,
) {
    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = PaddingValues(NyayaTheme.spacing.md),
        verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.md),
    ) {
        item { SectionHeader(title = stringResource(R.string.portal_cases_title)) }

        if (content.cases.isEmpty()) {
            item {
                EmptyState(
                    title = stringResource(R.string.portal_no_cases),
                    description = stringResource(R.string.portal_no_cases_detail),
                )
            }
        } else {
            itemsIndexed(content.cases, key = { _, c -> c.id.value }) { index, case ->
                PortalCaseCard(
                    case,
                    onClick = { onOpenCase(case.id) },
                    modifier = Modifier.animatedListEntry(index),
                )
            }
        }

        item { SectionHeader(title = stringResource(R.string.portal_invoices_title)) }

        if (content.invoices.isEmpty()) {
            item { EmptyState(title = stringResource(R.string.portal_no_invoices)) }
        } else {
            itemsIndexed(content.invoices, key = { _, i -> i.id.value }) { index, invoice ->
                PortalInvoiceCard(invoice, onPay, modifier = Modifier.animatedListEntry(index))
            }
        }
    }
}

@Composable
private fun PortalCaseCard(
    case: PortalCase,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    NyayaCard(modifier = modifier, onClick = onClick) {
        Row(
            verticalAlignment = Alignment.Top,
            horizontalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.md),
        ) {
            InitialAvatar(name = case.title)

            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.xs),
            ) {
                Text(text = case.title, style = MaterialTheme.typography.titleSmall)

                case.courtName?.let {
                    Text(
                        text = it,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }

                Text(
                    text =
                        case.nextHearingDate
                            ?.let { stringResource(R.string.portal_next_hearing, it.formatLong()) }
                            ?: stringResource(R.string.portal_no_next_hearing),
                    style = MaterialTheme.typography.bodyMedium,
                )

                if (case.statusLabel.isNotBlank()) {
                    StatusBadge(text = case.statusLabel, tone = StatusTone.NEUTRAL)
                }
            }
        }
    }
}

@Composable
private fun PortalInvoiceCard(
    invoice: PortalInvoice,
    onPay: (InvoiceId) -> Unit,
    modifier: Modifier = Modifier,
) {
    NyayaCard(modifier = modifier) {
        Column(verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.xs)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(text = invoice.number, style = MaterialTheme.typography.titleSmall)
                Text(
                    text = invoice.totalPaise.formatRupees(),
                    style = MaterialTheme.typography.titleSmall,
                )
            }

            invoice.dueDate?.let {
                Text(
                    text = stringResource(R.string.portal_due, it.formatShort()),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            if (invoice.status == InvoiceStatus.PAID) {
                StatusBadge(
                    text = stringResource(R.string.portal_paid),
                    tone = StatusTone.POSITIVE,
                )
            } else {
                TextButton(onClick = { onPay(invoice.id) }) {
                    Text(stringResource(R.string.portal_pay))
                }
            }
        }
    }
}
