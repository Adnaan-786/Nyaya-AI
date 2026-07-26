package ai.nyayaai.core.designsystem.theme

import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.ui.graphics.Color

/**
 * D.4.1: professional navy with an ivory surface and a saffron accent.
 *
 * The palette is deliberately restrained. This is a tool lawyers keep open all day next to
 * court documents; it should read as stationery, not as a consumer app. Saffron is the only
 * loud colour and it is reserved for the primary action on a screen.
 *
 * Dynamic colour is **off** (see [NyayaTheme]) — the brand must look the same on every
 * device, and a Material You palette derived from someone's wallpaper does not convey
 * "trustworthy legal software".
 */
internal object Palette {
    // Navy — primary brand, headers, primary text.
    val Navy900 = Color(0xFF0E1830)
    val Navy800 = Color(0xFF16233B)
    val Navy700 = Color(0xFF243759)
    val Navy300 = Color(0xFF7A8AA8)
    val Navy100 = Color(0xFFD6DDE9)

    // Saffron — the accent. Primary actions only.
    val Saffron700 = Color(0xFFC96F0A)
    val Saffron500 = Color(0xFFE8861B)
    val Saffron100 = Color(0xFFFDEEDA)

    // Ivory / paper — surfaces. Warmer than pure white, which is harsh over long sessions.
    val Ivory = Color(0xFFF6F2E8)
    val Paper = Color(0xFFFFFDF7)
    val CardLight = Color(0xFFFFFEFA)
    val LineLight = Color(0xFFE7E0D0)
    val MutedLight = Color(0xFF847B69)

    // Semantic.
    val Green600 = Color(0xFF1E7A4D)
    val Green100 = Color(0xFFE3F2E9)
    val Red600 = Color(0xFFB3402F)
    val Red100 = Color(0xFFF9E6E1)
    val Amber600 = Color(0xFF9A6B00)
    val Amber100 = Color(0xFFFBF0D4)

    // Dark mode surfaces.
    val DarkSurface = Color(0xFF10151F)
    val DarkSurfaceRaised = Color(0xFF18202E)
    val DarkLine = Color(0xFF2B3648)
    val DarkMuted = Color(0xFF9AA4B5)
    val OnDark = Color(0xFFEDEFF3)
}

internal val NyayaLightColors =
    lightColorScheme(
        primary = Palette.Navy800,
        onPrimary = Color.White,
        primaryContainer = Palette.Navy100,
        onPrimaryContainer = Palette.Navy900,
        secondary = Palette.Saffron500,
        onSecondary = Color.White,
        secondaryContainer = Palette.Saffron100,
        onSecondaryContainer = Palette.Saffron700,
        tertiary = Palette.Navy700,
        onTertiary = Color.White,
        background = Palette.Ivory,
        onBackground = Palette.Navy900,
        surface = Palette.CardLight,
        onSurface = Palette.Navy900,
        surfaceVariant = Palette.Paper,
        onSurfaceVariant = Palette.MutedLight,
        outline = Palette.LineLight,
        outlineVariant = Palette.LineLight,
        error = Palette.Red600,
        onError = Color.White,
        errorContainer = Palette.Red100,
        onErrorContainer = Palette.Red600,
    )

internal val NyayaDarkColors =
    darkColorScheme(
        primary = Palette.Saffron500,
        onPrimary = Palette.Navy900,
        primaryContainer = Palette.Navy700,
        onPrimaryContainer = Palette.OnDark,
        secondary = Palette.Saffron500,
        onSecondary = Palette.Navy900,
        secondaryContainer = Palette.Navy700,
        onSecondaryContainer = Palette.Saffron100,
        tertiary = Palette.Navy300,
        onTertiary = Palette.Navy900,
        background = Palette.DarkSurface,
        onBackground = Palette.OnDark,
        surface = Palette.DarkSurfaceRaised,
        onSurface = Palette.OnDark,
        surfaceVariant = Palette.DarkSurface,
        onSurfaceVariant = Palette.DarkMuted,
        outline = Palette.DarkLine,
        outlineVariant = Palette.DarkLine,
        error = Color(0xFFE98A78),
        onError = Palette.Navy900,
        errorContainer = Color(0xFF5A1D14),
        onErrorContainer = Color(0xFFF9E6E1),
    )

/**
 * Colours Material 3 has no slot for: status semantics that must stay consistent across
 * case stages, invoice states and AI confidence levels.
 */
data class NyayaSemanticColors(
    val success: Color,
    val successContainer: Color,
    val warning: Color,
    val warningContainer: Color,
    val info: Color,
    val infoContainer: Color,
)

internal val LightSemanticColors =
    NyayaSemanticColors(
        success = Palette.Green600,
        successContainer = Palette.Green100,
        warning = Palette.Amber600,
        warningContainer = Palette.Amber100,
        info = Palette.Navy700,
        infoContainer = Palette.Navy100,
    )

internal val DarkSemanticColors =
    NyayaSemanticColors(
        success = Color(0xFF5FBF8C),
        successContainer = Color(0xFF10352A),
        warning = Color(0xFFE0B25C),
        warningContainer = Color(0xFF3A2E10),
        info = Palette.Navy300,
        infoContainer = Palette.Navy700,
    )
