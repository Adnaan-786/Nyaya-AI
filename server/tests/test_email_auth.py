"""Email OTP login — the channel that exists because DLT does not apply to email.

The security properties (5-minute TTL, 5 attempts, 3/hour) are shared with the phone
channel by construction rather than reimplemented, so what is worth testing here is
that sharing actually holds, and that the two channels stay separate accounts.
"""

import uuid

import pytest
from httpx import AsyncClient

from app.integrations import email as mailer
from tests.conftest import BASE

pytestmark = pytest.mark.asyncio


def _address() -> str:
    """Unique per call: OTP rows outlive a test, and a fixed address would start the
    next run already inside its own hourly limit."""
    return f"lawyer-{uuid.uuid4().hex[:12]}@example.com"


async def _request(http: AsyncClient, address: str):
    return await http.post(f"{BASE}/auth/email/request", json={"email": address})


async def test_email_sign_in_creates_an_account_and_returns_tokens(
    client: AsyncClient,
) -> None:
    address = _address()

    assert (await _request(client, address)).status_code == 200
    verified = await client.post(
        f"{BASE}/auth/email/verify", json={"email": address, "otp": "123456"}
    )

    assert verified.status_code == 200
    data = verified.json()["data"]
    assert data["is_new_user"] is True
    assert data["access_token"]
    assert data["user"]["email"] == address
    # The account has no phone at all — the whole point of this channel, and the thing
    # that would 500 if UserOut still required one.
    assert data["user"]["phone"] is None


async def test_signing_in_again_returns_the_same_account(client: AsyncClient) -> None:
    address = _address()

    await _request(client, address)
    first = await client.post(
        f"{BASE}/auth/email/verify", json={"email": address, "otp": "123456"}
    )
    await _request(client, address)
    second = await client.post(
        f"{BASE}/auth/email/verify", json={"email": address, "otp": "123456"}
    )

    assert second.json()["data"]["is_new_user"] is False
    assert first.json()["data"]["user"]["id"] == second.json()["data"]["user"]["id"]


async def test_addresses_are_case_insensitive(client: AsyncClient) -> None:
    """Otherwise Ramesh@firm.com and ramesh@firm.com become two accounts holding two
    halves of one lawyer's practice."""
    address = _address()

    await _request(client, address.upper())
    verified = await client.post(
        f"{BASE}/auth/email/verify", json={"email": address, "otp": "123456"}
    )

    assert verified.status_code == 200
    assert verified.json()["data"]["user"]["email"] == address


async def test_a_wrong_code_is_rejected(client: AsyncClient) -> None:
    address = _address()
    await _request(client, address)

    rejected = await client.post(
        f"{BASE}/auth/email/verify", json={"email": address, "otp": "000000"}
    )

    assert rejected.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_a_code_cannot_be_replayed(client: AsyncClient) -> None:
    address = _address()
    await _request(client, address)
    body = {"email": address, "otp": "123456"}

    assert (await client.post(f"{BASE}/auth/email/verify", json=body)).status_code == 200
    replayed = await client.post(f"{BASE}/auth/email/verify", json=body)

    assert replayed.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_the_hourly_limit_is_shared_with_the_phone_channel_logic(
    client: AsyncClient,
) -> None:
    """Mail-bombing an address is the same abuse as SMS-bombing a number, and the
    limit is the same code path — this proves the new channel did not skip it."""
    address = _address()

    for _ in range(3):
        assert (await _request(client, address)).status_code == 200

    fourth = await _request(client, address)
    assert fourth.status_code == 429
    assert fourth.json()["error"]["code"] == "RATE_LIMITED"


async def test_a_malformed_address_is_rejected_before_any_row_is_written(
    client: AsyncClient,
) -> None:
    response = await client.post(f"{BASE}/auth/email/request", json={"email": "not-an-email"})
    # 400, not FastAPI's default 422 — C.3.2 normalises every validation failure into
    # the one envelope the app branches on.
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_a_failed_send_does_not_burn_the_hourly_limit(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same guarantee the SMS channel got, for the same reason: a relay that is down
    must not cost the user their three attempts."""
    address = _address()

    async def failing(*_args, **_kwargs):
        raise mailer.EmailDeliveryError("relay refused")

    monkeypatch.setattr(mailer, "send_otp", failing)
    for _ in range(3):
        response = await _request(client, address)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "UPSTREAM_UNAVAILABLE"

    monkeypatch.undo()
    assert (await _request(client, address)).status_code == 200


async def test_email_and_phone_accounts_do_not_collide(client: AsyncClient) -> None:
    """A phone sign-in must not resolve to an email account or vice versa, even though
    both channels share one otp_codes table."""
    address = _address()
    phone = f"9{uuid.uuid4().int % 10**9:09d}"

    await _request(client, address)
    by_email = await client.post(
        f"{BASE}/auth/email/verify", json={"email": address, "otp": "123456"}
    )
    await client.post(f"{BASE}/auth/otp/request", json={"phone": phone})
    by_phone = await client.post(
        f"{BASE}/auth/otp/verify", json={"phone": phone, "otp": "123456"}
    )

    assert by_email.json()["data"]["user"]["id"] != by_phone.json()["data"]["user"]["id"]
    assert by_phone.json()["data"]["user"]["email"] is None


async def test_the_team_roster_survives_a_member_who_has_no_phone(
    client: AsyncClient,
) -> None:
    """There are two separate UserOut schemas — auth's and users' — and only the first
    is exercised by signing in. The second one still required a phone, so the whole
    team roster 500'd for any firm containing one email signup. Caught end-to-end, not
    by the sign-in tests, which is exactly why this one exists."""
    address = _address()
    await _request(client, address)
    session = (
        await client.post(
            f"{BASE}/auth/email/verify", json={"email": address, "otp": "123456"}
        )
    ).json()["data"]

    await client.post(
        f"{BASE}/auth/onboard",
        headers={"Authorization": f"Bearer {session['access_token']}"},
        json={"name": "Adv. Priya", "role_hint": "firm_admin", "firm_name": "Priya Law"},
    )
    # Onboarding changes the role in the DB but does not reissue the token, so refresh
    # once to get a token that actually carries firm_admin — same dance conftest does.
    refreshed = await client.post(
        f"{BASE}/auth/refresh", json={"refresh_token": session["refresh_token"]}
    )
    admin = {"Authorization": f"Bearer {refreshed.json()['data']['access_token']}"}

    roster = await client.get(f"{BASE}/users", headers=admin)

    assert roster.status_code == 200
    assert roster.json()["data"][0]["phone"] is None
    assert roster.json()["data"][0]["email"] == address


async def test_a_code_issued_for_email_does_not_verify_a_phone(
    client: AsyncClient,
) -> None:
    """The code is hashed with its identifier, so a code mailed to an address cannot
    be replayed against a lookalike phone number."""
    address = _address()
    await _request(client, address)

    leaked = await client.post(
        f"{BASE}/auth/otp/verify", json={"phone": "+919812345678", "otp": "123456"}
    )

    assert leaked.status_code != 200
