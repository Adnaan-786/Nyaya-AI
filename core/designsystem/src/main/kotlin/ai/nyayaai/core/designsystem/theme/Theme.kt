package ai.nyayaai.core.designsystem.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/** 4dp base scale. Every padding in the app comes from here, never a literal. */
data class NyayaSpacing(
    val xs: Dp = 4.dp,
    val sm: Dp = 8.dp,
    val md: Dp = 16.dp,
    val lg: Dp = 24.dp,
    val xl: Dp = 32.dp,
    val xxl: Dp = 48.dp,
    /** D.4.4: minimum touch target. Anything tappable is at least this tall. */
    val minTouchTarget: Dp = 48.dp,
)

internal val NyayaShapes =
    Shapes(
        extraSmall = RoundedCornerShape(6.dp),
        small = RoundedCornerShape(10.dp),
        medium = RoundedCornerShape(14.dp),
        large = RoundedCornerShape(20.dp),
        extraLarge = RoundedCornerShape(28.dp),
    )

private val LocalSpacing = staticCompositionLocalOf { NyayaSpacing() }
private val LocalSemanticColors = staticCompositionLocalOf { LightSemanticColors }

/**
 * The app theme.
 *
 * **Dynamic colour is deliberately not supported.** Material You would derive the palette
 * from the user's wallpaper; a legal practice tool needs to look identical on every device
 * and to convey the brand, not the phone's mood.
 */
@Composable
fun NyayaTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    val colorScheme = if (darkTheme) NyayaDarkColors else NyayaLightColors
    val semantic = if (darkTheme) DarkSemanticColors else LightSemanticColors

    /*
     * Font family is chosen by locale, not by string content.
     *
     * Compose resolves a FontFamily to one typeface and does no per-script fallback within
     * it, so a single family has to cover everything a locale shows. Noto Sans Devanagari
     * carries Latin too, which is what makes it the right choice for Hindi: "Aaj ki
     * hearings", court names and CNR numbers all render from the same harmonised family
     * instead of falling back to whatever Devanagari font the device happens to ship.
     */
    val locale = LocalConfiguration.current.locales[0]
    val fontFamily = if (locale.language == HINDI_LANGUAGE) NotoSansDevanagari else NotoSans

    CompositionLocalProvider(
        LocalSpacing provides NyayaSpacing(),
        LocalSemanticColors provides semantic,
    ) {
        MaterialTheme(
            colorScheme = colorScheme,
            typography = nyayaTypography(fontFamily),
            shapes = NyayaShapes,
            content = content,
        )
    }
}

private const val HINDI_LANGUAGE = "hi"

/** `NyayaTheme.spacing.md` alongside `MaterialTheme.colorScheme`. */
object NyayaTheme {
    val spacing: NyayaSpacing
        @Composable @ReadOnlyComposable
        get() = LocalSpacing.current

    val semanticColors: NyayaSemanticColors
        @Composable @ReadOnlyComposable
        get() = LocalSemanticColors.current
}
