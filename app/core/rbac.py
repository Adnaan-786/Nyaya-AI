"""
Central RBAC permission matrix (plan C.5.3): coded as data, not scattered
if-statements. Every protected route declares the capability it needs via
`Depends(require("capability.name"))`; the matrix below decides which
roles may exercise that capability.

Roles: firm_admin, lawyer, intern, client  (Integration Contract B.4/B.6)
"""

from enum import StrEnum

from fastapi import Depends

from app.core.dependencies import AuthContext, get_current_auth
from app.core.exceptions import ForbiddenRoleException


class Role(StrEnum):
    FIRM_ADMIN = "firm_admin"
    LAWYER = "lawyer"
    INTERN = "intern"
    CLIENT = "client"


# capability -> set of roles allowed to perform it.
# Mirrors the RBAC matrix in plan C.5.3 / contract section on roles.
PERMISSIONS: dict[str, set[Role]] = {
    "firm.manage": {Role.FIRM_ADMIN},
    "firm.members.manage": {Role.FIRM_ADMIN},
    "clients.write": {Role.FIRM_ADMIN, Role.LAWYER},
    "clients.read": {Role.FIRM_ADMIN, Role.LAWYER, Role.INTERN},
    "cases.write": {Role.FIRM_ADMIN, Role.LAWYER},
    "cases.read.assigned": {Role.FIRM_ADMIN, Role.LAWYER, Role.INTERN},
    "cases.notes.write": {Role.FIRM_ADMIN, Role.LAWYER, Role.INTERN},
    "documents.write": {Role.FIRM_ADMIN, Role.LAWYER, Role.INTERN},
    "documents.delete": {Role.FIRM_ADMIN, Role.LAWYER},
    "ai.use": {Role.FIRM_ADMIN, Role.LAWYER},
    "ai.summarize": {Role.FIRM_ADMIN, Role.LAWYER, Role.INTERN},
    "billing.write": {Role.FIRM_ADMIN, Role.LAWYER},
    "billing.read": {Role.FIRM_ADMIN, Role.LAWYER, Role.CLIENT},
    "audit.read": {Role.FIRM_ADMIN},
    # Devices / profile / portal endpoints are available to every
    # authenticated role; there is no explicit entry because
    # `require()` is only used where a capability is actually
    # restricted (see get_current_auth for plain authentication).
}


def require(capability: str):
    """
    FastAPI dependency factory: returns a dependency that ensures the
    authenticated user's role is allowed to perform `capability`, per
    PERMISSIONS above. Raises 403 FORBIDDEN_ROLE otherwise.
    """

    allowed_roles = PERMISSIONS.get(capability)
    if allowed_roles is None:
        raise ValueError(f"Unknown RBAC capability: {capability!r}")

    def _dependency(auth: AuthContext = Depends(get_current_auth)) -> AuthContext:
        if auth.role not in {r.value for r in allowed_roles}:
            raise ForbiddenRoleException(
                message="You do not have permission to perform this action.",
                details={"required_roles": sorted(r.value for r in allowed_roles)},
            )
        return auth

    return _dependency
