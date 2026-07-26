package ai.nyayaai.core.designsystem.component

import ai.nyayaai.core.designsystem.theme.NyayaTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.ui.graphics.Color

/**
 * Status semantics shared by case stage, invoice state, OCR state, AI job state and hearing
 * urgency, so the same meaning always looks the same wherever it appears.
 */
enum class StatusTone { POSITIVE, NEUTRAL, WARNING, NEGATIVE }

/** Foreground and container colours for a tone. The single mapping every badge uses. */
@Composable
@ReadOnlyComposable
internal fun StatusTone.colors(): Pair<Color, Color> {
    val semantic = NyayaTheme.semanticColors
    return when (this) {
        StatusTone.POSITIVE -> semantic.success to semantic.successContainer
        StatusTone.WARNING -> semantic.warning to semantic.warningContainer
        StatusTone.NEUTRAL -> semantic.info to semantic.infoContainer
        StatusTone.NEGATIVE ->
            MaterialTheme.colorScheme.error to MaterialTheme.colorScheme.errorContainer
    }
}
