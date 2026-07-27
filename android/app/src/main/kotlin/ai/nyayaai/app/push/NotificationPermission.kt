package ai.nyayaai.app.push

import ai.nyayaai.app.R
import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.core.content.ContextCompat

/**
 * Android 13+ POST_NOTIFICATIONS, asked **after** an explainer.
 *
 * The system dialog is one-shot: a user who taps "Don't allow" cannot be asked again by
 * the app, only sent to Settings. Firing it cold on first launch — before the user has
 * seen a single hearing — is how apps get permanently denied by people who would have
 * said yes once they understood. So the explainer names the three things that will
 * actually notify them, and the system prompt only appears if they agree to it.
 */
@Composable
fun NotificationPermissionGate(onResolved: () -> Unit = {}) {
    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) {
        LaunchedEffect(Unit) { onResolved() }
        return
    }

    val context = LocalContext.current
    val alreadyGranted =
        remember {
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) ==
                PackageManager.PERMISSION_GRANTED
        }

    var showExplainer by remember { mutableStateOf(!alreadyGranted) }

    val launcher =
        rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {
            // Either answer is fine and neither blocks anything. Push is an enhancement;
            // the Today screen is still the source of truth for the day's list.
            onResolved()
        }

    if (alreadyGranted) {
        LaunchedEffect(Unit) { onResolved() }
        return
    }

    if (showExplainer) {
        AlertDialog(
            onDismissRequest = {
                showExplainer = false
                onResolved()
            },
            title = { Text(stringResource(R.string.notif_permission_title)) },
            text = { Text(stringResource(R.string.notif_permission_body)) },
            confirmButton = {
                TextButton(
                    onClick = {
                        showExplainer = false
                        launcher.launch(Manifest.permission.POST_NOTIFICATIONS)
                    },
                ) {
                    Text(stringResource(R.string.notif_permission_allow))
                }
            },
            dismissButton = {
                TextButton(
                    onClick = {
                        showExplainer = false
                        onResolved()
                    },
                ) {
                    Text(stringResource(R.string.notif_permission_skip))
                }
            },
        )
    }
}
