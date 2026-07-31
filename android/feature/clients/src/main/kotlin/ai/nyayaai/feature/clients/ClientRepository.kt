package ai.nyayaai.feature.clients

import ai.nyayaai.core.model.Case
import ai.nyayaai.core.model.Client
import ai.nyayaai.core.model.ClientId
import ai.nyayaai.core.network.api.ApiCaller
import ai.nyayaai.core.network.api.ApiResult
import ai.nyayaai.core.network.api.map
import ai.nyayaai.core.network.dto.ClientCreateDto
import ai.nyayaai.core.network.mapper.toDomain
import ai.nyayaai.core.network.service.CaseService
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Clients live on [CaseService] rather than a dedicated Retrofit interface — that service
 * already owns `GET /clients` and `POST /clients` (used by `feature:cases`' CNR intake
 * flow), so splitting the other two client endpoints onto a second interface would spread
 * one resource across two service types for no benefit. This repository is
 * `feature:clients`' own, independent of `feature:cases`' [ai.nyayaai.feature.cases.CaseRepository]
 * — feature modules never depend on each other, so each owns its slice of [CaseService].
 */
@Singleton
class ClientRepository
    @Inject
    constructor(
        private val service: CaseService,
        private val caller: ApiCaller,
    ) {
        suspend fun clients(query: String? = null): ApiResult<List<Client>> =
            caller
                .call { service.clients() }
                .map { list -> list.map { it.toDomain() } }
                .let { result ->
                    // The server's `clients` endpoint has no `q` param (unlike `cases`);
                    // filtering client-side keeps search-as-you-type working without a
                    // server contract change.
                    val q = query?.trim()?.takeIf { it.isNotBlank() }
                    if (q == null) {
                        result
                    } else {
                        result.map { list ->
                            list.filter { it.name.contains(q, ignoreCase = true) || it.phone.contains(q) }
                        }
                    }
                }

        suspend fun client(id: ClientId): ApiResult<Client> =
            caller.call { service.client(id.value) }.map { it.toDomain() }

        suspend fun cases(id: ClientId): ApiResult<List<Case>> =
            caller.call { service.clientCases(id.value) }.map { list -> list.map { it.toDomain() } }

        suspend fun create(
            name: String,
            phone: String,
            email: String?,
            address: String?,
            notes: String?,
        ): ApiResult<Client> =
            caller
                .call {
                    service.createClient(
                        ClientCreateDto(
                            name = name,
                            phone = phone,
                            email = email?.takeIf { it.isNotBlank() },
                            address = address?.takeIf { it.isNotBlank() },
                            notes = notes?.takeIf { it.isNotBlank() },
                        ),
                    )
                }.map { it.toDomain() }

        /** The invite is idempotent server-side; only `ok` matters here, never the DTO. */
        suspend fun invite(id: ClientId): ApiResult<Unit> = caller.call { service.inviteClient(id.value) }.map { }
    }
