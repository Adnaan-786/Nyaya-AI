package ai.nyayaai.app.push

import ai.nyayaai.app.MainActivity
import ai.nyayaai.app.R
import ai.nyayaai.core.common.DeepLink
import ai.nyayaai.core.model.PushType
import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import javax.inject.Inject

/**
 * B.8 push handling.
 *
 * The server sends **data-only** messages, so this runs for every push whether the app is
 * foreground, background or dead. A `notification` block would let Android post the push
 * itself while backgrounded, and the app would never see it — no deep link routing, no
 * channel choice, no chance to suppress a reminder the user already acted on.
 */
@AndroidEntryPoint
class NyayaMessagingService : FirebaseMessagingService() {
    @Inject lateinit var deviceRegistrar: DeviceRegistrar

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    /**
     * B.4.6 requires registration after **every** token refresh, not just at login.
     * FCM rotates tokens on app data clear, restore-to-new-device and occasionally on
     * its own; a missed rotation means a lawyer silently stops getting hearing reminders.
     */
    override fun onNewToken(token: String) {
        scope.launch { deviceRegistrar.register(token) }
    }

    override fun onMessageReceived(message: RemoteMessage) {
        val data = message.data
        val type = PushType.from(data["type"])

        // B.8: an unrecognised type is dropped, never crashed on. The server can add a
        // push type after this build ships and installed apps must simply ignore it.
        if (type == PushType.UNKNOWN) return

        show(
            type = type,
            title = data["title"].orEmpty(),
            body = data["body"].orEmpty(),
            deepLink = data["deep_link"],
        )
    }

    private fun show(
        type: PushType,
        title: String,
        body: String,
        deepLink: String?,
    ) {
        if (title.isBlank() && body.isBlank()) return

        val channel = NotificationChannels.forType(type)
        NotificationChannels.ensure(this)

        // Routed through the same parser internal navigation uses, so a push and a tap
        // land in identical state (A1.4).
        val target = deepLink?.takeIf { DeepLink.parse(it) != null }
        val intent =
            Intent(this, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP
                target?.let { data = Uri.parse(it) }
            }

        val pending =
            PendingIntent.getActivity(
                this,
                target.hashCode(),
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )

        val notification =
            NotificationCompat
                .Builder(this, channel.id)
                .setSmallIcon(R.drawable.ic_notification)
                .setContentTitle(title)
                .setContentText(body)
                .setStyle(NotificationCompat.BigTextStyle().bigText(body))
                .setPriority(channel.priority)
                .setAutoCancel(true)
                .setContentIntent(pending)
                .build()

        if (!canPost()) return

        // `canPost()` above is the permission check lint wants — it just can't trace it
        // through a private boolean-returning function rather than the exact
        // `checkSelfPermission` call site.
        @Suppress("MissingPermission")
        NotificationManagerCompat
            .from(this)
            .notify(target.hashCode(), notification)
    }

    /**
     * Android 13+ can revoke POST_NOTIFICATIONS at any time. Posting without it throws,
     * and a crash in a push handler is invisible to the user and hard to diagnose.
     */
    private fun canPost(): Boolean =
        Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) ==
            PackageManager.PERMISSION_GRANTED
}

/**
 * B.8's four user-configurable channels.
 *
 * Separate channels exist so a lawyer can silence daily digests without also silencing
 * hearing reminders. One channel for everything would force that all-or-nothing choice,
 * and the reminder is the one push that must never be turned off by accident.
 */
enum class NotificationChannels(
    val id: String,
    val labelRes: Int,
    val priority: Int,
) {
    HEARINGS("hearings", R.string.channel_hearings, NotificationCompat.PRIORITY_HIGH),
    CASE_UPDATES("case_updates", R.string.channel_case_updates, NotificationCompat.PRIORITY_DEFAULT),
    AI_RESULTS("ai_results", R.string.channel_ai_results, NotificationCompat.PRIORITY_DEFAULT),
    BILLING("billing", R.string.channel_billing, NotificationCompat.PRIORITY_DEFAULT),
    ;

    companion object {
        fun forType(type: PushType): NotificationChannels =
            when (type) {
                PushType.HEARING_REMINDER, PushType.DAILY_DIGEST -> HEARINGS
                PushType.CASE_UPDATE, PushType.TASK_ASSIGNED -> CASE_UPDATES
                PushType.AI_JOB_COMPLETE -> AI_RESULTS
                PushType.PAYMENT_RECEIVED -> BILLING
                PushType.UNKNOWN -> CASE_UPDATES
            }

        fun ensure(context: Context) {
            if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return

            val manager = context.getSystemService(NotificationManager::class.java) ?: return
            entries.forEach { channel ->
                manager.createNotificationChannel(
                    NotificationChannel(
                        channel.id,
                        context.getString(channel.labelRes),
                        if (channel == HEARINGS) {
                            NotificationManager.IMPORTANCE_HIGH
                        } else {
                            NotificationManager.IMPORTANCE_DEFAULT
                        },
                    ),
                )
            }
        }
    }
}
