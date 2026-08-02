package ai.nyayaai.app

import ai.nyayaai.core.model.CaseId
import ai.nyayaai.core.model.ClientId
import ai.nyayaai.core.model.InvoiceId
import ai.nyayaai.core.model.UserRole
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.ReceiptLong
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Today
import androidx.compose.ui.graphics.vector.ImageVector

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

    /** The manual-entry escape hatch from [ADD_CNR], and (D.5) a destination in its own right. */
    const val CASE_ADD_MANUAL = "case/new"
    const val CASE_HEARING_ADD = "case/{caseId}/hearing/new"
    const val CASE_TIME_ADD = "case/{caseId}/time/new"
    const val VAULT = "vault"
    const val AI = "ai"
    const val INVOICES = "invoices"
    const val INVOICE_DETAIL = "invoice/{invoiceId}"
    const val INVOICE_ADD = "invoice/new"
    const val CALENDAR = "calendar"
    const val TASKS = "tasks"
    const val TASK_ADD = "task/new"
    const val SETTINGS = "settings"
    const val PORTAL = "portal"
    const val CLIENTS = "clients"
    const val CLIENT_DETAIL = "client/{clientId}"
    const val CLIENT_ADD = "client/new"
    const val NOTIFICATIONS = "notifications"
    const val TEAM = "team"

    /** D.10: a leaf screen inside the client shell — distinct arg key from [CASE_DETAIL]. */
    const val PORTAL_CASE_DETAIL = "portal/case/{portalCaseId}"

    fun caseDetail(id: CaseId) = "case/${id.value}"

    fun caseHearingAdd(id: CaseId) = "case/${id.value}/hearing/new"

    fun caseTimeAdd(id: CaseId) = "case/${id.value}/time/new"

    fun clientDetail(id: ClientId) = "client/${id.value}"

    fun invoiceDetail(id: InvoiceId) = "invoice/${id.value}"

    fun portalCaseDetail(id: CaseId) = "portal/case/${id.value}"
}

/** A top-level tab. */
data class Destination(
    val route: String,
    val labelRes: Int,
    val icon: ImageVector,
)

/**
 * Titles for **pushed** screens — the ones with no tab of their own.
 *
 * Membership of this map is what puts a back arrow in the top bar. Deriving the arrow
 * from "is this a tab?" rather than from back-stack depth is deliberate: it is not
 * possible to add a pushed screen and forget the way out of it, which is exactly how
 * case detail ended up as a dead end.
 */
val PUSHED_TITLES: Map<String, Int> =
    mapOf(
        Route.CASE_DETAIL to R.string.title_case,
        Route.ADD_CNR to R.string.title_add_case,
        Route.CASE_ADD_MANUAL to R.string.title_add_case,
        Route.CASE_HEARING_ADD to R.string.title_add_hearing,
        Route.CASE_TIME_ADD to R.string.title_add_time_entry,
        Route.CALENDAR to R.string.title_calendar,
        Route.TASKS to R.string.title_tasks,
        Route.TASK_ADD to R.string.title_add_task,
        Route.SETTINGS to R.string.title_settings,
        Route.CLIENTS to R.string.title_clients,
        Route.CLIENT_DETAIL to R.string.title_client,
        Route.CLIENT_ADD to R.string.title_add_client,
        Route.INVOICE_DETAIL to R.string.title_invoice,
        Route.INVOICE_ADD to R.string.title_add_invoice,
        Route.NOTIFICATIONS to R.string.title_notifications,
        Route.TEAM to R.string.title_team,
        // Client mode's own case screen — same generic "Case" title staff mode uses.
        Route.PORTAL_CASE_DETAIL to R.string.title_case,
    )

private val STAFF_DESTINATIONS =
    listOf(
        Destination(Route.TODAY, R.string.nav_today, Icons.Default.Today),
        Destination(Route.CASES, R.string.nav_cases, Icons.AutoMirrored.Filled.List),
        Destination(Route.VAULT, R.string.nav_vault, Icons.Default.Folder),
        Destination(Route.AI, R.string.nav_ai, Icons.Default.Search),
        Destination(Route.INVOICES, R.string.nav_invoices, Icons.Default.ReceiptLong),
    )

/**
 * D.10: client mode is a *different shell*, not the staff shell with items hidden.
 * No AI, no vault, no team surfaces — and no navigation path to reach them.
 */
private val CLIENT_DESTINATIONS =
    listOf(
        Destination(Route.PORTAL, R.string.nav_my_cases, Icons.AutoMirrored.Filled.List),
        Destination(Route.SETTINGS, R.string.nav_settings, Icons.Default.Person),
    )

fun destinationsFor(role: UserRole): List<Destination> = if (role.isClient) CLIENT_DESTINATIONS else STAFF_DESTINATIONS
