package ai.nyayaai.feature.billing

import android.app.Activity
import android.util.Log
import com.razorpay.Checkout
import org.json.JSONObject

/**
 * B.10 step 3 — hands the Razorpay Checkout SDK an order the **server** created.
 *
 * The app never computes an amount and never decides an invoice is paid. It passes the
 * server's `order_id` to Checkout, and whatever Checkout reports comes straight back to
 * `POST /payments/verify` for the server to verify the signature itself. A client that
 * can mark its own invoices paid is a client that can be lied to.
 */
object CheckoutLauncher {
    private const val TAG = "Checkout"
    private const val CURRENCY = "INR"

    fun start(
        activity: Activity,
        request: CheckoutRequest,
    ) {
        val checkout = Checkout()
        checkout.setKeyID(request.keyId)

        val options =
            JSONObject().apply {
                put("name", request.firmName)
                put("description", "Invoice ${request.invoiceNumber}")
                // Razorpay's own unit is paise, which is why nothing in this codebase
                // ever converts money to a decimal.
                put("amount", request.amountPaise)
                put("currency", CURRENCY)
                put("order_id", request.orderId)
                put("send_sms_hash", true)
                put(
                    "prefill",
                    JSONObject().apply {
                        request.contactPhone?.let { put("contact", it) }
                        request.contactEmail?.let { put("email", it) }
                    },
                )
                put(
                    "theme",
                    JSONObject().apply { put("color", "#16233B") },
                )
                // UPI first: it is how most Indian clients actually pay.
                put(
                    "config",
                    JSONObject().apply {
                        put(
                            "display",
                            JSONObject().apply {
                                put(
                                    "blocks",
                                    JSONObject().apply {
                                        put(
                                            "upi",
                                            JSONObject().apply {
                                                put("name", "Pay by UPI")
                                                put(
                                                    "instruments",
                                                    listOf(JSONObject().apply { put("method", "upi") }),
                                                )
                                            },
                                        )
                                    },
                                )
                                put("sequence", listOf("block.upi"))
                                put("preferences", JSONObject().apply { put("show_default_blocks", true) })
                            },
                        )
                    },
                )
            }

        runCatching { checkout.open(activity, options) }
            .onFailure { Log.e(TAG, "could not open Razorpay Checkout", it) }
    }
}

/** Everything Checkout needs, all of it decided by the server except the display text. */
data class CheckoutRequest(
    val keyId: String,
    val orderId: String,
    val amountPaise: Long,
    val invoiceNumber: String,
    val firmName: String,
    val contactPhone: String? = null,
    val contactEmail: String? = null,
)
