package ai.nyayaai.feature.billing

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import dagger.hilt.android.AndroidEntryPoint
import kotlin.time.Instant
import javax.inject.Inject

/**
 * D.9: "per-case stopwatch as a foreground service with a persistent notification."
 *
 * This class owns nothing but the OS-level foreground lifecycle and the notification —
 * [TimeTrackerCoordinator] is the single source of truth for whether a timer is running
 * and what persisting it means, exactly so this service can be this thin. The Stop
 * action, whether tapped here or from [TimeTrackerScreen], always ends up back at
 * [TimeTrackerCoordinator.stop].
 *
 * Declared `foregroundServiceType="specialUse"` (see the module's AndroidManifest.xml):
 * none of Android 14's standard categories (dataSync, mediaPlayback, location, …)
 * describe a billable-hours stopwatch, and `specialUse` exists precisely for that case.
 */
@AndroidEntryPoint
class TimeTrackerService : Service() {
    @Inject lateinit var coordinator: TimeTrackerCoordinator

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(
        intent: Intent?,
        flags: Int,
        startId: Int,
    ): Int {
        when (intent?.action) {
            ACTION_STOP -> {
                coordinator.stop()
                stopForeground(STOP_FOREGROUND_REMOVE)
                stopSelf()
            }

            else -> {
                val caseTitle = intent?.getStringExtra(EXTRA_CASE_TITLE).orEmpty()
                val startedAtMillis = intent?.getLongExtra(EXTRA_STARTED_AT_MILLIS, 0L) ?: 0L
                ensureChannel()
                startForeground(NOTIFICATION_ID, buildNotification(caseTitle, startedAtMillis))
            }
        }

        // No persisted timer state to resume from if the process dies — a stopwatch is
        // inherently in-memory, same "first cut" scope as AddTimeEntryScreen's own
        // startedAt-is-always-now note.
        return START_NOT_STICKY
    }

    private fun buildNotification(
        caseTitle: String,
        startedAtMillis: Long,
    ): Notification {
        val stopIntent =
            Intent(this, TimeTrackerService::class.java).setAction(ACTION_STOP)
        val stopPending =
            PendingIntent.getService(
                this,
                0,
                stopIntent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )

        return NotificationCompat
            .Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_menu_recent_history)
            .setContentTitle(getString(R.string.timer_notification_title, caseTitle))
            .setContentText(getString(R.string.timer_notification_body))
            // The OS ticks this itself from `startedAtMillis` — no in-process timer loop
            // needed to keep the displayed duration live.
            .setWhen(startedAtMillis)
            .setUsesChronometer(true)
            .setShowWhen(true)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .addAction(0, getString(R.string.timer_stop), stopPending)
            .build()
    }

    private fun ensureChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = getSystemService(NotificationManager::class.java) ?: return
        manager.createNotificationChannel(
            NotificationChannel(
                CHANNEL_ID,
                getString(R.string.timer_channel_name),
                // Low, not default: a running timer notification is expected to sit there
                // for hours and must never make sound or heads-up on every tick.
                NotificationManager.IMPORTANCE_LOW,
            ),
        )
    }

    companion object {
        private const val CHANNEL_ID = "time_tracker"
        private const val NOTIFICATION_ID = 4201
        private const val EXTRA_CASE_TITLE = "case_title"
        private const val EXTRA_STARTED_AT_MILLIS = "started_at_millis"
        private const val ACTION_STOP = "ai.nyayaai.feature.billing.action.STOP_TIMER"

        fun start(
            context: Context,
            caseTitle: String,
            startedAt: Instant,
        ) {
            val intent =
                Intent(context, TimeTrackerService::class.java)
                    .putExtra(EXTRA_CASE_TITLE, caseTitle)
                    .putExtra(EXTRA_STARTED_AT_MILLIS, startedAt.toEpochMilliseconds())
            context.startForegroundService(intent)
        }

        fun stop(context: Context) {
            context.startService(Intent(context, TimeTrackerService::class.java).setAction(ACTION_STOP))
        }
    }
}
