package ai.nyayaai.feature.documents

import ai.nyayaai.core.model.CaseId
import ai.nyayaai.core.network.api.ApiError
import ai.nyayaai.core.network.api.ApiResult
import ai.nyayaai.core.network.api.isRetryable
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.content.pm.ServiceInfo
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.Data
import androidx.work.ForegroundInfo
import androidx.work.WorkerParameters
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import java.io.File
import java.io.FileInputStream

/**
 * D.7's WorkManager-backed half of B.9: [ScanUploadQueue] stages the scan and enqueues
 * this; this owns the reserve/PUT/confirm sequence via [ScanUploader], a foreground
 * progress notification, and turning a failure into either a WorkManager retry
 * (connectivity, a 5xx, a rate limit — the plan's "retries on connectivity restore") or
 * a terminal failure the app surfaces (a validation error retrying can never fix).
 */
@HiltWorker
class ScanUploadWorker
    @AssistedInject
    constructor(
        @Assisted appContext: Context,
        @Assisted params: WorkerParameters,
        private val uploader: ScanUploader,
    ) : CoroutineWorker(appContext, params) {
        override suspend fun doWork(): Result {
            val input = parseInput(inputData) ?: return Result.failure()

            val file = File(input.filePath)
            if (!file.exists()) {
                // The staging file is gone — nothing left to retry with. This should only
                // happen if a previous run of this same work already finished and the
                // process died before WorkManager recorded it.
                return Result.failure(errorOutput("This scan could no longer be found."))
            }

            ensureChannel(applicationContext)
            runCatching { setForeground(foregroundInfo(input.name, percent = 0, indeterminate = true)) }

            var lastPercent = -1
            val result =
                uploader.upload(
                    name = input.name,
                    sizeBytes = input.sizeBytes,
                    caseId = input.caseId,
                    folder = input.folder,
                    openStream = { FileInputStream(file) },
                    onProgress = { sent ->
                        val percent = ((sent * PERCENT_SCALE) / input.sizeBytes.coerceAtLeast(1)).toInt()
                        if (percent != lastPercent) {
                            lastPercent = percent
                            notify(foregroundInfo(input.name, percent, indeterminate = false).notification)
                        }
                    },
                )

            return when (result) {
                is ApiResult.Success -> {
                    file.delete()
                    cancelNotification()
                    Result.success()
                }

                is ApiResult.Failure -> onFailure(result.error, input.name, file)
            }
        }

        private fun parseInput(data: Data): WorkInput? {
            val filePath = data.getString(KEY_FILE_PATH) ?: return null
            val name = data.getString(KEY_NAME) ?: return null
            val sizeBytes = data.getLong(KEY_SIZE_BYTES, -1L)
            if (sizeBytes < 0) return null
            return WorkInput(
                filePath = filePath,
                name = name,
                sizeBytes = sizeBytes,
                caseId = data.getString(KEY_CASE_ID)?.let(::CaseId),
                folder = data.getString(KEY_FOLDER),
            )
        }

        private data class WorkInput(
            val filePath: String,
            val name: String,
            val sizeBytes: Long,
            val caseId: CaseId?,
            val folder: String?,
        )

        private fun onFailure(
            error: ApiError,
            name: String,
            file: File,
        ): Result {
            // A transient failure (offline, a 5xx, a rate limit) is exactly what the
            // constraints + backoff policy exist for — keep the staged file and let
            // WorkManager retry once connectivity is back. Anything else (over the size
            // limit, a role/plan problem, a malformed response) will never succeed on
            // retry, so it is reported once and the file is cleaned up.
            if (error.isRetryable && runAttemptCount < MAX_ATTEMPTS) {
                return Result.retry()
            }

            file.delete()
            notifyFailure(name)
            return Result.failure(errorOutput(error.message))
        }

        private fun errorOutput(message: String) =
            Data
                .Builder()
                .putString(KEY_ERROR_MESSAGE, message)
                .build()

        private fun notify(notification: Notification) {
            val manager = applicationContext.getSystemService(NotificationManager::class.java) ?: return
            if (!canPostNotifications(applicationContext)) return
            @Suppress("MissingPermission")
            manager.notify(id.hashCode(), notification)
        }

        private fun notifyFailure(name: String) {
            if (!canPostNotifications(applicationContext)) return
            val notification =
                NotificationCompat
                    .Builder(applicationContext, UPLOAD_CHANNEL_ID)
                    .setSmallIcon(R.drawable.ic_upload)
                    .setContentTitle(applicationContext.getString(R.string.vault_upload_notification_failed, name))
                    .setOngoing(false)
                    .setAutoCancel(true)
                    .build()
            @Suppress("MissingPermission")
            applicationContext.getSystemService(NotificationManager::class.java)?.notify(id.hashCode(), notification)
        }

        private fun cancelNotification() {
            applicationContext.getSystemService(NotificationManager::class.java)?.cancel(id.hashCode())
        }

        private fun foregroundInfo(
            name: String,
            percent: Int,
            indeterminate: Boolean,
        ): ForegroundInfo {
            val notification =
                NotificationCompat
                    .Builder(applicationContext, UPLOAD_CHANNEL_ID)
                    .setSmallIcon(R.drawable.ic_upload)
                    .setContentTitle(applicationContext.getString(R.string.vault_upload_notification_title, name))
                    .setProgress(PERCENT_SCALE, percent, indeterminate)
                    .setOngoing(true)
                    .setSilent(true)
                    .setPriority(NotificationCompat.PRIORITY_LOW)
                    .build()

            return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                ForegroundInfo(id.hashCode(), notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
            } else {
                ForegroundInfo(id.hashCode(), notification)
            }
        }

        companion object {
            const val TAG = "scan_upload"

            const val KEY_FILE_PATH = "file_path"
            const val KEY_NAME = "name"
            const val KEY_SIZE_BYTES = "size_bytes"
            const val KEY_CASE_ID = "case_id"
            const val KEY_FOLDER = "folder"
            const val KEY_ERROR_MESSAGE = "error_message"

            const val UPLOAD_CHANNEL_ID = "document_uploads"
            private const val MAX_ATTEMPTS = 5
            private const val PERCENT_SCALE = 100

            fun ensureChannel(context: Context) {
                if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
                val manager = context.getSystemService(NotificationManager::class.java) ?: return
                manager.createNotificationChannel(
                    NotificationChannel(
                        UPLOAD_CHANNEL_ID,
                        context.getString(R.string.vault_upload_channel_name),
                        NotificationManager.IMPORTANCE_LOW,
                    ),
                )
            }

            private fun canPostNotifications(context: Context): Boolean =
                Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
                    androidx.core.content.ContextCompat.checkSelfPermission(
                        context,
                        android.Manifest.permission.POST_NOTIFICATIONS,
                    ) == android.content.pm.PackageManager.PERMISSION_GRANTED
        }
    }
