package ai.nyayaai.feature.cases

import ai.nyayaai.core.common.UiState
import ai.nyayaai.core.model.Case
import ai.nyayaai.core.model.CaseId
import ai.nyayaai.core.model.Document
import ai.nyayaai.core.model.Hearing
import ai.nyayaai.core.network.api.ApiResult
import ai.nyayaai.core.network.api.isRetryable
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class CaseDetail(
    val case: Case,
    val hearings: List<Hearing>,
    val documents: List<Document>,
    val isSyncing: Boolean = false,
    /** Surfaced as a transient message; a failed sync must not replace the case on screen. */
    val syncMessage: String? = null,
)

@HiltViewModel
class CaseDetailViewModel
    @Inject
    constructor(
        private val repository: CaseRepository,
        savedStateHandle: SavedStateHandle,
    ) : ViewModel() {
        private val caseId = CaseId(checkNotNull(savedStateHandle.get<String>(ARG_CASE_ID)))

        private val _state = MutableStateFlow<UiState<CaseDetail>>(UiState.Loading)
        val state: StateFlow<UiState<CaseDetail>> = _state.asStateFlow()

        init {
            load()
        }

        fun load() {
            viewModelScope.launch {
                _state.value = UiState.Loading

                val caseCall = async { repository.case(caseId) }
                val hearingsCall = async { repository.hearings(caseId) }
                val documentsCall = async { repository.documents(caseId) }

                _state.value =
                    when (val case = caseCall.await()) {
                        is ApiResult.Failure ->
                            UiState.Error(case.error.message, case.error.isRetryable)

                        is ApiResult.Success ->
                            UiState.Content(
                                CaseDetail(
                                    case = case.data,
                                    // Tabs degrade independently: a documents failure must
                                    // not hide the hearing history the lawyer opened this for.
                                    hearings = (hearingsCall.await() as? ApiResult.Success)?.data.orEmpty(),
                                    documents = (documentsCall.await() as? ApiResult.Success)?.data.orEmpty(),
                                ),
                            )
                    }
            }
        }

        /**
         * Pull-to-refresh maps to `POST /cases/{id}/sync`, which the server rate-limits to
         * once an hour. A RATE_LIMITED response is shown as a message rather than an
         * error state — the case on screen is still perfectly good.
         */
        fun sync() {
            val current = _state.value as? UiState.Content ?: return
            if (current.data.isSyncing) return

            _state.update { UiState.Content(current.data.copy(isSyncing = true, syncMessage = null)) }

            viewModelScope.launch {
                when (val result = repository.sync(caseId)) {
                    is ApiResult.Success ->
                        _state.value =
                            UiState.Content(
                                current.data.copy(case = result.data, isSyncing = false),
                            )

                    is ApiResult.Failure ->
                        _state.value =
                            UiState.Content(
                                current.data.copy(
                                    isSyncing = false,
                                    syncMessage = result.error.message,
                                ),
                            )
                }
            }
        }

        fun dismissSyncMessage() {
            val current = _state.value as? UiState.Content ?: return
            _state.value = UiState.Content(current.data.copy(syncMessage = null))
        }

        companion object {
            const val ARG_CASE_ID = "caseId"
        }
    }
