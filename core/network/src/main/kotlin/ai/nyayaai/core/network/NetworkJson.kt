package ai.nyayaai.core.network

import kotlinx.serialization.ExperimentalSerializationApi
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonNamingStrategy

/**
 * The JSON configuration is a contract-safety device, not a preference. Each setting here
 * corresponds to a specific way the app would otherwise break against a server we do not
 * control (A1.2b in the build plan).
 */
@OptIn(ExperimentalSerializationApi::class)
val NyayaJson: Json =
    Json {
        /**
         * B.13 allows the server to add fields additively after the contract freeze. Without
         * this, the first additive server deploy crashes every installed app. Non-negotiable.
         */
        ignoreUnknownKeys = true

        /**
         * A `null` arriving where the DTO declares a non-null default becomes the default
         * instead of throwing. Belt and braces alongside DTO nullability.
         */
        coerceInputValues = true

        /**
         * Absent and explicit-null are treated the same on the way in, and nulls are omitted
         * on the way out, so we never send `"field": null` and have the server treat it as an
         * intentional clear.
         */
        explicitNulls = false

        /**
         * The contract's examples are snake_case but B never states it as a rule — filed for
         * v1.2. Declaring it once here beats ~200 hand-written @SerialName annotations, and
         * makes DTO property names match Kotlin conventions.
         */
        namingStrategy = JsonNamingStrategy.SnakeCase

        // Strict about malformed JSON: a broken body should be a reported contract violation,
        // not something we quietly half-parse.
        isLenient = false
    }
