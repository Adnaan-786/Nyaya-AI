package ai.nyayaai.app

import ai.nyayaai.app.push.DeviceRegistrar
import ai.nyayaai.app.push.NotificationPermissionGate
import ai.nyayaai.core.designsystem.theme.NyayaTheme
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
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Surface
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.razorpay.PaymentData
import com.razorpay.PaymentResultWithDataListener
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.flow.MutableStateFlow
import javax.inject.Inject

@AndroidEntryPoint
class MainActivity :
    ComponentActivity(),
    PaymentResultWithDataListener {
    @Inject lateinit var deviceRegistrar: DeviceRegistrar

    @Inject lateinit var paymentCoordinator: PaymentCoordinator

    /**
     * The deep link most recently handed to this activity.
     *
     * MainActivity is `singleTask`, so a push tapped while the app is already running
     * arrives at [onNewIntent] and never re-runs `onCreate`. Reading `intent` once at
     * composition time therefore handles only the cold-start case — which is the rarer
     * one, since a lawyer who gets a hearing reminder usually has the app in recents.
     */
    private val deepLinkFlow = MutableStateFlow<String?>(null)

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        deepLinkFlow.value = intent?.dataString

        setContent {
            NyayaTheme {
                Surface {
                    val sessionViewModel: SessionViewModel = hiltViewModel()
                    val session by sessionViewModel.state.collectAsStateWithLifecycle()

                    val pendingDeepLink by deepLinkFlow.collectAsStateWithLifecycle()

                    when (val current = session) {
                        // An empty *surface*, not empty composition. Rendering nothing
                        // leaves the activity with no focused window, and if `GET /me` is
                        // slow the system reports "Application does not have a focused
                        // window" and ANRs. A blank branded surface also avoids flashing
                        // the login screen for the duration of one request.
                        SessionState.Restoring ->
                            Box(
                                modifier = Modifier.fillMaxSize(),
                                contentAlignment = Alignment.Center,
                            ) {
                                CircularProgressIndicator()
                            }

                        SessionState.SignedOut ->
                            LoginRoute(onSignedIn = sessionViewModel::onSignedIn)

                        is SessionState.SignedIn -> {
                            val user = current.user
                            // B.4.6: register this device after every login, not only on FCM
                            // token refresh. A reinstall or a restore gives the same user a
                            // new token, and only a fresh login will surface it.
                            LaunchedEffect(user.id) {
                                deviceRegistrar.registerCurrentToken(BuildConfig.VERSION_NAME)
                            }
                            NotificationPermissionGate()

                            // The role picks the shell. A client-mode login never reaches
                            // the staff destinations at all (D.10).
                            NyayaApp(
                                user = user,
                                onOpenUrl = ::openUrl,
                                onLoggedOut = sessionViewModel::onSignedOut,
                                deepLink = pendingDeepLink,
                                // Cleared once consumed, so a configuration change does
                                // not re-navigate to the same case.
                                onDeepLinkHandled = { deepLinkFlow.value = null },
                            )
                        }
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

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        deepLinkFlow.value = intent.dataString
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
