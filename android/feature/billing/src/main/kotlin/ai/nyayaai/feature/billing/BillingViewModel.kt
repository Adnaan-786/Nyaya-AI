package ai.nyayaai.feature.billing

import ai.nyayaai.core.common.UiState
import ai.nyayaai.core.model.Case
import ai.nyayaai.core.model.CaseId
import ai.nyayaai.core.model.Client
import ai.nyayaai.core.model.ClientId
import ai.nyayaai.core.model.Invoice
import ai.nyayaai.core.model.InvoiceId
import ai.nyayaai.core.network.api.ApiCaller
import ai.nyayaai.core.network.api.ApiResult
import ai.nyayaai.core.network.api.isRetryable
import ai.nyayaai.core.network.api.map
import ai.nyayaai.core.network.dto.InvoiceCreateDto
import ai.nyayaai.core.network.dto.InvoiceLineItemDto
import ai.nyayaai.core.network.dto.PaymentOrderRequestDto
import ai.nyayaai.core.network.dto.PaymentVerifyRequestDto
import ai.nyayaai.core.network.mapper.toDomain
import ai.nyayaai.core.network.service.BillingService
import ai.nyayaai.core.network.service.CaseService
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject
import javax.inject.Singleton

data class PaymentOrder(
    val orderId: String,
    val amountPaise: Long,
    val keyId: String,
)

/**
 * A line item as the creation form collects it — deliberately not the domain
 * [ai.nyayaai.core.model.InvoiceLineItem], which carries an `amountPaise` the server
 * computes and a lawyer never types. Keeping this as its own feature-local shape means
 * the form never has to invent a fake amount just to satisfy a type built for
 * *displaying* an already-priced line.
 */
data class InvoiceLineItemInput(
    val description: String = "",
    val quantity: Int = 1,
    val ratePaise: Long = 0,
)

@Singleton
class BillingRepository
    @Inject
    constructor(
        private val service: BillingService,
        // Client and case pickers for the creation form live on CaseService, same as
        // ClientRepository in feature:clients — feature modules never depend on each
        // other, so each injects its own slice of the shared core:network service.
        private val caseService: CaseService,
        private val caller: ApiCaller,
    ) {
        suspend fun invoices(status: String? = null): ApiResult<List<Invoice>> =
            caller.call { service.invoices(status = status) }.map { list -> list.map { it.toDomain() } }

        suspend fun invoice(id: InvoiceId): ApiResult<Invoice> =
            caller.call { service.invoice(id.value) }.map { it.toDomain() }

        suspend fun send(id: InvoiceId): ApiResult<Invoice> =
            caller.call { service.sendInvoice(id.value) }.map { it.toDomain() }

        /**
         * B.5/B.6 pickers for the creation form. The server computes `amount_paise`
         * itself, so [InvoiceLineItemInput] rows never carry one — leaving the DTO's
         * `amountPaise` at its default omits it from the request body entirely.
         */
        suspend fun createInvoice(
            clientId: ClientId,
            caseId: CaseId?,
            lineItems: List<InvoiceLineItemInput>,
            gstRate: Int,
            reverseCharge: Boolean,
            importUnbilledTime: Boolean,
        ): ApiResult<Invoice> =
            caller
                .call {
                    service.createInvoice(
                        InvoiceCreateDto(
                            clientId = clientId.value,
                            caseId = caseId?.value,
                            lineItems =
                                lineItems.map {
                                    InvoiceLineItemDto(
                                        description = it.description,
                                        quantity = it.quantity,
                                        ratePaise = it.ratePaise,
                                    )
                                },
                            gstRate = gstRate,
                            importUnbilledTime = importUnbilledTime,
                            reverseCharge = reverseCharge,
                        ),
                    )
                }.map { it.toDomain() }

        suspend fun clients(): ApiResult<List<Client>> =
            caller.call { caseService.clients() }.map { list -> list.map { it.toDomain() } }

        suspend fun cases(): ApiResult<List<Case>> =
            caller.call { caseService.cases() }.map { list -> list.map { it.toDomain() } }

        /** B.10 step 2 — hands the Checkout SDK exactly what it needs and nothing more. */
        suspend fun createOrder(id: InvoiceId): ApiResult<PaymentOrder> =
            caller.call { service.createOrder(PaymentOrderRequestDto(id.value)) }.map { dto ->
                PaymentOrder(
                    orderId = dto.razorpayOrderId.orEmpty(),
                    amountPaise = dto.amountPaise,
                    keyId = dto.keyId.orEmpty(),
                )
            }

        /**
         * B.10 step 4. Returns the **invoice status decided by the server**, never the
         * SDK's own success flag: the app is explicitly told to treat the server as truth,
         * because a client that marks its own invoices paid is a client that can be lied to.
         */
        suspend fun verifyPayment(
            orderId: String,
            paymentId: String,
            signature: String,
        ): ApiResult<String> =
            caller
                .call { service.verifyPayment(PaymentVerifyRequestDto(orderId, paymentId, signature)) }
                .map { it.invoiceStatus.orEmpty() }
    }

@HiltViewModel
class InvoiceListViewModel
    @Inject
    constructor(
        private val repository: BillingRepository,
        val paymentCoordinator: PaymentCoordinator,
    ) : ViewModel() {
        private val _state = MutableStateFlow<UiState<List<Invoice>>>(UiState.Loading)
        val state: StateFlow<UiState<List<Invoice>>> = _state.asStateFlow()

        private val _message = MutableStateFlow<String?>(null)
        val message: StateFlow<String?> = _message.asStateFlow()

        init {
            load()
        }

        fun load() {
            viewModelScope.launch {
                _state.value = UiState.Loading
                _state.value =
                    when (val result = repository.invoices()) {
                        is ApiResult.Failure ->
                            UiState.Error(result.error.message, result.error.isRetryable)

                        is ApiResult.Success -> UiState.Content(result.data)
                    }
            }
        }

        fun send(id: InvoiceId) {
            viewModelScope.launch {
                when (val result = repository.send(id)) {
                    is ApiResult.Success -> load()
                    is ApiResult.Failure -> _message.value = result.error.message
                }
            }
        }

        fun clearMessage() {
            _message.value = null
        }

        /**
         * B.10 steps 2-3: the **server** creates the order, and Checkout is handed that
         * order id. The app never invents an amount — the one Razorpay charges is the
         * one the server put on the order.
         */
        fun pay(
            invoice: Invoice,
            onReady: (PaymentOrder) -> Unit,
        ) {
            viewModelScope.launch {
                when (val order = repository.createOrder(invoice.id)) {
                    is ApiResult.Success -> {
                        paymentCoordinator.beginning(invoice.id, order.data.orderId)
                        onReady(order.data)
                    }

                    is ApiResult.Failure -> _message.value = order.error.message
                }
            }
        }
    }
