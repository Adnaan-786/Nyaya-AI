package ai.nyayaai.feature.billing

import ai.nyayaai.core.model.InvoiceId
import ai.nyayaai.core.network.api.ApiResult
import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Bridges Razorpay Checkout's Activity-level callback back to whichever screen started
 * the payment.
 *
 * The SDK reports its result to the **Activity**, not to the composable that launched it,
 * so something outside the composition has to hold the in-flight payment. This is that
 * something.
 *
 * The important rule it enforces is B.10's: a Checkout "success" is only a *claim*. It
 * is forwarded to `POST /payments/verify`, and the invoice status the **server** returns
 * is what the UI shows. The SDK's own result never marks anything paid.
 */
@Singleton
class PaymentCoordinator
    @Inject
    constructor(
        private val repository: BillingRepository,
    ) {
        private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)

        private val _state = MutableStateFlow<PaymentState>(PaymentState.Idle)
        val state: StateFlow<PaymentState> = _state.asStateFlow()

        private var pending: PendingPayment? = null

        fun beginning(
            invoiceId: InvoiceId,
            orderId: String,
        ) {
            pending = PendingPayment(invoiceId, orderId)
            _state.value = PaymentState.InProgress
        }

        /** Called from the Activity's `onPaymentSuccess`. */
        fun onCheckoutSuccess(
            razorpayPaymentId: String?,
            signature: String?,
        ) {
            val inFlight = pending
            if (inFlight == null || razorpayPaymentId == null || signature == null) {
                _state.value = PaymentState.Failed(null)
                return
            }

            _state.value = PaymentState.Verifying
            scope.launch {
                val verified =
                    repository.verifyPayment(
                        orderId = inFlight.orderId,
                        paymentId = razorpayPaymentId,
                        signature = signature,
                    )

                _state.value =
                    when (verified) {
                        // The server's invoice status, not the SDK's word.
                        is ApiResult.Success -> PaymentState.Settled(verified.data)
                        is ApiResult.Failure -> PaymentState.Failed(verified.error.message)
                    }
                pending = null
            }
        }

        /** Called from the Activity's `onPaymentError`. */
        fun onCheckoutFailure(description: String?) {
            Log.i(TAG, "checkout did not complete: $description")
            pending = null
            // A cancelled payment is not an error worth shouting about — the user chose
            // to back out, and the invoice is simply still unpaid.
            _state.value = PaymentState.Idle
        }

        fun clear() {
            _state.value = PaymentState.Idle
        }

        private data class PendingPayment(
            val invoiceId: InvoiceId,
            val orderId: String,
        )

        private companion object {
            const val TAG = "PaymentCoordinator"
        }
    }

sealed interface PaymentState {
    data object Idle : PaymentState

    data object InProgress : PaymentState

    /** Checkout returned; the server is verifying the signature. */
    data object Verifying : PaymentState

    /** Carries the invoice status the server decided on — "paid", or something else. */
    data class Settled(
        val invoiceStatus: String,
    ) : PaymentState

    data class Failed(
        val message: String?,
    ) : PaymentState
}
