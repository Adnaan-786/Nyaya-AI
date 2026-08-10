package ai.nyayaai.app

import ai.nyayaai.core.network.api.ApiResult
import ai.nyayaai.feature.notifications.NotificationRepository
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

/**
 * State the app shell owns, as opposed to any one screen: currently just the unread
 * count behind the top bar's bell.
 *
 * The bell existed with no badge, which made it decorative — there was no way to know
 * a case had been listed or a client had paid without opening the screen to check.
 */
@HiltViewModel
class ShellViewModel
    @Inject
    constructor(
        private val repository: NotificationRepository,
    ) : ViewModel() {
        private val _unreadCount = MutableStateFlow(0)
        val unreadCount: StateFlow<Int> = _unreadCount.asStateFlow()

        init {
            refreshUnread()
        }

        /**
         * Deliberately silent on failure. This is a badge: a wrong count is a small,
         * self-correcting problem, and surfacing "could not load notifications" over
         * whichever screen the user is actually working on would be a much larger one.
         */
        fun refreshUnread() {
            viewModelScope.launch {
                when (val result = repository.notifications(unreadOnly = true)) {
                    is ApiResult.Success -> _unreadCount.value = result.data.size
                    is ApiResult.Failure -> Unit
                }
            }
        }
    }
