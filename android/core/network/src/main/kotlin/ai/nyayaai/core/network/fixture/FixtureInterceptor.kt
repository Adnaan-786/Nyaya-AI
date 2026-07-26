package ai.nyayaai.core.network.fixture

import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.Protocol
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody

/** Supplies fixture bodies. Backed by APK assets in the mock flavor. */
interface FixtureSource {
    /** Returns the raw JSON for a fixture name like `post_auth_otp_verify`, or null. */
    fun read(name: String): String?
}

/**
 * Replaces the network with recorded JSON — but *inside* OkHttp, so every layer above it
 * behaves exactly as it will against the real server.
 *
 * Swapping to Prism once `openapi.yaml` lands means turning this off and pointing the base
 * URL at `localhost:4010`; nothing else changes, which is the point.
 *
 * Fixture naming: `<method>_<path with ids collapsed>.json`
 *   `POST /v1/auth/otp/verify` -> `post_auth_otp_verify.json`
 *   `GET  /v1/cases/{uuid}`    -> `get_cases_id.json`
 *
 * A request may set [SCENARIO_HEADER] to load `<name>__<scenario>.json` instead, which is
 * how UI tests drive the B.3 error paths (quota exceeded, CNR invalid, upstream down)
 * without needing a server that can be told to misbehave.
 */
class FixtureInterceptor(
    private val source: FixtureSource,
) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val request = chain.request()
        val base = fixtureName(request.method, request.url.encodedPath)
        val scenario = request.header(SCENARIO_HEADER)

        val body =
            scenario?.let { source.read("${base}__$it") }
                ?: source.read(base)
                ?: return missingFixture(chain, base)

        // Recorded latency keeps loading states honest during development; without it
        // every screen renders instantly and skeletons never get designed properly.
        Thread.sleep(SIMULATED_LATENCY_MS)

        val status = STATUS_BY_SCENARIO[scenario] ?: DEFAULT_STATUS
        return Response
            .Builder()
            .request(request)
            .protocol(Protocol.HTTP_1_1)
            .code(status)
            .message(if (status < HTTP_BAD_REQUEST) "OK" else "Error")
            .header("Content-Type", JSON_MEDIA_TYPE)
            .body(body.toResponseBody(JSON_MEDIA_TYPE.toMediaType()))
            .build()
    }

    /**
     * A missing fixture returns a contract-shaped envelope rather than throwing, so a
     * screen wired ahead of its fixture shows an ordinary error state instead of crashing
     * the app — and the message names the file to create.
     *
     * The code is deliberately not `*_NOT_FOUND`: that suffix is a contract error family
     * (B.3), and a missing fixture is a developer mistake, not a server 404.
     */
    private fun missingFixture(
        chain: Interceptor.Chain,
        name: String,
    ): Response {
        val payload =
            """
            {"success":false,"data":null,
             "error":{"code":"FIXTURE_MISSING",
                      "message":"No fixture '$name.json' for this request.",
                      "details":{}}}
            """.trimIndent()
        return Response
            .Builder()
            .request(chain.request())
            .protocol(Protocol.HTTP_1_1)
            .code(HTTP_NOT_FOUND)
            .message("Not Found")
            .header("Content-Type", JSON_MEDIA_TYPE)
            .body(payload.toResponseBody(JSON_MEDIA_TYPE.toMediaType()))
            .build()
    }

    companion object {
        const val SCENARIO_HEADER = "X-Fixture-Scenario"

        private const val JSON_MEDIA_TYPE = "application/json"
        private const val SIMULATED_LATENCY_MS = 400L
        private const val DEFAULT_STATUS = 200
        private const val HTTP_BAD_REQUEST = 400
        private const val HTTP_NOT_FOUND = 404

        /** Maps a scenario suffix to the HTTP status the real server would return (B.3). */
        private val STATUS_BY_SCENARIO =
            mapOf(
                "validation" to 400,
                "unauthenticated" to 401,
                "token_expired" to 401,
                "quota_exceeded" to 402,
                "forbidden_role" to 403,
                "not_found" to 404,
                "duplicate" to 409,
                "cnr_invalid" to 422,
                "upgrade_required" to 426,
                "rate_limited" to 429,
                "internal" to 500,
                "upstream_unavailable" to 503,
            )

        /**
         * Collapses UUID path segments so one fixture serves any id.
         * `/v1/cases/6f1c.../hearings` -> `get_cases_id_hearings`
         */
        fun fixtureName(
            method: String,
            encodedPath: String,
        ): String {
            val segments =
                encodedPath
                    .removePrefix("/")
                    .split("/")
                    .filter { it.isNotBlank() && it != "v1" }
                    .map { if (it.looksLikeId()) "id" else it }
            return (listOf(method.lowercase()) + segments).joinToString("_")
        }

        private fun String.looksLikeId(): Boolean =
            length >= UUID_MIN_LENGTH && any { it.isDigit() } && all { it.isLetterOrDigit() || it == '-' }

        private const val UUID_MIN_LENGTH = 16
    }
}
