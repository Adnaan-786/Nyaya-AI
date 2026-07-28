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
import ai.nyayaai.core.model.InvoiceStatus
import ai.nyayaai.core.network.mapper.PortalCase
import ai.nyayaai.core.network.mapper.PortalInvoice
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
    onPay: (String) -> Unit,
    modifier: Modifier = Modifier,
    viewModel: PortalViewModel = hiltViewModel(),
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
            PortalContentList((state as UiState.Content<PortalContent>).data, onPay, modifier)
    }
}

@Composable
private fun PortalContentList(
    content: PortalContent,
    onPay: (String) -> Unit,
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
                PortalCaseCard(case, modifier = Modifier.animatedListEntry(index))
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
    modifier: Modifier = Modifier,
) {
    NyayaCard(modifier = modifier) {
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
    onPay: (String) -> Unit,
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
                invoice.paymentLink?.let { link ->
                    TextButton(onClick = { onPay(link) }) {
                        Text(stringResource(R.string.portal_pay))
                    }
                }
            }
        }
    }
}
