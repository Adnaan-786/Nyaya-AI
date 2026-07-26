package ai.nyayaai.core.designsystem.component

import ai.nyayaai.core.common.daysFromToday
import ai.nyayaai.core.common.formatShort
import ai.nyayaai.core.designsystem.R
import ai.nyayaai.core.designsystem.theme.NyayaTheme
import ai.nyayaai.core.model.CourtDate
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription

/**
 * D.4.2: hearing date plus a relative label ("01 Aug · in 3 days").
 *
 * The relative part uses [daysFromToday], which is IST-anchored calendar-date arithmetic —
 * not instant subtraction. Opening the app at 11pm must not turn "in 3 days" into
 * "in 2 days".
 */
@Composable
fun HearingChip(
    date: CourtDate,
    modifier: Modifier = Modifier,
) {
    val days = date.daysFromToday()
    val absolute = date.formatShort()
    val relative = relativeLabel(days)
    val (foreground, background) = toneFor(days).colors()

    Row(
        modifier =
            modifier
                .clip(MaterialTheme.shapes.extraSmall)
                .background(background)
                .padding(
                    horizontal = NyayaTheme.spacing.sm,
                    vertical = NyayaTheme.spacing.xs,
                )
                // Read as one phrase rather than three disconnected fragments.
                .clearAndSetSemantics { contentDescription = "$absolute, $relative" },
        horizontalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.xs),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(absolute, style = MaterialTheme.typography.labelMedium, color = foreground)
        Text("·", style = MaterialTheme.typography.labelMedium, color = foreground)
        Text(relative, style = MaterialTheme.typography.labelMedium, color = foreground)
    }
}

@Composable
private fun relativeLabel(days: Int): String =
    when {
        days == 0 -> stringResource(R.string.ds_hearing_today)
        days == 1 -> stringResource(R.string.ds_hearing_tomorrow)
        days == -1 -> stringResource(R.string.ds_hearing_yesterday)
        days > 1 -> stringResource(R.string.ds_hearing_in_days, days)
        else -> stringResource(R.string.ds_hearing_days_ago, -days)
    }

private fun toneFor(days: Int): StatusTone =
    when {
        days < 0 -> StatusTone.NEUTRAL
        days == 0 -> StatusTone.NEGATIVE
        days <= IMMINENT_DAYS -> StatusTone.WARNING
        else -> StatusTone.POSITIVE
    }

/** Within this many days a hearing needs preparation attention, so it reads as urgent. */
private const val IMMINENT_DAYS = 3
