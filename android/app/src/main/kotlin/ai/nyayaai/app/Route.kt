package ai.nyayaai.app

import ai.nyayaai.core.model.CaseId

/**
 * Routes are strings rather than a sealed type because they double as **deep-link
 * targets** (B.8): `nyayaai://case/{id}` resolves to the same destination the app
 * navigates to internally, so a push notification and a tap land in identical state.
 */
object Route {
    const val TODAY = "today"
    const val CASES = "cases"
    const val CASE_DETAIL = "case/{caseId}"
    const val ADD_CNR = "case/add"
    const val AI = "ai"
    const val INVOICES = "invoices"
    const val PORTAL = "portal"

    fun caseDetail(id: CaseId) = "case/${id.value}"
}
