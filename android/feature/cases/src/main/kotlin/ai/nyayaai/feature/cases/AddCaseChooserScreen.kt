package ai.nyayaai.feature.cases

import ai.nyayaai.core.designsystem.theme.NyayaTheme
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource

@Composable
fun AddCaseChooserRoute(
    onNavigateToCnr: () -> Unit,
    onNavigateToManual: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Scaffold(modifier = modifier) { innerPadding ->
        Column(
            modifier = Modifier
                .padding(innerPadding)
                .fillMaxSize()
                .padding(NyayaTheme.spacing.md),
            verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.md),
        ) {
            Button(
                onClick = onNavigateToCnr,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(stringResource(R.string.chooser_cnr))
            }

            OutlinedButton(
                onClick = onNavigateToManual,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(stringResource(R.string.chooser_manual))
            }
        }
    }
}
