package ai.nyayaai.feature.auth

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
fun LoginRoute(viewModel: LoginViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    LoginScreen(
        state = state,
        onPhoneChanged = viewModel::onPhoneChanged,
        onOtpChanged = viewModel::onOtpChanged,
        onRequestOtp = viewModel::requestOtp,
        onVerify = viewModel::verifyOtp,
        onBack = viewModel::back,
        onSignOut = viewModel::logout,
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
) {
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
