package ai.nyayaai.core.designsystem.component

import ai.nyayaai.core.designsystem.R
import ai.nyayaai.core.designsystem.theme.NyayaTheme
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Info
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp

/**
 * B.11, mandatory: **every** AI output surface in the app must display this, persistently.
 *
 * It ships as one component precisely so it cannot drift — the summarizer, researcher,
 * draftsman and risk-review screens all render this exact composable rather than each
 * writing their own caption. There is deliberately no dismiss affordance and no parameter
 * to hide it: an AI answer a lawyer might carry into court is not somewhere to be subtle
 * about provenance.
 *
 * The Hindi string is the exact wording specified in B.11, not a translation choice.
 */
@Composable
fun AiDisclaimerBanner(modifier: Modifier = Modifier) {
    Row(
        modifier =
            modifier
                .fillMaxWidth()
                .background(MaterialTheme.colorScheme.secondaryContainer)
                .padding(
                    horizontal = NyayaTheme.spacing.md,
                    vertical = NyayaTheme.spacing.sm,
                ).semantics { liveRegion = LiveRegionMode.Polite },
        horizontalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.sm),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(
            imageVector = Icons.Outlined.Info,
            // The adjacent text says the same thing; announcing it twice is noise.
            contentDescription = null,
            tint = MaterialTheme.colorScheme.onSecondaryContainer,
            modifier = Modifier.size(18.dp),
        )
        Text(
            text = stringResource(R.string.ds_ai_disclaimer),
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSecondaryContainer,
        )
    }
}
