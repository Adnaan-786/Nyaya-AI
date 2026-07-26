package ai.nyayaai.core.network.auth

import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Lets the network layer tell the app shell that the session is gone, without
 * `core:network` depending on navigation.
 *
 * Emitted when a refresh fails (B.4.4: the 30-day refresh token expired or was rotated
 * out from under us). The root NavHost collects this and resets to the login graph.
 */
@Singleton
class SessionEvents
    @Inject
    constructor() {
        private val _forcedLogout =
            MutableSharedFlow<Unit>(
                replay = 1,
                onBufferOverflow = BufferOverflow.DROP_OLDEST,
            )

        val forcedLogout: SharedFlow<Unit> = _forcedLogout.asSharedFlow()

        fun notifyForcedLogout() {
            _forcedLogout.tryEmit(Unit)
        }

        @OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
        fun consume() {
            _forcedLogout.resetReplayCache()
        }
    }
