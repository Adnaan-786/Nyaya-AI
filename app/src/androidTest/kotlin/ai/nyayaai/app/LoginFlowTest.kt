package ai.nyayaai.app

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.junit4.ComposeTestRule
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextInput
import androidx.test.ext.junit.runners.AndroidJUnit4
import dagger.hilt.android.testing.HiltAndroidRule
import dagger.hilt.android.testing.HiltAndroidTest
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * The Sprint A1 definition of done, as a repeatable test rather than a manual click-through.
 *
 * This drives the real screen against the real OkHttp stack — the mock flavor's fixture
 * interceptor stands in for the server, but JSON parsing, the auth interceptor, token
 * storage and B.3 error mapping all execute exactly as they will against staging. When
 * `openapi.yaml` lands and the base URL points at Prism, this same test is the check that
 * nothing changed.
 */
@HiltAndroidTest
@RunWith(AndroidJUnit4::class)
class LoginFlowTest {
    @get:Rule(order = 0)
    val hiltRule = HiltAndroidRule(this)

    @get:Rule(order = 1)
    val composeRule = createAndroidComposeRule<MainActivity>()

    @Before
    fun setUp() = hiltRule.inject()

    @Test
    fun otpLoginRoundTripReachesTheSignedInState() {
        // Step 1 — phone entry. The action stays disabled until the number is valid, which
        // is the app enforcing B.4's 10-digit Indian mobile format before spending an OTP.
        composeRule.onNodeWithText("Get OTP").assertIsNotEnabled()

        composeRule.onNodeWithText("Mobile number").performTextInput("9812345678")
        composeRule.onNodeWithText("Get OTP").assertIsEnabled().performClick()

        // Step 2 — POST /auth/otp/request round-tripped, so the OTP step is showing with
        // the number echoed back in +91 form.
        composeRule.awaitText("Enter the code")
        composeRule.onNodeWithText("Sent to +919812345678").assertIsDisplayed()

        composeRule.onNodeWithText("6-digit code").performTextInput("123456")
        composeRule.onNodeWithText("Verify").assertIsEnabled().performClick()

        // Step 3 — POST /auth/otp/verify stored the token pair, and the follow-up GET /me
        // succeeded *using that token*. If the auth interceptor were not attaching it, this
        // is the assertion that would fail.
        composeRule.awaitText("Signed in as Adv. Meera Raghavan")
        composeRule.onNodeWithText("Signed in as Adv. Meera Raghavan").assertIsDisplayed()
    }
}

/**
 * Waits for text to appear. The fixture interceptor adds deliberate latency, so every step
 * here is genuinely asynchronous — the same as it will be against a real server.
 */
private fun ComposeTestRule.awaitText(text: String) {
    waitUntil(timeoutMillis = TIMEOUT_MS) {
        runCatching {
            onAllNodesWithText(text).fetchSemanticsNodes().isNotEmpty()
        }.getOrDefault(false)
    }
}

private const val TIMEOUT_MS = 20_000L
