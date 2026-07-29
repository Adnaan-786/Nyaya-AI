import uuid

import pytest

from app.core.dependencies import AuthContext
from app.core.exceptions import ForbiddenRoleException
from app.core.rbac import PERMISSIONS, require


def _auth(role: str) -> AuthContext:
    return AuthContext(user_id=uuid.uuid4(), tenant_id=uuid.uuid4(), role=role)


@pytest.mark.asyncio
async def test_require_allows_permitted_role():
    dependency = require("firm.manage")
    auth = _auth("firm_admin")

    result = dependency(auth=auth)

    assert result is auth


@pytest.mark.asyncio
async def test_require_blocks_unpermitted_role():
    dependency = require("firm.manage")
    auth = _auth("intern")

    with pytest.raises(ForbiddenRoleException):
        dependency(auth=auth)


def test_require_rejects_unknown_capability():
    with pytest.raises(ValueError):
        require("not.a.real.capability")


def test_client_role_cannot_write_cases():
    assert "client" not in {r.value for r in PERMISSIONS["cases.write"]}


def test_intern_can_read_but_not_write_clients():
    intern_ok = "intern" in {r.value for r in PERMISSIONS["clients.read"]}
    intern_write = "intern" in {r.value for r in PERMISSIONS["clients.write"]}

    assert intern_ok is True
    assert intern_write is False
