package ai.nyayaai.feature.auth

import ai.nyayaai.core.designsystem.component.FormScaffold
import ai.nyayaai.core.designsystem.component.NyayaCard
import ai.nyayaai.core.designsystem.component.NyayaDropdownField
import ai.nyayaai.core.designsystem.component.NyayaTextField
import ai.nyayaai.core.designsystem.theme.NyayaTheme
import ai.nyayaai.core.model.Language
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle

/**
 * D.2 login flow: phone entry, OTP verification, first-run onboarding and the (practically
 * unreachable — see [SignedInStep]) signed-in step, one [LoginUiState] at a time. Every step
 * now renders through the shared `core/designsystem` form components ([FormScaffold],
 * [NyayaTextField]) so this, the very first screen a user sees, matches the rest of the app.
 */
@Composable
fun LoginRoute(
    onSignedIn: (ai.nyayaai.core.model.User) -> Unit = {},
    viewModel: LoginViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    // Hoisted to the caller so the shell — not this screen — decides where a signed-in
    // user lands. The role in the returned user is what picks the staff or client shell.
    androidx.compose.runtime.LaunchedEffect(state.signedInUser) {
        state.signedInUser?.let(onSignedIn)
    }

    LoginScreen(
        state = state,
        onPhoneChanged = viewModel::onPhoneChanged,
        onEmailChanged = viewModel::onEmailChanged,
        onChannelChanged = viewModel::onChannelChanged,
        onOtpChanged = viewModel::onOtpChanged,
        onRequestOtp = viewModel::requestOtp,
        onVerify = viewModel::verifyOtp,
        onBack = viewModel::back,
        onSignOut = viewModel::logout,
        onOnboardNameChanged = viewModel::onOnboardNameChanged,
        onOnboardRoleChanged = viewModel::onOnboardRoleChanged,
        onOnboardFirmNameChanged = viewModel::onOnboardFirmNameChanged,
        onOnboardBarCouncilIdChanged = viewModel::onOnboardBarCouncilIdChanged,
        onOnboardLanguageChanged = viewModel::onOnboardLanguageChanged,
        onSubmitOnboarding = viewModel::submitOnboarding,
    )
}

@Composable
internal fun LoginScreen(
    state: LoginUiState,
    onPhoneChanged: (String) -> Unit,
    onEmailChanged: (String) -> Unit,
    onChannelChanged: (LoginUiState.Channel) -> Unit,
    onOtpChanged: (String) -> Unit,
    onRequestOtp: () -> Unit,
    onVerify: () -> Unit,
    onBack: () -> Unit,
    onSignOut: () -> Unit,
    onOnboardNameChanged: (String) -> Unit,
    onOnboardRoleChanged: (OnboardRole) -> Unit,
    onOnboardFirmNameChanged: (String) -> Unit,
    onOnboardBarCouncilIdChanged: (String) -> Unit,
    onOnboardLanguageChanged: (Language) -> Unit,
    onSubmitOnboarding: () -> Unit,
) {
    // Every step below is either a FormScaffold (which renders its own title, error text and
    // submit spinner) or, for SignedInStep, a self-contained full-screen layout — so unlike
    // the bare-Column version this replaces, nothing here needs a shared centering wrapper or
    // a second, top-level rendering of state.error/isSubmitting.
    when (state.step) {
        LoginUiState.Step.PHONE ->
            PhoneStep(
                state = state,
                onPhoneChanged = onPhoneChanged,
                onEmailChanged = onEmailChanged,
                onChannelChanged = onChannelChanged,
                onRequestOtp = onRequestOtp,
                modifier = Modifier.fillMaxSize(),
            )

        LoginUiState.Step.OTP ->
            OtpStep(state, onOtpChanged, onVerify, onBack, modifier = Modifier.fillMaxSize())

        LoginUiState.Step.ONBOARDING ->
            OnboardingStep(
                state = state,
                onNameChanged = onOnboardNameChanged,
                onRoleChanged = onOnboardRoleChanged,
                onFirmNameChanged = onOnboardFirmNameChanged,
                onBarCouncilIdChanged = onOnboardBarCouncilIdChanged,
                onLanguageChanged = onOnboardLanguageChanged,
                onSubmit = onSubmitOnboarding,
                modifier = Modifier.fillMaxSize(),
            )

        LoginUiState.Step.SIGNED_IN ->
            SignedInStep(state, onSignOut, modifier = Modifier.fillMaxSize())
    }
}

