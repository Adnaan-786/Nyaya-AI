package ai.nyayaai.app

import ai.nyayaai.feature.ai.AiRoute
import ai.nyayaai.feature.billing.InvoiceListRoute
import ai.nyayaai.feature.cases.AddByCnrRoute
import ai.nyayaai.feature.cases.CaseDetailRoute
import ai.nyayaai.feature.cases.CaseDetailViewModel
import ai.nyayaai.feature.cases.CaseListRoute
import ai.nyayaai.feature.dashboard.TodayRoute
import ai.nyayaai.feature.portal.PortalRoute
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.navArgument

@Composable
fun NyayaNavHost(
    navController: NavHostController,
    startDestination: String,
    onOpenUrl: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    NavHost(
        navController = navController,
        startDestination = startDestination,
        modifier = modifier,
    ) {
        composable(Route.TODAY) {
            TodayRoute(onOpenCase = { navController.navigate(Route.caseDetail(it)) })
        }

        composable(Route.CASES) {
            CaseListRoute(
                onOpenCase = { navController.navigate(Route.caseDetail(it)) },
                onAddCase = { navController.navigate(Route.ADD_CNR) },
            )
        }

        composable(
            route = Route.CASE_DETAIL,
            arguments =
                listOf(
                    navArgument(CaseDetailViewModel.ARG_CASE_ID) { type = NavType.StringType },
                ),
        ) {
            CaseDetailRoute()
        }

        composable(Route.ADD_CNR) {
            AddByCnrRoute(
                onCaseCreated = { id ->
                    // Replace rather than stack: after adding a case, going back should
                    // return to the list, not to the form that just succeeded.
                    navController.navigate(Route.caseDetail(id)) {
                        popUpTo(Route.ADD_CNR) { inclusive = true }
                    }
                },
                onManualEntry = { navController.popBackStack() },
            )
        }

        composable(Route.AI) {
            AiRoute(onOpenCitation = onOpenUrl, onUpgrade = { /* paywall lands in A8 */ })
        }

        composable(Route.INVOICES) {
            InvoiceListRoute()
        }

        composable(Route.PORTAL) {
            PortalRoute(onPay = onOpenUrl)
        }
    }
}
