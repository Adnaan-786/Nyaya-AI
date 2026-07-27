package ai.nyayaai.core.designsystem.component

import ai.nyayaai.core.designsystem.theme.NyayaTheme
import androidx.compose.animation.core.LinearOutSlowInEasing
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

/**
 * The one card every list row uses.
 *
 * A hairline border does the work that elevation usually does. On the ivory background a
 * drop shadow muddies into the paper tone and reads as a smudge, while a 1dp outline
 * stays crisp on the cheap LCD panels this app is expected to run on.
 */
@Composable
fun NyayaCard(
    modifier: Modifier = Modifier,
    onClick: (() -> Unit)? = null,
    containerColor: Color = Color.Unspecified,
    content: @Composable ColumnScope.() -> Unit,
) {
    val interactionSource = remember { MutableInteractionSource() }
    val pressed by interactionSource.collectIsPressedAsState()

    // A small press scale gives touch feedback on rows that have no ripple-bearing
    // control of their own — a whole card that only navigates otherwise feels inert.
    val scale by animateFloatAsState(
        targetValue = if (pressed) PRESSED_SCALE else 1f,
        animationSpec = tween(PRESS_MS),
        label = "card-press",
    )

    Card(
        modifier =
            modifier
                .fillMaxWidth()
                .scale(scale)
                .then(
                    if (onClick != null) {
                        Modifier.clickable(
                            interactionSource = interactionSource,
                            indication = null,
                            onClick = onClick,
                        )
                    } else {
                        Modifier
                    },
                ),
        colors =
            CardDefaults.cardColors(
                containerColor =
                    containerColor.takeIf { it != Color.Unspecified }
                        ?: MaterialTheme.colorScheme.surfaceContainerLowest,
                // Content colour is pinned to onSurface rather than derived from the
                // container. Material would pair a saffron tint with saffron text, and
                // orange body copy on peach both reads as a warning and is harder to
                // read than it looks in a palette. Every tint here is pale enough that
                // ordinary dark text is the right answer on all of them.
                contentColor = MaterialTheme.colorScheme.onSurface,
            ),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
    ) {
        Column(
            modifier = Modifier.padding(NyayaTheme.spacing.md),
            content = content,
        )
    }
}

/**
 * Staggered entrance for list rows.
 *
 * [index] delays each row slightly so a list assembles rather than snapping in. Capped
 * at [MAX_STAGGERED] — past that the delay stops being a flourish and becomes the user
 * waiting for their own data.
 */
@Composable
fun Modifier.animatedListEntry(index: Int): Modifier {
    var appeared by remember { mutableStateOf(false) }

    val progress by animateFloatAsState(
        targetValue = if (appeared) 1f else 0f,
        animationSpec =
            tween(
                durationMillis = ENTRY_MS,
                delayMillis = (index.coerceAtMost(MAX_STAGGERED)) * STAGGER_MS,
                easing = LinearOutSlowInEasing,
            ),
        label = "list-entry",
    )

    LaunchedEffect(Unit) { appeared = true }

    return this
        .alpha(progress)
        .scale(scaleX = 1f, scaleY = ENTRY_SCALE_FROM + (1f - ENTRY_SCALE_FROM) * progress)
}

private const val PRESSED_SCALE = 0.985f
private const val PRESS_MS = 90
private const val ENTRY_MS = 260
private const val STAGGER_MS = 40
private const val MAX_STAGGERED = 6
private const val ENTRY_SCALE_FROM = 0.96f