@Composable
private fun PhoneStep(
    state: LoginUiState,
    onPhoneChanged: (String) -> Unit,
    onEmailChanged: (String) -> Unit,
    onChannelChanged: (LoginUiState.Channel) -> Unit,
    onRequestOtp: () -> Unit,
    modifier: Modifier = Modifier,
) {
    FormScaffold(
        title = stringResource(R.string.auth_title),
        submitLabel = stringResource(R.string.auth_get_otp),
        canSubmit = state.isIdentifierValid,
        isSubmitting = state.isSubmitting,
        onSubmit = onRequestOtp,
        modifier = modifier,
        error = state.error,
    ) {
        // Two channels, so the choice is a segmented button rather than a hidden default —
        // a lawyer whose firm runs on WhatsApp and a lawyer who lives in their inbox should
        // both find their way in without reading anything.
        SingleChoiceSegmentedButtonRow(modifier = Modifier.fillMaxWidth()) {
            LoginUiState.Channel.entries.forEachIndexed { index, channel ->
                SegmentedButton(
                    selected = state.channel == channel,
                    onClick = { onChannelChanged(channel) },
                    shape =
                        SegmentedButtonDefaults.itemShape(
                            index = index,
                            count = LoginUiState.Channel.entries.size,
                        ),
                ) {
                    Text(
                        stringResource(
                            when (channel) {
                                LoginUiState.Channel.EMAIL -> R.string.auth_channel_email
                                LoginUiState.Channel.PHONE -> R.string.auth_channel_phone
                            },
                        ),
                    )
                }
            }
        }

        // Animated so switching channels reads as one field changing rather than the form
        // rebuilding under the user; 260ms matches the app's content-swap timing.
        AnimatedContent(
            targetState = state.channel,
            transitionSpec = { fadeIn(tween(CHANNEL_SWAP_MS)) togetherWith fadeOut(tween(CHANNEL_SWAP_MS)) },
            label = "login-channel",
        ) { channel ->
            when (channel) {
                LoginUiState.Channel.EMAIL ->
                    NyayaTextField(
                        value = state.email,
                        onValueChange = onEmailChanged,
                        label = stringResource(R.string.auth_email_label),
                        helper = stringResource(R.string.auth_email_helper),
                        keyboardType = KeyboardType.Email,
                        capitalization = KeyboardCapitalization.None,
                    )

                LoginUiState.Channel.PHONE ->
                    NyayaTextField(
                        value = state.phone,
                        onValueChange = onPhoneChanged,
                        label = stringResource(R.string.auth_phone_label),
                        prefix = stringResource(R.string.auth_phone_prefix),
                        helper = stringResource(R.string.auth_phone_helper),
                        keyboardType = KeyboardType.Phone,
                    )
            }
        }
    }
}

private const val CHANNEL_SWAP_MS = 260

@Composable
private fun OtpStep(
    state: LoginUiState,
    onOtpChanged: (String) -> Unit,
    onVerify: () -> Unit,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    FormScaffold(
        title = stringResource(R.string.auth_otp_title),
        submitLabel = stringResource(R.string.auth_verify),
        canSubmit = state.isOtpValid,
        isSubmitting = state.isSubmitting,
        onSubmit = onVerify,
        modifier = modifier,
        error = state.error,
    ) {
        Text(
            text =
                stringResource(
                    R.string.auth_otp_sent_to,
                    when (state.channel) {
                        LoginUiState.Channel.EMAIL -> state.email
                        LoginUiState.Channel.PHONE -> LoginUiState.COUNTRY_CODE + state.phone
                    },
                ),
            style = MaterialTheme.typography.bodyMedium,
        )

        NyayaTextField(
            value = state.otp,
            onValueChange = onOtpChanged,
            label = stringResource(R.string.auth_otp_label),
            keyboardType = KeyboardType.NumberPassword,
        )

        TextButton(onClick = onBack) {
            Text(
                stringResource(
                    when (state.channel) {
                        LoginUiState.Channel.EMAIL -> R.string.auth_change_email
                        LoginUiState.Channel.PHONE -> R.string.auth_change_number
                    },
                ),
            )
        }
    }
}

