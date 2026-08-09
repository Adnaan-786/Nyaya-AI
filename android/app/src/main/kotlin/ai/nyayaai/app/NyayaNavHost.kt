package ai.nyayaai.app

import ai.nyayaai.core.model.CaseId
import ai.nyayaai.core.model.InvoiceId
import ai.nyayaai.core.model.User
import ai.nyayaai.core.model.UserRole
import ai.nyayaai.feature.ai.AiRoute
import ai.nyayaai.feature.billing.AddInvoiceRoute
import ai.nyayaai.feature.billing.InvoiceDetailRoute
import ai.nyayaai.feature.billing.InvoiceDetailViewModel
import ai.nyayaai.feature.billing.InvoiceListRoute
import ai.nyayaai.feature.calendar.CalendarRoute
import ai.nyayaai.feature.cases.AddByCnrRoute
import ai.nyayaai.feature.cases.AddCaseRoute
import ai.nyayaai.feature.cases.AddHearingRoute
import ai.nyayaai.feature.cases.AddHearingViewModel
import ai.nyayaai.feature.cases.AddTimeEntryRoute
import ai.nyayaai.feature.cases.AddTimeEntryViewModel
import ai.nyayaai.feature.cases.CaseDetailRoute
import ai.nyayaai.feature.cases.CaseDetailViewModel
import ai.nyayaai.feature.cases.CaseListRoute
import ai.nyayaai.feature.clients.AddClientRoute
import ai.nyayaai.feature.clients.ClientDetailRoute
import ai.nyayaai.feature.clients.ClientDetailViewModel
import ai.nyayaai.feature.clients.ClientListRoute
import ai.nyayaai.core.common.DeepLink
import ai.nyayaai.feature.dashboard.TodayRoute
import ai.nyayaai.feature.documents.VaultRoute
import ai.nyayaai.feature.notifications.NotificationsRoute
import ai.nyayaai.feature.portal.PortalCaseDetailRoute
import ai.nyayaai.feature.portal.PortalCaseDetailViewModel
import ai.nyayaai.feature.portal.PortalRoute
import ai.nyayaai.feature.settings.SettingsRoute
import ai.nyayaai.feature.tasks.AddTaskRoute
import ai.nyayaai.feature.tasks.TasksRoute
import ai.nyayaai.feature.team.TeamRoute
import androidx.compose.animation.AnimatedContentTransitionScope
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.navArgument

private const val TRANSITION_MS = 260

