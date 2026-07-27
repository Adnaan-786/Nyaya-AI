package ai.nyayaai.feature.settings

import ai.nyayaai.core.model.Language
import ai.nyayaai.core.network.auth.TokenStore
import androidx.appcompat.app.AppCompatDelegate
import androidx.core.os.LocaleListCompat
import androidx.lifecycle.ViewModel
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject

@HiltViewModel
class SettingsViewModel
    @Inject
    constructor(
        // Injected directly rather than through feature:auth — features must not depend
        // on each other (D.2), and clearing the session is a core:network concern.
        private val tokenStore: TokenStore,
    ) : ViewModel() {
        /**
         * D.11.4: logout wipes the token pair. Room and cached files are wiped here too
         * once offline caching lands — a shared device must not leave one lawyer's
         * privileged case data readable by the next person to sign in.
         */
        fun logout() = tokenStore.clear()

        fun setLanguage(language: Language) {
            // Per-app language: the OS remembers it across launches and it does not
            // change the device locale for anything else.
            AppCompatDelegate.setApplicationLocales(
                LocaleListCompat.forLanguageTags(language.wire),
            )
        }
    }
