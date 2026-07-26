package ai.nyayaai.core.designsystem.component

import ai.nyayaai.core.designsystem.theme.NyayaTheme
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip

/**
 * A small pill. Text arrives already localized — this component never formats or
 * translates, because the same tone serves several different vocabularies (case stage,
 * invoice status, OCR state).
 */
@Composable
fun StatusBadge(
    text: String,
    tone: StatusTone,
    modifier: Modifier = Modifier,
) {
    val (foreground, background) = tone.colors()

    Text(
        text = text,
        style = MaterialTheme.typography.labelMedium,
        color = foreground,
        modifier =
            modifier
                .clip(MaterialTheme.shapes.extraSmall)
                .background(background)
                .padding(
                    horizontal = NyayaTheme.spacing.sm,
                    vertical = NyayaTheme.spacing.xs,
                ),
    )
}