@Composable
fun NyayaNavHost(
    navController: NavHostController,
    startDestination: String,
    user: User,
    onOpenUrl: (String) -> Unit,
    onLoggedOut: () -> Unit,
    modifier: Modifier = Modifier,
) {
    NavHost(
        navController = navController,
        startDestination = startDestination,
        modifier = modifier,
        // Push/pop slides horizontally so the back arrow's direction matches what the
        // screen actually does; tab switches cross-fade instead, because sliding
        // sideways between peers implies a hierarchy that isn't there.
        enterTransition = {
            slideInHorizontally(tween(TRANSITION_MS)) { it / SLIDE_FRACTION } + fadeIn(tween(TRANSITION_MS))
        },
        exitTransition = {
            slideOutHorizontally(tween(TRANSITION_MS)) { -it / SLIDE_FRACTION } + fadeOut(tween(TRANSITION_MS))
        },
        popEnterTransition = {
            slideInHorizontally(tween(TRANSITION_MS)) { -it / SLIDE_FRACTION } + fadeIn(tween(TRANSITION_MS))
        },
        popExitTransition = {
            slideOutHorizontally(tween(TRANSITION_MS)) { it / SLIDE_FRACTION } + fadeOut(tween(TRANSITION_MS))
        },
    ) {
        composable(Route.TODAY, enterTransition = { fade() }, exitTransition = { fadeAway() }) {
            TodayRoute(onOpenCase = { navController.navigate(Route.caseDetail(it)) })
        }

        composable(Route.CASES, enterTransition = { fade() }, exitTransition = { fadeAway() }) {
            CaseListRoute(
                onOpenCase = { navController.navigate(Route.caseDetail(it)) },
                onAddCase = { navController.navigate(Route.ADD_CNR) },
            )
        }

        composable(Route.VAULT, enterTransition = { fade() }, exitTransition = { fadeAway() }) {
            VaultRoute(onOpenDocument = { document -> document.downloadUrl?.let(onOpenUrl) })
        }

        composable(Route.AI, enterTransition = { fade() }, exitTransition = { fadeAway() }) {
            AiRoute(onOpenCitation = onOpenUrl, onUpgrade = { /* paywall lands in A8 */ })
        }

        composable(Route.INVOICES, enterTransition = { fade() }, exitTransition = { fadeAway() }) {
            InvoiceListRoute(
                firmName = user.name,
                onOpenInvoice = { navController.navigate(Route.invoiceDetail(it)) },
                onAddInvoice = { navController.navigate(Route.INVOICE_ADD) },
            )
        }

        composable(
            route = Route.INVOICE_DETAIL,
            arguments = listOf(navArgument(InvoiceDetailViewModel.ARG_INVOICE_ID) { type = NavType.StringType }),
        ) {
            InvoiceDetailRoute(onOpenPdf = onOpenUrl)
        }

        composable(Route.INVOICE_ADD) {
            AddInvoiceRoute(
                onInvoiceCreated = { id ->
                    navController.navigate(Route.invoiceDetail(id)) {
                        popUpTo(Route.INVOICE_ADD) { inclusive = true }
                    }
                },
            )
        }

        composable(
            route = Route.CASE_DETAIL,
            arguments = listOf(navArgument(CaseDetailViewModel.ARG_CASE_ID) { type = NavType.StringType }),
        ) { backStackEntry ->
            val caseId = backStackEntry.arguments?.getString(CaseDetailViewModel.ARG_CASE_ID)
            CaseDetailRoute(
                onAddHearing = {
                    caseId?.let { navController.navigate(Route.caseHearingAdd(CaseId(it))) }
                },
                onAddTimeEntry = {
                    caseId?.let { navController.navigate(Route.caseTimeAdd(CaseId(it))) }
                },
            )
        }

        composable(Route.ADD_CNR) {
            AddByCnrRoute(
                onCaseCreated = { id ->
                    // Replace rather than stack: after adding a case, back should return
                    // to the list, not to the form that just succeeded.
                    navController.navigate(Route.caseDetail(id)) {
                        popUpTo(Route.ADD_CNR) { inclusive = true }
                    }
                },
                onManualEntry = { navController.navigate(Route.CASE_ADD_MANUAL) },
            )
        }

        composable(Route.CASE_ADD_MANUAL) {
            AddCaseRoute(
                onCaseCreated = { id ->
                    // Clears both CASE_ADD_MANUAL and, if present, the ADD_CNR screen
                    // underneath it — back from the new case lands on the case list
                    // either way the form was reached.
                    navController.navigate(Route.caseDetail(id)) {
                        popUpTo(Route.CASES) { inclusive = false }
                    }
                },
            )
        }

        composable(
            route = Route.CASE_HEARING_ADD,
            arguments = listOf(navArgument(AddHearingViewModel.ARG_CASE_ID) { type = NavType.StringType }),
        ) {
            AddHearingRoute(onHearingAdded = { navController.popBackStack() })
        }

        composable(
            route = Route.CASE_TIME_ADD,
            arguments = listOf(navArgument(AddTimeEntryViewModel.ARG_CASE_ID) { type = NavType.StringType }),
        ) {
            AddTimeEntryRoute(onTimeEntryAdded = { navController.popBackStack() })
        }

        composable(Route.CALENDAR) {
            CalendarRoute(onOpenCase = { navController.navigate(Route.caseDetail(it)) })
        }

        composable(Route.TASKS) {
            TasksRoute(onAddTask = { navController.navigate(Route.TASK_ADD) })
        }

        composable(Route.TASK_ADD) {
            AddTaskRoute(onTaskCreated = { navController.popBackStack() })
        }

        composable(Route.SETTINGS) {
            SettingsRoute(
                userName = user.name,
                userContact = user.phone ?: user.email,
                roleLabel = stringResource(user.role.labelRes()),
                onLoggedOut = onLoggedOut,
                showTeam = !user.role.isClient,
                onOpenTeam = { navController.navigate(Route.TEAM) },
            )
        }

        composable(Route.PORTAL, enterTransition = { fade() }, exitTransition = { fadeAway() }) {
            // D.10: PortalCaseDetailRoute, never the staff CaseDetailRoute — a client tap
            // must never reach a staff screen.
            PortalRoute(
                onPay = onOpenUrl,
                onOpenCase = { navController.navigate(Route.portalCaseDetail(it)) },
            )
        }

        composable(
            route = Route.PORTAL_CASE_DETAIL,
            arguments = listOf(navArgument(PortalCaseDetailViewModel.ARG_CASE_ID) { type = NavType.StringType }),
        ) {
            PortalCaseDetailRoute()
        }

        composable(Route.NOTIFICATIONS) {
            NotificationsRoute(
                onOpenDeepLink = { raw ->
                    // Same parser and route mapping a system push already goes through
                    // (NyayaApp's HandleDeepLink/routeFor) — a tap in this inbox must land
                    // exactly where the equivalent push notification would.
                    DeepLink.parse(raw)?.let { target -> routeFor(target)?.let(navController::navigate) }
                },
            )
        }

        composable(Route.TEAM) {
            TeamRoute(
                currentUserId = user.id,
                isAdmin = user.role == UserRole.FIRM_ADMIN,
            )
        }

        composable(Route.CLIENTS) {
            ClientListRoute(
                onOpenClient = { navController.navigate(Route.clientDetail(it)) },
                onAddClient = { navController.navigate(Route.CLIENT_ADD) },
            )
        }

        composable(
            route = Route.CLIENT_DETAIL,
            arguments = listOf(navArgument(ClientDetailViewModel.ARG_CLIENT_ID) { type = NavType.StringType }),
        ) {
            ClientDetailRoute(onOpenCase = { navController.navigate(Route.caseDetail(it)) })
        }

        composable(Route.CLIENT_ADD) {
            AddClientRoute(
                onClientCreated = { id ->
                    navController.navigate(Route.clientDetail(id)) {
                        popUpTo(Route.CLIENT_ADD) { inclusive = true }
                    }
                },
            )
        }
    }
}

private fun AnimatedContentTransitionScope<*>.fade() = fadeIn(tween(TRANSITION_MS))

private fun AnimatedContentTransitionScope<*>.fadeAway() = fadeOut(tween(TRANSITION_MS))

private fun UserRole.labelRes(): Int =
    when (this) {
        UserRole.FIRM_ADMIN -> ai.nyayaai.feature.settings.R.string.settings_role_firm_admin
        UserRole.LAWYER -> ai.nyayaai.feature.settings.R.string.settings_role_lawyer
        UserRole.INTERN -> ai.nyayaai.feature.settings.R.string.settings_role_intern
        UserRole.CLIENT -> ai.nyayaai.feature.settings.R.string.settings_role_client
        UserRole.UNKNOWN -> ai.nyayaai.feature.settings.R.string.settings_role_lawyer
    }

private const val SLIDE_FRACTION = 6
