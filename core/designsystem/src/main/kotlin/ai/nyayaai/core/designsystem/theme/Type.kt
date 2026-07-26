package ai.nyayaai.core.designsystem.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

/**
 * D.4.1 requires a type scale that "must render Devanagari cleanly".
 *
 * The doc offers Inter or Noto Sans. **Inter has no Devanagari coverage**, so Noto Sans is
 * the only real option: Noto Sans for Latin, Noto Sans Devanagari for Hindi, resolved by
 * [NyayaFontFamily].
 *
 * TODO(A2): bundle NotoSans-*.ttf and NotoSansDevanagari-*.ttf under `res/font/` and point
 * [NyayaFontFamily] at them. Until then this falls back to the platform font, which renders
 * Devanagari inconsistently across budget Indian devices — matra placement in particular —
 * which is exactly the risk bundling removes. This must land before the Hindi review pass.
 */
val NyayaFontFamily: FontFamily = FontFamily.SansSerif

/**
 * Slightly larger body sizes than the Material default. The users are reading case titles
 * and hearing dates at arm's length in a corridor outside a courtroom, not curled up with
 * the phone.
 */
val NyayaTypography =
    Typography(
        displaySmall =
            TextStyle(
                fontFamily = NyayaFontFamily,
                fontWeight = FontWeight.SemiBold,
                fontSize = 32.sp,
                lineHeight = 40.sp,
            ),
        headlineMedium =
            TextStyle(
                fontFamily = NyayaFontFamily,
                fontWeight = FontWeight.SemiBold,
                fontSize = 26.sp,
                lineHeight = 34.sp,
            ),
        headlineSmall =
            TextStyle(
                fontFamily = NyayaFontFamily,
                fontWeight = FontWeight.SemiBold,
                fontSize = 22.sp,
                lineHeight = 30.sp,
            ),
        titleLarge =
            TextStyle(
                fontFamily = NyayaFontFamily,
                fontWeight = FontWeight.SemiBold,
                fontSize = 19.sp,
                lineHeight = 26.sp,
            ),
        titleMedium =
            TextStyle(
                fontFamily = NyayaFontFamily,
                fontWeight = FontWeight.Medium,
                fontSize = 16.sp,
                lineHeight = 24.sp,
            ),
        bodyLarge =
            TextStyle(
                fontFamily = NyayaFontFamily,
                fontWeight = FontWeight.Normal,
                fontSize = 16.sp,
                // Generous leading: Devanagari needs vertical room for matras above and below the
                // baseline, and tight line height clips them.
                lineHeight = 26.sp,
            ),
        bodyMedium =
            TextStyle(
                fontFamily = NyayaFontFamily,
                fontWeight = FontWeight.Normal,
                fontSize = 14.sp,
                lineHeight = 22.sp,
            ),
        labelLarge =
            TextStyle(
                fontFamily = NyayaFontFamily,
                fontWeight = FontWeight.Medium,
                fontSize = 14.sp,
                lineHeight = 20.sp,
            ),
        labelMedium =
            TextStyle(
                fontFamily = NyayaFontFamily,
                fontWeight = FontWeight.Medium,
                fontSize = 12.sp,
                lineHeight = 18.sp,
            ),
    )
