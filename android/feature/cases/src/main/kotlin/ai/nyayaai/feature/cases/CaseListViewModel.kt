package ai.nyayaai.feature.cases

import ai.nyayaai.core.common.UiState
import ai.nyayaai.core.model.Case
import ai.nyayaai.core.network.api.ApiResult
import ai.nyayaai.core.network.api.isRetryable
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.debounce
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

enum class CaseFilter(
    val wire: String?,
) {
    ALL(null),
    ACTIVE("active"),
    DISPOSED("disposed"),
}

@OptIn(FlowPreview::class)
@HiltViewModel
class CaseListViewModel
    @Inject
    constructor(
        private val repository: CaseRepository,
    ) : ViewModel() {
        private val _state = MutableStateFlow<UiState<List<Case>>>(UiState.Loading)
        val state: StateFlow<UiState<List<Case>>> = _state.asStateFlow()

        private val _query = MutableStateFlow("")
        val query: StateFlow<String> = _query.asStateFlow()

        private val _filter = MutableStateFlow(CaseFilter.ACTIVE)
        val filter: StateFlow<CaseFilter> = _filter.asStateFlow()

        init {
            viewModelScope.launch {
                // Search-as-you-type (D.5), debounced so a 12-character case name is one
                // request rather than twelve — this runs on Indian mobile data.
                _query
                    .debounce(SEARCH_DEBOUNCE_MS)
                    .distinctUntilChanged()
                    .collect { load() }
            }
        }

        fun onQueryChanged(value: String) {
            _query.value = value
        }

        fun onFilterChanged(value: CaseFilter) {
            _filter.value = value
            load()
        }

        fun load() {
            viewModelScope.launch {
                _state.update { if (it is UiState.Content) it.copy(isRefreshing = true) else UiState.Loading }

                _state.value =
                    when (val result = repository.cases(_query.value, _filter.value.wire)) {
                        is ApiResult.Failure ->
                            UiState.Error(result.error.message, result.error.isRetryable)

                        // An empty result stays Content. "No cases yet" and "nothing matched
                        // your search" need different words and different next steps, and the
                        // screen is the only layer that has both the query and a Context to
                        // localize with — the ViewModel has neither.
                        is ApiResult.Success -> UiState.Content(result.data)
                    }
            }
        }

        private companion object {
            const val SEARCH_DEBOUNCE_MS = 300L
        }
    }
