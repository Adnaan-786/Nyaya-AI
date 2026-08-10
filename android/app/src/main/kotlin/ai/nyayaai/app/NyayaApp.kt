package ai.nyayaai.app

import ai.nyayaai.core.common.DeepLink
import ai.nyayaai.core.model.CaseId
import ai.nyayaai.core.model.User
import ai.nyayaai.core.model.UserRole
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.scaleIn
import androidx.compose.animation.scaleOut
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.MoreHoriz
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
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
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavHostController
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import kotlinx.coroutines.launch

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

    val shellViewModel: ShellViewModel = hiltViewModel()
    val unreadCount by shellViewModel.unreadCount.collectAsStateWithLifecycle()

    val sheetState = rememberModalBottomSheetState()
    var showMoreSheet by rememberSaveable { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    /** Closes the sheet before navigating, so it does not linger over the new screen. */
    fun navigateFromSheet(route: String) {
        scope.launch { sheetState.hide() }.invokeOnCompletion {
            showMoreSheet = false
            navController.navigate(route)
        }
    }

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
                    // One action, not five. The rest moved into the "More" sheet, where
                    // they have names; this one stays because a notification badge is
                    // only useful where it is always in view.
                    if (!user.role.isClient) {
                        NotificationsAction(
                            visible = isTab,
                            unreadCount = unreadCount,
                            onClick = {
                                navController.navigate(Route.NOTIFICATIONS)
                                // The count is read on the way in, so it is already stale
                                // on the way back; re-reading here is what stops the badge
                                // outliving the notifications it counts.
                                shellViewModel.refreshUnread()
                            },
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

                    // Staff only: client mode's two destinations are the whole app it has.
                    if (!user.role.isClient) {
                        NavigationBarItem(
                            // Selected while open so the bar still shows where the sheet
                            // came from; it is never "the current screen", because it is
                            // not a screen.
                            selected = showMoreSheet,
                            onClick = { showMoreSheet = true },
                            icon = {
                                Icon(Icons.Default.MoreHoriz, contentDescription = null)
                            },
                            label = { Text(stringResource(R.string.nav_more)) },
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

    if (showMoreSheet) {
        MoreSheet(
            isAdmin = user.role == UserRole.FIRM_ADMIN,
            sheetState = sheetState,
            onNavigate = ::navigateFromSheet,
            onDismiss = { showMoreSheet = false },
        )
    }
}

/**
 * The one surviving top-bar action.
 *
 * The count is on the icon rather than in a list somewhere because its whole job is to
 * be noticed without being looked for. The content description carries the number too —
 * a badge is a visual channel, and "Notifications" alone would tell a screen-reader user
 * nothing about whether opening it is worth their time.
 */
@Composable
private fun NotificationsAction(
    visible: Boolean,
    unreadCount: Int,
    onClick: () -> Unit,
) {
    AnimatedVisibility(
        visible = visible,
        enter = fadeIn() + scaleIn(),
        exit = fadeOut() + scaleOut(),
    ) {
        IconButton(onClick = onClick) {
            BadgedBox(
                badge = {
                    if (unreadCount > 0) {
                        Badge {
                            Text(
                                if (unreadCount > MAX_BADGE_COUNT) {
                                    stringResource(R.string.nav_badge_overflow, MAX_BADGE_COUNT)
                                } else {
                                    unreadCount.toString()
                                },
                            )
                        }
                    }
                },
            ) {
                Icon(
                    Icons.Default.Notifications,
                    contentDescription =
                        if (unreadCount > 0) {
                            stringResource(R.string.nav_notifications_unread, unreadCount)
                        } else {
                            stringResource(R.string.nav_notifications)
                        },
                )
            }
        }
    }
}

/** Past this the badge is wider than the icon and stops reading as a count. */
private const val MAX_BADGE_COUNT = 9

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
