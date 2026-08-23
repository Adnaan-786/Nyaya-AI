package ai.nyayaai.feature.portal

import ai.nyayaai.core.model.InvoiceId
import ai.nyayaai.feature.billing.BillingRepository
import ai.nyayaai.feature.billing.PaymentCoordinator
import ai.nyayaai.feature.billing.PaymentOrder
import ai.nyayaai.core.common.UiState
import ai.nyayaai.core.model.CaseId
import ai.nyayaai.core.network.api.ApiCaller
import ai.nyayaai.core.network.api.ApiResult
import ai.nyayaai.core.network.api.isRetryable
import ai.nyayaai.core.network.api.map
import ai.nyayaai.core.network.mapper.PortalCase
import ai.nyayaai.core.network.mapper.PortalInvoice
import ai.nyayaai.core.network.mapper.toDomain
import ai.nyayaai.core.network.service.PortalService
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class PortalRepository
    @Inject
    constructor(
        private val service: PortalService,
        private val caller: ApiCaller,
    ) {
        suspend fun cases(): ApiResult<List<PortalCase>> =
            caller.call { service.cases() }.map { list -> list.map { it.toDomain() } }

        suspend fun invoices(): ApiResult<List<PortalInvoice>> =
            caller.call { service.invoices() }.map { list -> list.map { it.toDomain() } }

        suspend fun case(id: CaseId): ApiResult<PortalCase> =
            caller.call { service.case(id.value) }.map { it.toDomain() }
    }

data class PortalContent(
    val cases: List<PortalCase>,
    val invoices: List<PortalInvoice>,
)


/**
 * D.10 client mode.
 *
 * This ViewModel talks only to the portal endpoints. It has no access to the case,
 * document or AI
 * repositories at all — the server enforces the boundary, and building client mode out of
 * separate types means a staff endpoint cannot be called here even by mistake.
 */
@HiltViewModel
class PortalViewModel
    @Inject
    constructor(
        private val repository: PortalRepository,
        private val billingRepository: BillingRepository,
        val paymentCoordinator: PaymentCoordinator,
    ) : ViewModel() {
        private val _state = MutableStateFlow<UiState<PortalContent>>(UiState.Loading)
        val state: StateFlow<UiState<PortalContent>> = _state.asStateFlow()

        private val _message = MutableStateFlow<String?>(null)
        val message: StateFlow<String?> = _message.asStateFlow()

        init {
            load()
        }

        fun load() {
            viewModelScope.launch {
                _state.value = UiState.Loading

                val casesCall = async { repository.cases() }
                val invoicesCall = async { repository.invoices() }

                _state.value =
                    when (val cases = casesCall.await()) {
                        is ApiResult.Failure ->
                            UiState.Error(cases.error.message, cases.error.isRetryable)

                        is ApiResult.Success ->
                            UiState.Content(
                                PortalContent(
                                    cases = cases.data,
                                    invoices = (invoicesCall.await() as? ApiResult.Success)?.data.orEmpty(),
                                ),
                            )
                    }
            }
        }

        fun clearMessage() {
            _message.value = null
        }

        fun pay(
            invoiceId: InvoiceId,
            onReady: (PaymentOrder) -> Unit,
        ) {
            viewModelScope.launch {
                when (val order = billingRepository.createOrder(invoiceId)) {
                    is ApiResult.Success -> {
                        paymentCoordinator.beginning(invoiceId, order.data.orderId)
                        onReady(order.data)
                    }
                    is ApiResult.Failure -> _message.value = order.error.message
                }
            }
        }
    }
