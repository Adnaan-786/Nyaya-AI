package ai.nyayaai.core.designsystem.component

import ai.nyayaai.core.common.formatLong
import ai.nyayaai.core.designsystem.R
import ai.nyayaai.core.designsystem.theme.NyayaTheme
import ai.nyayaai.core.model.CourtDate
import ai.nyayaai.core.model.Paise
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuAnchorType
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults.TrailingIcon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import kotlinx.datetime.TimeZone
import kotlinx.datetime.atStartOfDayIn
import kotlinx.datetime.toLocalDateTime
import kotlin.time.Instant

/**
 * The one text input every form in this app uses.
 *
 * Every screen that wraps [OutlinedTextField] directly ends up re-deriving the same
 * `isError` / `supportingText` branch (see the CNR field this replaces) — one field wrong,
 * one visible, never both. Folding that here means a form gets error-or-helper text for
 * free instead of every screen author re-deciding the precedence.
 */
@Composable
fun NyayaTextField(
    value: String,
    onValueChange: (String) -> Unit,
    label: String,
    modifier: Modifier = Modifier,
    error: String? = null,
    helper: String? = null,
    keyboardType: KeyboardType = KeyboardType.Text,
    capitalization: KeyboardCapitalization = KeyboardCapitalization.Sentences,
    singleLine: Boolean = true,
    maxLines: Int = 1,
    prefix: String? = null,
    enabled: Boolean = true,
) {
    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        label = { Text(label) },
        modifier = modifier.fillMaxWidth(),
        enabled = enabled,
        isError = error != null,
        supportingText =
            when {
                error != null -> ({ Text(error) })
                helper != null -> ({ Text(helper) })
                else -> null
            },
        prefix = prefix?.let { { Text(it) } },
        keyboardOptions =
            KeyboardOptions(
                keyboardType = keyboardType,
                capitalization = capitalization,
            ),
        singleLine = singleLine,
        maxLines = maxLines,
    )
}

/**
 * A calendar-day picker for the [CourtDate] fields — hearing dates, due dates — that must
 * never travel through a timezone conversion (see the warning on [CourtDate] itself).
 *
 * Material's [DatePicker] hands back its selection as UTC epoch millis at **midnight UTC of
 * the chosen day**, regardless of the device's zone. That means the correct way to recover
 * the day is to read it back out through [TimeZone.UTC], not through the device zone and
 * not through IST — either of those would only coincidentally agree with what the user
 * tapped. Doing this conversion once, here, is exactly why this component exists instead of
 * every screen with a due date reaching for `DatePickerDialog` on its own.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NyayaDateField(
    value: CourtDate?,
    onValueChange: (CourtDate) -> Unit,
    label: String,
    modifier: Modifier = Modifier,
    error: String? = null,
    helper: String? = null,
    enabled: Boolean = true,
) {
    var showPicker by rememberSaveable { mutableStateOf(false) }

    Box(modifier = modifier) {
        NyayaTextField(
            value = value?.formatLong() ?: stringResource(R.string.ds_form_date_placeholder),
            onValueChange = {},
            label = label,
            error = error,
            helper = helper,
            enabled = enabled,
        )

        // A transparent tap-catcher over the (enabled-looking) field. The field itself
        // stays `enabled` so it does not render as greyed-out — it is read-only, not
        // disabled — but its own `onValueChange` is a no-op, so the click has to be
        // caught here rather than relying on the keyboard never opening.
        if (enabled) {
            Box(
                modifier =
                    Modifier
                        .matchParentSize()
                        .clickable(
                            interactionSource = remember { MutableInteractionSource() },
                            indication = null,
                            onClick = { showPicker = true },
                        ),
            )
        }
    }

    if (showPicker) {
        val initialMillis = value?.date?.atStartOfDayIn(TimeZone.UTC)?.toEpochMilliseconds()
        val pickerState = rememberDatePickerState(initialSelectedDateMillis = initialMillis)

        DatePickerDialog(
            onDismissRequest = { showPicker = false },
            confirmButton = {
                TextButton(
                    onClick = {
                        pickerState.selectedDateMillis?.let { millis ->
                            onValueChange(millis.toCourtDateViaUtc())
                        }
                        showPicker = false
                    },
                ) {
                    Text(stringResource(R.string.ds_form_date_confirm))
                }
            },
            dismissButton = {
                TextButton(onClick = { showPicker = false }) {
                    Text(stringResource(R.string.ds_form_date_cancel))
                }
            },
        ) {
            DatePicker(state = pickerState)
        }
    }
}

/** UTC millis (as [DatePicker] reports them) to the [CourtDate] they represent. */
private fun Long.toCourtDateViaUtc(): CourtDate =
    CourtDate(Instant.fromEpochMilliseconds(this).toLocalDateTime(TimeZone.UTC).date)

