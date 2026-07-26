package ai.nyayaai.core.designsystem.component

import ai.nyayaai.core.designsystem.R
import ai.nyayaai.core.designsystem.theme.NyayaTheme
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp

// D.2 requires every screen to render one of Loading / Content / Error / Empty. These are
// the shared Loading, Error and Empty renderings, so the app fails and waits the same way
// everywhere instead of each screen inventing its own spinner.

/**
 * Skeleton placeholder. Used instead of a centred spinner because most screens here are
 * lists whose shape is known in advance, and a skeleton makes a slow eCourts sync feel
 * like loading rather than like breakage.
 */
@Composable
fun SkeletonBlock(
    modifier: Modifier = Modifier,
    height: androidx.compose.ui.unit.Dp = 16.dp,
) {
    val transition = rememberInfiniteTransition(label = "skeleton")
    val alpha by transition.animateFloat(
        initialValue = SKELETON_MIN_ALPHA,
        targetValue = SKELETON_MAX_ALPHA,
        animationSpec =
            infiniteRepeatable(
                animation = tween(SKELETON_PERIOD_MS),
                repeatMode = RepeatMode.Reverse,
            ),
        label = "skeleton-alpha",
    )

    Column(
        modifier =
            modifier
                .fillMaxWidth()
                .height(height)
                .alpha(alpha)
                .clip(MaterialTheme.shapes.extraSmall)
                .background(MaterialTheme.colorScheme.outlineVariant),
        content = {},
    )
}

/** A list-shaped loading state: several skeleton rows. */
@Composable
fun LoadingList(
    modifier: Modifier = Modifier,
    rows: Int = DEFAULT_SKELETON_ROWS,
) {
    Column(
        modifier =
            modifier
                .fillMaxWidth()
                .padding(NyayaTheme.spacing.md)
                .semantics { contentDescription = "Loading" },
        verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.md),
    ) {
        repeat(rows) {
            SkeletonBlock(height = SKELETON_ROW_HEIGHT)
        }
    }
}

/**
 * The error state. [onRetry] is nullable because not every failure is retryable — showing
 * "Try again" on a 403 teaches users to tap a button that can never work.
 */
@Composable
fun ErrorState(
    message: String,
    modifier: Modifier = Modifier,
    onRetry: (() -> Unit)? = null,
) {
    Column(
        modifier =
            modifier
                .fillMaxWidth()
                .padding(NyayaTheme.spacing.lg),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.sm),
    ) {
        Text(
            text = stringResource(R.string.ds_state_error_title),
            style = MaterialTheme.typography.titleMedium,
            color = MaterialTheme.colorScheme.onSurface,
        )
        Text(
            text = message,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
        )
        if (onRetry != null) {
            Button(onClick = onRetry) {
                Text(stringResource(R.string.ds_state_retry))
            }
        }
    }
}

/**
 * The empty state. [title] and [action] are passed in because an empty case list and an
 * empty document vault need different words and different next steps — a generic
 * "No data" is the one thing this must never render.
 */
@Composable
fun EmptyState(
    title: String,
    modifier: Modifier = Modifier,
    description: String? = null,
    action: @Composable (() -> Unit)? = null,
) {
    Column(
        modifier =
            modifier
                .fillMaxWidth()
                .padding(NyayaTheme.spacing.lg),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.sm),
    ) {
        Text(
            text = title,
            style = MaterialTheme.typography.titleMedium,
            color = MaterialTheme.colorScheme.onSurface,
        )
        description?.let {
            Text(
                text = it,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
            )
        }
        action?.invoke()
    }
}

private const val SKELETON_MIN_ALPHA = 0.35f
private const val SKELETON_MAX_ALPHA = 0.75f
private const val SKELETON_PERIOD_MS = 700
private const val DEFAULT_SKELETON_ROWS = 4
private val SKELETON_ROW_HEIGHT = 64.dp
