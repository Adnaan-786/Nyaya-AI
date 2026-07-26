package ai.nyayaai.app.debug

import ai.nyayaai.core.designsystem.gallery.ComponentGalleryScreen
import ai.nyayaai.core.designsystem.theme.NyayaTheme
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge

/**
 * A2 acceptance surface. Open it, then toggle system dark mode, app language (EN/HI) and
 * font scale to 1.3x — every component should hold its layout in all eight combinations.
 */
class GalleryActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        setContent {
            NyayaTheme {
                ComponentGalleryScreen()
            }
        }
    }
}
