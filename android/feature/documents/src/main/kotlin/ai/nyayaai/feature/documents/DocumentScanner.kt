package ai.nyayaai.feature.documents

import android.app.Activity
import android.content.Context
import android.util.Log
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.IntentSenderRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.platform.LocalContext
import com.google.mlkit.vision.documentscanner.GmsDocumentScannerOptions
import com.google.mlkit.vision.documentscanner.GmsDocumentScanning
import com.google.mlkit.vision.documentscanner.GmsDocumentScanningResult

/**
 * D.7's scanner: ML Kit's document scanner, which runs **on device**.
 *
 * No image ever leaves the phone during scanning — the crop, the perspective correction
 * and the PDF assembly all happen locally, and the app only uploads the finished PDF
 * through the normal B.9 flow. For privileged legal documents that distinction matters,
 * and it is why this is the scanner rather than a cloud imaging API.
 *
 * The UI is Google's, delivered through Play Services, so it is one implementation the
 * user already recognises from other apps rather than a camera screen we maintain.
 */
private const val TAG = "DocumentScanner"
private const val MAX_PAGES = 20

@Composable
fun rememberDocumentScanner(
    onScanned: (GmsDocumentScanningResult) -> Unit,
    onUnavailable: () -> Unit = {},
): () -> Unit {
    val context = LocalContext.current

    val scanner =
        remember {
            GmsDocumentScanning.getClient(
                GmsDocumentScannerOptions
                    .Builder()
                    .setGalleryImportAllowed(true)
                    .setPageLimit(MAX_PAGES)
                    // PDF only. A multi-page order sheet is one document, and the OCR
                    // pipeline and the vault both treat it as one.
                    .setResultFormats(GmsDocumentScannerOptions.RESULT_FORMAT_PDF)
                    .setScannerMode(GmsDocumentScannerOptions.SCANNER_MODE_FULL)
                    .build(),
            )
        }

    val launcher =
        rememberLauncherForActivityResult(ActivityResultContracts.StartIntentSenderForResult()) { result ->
            if (result.resultCode != Activity.RESULT_OK) return@rememberLauncherForActivityResult

            GmsDocumentScanningResult
                .fromActivityResultIntent(result.data)
                ?.let(onScanned)
        }

    return {
        val activity = context.findActivity()
        if (activity == null) {
            onUnavailable()
        } else {
            scanner
                .getStartScanIntent(activity)
                .addOnSuccessListener { sender ->
                    launcher.launch(IntentSenderRequest.Builder(sender).build())
                }.addOnFailureListener { error ->
                    // The scanner module downloads on first use. On a device with no
                    // Play Services — or no space for the module — this is where it
                    // fails, and the caller offers file import instead of a dead button.
                    Log.w(TAG, "document scanner unavailable", error)
                    onUnavailable()
                }
        }
    }
}

private fun Context.findActivity(): Activity? {
    var current = this
    while (current is android.content.ContextWrapper) {
        if (current is Activity) return current
        current = current.baseContext
    }
    return null
}
