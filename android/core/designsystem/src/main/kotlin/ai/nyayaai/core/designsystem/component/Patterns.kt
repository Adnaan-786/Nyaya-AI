package ai.nyayaai.core.designsystem.component

import ai.nyayaai.core.designsystem.theme.NyayaTheme
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import kotlin.math.absoluteValue

/**
 * Section title with an optional pill action on the right.
 *
 * The pattern earns its place because it puts the escape hatch where the eye already is:
 * a lawyer scanning "Cases" sees "See all" in the same glance, instead of scrolling to
 * find it. One component so every section reads identically.
 */
@Composable
fun SectionHeader(
    title: String,
    modifier: Modifier = Modifier,
    actionLabel: String? = null,
    onAction: (() -> Unit)? = null,
) {
    Row(
        modifier = modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = title,
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.SemiBold,
        )

        if (actionLabel != null && onAction != null) {
            Text(
                text = actionLabel,
                style = MaterialTheme.typography.labelLarge,
                color = MaterialTheme.colorScheme.onPrimary,
                modifier =
                    Modifier
                        .clip(CircleShape)
                        .background(MaterialTheme.colorScheme.primary)
                        .clickable(onClick = onAction)
                        .padding(horizontal = NyayaTheme.spacing.md, vertical = NyayaTheme.spacing.sm),
            )
        }
    }
}

/**
 * A circular initials badge standing in for the avatar photo a consumer app would use.
 *
 * This product has no photos to show — its subjects are companies and litigants, not
 * profiles — but the *shape* still does the work: it gives every row a fixed anchor on
 * the left so a list scans vertically instead of as ragged text.
 *
 * Colour is derived from the **initials**, not the full name, so two matters for the same
 * client carry the same badge. Hashing the whole title instead gives "Sharma Textiles vs.
 * Anil Traders" and "Sharma Textiles — GST appeal" different colours under identical
 * letters, which reads as a rendering bug rather than as information.
 */
@Composable
fun InitialAvatar(
    name: String,
    modifier: Modifier = Modifier,
    size: androidx.compose.ui.unit.Dp = AVATAR_SIZE,
) {
    val palette = NyayaTheme.semanticColors
    val tints =
        listOf(
            palette.infoContainer to palette.info,
            palette.successContainer to palette.success,
            palette.warningContainer to palette.warning,
        )
    val initials = name.initials()
    val (background, foreground) = tints[initials.hashCode().absoluteValue % tints.size]

    Box(
        modifier = modifier.size(size).clip(CircleShape).background(background),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = initials,
            style = MaterialTheme.typography.labelLarge,
            fontWeight = FontWeight.SemiBold,
            color = foreground,
        )
    }
}

/**
 * Up to two initials, skipping the honorifics Indian legal names are full of.
 *
 * "Adv. Meera Iyer" should read MI, not AM — an avatar that says "Ad." for every lawyer
 * in the firm is worse than no avatar.
 */
private fun String.initials(): String {
    val skip = setOf("adv", "adv.", "mr", "mr.", "mrs", "mrs.", "ms", "ms.", "dr", "dr.", "m/s")
    val words =
        trim()
            .split(' ', '.', ',')
            .filter { it.isNotBlank() && it.lowercase() !in skip }

    return when (words.size) {
        0 -> "?"
        1 -> words[0].take(2).uppercase()
        else -> "${words[0].first()}${words[1].first()}".uppercase()
    }
}

/** One cell of a [StatStrip]. */
data class Stat(
    val label: String,
    val value: String,
)

/**
 * Three or four counts in a row, label above value.
 *
 * Answers "how big is this thing" before the user opens anything — on a case that is
 * hearings, documents and tasks, which is exactly what a lawyer checks first when
 * picking a file up again after a month.
 */
@Composable
fun StatStrip(
    stats: List<Stat>,
    modifier: Modifier = Modifier,
) {
    NyayaCard(modifier = modifier) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceEvenly,
        ) {
            stats.forEach { stat ->
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(
                        text = stat.label,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        textAlign = TextAlign.Center,
                    )
                    Text(
                        text = stat.value,
                        style = MaterialTheme.typography.headlineSmall,
                        fontWeight = FontWeight.Bold,
                    )
                }
            }
        }
    }
}

/**
 * The one number a screen is about, rendered large.
 *
 * Borrowed from the balance treatment in consumer finance apps, and it transfers because
 * the question is the same shape: a lawyer opening billing wants "how much am I owed"
 * answered before they read anything else.
 */
@Composable
fun HeroAmount(
    label: String,
    value: String,
    modifier: Modifier = Modifier,
    caption: String? = null,
) {
    Column(
        modifier = modifier.fillMaxWidth(),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            text = value,
            style = MaterialTheme.typography.displaySmall,
            fontWeight = FontWeight.Bold,
        )
        caption?.let {
            Text(
                text = it,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

/**
 * The dot and rule that turn a list of times into a timeline.
 *
 * [isNow] marks the entry the user is closest to, which is the most useful thing on a
 * day view: a lawyer glancing at the phone between hearings wants "which one am I on"
 * answered without reading times.
 */
@Composable
fun TimelineRail(
    isNow: Boolean,
    isLast: Boolean,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier.width(RAIL_COLUMN_WIDTH),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Box(
            modifier =
                Modifier
                    .padding(top = NyayaTheme.spacing.sm)
                    .size(if (isNow) DOT_NOW else DOT)
                    .clip(CircleShape)
                    .background(
                        if (isNow) {
                            MaterialTheme.colorScheme.secondary
                        } else {
                            MaterialTheme.colorScheme.outline
                        },
                    ),
        )
        if (!isLast) {
            Box(
                modifier =
                    Modifier
                        .weight(1f)
                        .width(RAIL_WIDTH)
                        .background(MaterialTheme.colorScheme.outlineVariant),
            )
        }
    }
}

private val AVATAR_SIZE = 44.dp
private val DOT = 8.dp
private val DOT_NOW = 12.dp
private val RAIL_WIDTH = 2.dp

/** Wide enough to centre the dot and leave the card clear of it. */
val RAIL_COLUMN_WIDTH = 24.dp
