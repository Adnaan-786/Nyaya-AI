package ai.nyayaai.core.network.interceptor

import okhttp3.Interceptor
import okhttp3.Response
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Adds `Idempotency-Key` to every mutating request.
 *
 * On Indian mobile networks a request that times out has often already been processed.
 * Without a key, the automatic retry creates a second case — or worse, a second payment.
 *
 * The key must be **stable across retries of the same logical operation**, so:
 *  - OkHttp-level retries reuse this request object and therefore this key;
 *  - callers that queue work across process death (the WorkManager upload/write queue in
 *    D.11) generate their own key, persist it with the queued item, and set
 *    [HEADER] explicitly. This interceptor never overwrites an existing key.
 *
 * Server support is a v1.2 contract addition — until it lands the header is ignored,
 * which is harmless.
 */
@Singleton
class IdempotencyInterceptor
    @Inject
    constructor() : Interceptor {
        override fun intercept(chain: Interceptor.Chain): Response {
            val request = chain.request()
            if (request.method !in MUTATING_METHODS) return chain.proceed(request)
            if (request.header(HEADER) != null) return chain.proceed(request)

            return chain.proceed(
                request
                    .newBuilder()
                    .header(HEADER, UUID.randomUUID().toString())
                    .build(),
            )
        }

        companion object {
            const val HEADER = "Idempotency-Key"
            private val MUTATING_METHODS = setOf("POST", "PUT", "PATCH", "DELETE")
        }
    }
