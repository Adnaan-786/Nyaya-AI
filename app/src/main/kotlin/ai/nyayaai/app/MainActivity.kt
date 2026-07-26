package ai.nyayaai.app

import ai.nyayaai.core.designsystem.theme.NyayaTheme
import ai.nyayaai.feature.auth.LoginRoute
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.material3.Surface
import dagger.hilt.android.AndroidEntryPoint

/**
 * Sprint A1 host. The real navigation graph, session-aware start destination and deep-link
 * routing (B.8) land alongside the design system and the Today screen in A2/A3.
 */
@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        setContent {
            NyayaTheme {
                Surface {
                    LoginRoute()
                }
            }
        }
    }
}
