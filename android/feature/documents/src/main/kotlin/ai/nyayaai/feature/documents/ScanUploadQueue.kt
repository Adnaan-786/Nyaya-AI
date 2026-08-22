package ai.nyayaai.feature.documents

import ai.nyayaai.core.model.CaseId
import android.content.ContentResolver
import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.Data
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkInfo
import androidx.work.WorkManager
import androidx.work.WorkRequest
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.withContext
import java.io.File
import java.util.UUID
import java.util.concurrent.TimeUnit
import javax.inject.Inject
import javax.inject.Singleton

/**
 * D.7: turns a finished scan into a durable [ScanUploadWorker] job.
 *
 * A scanner `Uri` is not something the app can rely on being readable minutes later —
 * WorkManager may run this job well after the scan screen closed, on retry after a
 * connectivity gap or a fresh process. So the bytes are copied into the app's own cache
 * once, here, and the worker reads that stable file rather than the original `Uri`.
 *
 * The 50 MB check happens twice by design: once here, cheaply, off `ContentResolver`
 * metadata, so an oversized file is rejected before it is even copied; and again, the one
 * that is actually load-bearing, inside [ScanUploader] before any network call — see that
 * class's tests. This one is just the fast path that saves a pointless disk copy.
 */
@Singleton
class ScanUploadQueue
    @Inject
    constructor(
        @ApplicationContext private val context: Context,
    ) {
        suspend fun enqueue(
            uri: Uri,
            name: String,
            caseId: CaseId?,
            folder: String?,
        ): QueueResult =
            withContext(Dispatchers.IO) {
                val declaredSize = context.contentResolver.querySize(uri)
                if (declaredSize != null && declaredSize > MAX_UPLOAD_BYTES) {
                    return@withContext QueueResult.Rejected(context.getString(R.string.vault_upload_too_large))
                }

                val staged =
                    runCatching { stage(uri) }.getOrNull()
                        ?: return@withContext QueueResult.Rejected(context.getString(R.string.vault_scan_unreadable))

                if (staged.length() > MAX_UPLOAD_BYTES) {
                    staged.delete()
                    return@withContext QueueResult.Rejected(context.getString(R.string.vault_upload_too_large))
                }

                val data =
                    Data
                        .Builder()
                        .putString(ScanUploadWorker.KEY_FILE_PATH, staged.absolutePath)
                        .putString(ScanUploadWorker.KEY_NAME, name)
                        .putLong(ScanUploadWorker.KEY_SIZE_BYTES, staged.length())
                        .putString(ScanUploadWorker.KEY_CASE_ID, caseId?.value)
                        .putString(ScanUploadWorker.KEY_FOLDER, folder)
                        .build()

                val request =
                    OneTimeWorkRequestBuilder<ScanUploadWorker>()
                        .setInputData(data)
                        .setConstraints(
                            Constraints
                                .Builder()
                                .setRequiredNetworkType(NetworkType.CONNECTED)
                                .build(),
                        ).setBackoffCriteria(
                            BackoffPolicy.EXPONENTIAL,
                            WorkRequest.MIN_BACKOFF_MILLIS,
                            TimeUnit.MILLISECONDS,
                        ).addTag(ScanUploadWorker.TAG)
                        .build()

                WorkManager.getInstance(context).enqueue(request)
                QueueResult.Enqueued(request.id)
            }

        /** All uploads currently tracked by WorkManager, regardless of which screen queued
         * them — a lawyer who backgrounds the app mid-upload still sees it finish. */
        fun uploads(): Flow<List<WorkInfo>> =
            WorkManager
                .getInstance(context)
                .getWorkInfosByTagFlow(ScanUploadWorker.TAG)

        private fun stage(uri: Uri): File {
            val dir = File(context.cacheDir, STAGING_DIR).apply { mkdirs() }
            val destination = File(dir, "${UUID.randomUUID()}.pdf")
            context.contentResolver.openInputStream(uri)?.use { input ->
                destination.outputStream().use { output -> input.copyTo(output) }
            } ?: error("The scan could not be opened.")
            return destination
        }

        private fun ContentResolver.querySize(uri: Uri): Long? =
            runCatching {
                query(uri, arrayOf(OpenableColumns.SIZE), null, null, null)?.use { cursor ->
                    val column = cursor.getColumnIndex(OpenableColumns.SIZE)
                    if (column >= 0 && cursor.moveToFirst() && !cursor.isNull(column)) {
                        cursor.getLong(column)
                    } else {
                        null
                    }
                }
            }.getOrNull()

        companion object {
            private const val STAGING_DIR = "pending_uploads"
        }
    }

sealed interface QueueResult {
    data class Enqueued(
        val workId: UUID,
    ) : QueueResult

    data class Rejected(
        val message: String,
    ) : QueueResult
}
