package ai.nyayaai.app

import ai.nyayaai.core.model.User
import ai.nyayaai.core.model.UserRole
import ai.nyayaai.feature.ai.AiRoute
import ai.nyayaai.feature.billing.InvoiceListRoute
import ai.nyayaai.feature.calendar.CalendarRoute
import ai.nyayaai.feature.cases.AddByCnrRoute
import ai.nyayaai.feature.cases.CaseDetailRoute
import ai.nyayaai.feature.cases.CaseDetailViewModel
import ai.nyayaai.feature.cases.CaseListRoute
import ai.nyayaai.feature.dashboard.TodayRoute
import ai.nyayaai.feature.documents.VaultRoute
import ai.nyayaai.feature.portal.PortalRoute
import ai.nyayaai.feature.settings.SettingsRoute
import ai.nyayaai.feature.tasks.TasksRoute
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
            InvoiceListRoute(firmName = user.name)
        }

        composable(
            route = Route.CASE_DETAIL,
            arguments = listOf(navArgument(CaseDetailViewModel.ARG_CASE_ID) { type = NavType.StringType }),
        ) {
            CaseDetailRoute()
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
                onManualEntry = { navController.popBackStack() },
            )
        }

        composable(Route.CALENDAR) {
            CalendarRoute(onOpenCase = { navController.navigate(Route.caseDetail(it)) })
        }

        composable(Route.TASKS) {
            TasksRoute()
        }

        composable(Route.SETTINGS) {
            SettingsRoute(
                userName = user.name,
                userPhone = user.phone,
                roleLabel = stringResource(user.role.labelRes()),
                onLoggedOut = onLoggedOut,
            )
        }

        composable(Route.PORTAL, enterTransition = { fade() }, exitTransition = { fadeAway() }) {
            PortalRoute(onPay = onOpenUrl)
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
