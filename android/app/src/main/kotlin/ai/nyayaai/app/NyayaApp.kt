package ai.nyayaai.app

import ai.nyayaai.core.model.UserRole
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.DateRange
import androidx.compose.material.icons.filled.List
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.ShoppingCart
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.navigation.NavHostController
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController

/**
 * The app shell.
 *
 * D.10: a `role=client` login gets a **different shell**, not the staff shell with items
 * hidden. Building it as a separate destination set means there is no navigation path
 * from client mode into the vault or the AI hub at all — the server would reject those
 * calls anyway, but a client should never see a tab that 403s.
 */
@Composable
fun NyayaApp(
    role: UserRole,
    onOpenUrl: (String) -> Unit,
    navController: NavHostController = rememberNavController(),
) {
    val destinations = if (role.isClient) CLIENT_DESTINATIONS else STAFF_DESTINATIONS
    val backStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = backStackEntry?.destination?.route

    Scaffold(
        bottomBar = {
            NavigationBar {
                destinations.forEach { destination ->
                    NavigationBarItem(
                        selected = currentRoute == destination.route,
                        onClick = {
                            navController.navigate(destination.route) {
                                // Tapping a tab returns to that tab's root rather than
                                // deepening the stack — standard bottom-nav behaviour.
                                popUpTo(destinations.first().route) { saveState = true }
                                launchSingleTop = true
                                restoreState = true
                            }
                        },
                        icon = { Icon(destination.icon, contentDescription = null) },
                        label = { Text(stringResource(destination.labelRes)) },
                    )
                }
            }
        },
    ) { padding ->
        NyayaNavHost(
            navController = navController,
            startDestination = destinations.first().route,
            onOpenUrl = onOpenUrl,
            modifier = Modifier.padding(padding),
        )
    }
}

data class Destination(
    val route: String,
    val labelRes: Int,
    val icon: ImageVector,
)

private val STAFF_DESTINATIONS =
    listOf(
        Destination(Route.TODAY, R.string.nav_today, Icons.Default.DateRange),
        Destination(Route.CASES, R.string.nav_cases, Icons.Default.List),
        Destination(Route.AI, R.string.nav_ai, Icons.Default.Search),
        Destination(Route.INVOICES, R.string.nav_invoices, Icons.Default.ShoppingCart),
    )

private val CLIENT_DESTINATIONS =
    listOf(
        Destination(Route.PORTAL, R.string.nav_my_cases, Icons.Default.List),
    )
