package ai.nyayaai.feature.settings

import ai.nyayaai.core.designsystem.component.InitialAvatar
import ai.nyayaai.core.designsystem.component.NyayaCard
import ai.nyayaai.core.designsystem.component.SectionHeader
import ai.nyayaai.core.designsystem.theme.NyayaTheme
import ai.nyayaai.core.model.Language
import androidx.appcompat.app.AppCompatDelegate
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.hilt.navigation.compose.hiltViewModel

@Composable
fun SettingsRoute(
    userName: String,
    userPhone: String,
    roleLabel: String,
    onLoggedOut: () -> Unit,
    modifier: Modifier = Modifier,
    // D.10: client-mode logins never see team management — it is a staff-only surface,
    // so the caller decides whether to offer it rather than this screen guessing from role.
    showTeam: Boolean = false,
    onOpenTeam: () -> Unit = {},
    viewModel: SettingsViewModel = hiltViewModel(),
) {
    var confirmingLogout by remember { mutableStateOf(false) }
    var language by remember { mutableStateOf(currentLanguage()) }

    Column(
        modifier =
            modifier
                .fillMaxSize()
                .padding(NyayaTheme.spacing.md),
        verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.md),
    ) {
        NyayaCard {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.md),
            ) {
                InitialAvatar(name = userName)

                Column(verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.xs)) {
                    Text(text = userName, style = MaterialTheme.typography.titleMedium)
                    Text(
                        text = userPhone,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Text(
                        text = roleLabel,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }

        SectionHeader(title = stringResource(R.string.settings_language))

        SingleChoiceSegmentedButtonRow(modifier = Modifier.fillMaxWidth()) {
            Language.entries.forEachIndexed { index, option ->
                SegmentedButton(
                    selected = option == language,
                    onClick = {
                        language = option
                        viewModel.setLanguage(option)
                    },
                    shape = SegmentedButtonDefaults.itemShape(index, Language.entries.size),
                ) {
                    Text(stringResource(option.labelRes()))
                }
            }
        }

        if (showTeam) {
            HorizontalDivider()

            OutlinedButton(
                onClick = onOpenTeam,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(stringResource(R.string.settings_team))
            }
        }

        HorizontalDivider()

        OutlinedButton(
            onClick = { confirmingLogout = true },
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(stringResource(R.string.settings_logout))
        }
    }

    if (confirmingLogout) {
        AlertDialog(
            onDismissRequest = { confirmingLogout = false },
            title = { Text(stringResource(R.string.settings_logout_title)) },
            // Confirmed because signing out costs an OTP round trip to undo, and on a
            // rate-limited number that is a real wait rather than a small annoyance.
            text = { Text(stringResource(R.string.settings_logout_body)) },
            confirmButton = {
                TextButton(
                    onClick = {
                        confirmingLogout = false
                        viewModel.logout(onComplete = onLoggedOut)
                    },
                ) {
                    Text(stringResource(R.string.settings_logout))
                }
            },
            dismissButton = {
                TextButton(onClick = { confirmingLogout = false }) {
                    Text(stringResource(R.string.settings_cancel))
                }
            },
        )
    }
}

/** Reads the per-app locale the OS has stored. Not composable — it is a plain query. */
private fun currentLanguage(): Language {
    val tag = AppCompatDelegate.getApplicationLocales().toLanguageTags()
    return if (tag.startsWith("hi")) Language.HI else Language.EN
}

private fun Language.labelRes(): Int =
    when (this) {
        Language.EN -> R.string.settings_language_en
        Language.HI -> R.string.settings_language_hi
    }
