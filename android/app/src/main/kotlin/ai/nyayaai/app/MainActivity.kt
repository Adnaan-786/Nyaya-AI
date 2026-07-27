package ai.nyayaai.app

import ai.nyayaai.core.designsystem.theme.NyayaTheme
import ai.nyayaai.core.model.User
import ai.nyayaai.feature.auth.LoginRoute
import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.material3.Surface
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
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
                        // The role picks the shell. A client-mode login never reaches the
                        // staff destinations at all (D.10).
                        NyayaApp(role = user.role, onOpenUrl = ::openUrl)
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
}
