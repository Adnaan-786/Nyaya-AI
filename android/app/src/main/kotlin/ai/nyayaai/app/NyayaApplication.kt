package ai.nyayaai.app

import ai.nyayaai.app.push.NotificationChannels
import android.app.Application
import dagger.hilt.android.HiltAndroidApp

@HiltAndroidApp
class NyayaApplication : Application() {
    override fun onCreate() {
        super.onCreate()

        // Registered at startup, not on first push. B.8 calls these user-configurable,
        // and a channel that does not exist until the first notification arrives cannot
        // be configured in advance — the user would have to receive a hearing reminder
        // before they could choose how hearing reminders behave.
        NotificationChannels.ensure(this)
    }
}