/**
 * In practice unreachable: [LoginRoute]'s `onSignedIn` fires the moment `state.signedInUser`
 * is set and the caller navigates away before this would ever compose. Restyled anyway, on
 * the off chance it is ever visible — no form/submit action here, so [FormScaffold] (built
 * for exactly that) is not the right fit; a [NyayaCard] keeps it visually consistent instead.
 */
@Composable
private fun SignedInStep(
    state: LoginUiState,
    onSignOut: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier.fillMaxSize().padding(NyayaTheme.spacing.lg),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        NyayaCard {
            Text(
                text =
                    stringResource(
                        R.string.auth_signed_in_as,
                        state.signedInUser?.name.orEmpty(),
                    ),
                style = MaterialTheme.typography.headlineSmall,
            )

            TextButton(onClick = onSignOut) {
                Text(stringResource(R.string.auth_sign_out))
            }
        }
    }
}

/**
 * B.6: shown once, right after OTP verification, only for a brand-new user
 * ([VerifiedLogin.isNewUser]) — finishes the placeholder profile the server created so the
 * name and tenant are no longer empty / "Pending setup" once the app treats them as signed in.
 *
 * Built on the shared `core/designsystem` form components, same as [PhoneStep]/[OtpStep] above.
 */
@Composable
private fun OnboardingStep(
    state: LoginUiState,
    onNameChanged: (String) -> Unit,
    onRoleChanged: (OnboardRole) -> Unit,
    onFirmNameChanged: (String) -> Unit,
    onBarCouncilIdChanged: (String) -> Unit,
    onLanguageChanged: (Language) -> Unit,
    onSubmit: () -> Unit,
    modifier: Modifier = Modifier,
) {
    // optionLabel is a plain (non-@Composable) lambda, so the localized strings for each
    // enum option are resolved up front, here, rather than inside the lambda itself.
    val roleLabels =
        mapOf(
            OnboardRole.LAWYER to stringResource(R.string.auth_onboard_role_lawyer),
            OnboardRole.FIRM_ADMIN to stringResource(R.string.auth_onboard_role_firm_admin),
        )
    val languageLabels =
        mapOf(
            Language.EN to stringResource(R.string.auth_onboard_language_en),
            Language.HI to stringResource(R.string.auth_onboard_language_hi),
        )

    FormScaffold(
        title = stringResource(R.string.auth_onboard_title),
        submitLabel = stringResource(R.string.auth_onboard_submit),
        canSubmit = state.isOnboardingValid,
        isSubmitting = state.isSubmitting,
        onSubmit = onSubmit,
        modifier = modifier,
        error = state.error,
    ) {
        NyayaTextField(
            value = state.onboardName,
            onValueChange = onNameChanged,
            label = stringResource(R.string.auth_onboard_name_label),
        )

        NyayaDropdownField(
            value = state.onboardRole,
            options = OnboardRole.entries,
            onSelect = onRoleChanged,
            label = stringResource(R.string.auth_onboard_role_label),
            optionLabel = { role -> roleLabels.getValue(role) },
        )

        NyayaTextField(
            value = state.onboardFirmName,
            onValueChange = onFirmNameChanged,
            label = stringResource(R.string.auth_onboard_firm_name_label),
        )

        NyayaTextField(
            value = state.onboardBarCouncilId,
            onValueChange = onBarCouncilIdChanged,
            label = stringResource(R.string.auth_onboard_bar_council_id_label),
        )

        NyayaDropdownField(
            value = state.onboardLanguage,
            options = Language.entries,
            onSelect = onLanguageChanged,
            label = stringResource(R.string.auth_onboard_language_label),
            optionLabel = { language -> languageLabels.getValue(language) },
        )
    }
}
