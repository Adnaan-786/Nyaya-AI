package ai.nyayaai.app

import ai.nyayaai.core.common.DeepLink
import ai.nyayaai.core.model.CaseId
import ai.nyayaai.core.model.User
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.scaleIn
import androidx.compose.animation.scaleOut
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Groups
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.navigation.NavHostController
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController

/**
 * The app shell: a top bar that always offers a way out, a bottom bar of tabs, and the
 * nav host between them.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NyayaApp(
    user: User,
    onOpenUrl: (String) -> Unit,
    onLoggedOut: () -> Unit,
    deepLink: String? = null,
    onDeepLinkHandled: () -> Unit = {},
    navController: NavHostController = rememberNavController(),
) {
    val destinations = destinationsFor(user.role)

    HandleDeepLink(deepLink, user.role.isClient, navController, onDeepLinkHandled)
    val backStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = backStackEntry?.destination?.route

    val isTab = destinations.any { it.route == currentRoute }
    val titleRes =
        destinations.firstOrNull { it.route == currentRoute }?.labelRes
            ?: PUSHED_TITLES[currentRoute]
            ?: R.string.app_name

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(titleRes)) },
                navigationIcon = {
                    // Every non-tab screen gets an explicit back arrow. System back
                    // still works, but on gesture navigation it is a swipe the user has
                    // to know about — an affordance they can see is not optional.
                    if (!isTab) {
                        IconButton(onClick = { navController.navigateUp() }) {
                            Icon(
                                Icons.AutoMirrored.Filled.ArrowBack,
                                contentDescription = stringResource(R.string.action_back),
                            )
                        }
                    }
                },
                actions = {
                    if (!user.role.isClient) {
                        StaffActions(
                            visible = isTab,
                            onNavigate = navController::navigate,
                        )
                    }
                },
                colors =
                    TopAppBarDefaults.topAppBarColors(
                        containerColor = MaterialTheme.colorScheme.surfaceContainerLowest,
                    ),
            )
        },
        bottomBar = {
            // Hidden on pushed screens so a detail view gets the whole height, and so
            // the tab bar never implies "you are on a tab" when you are three deep.
            AnimatedVisibility(
                visible = isTab,
                enter = fadeIn(),
                exit = fadeOut(),
            ) {
                NavigationBar {
                    destinations.forEach { destination ->
                        NavigationBarItem(
                            selected = currentRoute == destination.route,
                            onClick = {
                                navController.navigate(destination.route) {
                                    popUpTo(destinations.first().route) { saveState = true }
                                    launchSingleTop = true
                                    restoreState = true
                                }
                            },
                            icon = {
                                Icon(destination.icon, contentDescription = null)
                            },
                            label = { Text(stringResource(destination.labelRes)) },
                        )
                    }
                }
            }
        },
    ) { padding ->
        NyayaNavHost(
            navController = navController,
            startDestination = destinations.first().route,
            user = user,
            onOpenUrl = onOpenUrl,
            onLoggedOut = onLoggedOut,
            modifier = Modifier.padding(padding),
        )
    }
}

/**
 * Calendar, tasks and settings live in the top bar rather than the bottom one: five tabs
 * is already the limit, and these are things a lawyer reaches for occasionally rather
 * than as a home base.
 */
@Composable
private fun StaffActions(
    visible: Boolean,
    onNavigate: (String) -> Unit,
) {
    AnimatedVisibility(
        visible = visible,
        enter = fadeIn() + scaleIn(),
        exit = fadeOut() + scaleOut(),
    ) {
        Row {
            IconButton(onClick = { onNavigate(Route.NOTIFICATIONS) }) {
                Icon(
                    Icons.Default.Notifications,
                    contentDescription = stringResource(R.string.nav_notifications),
                )
            }
            IconButton(onClick = { onNavigate(Route.CALENDAR) }) {
                Icon(
                    Icons.Default.CalendarMonth,
                    contentDescription = stringResource(R.string.title_calendar),
                )
            }
            IconButton(onClick = { onNavigate(Route.TASKS) }) {
                Icon(
                    Icons.Default.CheckCircle,
                    contentDescription = stringResource(R.string.title_tasks),
                )
            }
            IconButton(onClick = { onNavigate(Route.CLIENTS) }) {
                Icon(
                    Icons.Default.Groups,
                    contentDescription = stringResource(R.string.title_clients),
                )
            }
            IconButton(onClick = { onNavigate(Route.SETTINGS) }) {
                Icon(
                    Icons.Default.Settings,
                    contentDescription = stringResource(R.string.title_settings),
                )
            }
        }
    }
}

/**
 * B.8: a push and an in-app tap must land in identical state, so an incoming link is
 * resolved by the same parser and navigated with the same routes.
 *
 * Client-mode logins are excluded outright — a link to a staff screen must never become
 * a way into one.
 */
@Composable
private fun HandleDeepLink(
    deepLink: String?,
    isClient: Boolean,
    navController: NavHostController,
    onHandled: () -> Unit,
) {
    LaunchedEffect(deepLink) {
        if (deepLink == null) return@LaunchedEffect

        DeepLink.parse(deepLink)?.takeUnless { isClient }?.let { target ->
            routeFor(target)?.let(navController::navigate)
        }
        onHandled()
    }
}

/**
 * Maps a parsed deep link to a route.
 *
 * Job and task links resolve to their nearest existing home rather than being dropped:
 * the AI hub lists recent results, and tasks live on their own screen. A push that
 * opens nothing at all is worse than one that opens the right neighbourhood.
 *
 * Not `private`: [NyayaNavHost] reuses this exact mapping for a tap inside the in-app
 * notification inbox, which must land in the same place a system push does.
 */
fun routeFor(link: DeepLink): String? =
    when (link) {
        is DeepLink.Case -> Route.caseDetail(CaseId(link.caseId))
        is DeepLink.Job -> Route.AI
        is DeepLink.Invoice -> Route.INVOICES
        is DeepLink.Task -> Route.TASKS
        DeepLink.Today -> Route.TODAY
    }
