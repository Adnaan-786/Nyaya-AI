package ai.nyayaai.app

import ai.nyayaai.app.push.DeviceRegistrar
import ai.nyayaai.app.push.NotificationPermissionGate
import ai.nyayaai.core.designsystem.theme.NyayaTheme
import ai.nyayaai.core.model.User
import ai.nyayaai.feature.auth.LoginRoute
import ai.nyayaai.feature.billing.PaymentCoordinator
import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.material3.Surface
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import com.razorpay.PaymentData
import com.razorpay.PaymentResultWithDataListener
import dagger.hilt.android.AndroidEntryPoint
import javax.inject.Inject

@AndroidEntryPoint
class MainActivity :
    ComponentActivity(),
    PaymentResultWithDataListener {
    @Inject lateinit var deviceRegistrar: DeviceRegistrar

    @Inject lateinit var paymentCoordinator: PaymentCoordinator

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)

        setContent {
            NyayaTheme {
                Surface {
                    var signedInUser by remember { mutableStateOf<User?>(null) }
                    val user = signedInUser

                    if (user == null) {
                        LoginRoute(onSignedIn = { signedInUser = it })
                    } else {
                        // B.4.6: register this device after every login, not only on FCM
                        // token refresh. A reinstall or a restore gives the same user a
                        // new token, and only a fresh login will surface it.
                        LaunchedEffect(user.id) {
                            deviceRegistrar.registerCurrentToken(BuildConfig.VERSION_NAME)
                        }
                        NotificationPermissionGate()

                        // The role picks the shell. A client-mode login never reaches the
                        // staff destinations at all (D.10).
                        NyayaApp(
                            user = user,
                            onOpenUrl = ::openUrl,
                            // Dropping the user back to null returns the whole app to the
                            // login screen; the token wipe already happened in Settings.
                            onLoggedOut = { signedInUser = null },
                        )
                    }
                }
            }
        }
    }

    /**
     * Citations and payment links open in the browser, not an in-app WebView. A payment
     * page inside a WebView the app controls has exactly the shape of a phishing screen,
     * and B.1.3 keeps this app off third-party surfaces entirely.
     */
    private fun openUrl(url: String) {
        try {
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
        } catch (_: ActivityNotFoundException) {
            Toast.makeText(this, R.string.no_browser, Toast.LENGTH_SHORT).show()
        }
    }

    /**
     * B.10 step 4. Razorpay reports to the Activity, so this is where the SDK's claim
     * enters the app — and it goes straight to the server for verification. The app
     * never treats this callback as proof of payment.
     */
    override fun onPaymentSuccess(
        razorpayPaymentId: String?,
        data: PaymentData?,
    ) {
        paymentCoordinator.onCheckoutSuccess(razorpayPaymentId, data?.signature)
    }

    override fun onPaymentError(
        code: Int,
        description: String?,
        data: PaymentData?,
    ) {
        paymentCoordinator.onCheckoutFailure(description)
    }
}
