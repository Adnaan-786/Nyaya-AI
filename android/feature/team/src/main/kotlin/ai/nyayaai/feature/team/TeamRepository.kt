package ai.nyayaai.feature.team

import ai.nyayaai.core.model.TeamMember
import ai.nyayaai.core.model.UserId
import ai.nyayaai.core.network.api.ApiCaller
import ai.nyayaai.core.network.api.ApiResult
import ai.nyayaai.core.network.api.map
import ai.nyayaai.core.network.dto.UserRoleUpdateDto
import ai.nyayaai.core.network.mapper.toTeamMember
import ai.nyayaai.core.network.service.UserService
import javax.inject.Inject
import javax.inject.Singleton

/**
 * The three roles `PATCH /users/{id}` actually accepts. Deliberately narrower than
 * [ai.nyayaai.core.model.UserRole] — the server never lets a firm admin hand out `client`
 * through this endpoint (that role only ever arrives via the separate portal-login
 * mechanism), so offering it in a picker here would just be an action the server rejects.
 * Mirrors the same narrowing [ai.nyayaai.feature.auth]'s `OnboardRole` does for onboarding.
 */
enum class AssignableRole(val wire: String) {
    FIRM_ADMIN("firm_admin"),
    LAWYER("lawyer"),
    INTERN("intern"),
}

/**
 * B.6 team management. `PATCH`/`DELETE` are firm_admin-only server-side, and the server
 * itself refuses a self-role-change or any action against a client-role account — this
 * repository does not re-enforce those guards, it just relays whatever the server decides.
 */
@Singleton
class TeamRepository
    @Inject
    constructor(
        private val service: UserService,
        private val caller: ApiCaller,
    ) {
        suspend fun members(): ApiResult<List<TeamMember>> =
            caller.call { service.users() }.map { list -> list.map { it.toTeamMember() } }

        suspend fun updateRole(
            id: UserId,
            role: String,
        ): ApiResult<TeamMember> =
            caller.call { service.updateRole(id.value, UserRoleUpdateDto(role)) }.map { it.toTeamMember() }

        suspend fun remove(id: UserId): ApiResult<Unit> = caller.call { service.removeUser(id.value) }.map { }
    }
