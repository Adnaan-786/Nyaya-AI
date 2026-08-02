package ai.nyayaai.feature.auth

import ai.nyayaai.core.designsystem.component.FormScaffold
import ai.nyayaai.core.designsystem.component.NyayaDropdownField
import ai.nyayaai.core.designsystem.component.NyayaTextField
import ai.nyayaai.core.model.Language
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle

/**
 * Sprint A1 login. Deliberately plain Material 3 — the real visual design, components and
 * OTP autofill (SMS Retriever) arrive with the design system in A2/A3. What this screen
 * proves is the A1 contract: a full OTP round-trip through the real OkHttp stack.
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
    if (state.step == LoginUiState.Step.ONBOARDING) {
        // FormScaffold (core/designsystem) already renders its own title, scrolling content,
        // error text and submit spinner — wrapping it in the plain steps' centered Column
        // below would double up the error/spinner the scaffold already shows.
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
        return
    }

    Column(
        modifier =
            Modifier
                .fillMaxSize()
                .padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp, Alignment.CenterVertically),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        when (state.step) {
            LoginUiState.Step.PHONE ->
                PhoneStep(state, onPhoneChanged, onRequestOtp)

            LoginUiState.Step.OTP ->
                OtpStep(state, onOtpChanged, onVerify, onBack)

            LoginUiState.Step.ONBOARDING -> Unit // handled above

            LoginUiState.Step.SIGNED_IN ->
                SignedInStep(state, onSignOut)
        }

        state.error?.let { message ->
            Text(text = message, color = MaterialTheme.colorScheme.error)
        }

        if (state.isSubmitting) {
            CircularProgressIndicator(modifier = Modifier.size(24.dp))
        }
    }
}

@Composable
private fun PhoneStep(
    state: LoginUiState,
    onPhoneChanged: (String) -> Unit,
    onRequestOtp: () -> Unit,
) {
    Text(text = stringResource(R.string.auth_title), style = MaterialTheme.typography.headlineSmall)

    OutlinedTextField(
        value = state.phone,
        onValueChange = onPhoneChanged,
        label = { Text(stringResource(R.string.auth_phone_label)) },
        prefix = { Text(stringResource(R.string.auth_phone_prefix)) },
        supportingText = { Text(stringResource(R.string.auth_phone_helper)) },
        singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone),
        modifier = Modifier.fillMaxWidth(),
    )

    Button(
        onClick = onRequestOtp,
        enabled = state.isPhoneValid && !state.isSubmitting,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Text(stringResource(R.string.auth_get_otp))
    }
}

@Composable
private fun OtpStep(
    state: LoginUiState,
    onOtpChanged: (String) -> Unit,
    onVerify: () -> Unit,
    onBack: () -> Unit,
) {
    Text(
        text = stringResource(R.string.auth_otp_title),
        style = MaterialTheme.typography.headlineSmall,
    )
    Text(
        text =
            stringResource(
                R.string.auth_otp_sent_to,
                LoginUiState.COUNTRY_CODE + state.phone,
            ),
        style = MaterialTheme.typography.bodyMedium,
    )

    OutlinedTextField(
        value = state.otp,
        onValueChange = onOtpChanged,
        label = { Text(stringResource(R.string.auth_otp_label)) },
        singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword),
        modifier = Modifier.fillMaxWidth(),
    )

    Button(
        onClick = onVerify,
        enabled = state.isOtpValid && !state.isSubmitting,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Text(stringResource(R.string.auth_verify))
    }

    TextButton(onClick = onBack) {
        Text(stringResource(R.string.auth_change_number))
    }
}

@Composable
private fun SignedInStep(
    state: LoginUiState,
    onSignOut: () -> Unit,
) {
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

/**
 * B.6: shown once, right after OTP verification, only for a brand-new user
 * ([VerifiedLogin.isNewUser]) — finishes the placeholder profile the server created so the
 * name and tenant are no longer empty / "Pending setup" once the app treats them as signed in.
 *
 * Built on the shared `core/designsystem` form components (unlike [PhoneStep]/[OtpStep]/
 * [SignedInStep] above, which predate that design system and are left untouched).
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
