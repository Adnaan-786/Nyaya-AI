"""IC-4: "firm A can never see firm B data — automated".

This is the test that has to exist. Every other bug in this product is recoverable;
one firm reading another firm's case files is not, and the failure mode is silent —
the app looks perfectly normal while serving the wrong data.

Isolation is checked against a *known* id rather than a guessed one, because the real
threat is not enumeration, it is a stale or shared identifier reaching the wrong query.
"""

import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import BASE, sign_in

pytestmark = pytest.mark.asyncio


async def _seed_firm(http: AsyncClient, name: str) -> tuple[dict, str, str]:
    headers = await sign_in(http, name)

    client_id = (
        await http.post(
            f"{BASE}/clients",
            headers=headers,
            # Unique per firm: a shared number would trip the per-phone OTP rate
            # limit when several tests invite "their" client to the portal.
            json={"name": f"{name} client", "phone": f"+91{uuid.uuid4().int % 10**10:010d}"},
        )
    ).json()["data"]["id"]

    case_id = (
        await http.post(
            f"{BASE}/cases",
            headers=headers,
            json={"title": f"{name} confidential matter", "client_id": client_id},
        )
    ).json()["data"]["id"]

    return headers, client_id, case_id


async def test_firm_b_cannot_reach_firm_a_data(client: AsyncClient) -> None:
    a_headers, a_client, a_case = await _seed_firm(client, "Firm A")
    b_headers, _, _ = await _seed_firm(client, "Firm B")

    # Listing is scoped: B sees only its own case, never A's.
    listed = (await client.get(f"{BASE}/cases", headers=b_headers)).json()
    assert all(c["id"] != a_case for c in listed["data"])
    assert all("Firm A" not in c["title"] for c in listed["data"])

    # Direct access with the exact id must be indistinguishable from "does not exist".
    for method, path in [
        ("get", f"/cases/{a_case}"),
        ("get", f"/cases/{a_case}/timeline"),
        ("get", f"/cases/{a_case}/hearings"),
        ("get", f"/clients/{a_client}"),
        ("get", f"/clients/{a_client}/cases"),
        ("delete", f"/cases/{a_case}"),
    ]:
        response = await getattr(client, method)(f"{BASE}{path}", headers=b_headers)
        body = response.json()
        assert body["success"] is False, f"{method} {path} leaked to another firm"
        assert body["error"]["code"].endswith("_NOT_FOUND")

    # Writes must not land either.
    patched = await client.patch(
        f"{BASE}/cases/{a_case}", headers=b_headers, json={"title": "hijacked"}
    )
    assert patched.json()["error"]["code"] == "CASE_NOT_FOUND"

    # And A's data is untouched after all of that.
    still_there = (await client.get(f"{BASE}/cases/{a_case}", headers=a_headers)).json()
    assert still_there["success"] is True
    assert still_there["data"]["title"] == "Firm A confidential matter"


async def test_client_role_cannot_reach_staff_endpoints(client: AsyncClient) -> None:
    """D.10: role=client gets a reduced app. The server enforces it; the app only hides
    the UI, so a client-role token hitting a staff route must be refused here."""
    headers, client_id, _ = await _seed_firm(client, "Firm C")

    invited = await client.post(
        f"{BASE}/clients/{client_id}/invite", headers=headers
    )
    assert invited.json()["success"] is True

    phone = invited.json()["data"]["invited_phone"]
    await client.post(f"{BASE}/auth/otp/request", json={"phone": phone})
    token = (
        await client.post(
            f"{BASE}/auth/otp/verify", json={"phone": phone, "otp": "123456"}
        )
    ).json()["data"]["access_token"]
    client_headers = {"Authorization": f"Bearer {token}"}

    refused = await client.get(f"{BASE}/cases", headers=client_headers)
    assert refused.json()["error"]["code"] == "FORBIDDEN_ROLE"
