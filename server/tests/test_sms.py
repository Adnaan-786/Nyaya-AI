"""MSG91 delivery, and the two failure modes that only appear once it is live.

Everything here runs against a stubbed transport — the point is the request this
server *builds* and how it reads the reply, neither of which a FAKE_MODE run exercises.
"""

import uuid

import httpx
import pytest
from httpx import AsyncClient

from app.integrations import sms
from tests.conftest import BASE

pytestmark = pytest.mark.asyncio


def _go_live(monkeypatch: pytest.MonkeyPatch, **templates: str) -> None:
    monkeypatch.setattr(sms.settings, "fake_mode", False)
    monkeypatch.setattr(sms.settings, "msg91_auth_key", "test-key")
    monkeypatch.setattr(sms.settings, "msg91_sender_id", None)
    for name, value in templates.items():
        monkeypatch.setattr(sms.settings, name, value)


def _stub(monkeypatch: pytest.MonkeyPatch, response: httpx.Response) -> list[dict]:
    """Captures what would have gone to MSG91 and replies with `response`."""
    calls: list[dict] = []

    async def post(self, url, *, json=None, params=None, headers=None):  # noqa: ANN001
        calls.append({"url": url, "json": json, "params": params, "headers": headers})
        return response

    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    return calls


SUCCESS = {"type": "success", "message": "3d5f1a2b"}
# MSG91's rejection shape. Note the 200 — see below.
REJECTED = {"type": "error", "message": "No DLT Template ID or Invalid Template ID"}


async def test_a_rejection_arrives_as_http_200_and_is_still_a_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The single most misleading thing about this API.

    MSG91 answers a refused send with 200 and an error body, so `raise_for_status()`
    on its own reports a message that was never delivered as sent — an OTP screen that
    waits forever, with a clean server log.
    """
    _go_live(monkeypatch, msg91_template_id="otp-tpl")
    _stub(monkeypatch, httpx.Response(200, json=REJECTED))

    with pytest.raises(sms.SmsDeliveryError, match="DLT Template"):
        await sms.send_otp("+919876543210", "123456")


async def test_otp_success_is_not_mistaken_for_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _go_live(monkeypatch, msg91_template_id="otp-tpl")
    calls = _stub(monkeypatch, httpx.Response(200, json=SUCCESS))

    await sms.send_otp("+919876543210", "123456")

    assert calls[0]["params"]["mobile"] == "919876543210", "the + must be stripped"
    assert calls[0]["params"]["otp"] == "123456"
    assert calls[0]["headers"]["authkey"] == "test-key"


async def test_http_error_is_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _go_live(monkeypatch, msg91_template_id="otp-tpl")
    _stub(monkeypatch, httpx.Response(401, json={"message": "authkey invalid"}))

    with pytest.raises(sms.SmsDeliveryError, match="401"):
        await sms.send_otp("+919876543210", "123456")


async def test_template_sends_use_the_flow_payload_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`{"template_id", "recipients": [{"mobiles", ...vars}]}` is the only shape the
    flow API accepts — the free-text `{"mobiles", "message"}` this replaced was
    rejected every time, which no FAKE_MODE test could have caught."""
    _go_live(monkeypatch, msg91_template_invoice="inv-tpl")
    calls = _stub(monkeypatch, httpx.Response(200, json=SUCCESS))

    sent = await sms.send_invoice_link("+919876543210", "INV-1", "5,000", "https://pay/x")

    assert sent is True
    payload = calls[0]["json"]
    assert payload["template_id"] == "inv-tpl"
    assert payload["recipients"] == [
        {
            "mobiles": "919876543210",
            "number": "INV-1",
            "amount": "5,000",
            "link": "https://pay/x",
        }
    ]
    # Unset sender means MSG91 uses the header bound to the template on its panel.
    assert "sender" not in payload


async def test_sender_id_is_included_only_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _go_live(monkeypatch, msg91_template_client_invite="inv-tpl")
    monkeypatch.setattr(sms.settings, "msg91_sender_id", "NYAYAI")
    calls = _stub(monkeypatch, httpx.Response(200, json=SUCCESS))

    await sms.send_client_invite("+919876543210", "Ramesh", "A1B2C3")

    assert calls[0]["json"]["sender"] == "NYAYAI"


async def test_a_failed_invoice_sms_does_not_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The invoice is already raised and committed by this point. Letting a dead SMS
    gateway turn that into a 500 would tell the lawyer their invoice failed when it
    did not."""
    _go_live(monkeypatch, msg91_template_invoice="inv-tpl")
    _stub(monkeypatch, httpx.Response(200, json=REJECTED))

    assert await sms.send_invoice_link("+919876543210", "INV-1", "5,000", "https://p") is False


async def test_one_unregistered_template_does_not_break_the_others(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DLT approves templates one at a time, so a live account with only some of them
    registered is the normal state for days — it must degrade per message type."""
    _go_live(monkeypatch, msg91_template_invoice=None, msg91_template_client_invite="ok")
    _stub(monkeypatch, httpx.Response(200, json=SUCCESS))

    assert await sms.send_invoice_link("+919876543210", "INV-1", "1", "https://p") is False
    assert await sms.send_client_invite("+919876543210", "Ramesh", "A1B2C3") is True


async def test_a_failed_send_does_not_burn_the_hourly_otp_limit(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Running out of SMS credit is the most ordinary MSG91 failure there is.

    If those attempts still counted, three undelivered codes would lock a lawyer out
    of their own account for an hour — punishing them for our outage.
    """
    # Unique per run, for the reason conftest.sign_in gives: OTP rows outlive the test
    # and a fixed number would start the next run inside its own hourly limit.
    phone = f"9{uuid.uuid4().int % 10**9:09d}"

    async def failing(*_args, **_kwargs):
        raise sms.SmsDeliveryError("balance exhausted")

    monkeypatch.setattr(sms, "send_otp", failing)
    for _ in range(sms_attempts := 3):
        response = await client.post(f"{BASE}/auth/otp/request", json={"phone": phone})
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "UPSTREAM_UNAVAILABLE"
    assert sms_attempts == 3

    # The gateway recovers; the user has not spent their allowance.
    monkeypatch.undo()
    recovered = await client.post(f"{BASE}/auth/otp/request", json={"phone": phone})
    assert recovered.status_code == 200, "failed sends were counted against the limit"
