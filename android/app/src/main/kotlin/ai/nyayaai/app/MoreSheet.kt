package ai.nyayaai.app

import ai.nyayaai.core.designsystem.theme.NyayaTheme
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.SheetState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource

/**
 * The fifth bottom-bar slot, opened rather than navigated to.
 *
 * Everything here used to be an unlabelled icon in the top bar, five of them on every
 * screen. Icons alone are a memory test — "which of these is clients?" — and the top bar
 * is also the worst place to put them on a large phone, since it is the part of the
 * screen a thumb cannot reach. A sheet rises from the bottom, next to the thumb, and
 * every entry carries its name.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MoreSheet(
    isAdmin: Boolean,
    sheetState: SheetState,
    onNavigate: (String) -> Unit,
    onDismiss: () -> Unit,
) {
    ModalBottomSheet(onDismissRequest = onDismiss, sheetState = sheetState) {
        Column(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .padding(bottom = NyayaTheme.spacing.md)
                    .navigationBarsPadding(),
        ) {
            MORE_ENTRIES
                .filter { !it.adminOnly || isAdmin }
                .forEach { entry ->
                    Row(
                        modifier =
                            Modifier
                                .fillMaxWidth()
                                // clickable on the Row, not the Text: the whole strip is
                                // the target, which is what makes this comfortable to hit
                                // without looking.
                                .clickable { onNavigate(entry.route) }
                                .padding(
                                    horizontal = NyayaTheme.spacing.lg,
                                    vertical = NyayaTheme.spacing.md,
                                ),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.lg),
                    ) {
                        Icon(
                            entry.icon,
                            // The label beside it already says this; announcing both would
                            // read the name twice to a screen reader.
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Text(
                            text = stringResource(entry.labelRes),
                            style = MaterialTheme.typography.bodyLarge,
                        )
                    }
                }
        }
    }
}
