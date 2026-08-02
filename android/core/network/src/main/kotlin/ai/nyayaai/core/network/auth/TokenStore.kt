package ai.nyayaai.core.network.auth

import ai.nyayaai.core.model.Session
import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Credential storage.
 *
 * Reads are synchronous because [ai.nyayaai.core.network.interceptor.AuthInterceptor] and
 * [TokenAuthenticator] run on OkHttp's threads and cannot suspend.
 *
 * This is an interface so the refresh logic can be tested without an Android runtime —
 * token rotation under concurrency is the kind of thing that must be proven, not assumed.
 */
interface TokenStore {
    /** Drives the root navigation graph: logged out sends the user to the OTP screen. */
    val isLoggedIn: StateFlow<Boolean>

    val accessToken: String?

    val refreshToken: String?

    /**
     * The id `POST /devices` returned for this handset's current registration, if any.
     * Session-scoped like the tokens: [clear] wipes it too, so a shared handset does not
     * carry a stale device id into the next person's login.
     */
    var deviceId: String?

    fun save(
        accessToken: String,
        refreshToken: String,
    )

    /**
     * D.11.4: logout wipes tokens. Wiping Room and cached files is the caller's job —
     * this owns credentials only.
     */
    fun clear()
}

fun TokenStore.save(session: Session) = save(session.accessToken, session.refreshToken)

/** D.11.4: tokens live in EncryptedSharedPreferences, never in plain DataStore. */
@Singleton
class EncryptedTokenStore
    @Inject
    constructor(
        @ApplicationContext context: Context,
    ) : TokenStore {
        private val prefs: SharedPreferences =
            EncryptedSharedPreferences.create(
                context,
                FILE_NAME,
                MasterKey
                    .Builder(context)
                    .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                    .build(),
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
            )

        private val _isLoggedIn = MutableStateFlow(prefs.contains(KEY_ACCESS))

        override val isLoggedIn: StateFlow<Boolean> = _isLoggedIn.asStateFlow()

        override val accessToken: String? get() = prefs.getString(KEY_ACCESS, null)

        override val refreshToken: String? get() = prefs.getString(KEY_REFRESH, null)

        override var deviceId: String?
            get() = prefs.getString(KEY_DEVICE_ID, null)
            set(value) {
                prefs.edit().putString(KEY_DEVICE_ID, value).commit()
            }

        override fun save(
            accessToken: String,
            refreshToken: String,
        ) {
            // commit(), not apply(): the OkHttp thread that just rotated the token may hand
            // off to another thread immediately, and a lost write logs the user out.
            prefs
                .edit()
                .putString(KEY_ACCESS, accessToken)
                .putString(KEY_REFRESH, refreshToken)
                .commit()
            _isLoggedIn.value = true
        }

        override fun clear() {
            prefs.edit().clear().commit()
            _isLoggedIn.value = false
        }

        private companion object {
            const val FILE_NAME = "nyayaai_session"
            const val KEY_ACCESS = "access_token"
            const val KEY_REFRESH = "refresh_token"
            const val KEY_DEVICE_ID = "device_id"
        }
    }
