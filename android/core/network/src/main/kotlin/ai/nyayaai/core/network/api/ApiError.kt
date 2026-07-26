package ai.nyayaai.core.network.api

/**
 * Every error code in B.3, plus the two failure modes the contract cannot describe
 * (no network at all, and a response that violates the contract).
 *
 * B.3 says "the app must handle every code; unknown codes fall back to a generic error
 * toast" — [Unknown] is that fallback and it is deliberately not an exception.
 */
sealed interface ApiError {
    val message: String

    /** 400 — field-level problems, keyed by field name. */
    data class Validation(
        override val message: String,
        val fieldErrors: Map<String, String> = emptyMap(),
    ) : ApiError

    /** 401 — no/invalid credentials. Route to login. */
    data class Unauthenticated(
        override val message: String,
    ) : ApiError

    /**
     * 401 — access token past its 30-minute life. Handled transparently by
     * [ai.nyayaai.core.network.auth.TokenAuthenticator]; a ViewModel should never see it.
     */
    data class TokenExpired(
        override val message: String,
    ) : ApiError

    /**
     * 402 — plan limit hit. B.14 requires every occurrence anywhere in the app to route to
     * the paywall with [upgradeTo] preselected.
     */
    data class QuotaExceeded(
        override val message: String,
        val limit: Int?,
        val plan: String?,
        val upgradeTo: String?,
    ) : ApiError

    /** 403 — the role is not allowed. The app hides the UI too, but the server decides. */
    data class ForbiddenRole(
        override val message: String,
    ) : ApiError

    /** 404 — `CASE_NOT_FOUND`, `CLIENT_NOT_FOUND`, ... [resource] is the prefix. */
    data class NotFound(
        override val message: String,
        val resource: String,
    ) : ApiError

    /** 409 */
    data class DuplicateResource(
        override val message: String,
    ) : ApiError

    /** 422 — the CNR failed validation. Shown inline on the add-by-CNR field. */
    data class CnrInvalid(
        override val message: String,
    ) : ApiError

    /** 426 — app below `min_supported_version`. Blocking update screen (B.14). */
    data class UpgradeRequired(
        override val message: String,
    ) : ApiError

    /** 429 — includes `POST /cases/{id}/sync`, which is rate-limited to 1/hour/case. */
    data class RateLimited(
        override val message: String,
        val retryAfterSeconds: Int?,
    ) : ApiError

    /** 500 */
    data class InternalError(
        override val message: String,
    ) : ApiError

    /** 503 — eCourts or an AI provider is down. The app shows a retry affordance. */
    data class UpstreamUnavailable(
        override val message: String,
    ) : ApiError

    /** A code we have never seen. Generic toast, per B.3. */
    data class Unknown(
        override val message: String,
        val code: String,
    ) : ApiError

    /** No HTTP exchange happened: airplane mode, DNS, timeout. */
    data class Network(
        override val message: String,
        val cause: Throwable?,
    ) : ApiError

    /**
     * The server answered, but not in a shape the contract allows — non-envelope body,
     * required field missing, unparseable date.
     *
     * D.13 makes this a same-day blocking bug against the server repo, so it is a distinct
     * type rather than being folded into [InternalError].
     */
    data class ContractViolation(
        override val message: String,
        val detail: String,
        val cause: Throwable? = null,
    ) : ApiError

    companion object {
        const val CODE_VALIDATION = "VALIDATION_ERROR"
        const val CODE_UNAUTHENTICATED = "UNAUTHENTICATED"
        const val CODE_TOKEN_EXPIRED = "TOKEN_EXPIRED"
        const val CODE_QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
        const val CODE_FORBIDDEN_ROLE = "FORBIDDEN_ROLE"
        const val CODE_DUPLICATE = "DUPLICATE_RESOURCE"
        const val CODE_CNR_INVALID = "CNR_INVALID"
        const val CODE_UPGRADE_REQUIRED = "UPGRADE_REQUIRED"
        const val CODE_RATE_LIMITED = "RATE_LIMITED"
        const val CODE_INTERNAL = "INTERNAL_ERROR"
        const val CODE_UPSTREAM_UNAVAILABLE = "UPSTREAM_UNAVAILABLE"
        const val NOT_FOUND_SUFFIX = "_NOT_FOUND"
    }
}

/** True for errors where showing the user a "Retry" button is honest. */
val ApiError.isRetryable: Boolean
    get() =
        this is ApiError.Network ||
            this is ApiError.UpstreamUnavailable ||
            this is ApiError.InternalError ||
            this is ApiError.RateLimited
