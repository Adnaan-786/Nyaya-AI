package ai.nyayaai.feature.ai

import ai.nyayaai.core.designsystem.component.AiDisclaimerBanner
import ai.nyayaai.core.designsystem.component.StatusBadge
import ai.nyayaai.core.designsystem.component.StatusTone
import ai.nyayaai.core.designsystem.theme.NyayaTheme
import ai.nyayaai.core.model.ResearchConfidence
import ai.nyayaai.core.network.mapper.AiContent
import ai.nyayaai.core.network.mapper.Citation
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.Button
import androidx.compose.material3.Card
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
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle

@Composable
fun AiRoute(
    onOpenCitation: (String) -> Unit,
    onUpgrade: (String) -> Unit,
    modifier: Modifier = Modifier,
    viewModel: AiViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    Column(modifier = modifier.fillMaxSize()) {
        // B.11: mandatory on every AI surface, and never dismissible. It ships as one
        // component precisely so no screen can forget it.
        AiDisclaimerBanner()

        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(NyayaTheme.spacing.md),
            verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.md),
        ) {
            item {
                OutlinedTextField(
                    value = state.query,
                    onValueChange = viewModel::onQueryChanged,
                    label = { Text(stringResource(R.string.ai_hint)) },
                    modifier = Modifier.fillMaxWidth(),
                )
            }

            item {
                if (state.isSubmitting) {
                    ProgressCard(state.estimatedSeconds)
                } else {
                    Button(
                        onClick = { viewModel.ask() },
                        enabled = state.query.isNotBlank(),
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(stringResource(R.string.ai_ask))
                    }
                }
            }

            state.upgradeTo?.let { plan ->
                item {
                    Card(modifier = Modifier.fillMaxWidth()) {
                        Column(modifier = Modifier.padding(NyayaTheme.spacing.md)) {
                            Text(
                                text = stringResource(R.string.ai_quota_title),
                                style = MaterialTheme.typography.titleSmall,
                            )
                            // B.14: the 402 carries upgrade_to, so the paywall opens with
                            // the right plan already selected rather than a generic pitch.
                            TextButton(onClick = { onUpgrade(plan) }) {
                                Text(stringResource(R.string.ai_upgrade, plan))
                            }
                        }
                    }
                }
            }

            state.error?.takeIf { state.upgradeTo == null }?.let { message ->
                item {
                    Text(
                        text = message,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.error,
                    )
                }
            }

            state.content?.let { content ->
                item { AnswerCard(content, onOpenCitation) }
            }
        }
    }
}

@Composable
private fun ProgressCard(
    estimatedSeconds: Int?,
    modifier: Modifier = Modifier,
) {
    Card(modifier = modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.padding(NyayaTheme.spacing.md),
            horizontalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.md),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            CircularProgressIndicator()
            Column {
                Text(
                    text = stringResource(R.string.ai_working),
                    style = MaterialTheme.typography.bodyMedium,
                )
                // Showing the server's own estimate rather than an invented one: B.7
                // returns estimated_seconds precisely so the wait has a shape.
                estimatedSeconds?.let {
                    Text(
                        text = stringResource(R.string.ai_working_eta, it),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }
}

@Composable
private fun AnswerCard(
    content: AiContent,
    onOpenCitation: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.sm),
    ) {
        // `insufficient` gets its own distinct state, never a blank result. An empty
        // answer reads as a bug; this reads as an honest "I could not find authority",
        // which is the only safe thing to tell someone heading into a courtroom.
        if (content.confidence == ResearchConfidence.INSUFFICIENT) {
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(NyayaTheme.spacing.md)) {
                    Text(
                        text = stringResource(R.string.ai_insufficient_title),
                        style = MaterialTheme.typography.titleSmall,
                    )
                    Text(
                        text = stringResource(R.string.ai_insufficient_detail),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        } else {
            StatusBadge(
                text =
                    stringResource(
                        if (content.confidence == ResearchConfidence.HIGH) {
                            R.string.ai_confidence_high
                        } else {
                            R.string.ai_confidence_medium
                        },
                    ),
                tone =
                    if (content.confidence == ResearchConfidence.HIGH) {
                        StatusTone.POSITIVE
                    } else {
                        StatusTone.WARNING
                    },
            )
        }

        (content.answerMarkdown ?: content.summaryMarkdown)?.let {
            Text(text = it, style = MaterialTheme.typography.bodyMedium)
        }

        if (content.keyPoints.isNotEmpty()) {
            content.keyPoints.forEach { point ->
                Text(text = "• $point", style = MaterialTheme.typography.bodyMedium)
            }
        }

        if (content.citations.isNotEmpty()) {
            Text(
                text = stringResource(R.string.ai_citations),
                style = MaterialTheme.typography.titleSmall,
            )
            content.citations.forEach { citation ->
                CitationCard(citation, onOpenCitation)
            }
        }
    }
}

@Composable
private fun CitationCard(
    citation: Citation,
    onOpen: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier =
            modifier
                .fillMaxWidth()
                // Tappable only when there is somewhere to go — a citation card that
                // does nothing on tap is worse than one that is plainly static.
                .let { base ->
                    citation.sourceUrl?.let { url -> base.clickable { onOpen(url) } } ?: base
                },
    ) {
        Column(
            modifier = Modifier.padding(NyayaTheme.spacing.md),
            verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.xs),
        ) {
            Text(text = citation.title, style = MaterialTheme.typography.bodyMedium)

            val meta = listOfNotNull(citation.court, citation.year?.toString(), citation.citation)
            if (meta.isNotEmpty()) {
                Text(
                    text = meta.joinToString(" · "),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            citation.snippet?.let {
                Text(
                    text = it,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}
