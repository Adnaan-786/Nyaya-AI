package ai.nyayaai.app

import ai.nyayaai.core.model.CaseId
import ai.nyayaai.core.model.ClientId
import ai.nyayaai.core.model.InvoiceId
import ai.nyayaai.core.model.UserRole
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material.icons.filled.Badge
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.Groups
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.ReceiptLong
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Timer
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
    const val CASE_ADD_CHOOSER = "case/chooser"
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

    /** D.9 screen inventory #19: a global stopwatch across cases, distinct from
     * [CASE_TIME_ADD]'s per-case manual entry. */
    const val TIME_TRACKER = "billing/timer"
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
        Route.CASE_ADD_CHOOSER to R.string.title_add_case,
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
        // A tab until the "More" sheet took the fifth slot. Being here is what gives it a
        // back arrow now that it is pushed rather than switched to.
        Route.INVOICES to R.string.nav_invoices,
        Route.INVOICE_DETAIL to R.string.title_invoice,
        Route.INVOICE_ADD to R.string.title_add_invoice,
        Route.TIME_TRACKER to R.string.title_time_tracker,
        Route.NOTIFICATIONS to R.string.title_notifications,
        Route.TEAM to R.string.title_team,
        // Client mode's own case screen — same generic "Case" title staff mode uses.
        Route.PORTAL_CASE_DETAIL to R.string.title_case,
    )

/**
 * Four tabs, not five: the fifth slot is the "More" sheet ([MoreSheet]), which is a
 * disclosure rather than a destination.
 *
 * These four are the ones a litigator is *in* during a working day. Everything else —
 * invoices, the calendar, tasks, clients, team, settings — is reached by name from the
 * sheet. That is a longer path for invoices than the tab it used to have, and a much
 * shorter one for clients and tasks, which were previously unlabelled icons in the top
 * bar and effectively unfindable.
 */
private val STAFF_DESTINATIONS =
    listOf(
        Destination(Route.TODAY, R.string.nav_today, Icons.Default.Today),
        Destination(Route.CASES, R.string.nav_cases, Icons.AutoMirrored.Filled.List),
        Destination(Route.VAULT, R.string.nav_vault, Icons.Default.Folder),
        Destination(Route.AI, R.string.nav_ai, Icons.Default.Search),
    )

/**
 * What the "More" sheet lists, in the order it shows them. Ordered by how often a
 * practice actually reaches for each, not alphabetically.
 *
 * [adminOnly] mirrors the gate `NyayaNavHost` already applies to `TeamRoute` — offering
 * a tap that lands on a screen with every control disabled is worse than not offering it.
 */
data class MoreEntry(
    val route: String,
    val labelRes: Int,
    val icon: ImageVector,
    val adminOnly: Boolean = false,
)

val MORE_ENTRIES =
    listOf(
        MoreEntry(Route.CALENDAR, R.string.title_calendar, Icons.Default.CalendarMonth),
        MoreEntry(Route.TASKS, R.string.title_tasks, Icons.Default.CheckCircle),
        MoreEntry(Route.CLIENTS, R.string.title_clients, Icons.Default.Groups),
        MoreEntry(Route.INVOICES, R.string.nav_invoices, Icons.Default.ReceiptLong),
        MoreEntry(Route.TIME_TRACKER, R.string.title_time_tracker, Icons.Default.Timer),
        MoreEntry(Route.TEAM, R.string.title_team, Icons.Default.Badge, adminOnly = true),
        MoreEntry(Route.SETTINGS, R.string.title_settings, Icons.Default.Settings),
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
