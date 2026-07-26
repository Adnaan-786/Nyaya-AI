package ai.nyayaai.core.designsystem.gallery

import ai.nyayaai.core.common.todayInIndia
import ai.nyayaai.core.designsystem.component.AiDisclaimerBanner
import ai.nyayaai.core.designsystem.component.EmptyState
import ai.nyayaai.core.designsystem.component.ErrorState
import ai.nyayaai.core.designsystem.component.HearingChip
import ai.nyayaai.core.designsystem.component.LoadingList
import ai.nyayaai.core.designsystem.component.StatusBadge
import ai.nyayaai.core.designsystem.component.StatusTone
import ai.nyayaai.core.designsystem.theme.NyayaTheme
import ai.nyayaai.core.model.CourtDate
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import kotlinx.datetime.LocalDate

/**
 * The A2 definition of done: every design-system component on one screen, so it can be
 * checked in EN and HI, light and dark, at 1.0x and 1.3x font scale in a single pass.
 *
 * Debug builds only — it is a review surface, not a feature. It is also the target for
 * screenshot tests, which is what makes a design regression fail CI instead of being
 * noticed three sprints later.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ComponentGalleryScreen(modifier: Modifier = Modifier) {
    val today = todayInIndia()

    Surface(modifier = modifier.fillMaxSize()) {
        Column(
            modifier =
                Modifier
                    .verticalScroll(rememberScrollState())
                    .padding(NyayaTheme.spacing.md),
            verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.md),
        ) {
            Section("Typography")
            Text("Display Small", style = MaterialTheme.typography.displaySmall)
            Text("Headline Small", style = MaterialTheme.typography.headlineSmall)
            Text("Title Medium", style = MaterialTheme.typography.titleMedium)
            Text("Body Large — the quick brown fox", style = MaterialTheme.typography.bodyLarge)
            // Devanagari sample: matras above and below the baseline are where a font
            // without proper coverage visibly breaks.
            Text("शीर्षक — अगली सुनवाई की तारीख", style = MaterialTheme.typography.bodyLarge)
            Text("Aaj ki hearings · कल की सुनवाई", style = MaterialTheme.typography.bodyMedium)

            Section("Buttons")
            Button(onClick = {}, modifier = Modifier.fillMaxWidth()) { Text("Primary action") }
            OutlinedButton(onClick = {}, modifier = Modifier.fillMaxWidth()) { Text("Secondary") }
            TextButton(onClick = {}) { Text("Tertiary") }

            Section("Text fields")
            OutlinedTextField(
                value = "",
                onValueChange = {},
                label = { Text("Empty") },
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = "MHAU01",
                onValueChange = {},
                label = { Text("With value") },
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = "12345",
                onValueChange = {},
                isError = true,
                label = { Text("Error") },
                supportingText = { Text("CNR must be 16 characters") },
                modifier = Modifier.fillMaxWidth(),
            )

            Section("Status badges")
            FlowRow(horizontalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.sm)) {
                StatusBadge("Active", StatusTone.POSITIVE)
                StatusBadge("Archived", StatusTone.NEUTRAL)
                StatusBadge("Overdue", StatusTone.NEGATIVE)
                StatusBadge("Pending OCR", StatusTone.WARNING)
            }

            Section("Hearing chips")
            FlowRow(horizontalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.sm)) {
                HearingChip(CourtDate(today))
                HearingChip(CourtDate(today.plusDays(1)))
                HearingChip(CourtDate(today.plusDays(3)))
                HearingChip(CourtDate(today.plusDays(21)))
                HearingChip(CourtDate(today.plusDays(-2)))
            }

            Section("AI disclaimer (B.11 — mandatory on every AI surface)")
            AiDisclaimerBanner()

            Section("Loading")
            LoadingList(rows = 2)

            Section("Error")
            ErrorState(message = "eCourts is not responding.", onRetry = {})

            Section("Empty")
            EmptyState(
                title = "No cases yet",
                description = "Add your first case by CNR to start tracking hearings.",
                action = { Button(onClick = {}) { Text("Add case") } },
            )
        }
    }
}

private fun LocalDate.plusDays(days: Int): LocalDate = LocalDate.fromEpochDays(toEpochDays() + days)

@Composable
private fun Section(title: String) {
    HorizontalDivider(modifier = Modifier.padding(top = NyayaTheme.spacing.sm))
    Text(
        text = title,
        style = MaterialTheme.typography.labelLarge,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
}

@Preview(name = "Gallery — light", showBackground = true, heightDp = 1600)
@Composable
private fun GalleryLightPreview() {
    ai.nyayaai.core.designsystem.theme.NyayaTheme(darkTheme = false) {
        ComponentGalleryScreen()
    }
}

@Preview(name = "Gallery — dark", showBackground = true, heightDp = 1600)
@Composable
private fun GalleryDarkPreview() {
    ai.nyayaai.core.designsystem.theme.NyayaTheme(darkTheme = true) {
        ComponentGalleryScreen()
    }
}
