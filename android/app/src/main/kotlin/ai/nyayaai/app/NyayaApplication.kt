package ai.nyayaai.app

import ai.nyayaai.app.push.NotificationChannels
import android.app.Application
import androidx.hilt.work.HiltWorkerFactory
import androidx.work.Configuration
import dagger.hilt.android.HiltAndroidApp
import javax.inject.Inject

@HiltAndroidApp
class NyayaApplication :
    Application(),
    Configuration.Provider {
        // D.7's upload queue runs as a Hilt-injected CoroutineWorker (ScanUploadWorker,
        // feature:documents), so WorkManager needs this factory to construct it with its
        // real dependencies rather than a no-arg constructor. The default WorkManager
        // initializer is disabled in the manifest specifically so it does not build
        // itself with the stock factory before this runs.
        @Inject
        lateinit var workerFactory: HiltWorkerFactory

        override val workManagerConfiguration: Configuration
            get() = Configuration.Builder().setWorkerFactory(workerFactory).build()

        override fun onCreate() {
            super.onCreate()

            // Registered at startup, not on first push. B.8 calls these user-configurable,
            // and a channel that does not exist until the first notification arrives cannot
            // be configured in advance — the user would have to receive a hearing reminder
            // before they could choose how hearing reminders behave.
            NotificationChannels.ensure(this)
        }
    }