/**
 * A closed-choice picker for the enum-shaped fields this app is full of — case stage,
 * case status, court type, user role. [optionLabel] takes a lambda rather than requiring
 * `T` to be a string or to implement some display interface, so callers can hand it an
 * already-localized string without this component needing to know about string resources
 * for types it has never heard of.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun <T> NyayaDropdownField(
    value: T?,
    options: List<T>,
    onSelect: (T) -> Unit,
    label: String,
    optionLabel: (T) -> String,
    modifier: Modifier = Modifier,
    error: String? = null,
    helper: String? = null,
    enabled: Boolean = true,
) {
    var expanded by remember { mutableStateOf(false) }

    ExposedDropdownMenuBox(
        expanded = expanded && enabled,
        onExpandedChange = { if (enabled) expanded = !expanded },
        modifier = modifier,
    ) {
        OutlinedTextField(
            value = value?.let(optionLabel) ?: "",
            onValueChange = {},
            label = { Text(label) },
            readOnly = true,
            enabled = enabled,
            isError = error != null,
            supportingText =
                when {
                    error != null -> ({ Text(error) })
                    helper != null -> ({ Text(helper) })
                    else -> null
                },
            trailingIcon = { TrailingIcon(expanded = expanded) },
            modifier =
                Modifier
                    .fillMaxWidth()
                    .menuAnchor(ExposedDropdownMenuAnchorType.PrimaryNotEditable, enabled),
        )

        ExposedDropdownMenu(
            expanded = expanded && enabled,
            onDismissRequest = { expanded = false },
        ) {
            options.forEach { option ->
                DropdownMenuItem(
                    text = { Text(optionLabel(option)) },
                    onClick = {
                        onSelect(option)
                        expanded = false
                    },
                )
            }
        }
    }
}

/**
 * Rupee entry for [Paise] fields — filing fees, invoice amounts, settlement figures.
 *
 * The lawyer types rupees; the callback always emits integer paise, because paise is the
 * only representation of money that exists anywhere else in this codebase (see [Paise] —
 * no `Double` ever carries an amount). Internal text is kept as its own state, keyed off
 * [paise], rather than re-deriving the text from the incoming value on every recomposition
 * — otherwise typing "150" then a trailing "." would be stomped back to "150" mid-keystroke
 * because 150 rupees round-trips to itself with nothing after the decimal point.
 */
@Composable
fun NyayaMoneyField(
    paise: Long,
    onValueChange: (Long) -> Unit,
    label: String,
    modifier: Modifier = Modifier,
    error: String? = null,
    helper: String? = null,
    enabled: Boolean = true,
) {
    var text by remember(paise) {
        mutableStateOf(if (paise == 0L) "" else (paise / Paise.PAISE_PER_RUPEE).toString())
    }

    NyayaTextField(
        value = text,
        onValueChange = { input ->
            val digitsOnly = input.filter(Char::isDigit)
            text = digitsOnly
            val rupees = digitsOnly.toLongOrNull() ?: 0L
            onValueChange(rupees * Paise.PAISE_PER_RUPEE)
        },
        label = label,
        modifier = modifier,
        error = error,
        helper = helper,
        keyboardType = KeyboardType.Number,
        capitalization = KeyboardCapitalization.None,
        prefix = RUPEE_PREFIX,
        enabled = enabled,
    )
}

private const val RUPEE_PREFIX = "₹"

/**
 * The frame every create/edit form in the app renders inside.
 *
 * Scrollable because these forms (case intake, hearing entry, task creation) run longer
 * than a phone screen once the keyboard is up — a fixed [Column] would clip the submit
 * button under the IME exactly when the user has finished filling the last field. The
 * submit button's own busy state lives here too, so "submitting" always looks the same
 * whether the form is a two-field task or the multi-section case intake screen.
 */
@Composable
fun FormScaffold(
    title: String,
    submitLabel: String,
    canSubmit: Boolean,
    isSubmitting: Boolean,
    onSubmit: () -> Unit,
    modifier: Modifier = Modifier,
    error: String? = null,
    content: @Composable ColumnScope.() -> Unit,
) {
    Column(
        modifier =
            modifier
                .fillMaxWidth()
                .verticalScroll(rememberScrollState())
                .padding(NyayaTheme.spacing.md),
        verticalArrangement = Arrangement.spacedBy(NyayaTheme.spacing.md),
    ) {
        Text(
            text = title,
            style = MaterialTheme.typography.headlineSmall,
        )

        content()

        // Faded, not cut, so an error appearing or clearing doesn't jolt the form.
        AnimatedVisibility(
            visible = error != null,
            enter = fadeIn(tween(200)),
            exit = fadeOut(tween(200)),
        ) {
            error?.let {
                Text(
                    text = it,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.error,
                )
            }
        }

        Button(
            onClick = onSubmit,
            enabled = canSubmit && !isSubmitting,
            modifier = Modifier.fillMaxWidth(),
        ) {
            // Faded, not cut, so the label-to-spinner swap reads as one button settling
            // into a busy state rather than two different buttons trading places.
            AnimatedContent(
                targetState = isSubmitting,
                transitionSpec = { fadeIn(tween(200)) togetherWith fadeOut(tween(200)) },
                contentAlignment = Alignment.Center,
            ) { submitting ->
                if (submitting) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(SUBMIT_SPINNER_SIZE),
                        color = MaterialTheme.colorScheme.onPrimary,
                    )
                } else {
                    Text(submitLabel)
                }
            }
        }
    }
}

private val SUBMIT_SPINNER_SIZE = 20.dp
