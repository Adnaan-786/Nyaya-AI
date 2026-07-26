"""Invoicing, GST, payments (B.10) and client-mode scoping (D.10)."""

import uuid

import pytest
from httpx import AsyncClient

from app.core.india import today_in_india
from app.integrations import razorpay
from app.services import invoicing
from tests.conftest import BASE, sign_in

pytestmark = pytest.mark.asyncio


async def _client_record(http: AsyncClient, headers: dict, name: str = "Sharma Textiles") -> str:
    phone = f"9{uuid.uuid4().int % 10**9:09d}"
    created = await http.post(
        f"{BASE}/clients", headers=headers, json={"name": name, "phone": phone}
    )
    return created.json()["data"]["id"]


async def _invoice(http: AsyncClient, headers: dict, **overrides) -> dict:
    client_id = overrides.pop("client_id", None) or await _client_record(http, headers)
    body = {
        "client_id": client_id,
        "line_items": [
            {"description": "Drafting written statement", "quantity": 1, "rate_paise": 2500000},
            {"description": "Court appearance", "quantity": 3, "rate_paise": 150000},
        ],
        **overrides,
    }
    response = await http.post(f"{BASE}/invoices", headers=headers, json=body)
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def test_gst_is_computed_in_integer_paise(client: AsyncClient) -> None:
    """Rs 25,000 + 3 x Rs 1,500 = Rs 29,500, +18% GST = Rs 34,810.

    Asserted in paise because that is what the API returns; a float anywhere in this
    path would show up as 3480999 or 3481000.00000001.
    """
    headers = await sign_in(client, "GST Firm")
    invoice = await _invoice(client, headers)

    assert invoice["subtotal_paise"] == 2950000
    assert invoice["gst_paise"] == 531000
    assert invoice["total_paise"] == 3481000
    assert isinstance(invoice["total_paise"], int)


async def test_reverse_charge_zeroes_the_tax(client: AsyncClient) -> None:
    """An advocate billing a business entity charges no GST — the recipient pays it.

    Adding 18% here would produce an invoice the client's accounts team rejects.
    """
    headers = await sign_in(client, "RCM Firm")
    invoice = await _invoice(client, headers, reverse_charge=True)

    assert invoice["gst_paise"] == 0
    assert invoice["total_paise"] == invoice["subtotal_paise"] == 2950000
    # The rate is still recorded so the PDF can name the mechanism.
    assert invoice["gst_rate"] == 18


async def test_invoice_numbers_are_sequential_within_the_financial_year(
    client: AsyncClient,
) -> None:
    """GST requires unique consecutive numbering per FY, and India's FY starts in April."""
    headers = await sign_in(client, "Numbering Firm")

    first = await _invoice(client, headers)
    second = await _invoice(client, headers)

    fy = invoicing.financial_year(today_in_india())
    assert first["number"] == f"NY/{fy}/0001"
    assert second["number"] == f"NY/{fy}/0002"


async def test_numbering_is_per_firm(client: AsyncClient) -> None:
    """Firm B's first invoice is 0001, not 0003 — numbering must not leak the volume
    of other firms on the platform, and each firm's books must start at one."""
    a_headers = await sign_in(client, "Books A")
    b_headers = await sign_in(client, "Books B")

    await _invoice(client, a_headers)
    await _invoice(client, a_headers)
    b_first = await _invoice(client, b_headers)

    assert b_first["number"].endswith("/0001")


async def test_unbilled_time_imports_once_and_only_once(client: AsyncClient) -> None:
    """D.9 "import unbilled time". The same hour must never reach two invoices."""
    headers = await sign_in(client, "Timer Firm")
    client_id = await _client_record(client, headers)
    case = (
        await client.post(
            f"{BASE}/cases",
            headers=headers,
            json={"title": "Sharma v. State", "client_id": client_id},
        )
    ).json()["data"]

    await client.post(
        f"{BASE}/time-entries",
        headers=headers,
        json={
            "case_id": case["id"],
            "started_at": "2026-07-20T10:00:00Z",
            "duration_seconds": 7200,
            "description": "Conference with client",
            "rate_paise": 500000,
        },
    )

    first = await _invoice(
        client,
        headers,
        client_id=client_id,
        case_id=case["id"],
        import_unbilled_time=True,
    )
    assert len(first["line_items"]) == 3
    assert first["subtotal_paise"] == 2950000 + 2 * 500000

    second = await _invoice(
        client,
        headers,
        client_id=client_id,
        case_id=case["id"],
        import_unbilled_time=True,
    )
    assert len(second["line_items"]) == 2, "the same time entry was billed twice"


async def test_forged_payment_signature_never_marks_an_invoice_paid(
    client: AsyncClient,
) -> None:
    """The security property of B.10.

    Anyone can POST to /payments/verify with an order id they saw. Only a valid HMAC
    may move an invoice to paid — otherwise every invoice on the platform is free.
    """
    headers = await sign_in(client, "Payment Firm")
    invoice = await _invoice(client, headers)

    order = (
        await client.post(
            f"{BASE}/payments/order", headers=headers, json={"invoice_id": invoice["id"]}
        )
    ).json()["data"]

    forged = await client.post(
        f"{BASE}/payments/verify",
        headers=headers,
        json={
            "order_id": order["razorpay_order_id"],
            "payment_id": "pay_attacker",
            "signature": "0" * 64,
        },
    )
    assert forged.json()["error"]["code"] == "VALIDATION_ERROR"

    still = (await client.get(f"{BASE}/invoices/{invoice['id']}", headers=headers)).json()
    assert still["data"]["status"] != "paid"


async def test_valid_signature_marks_the_invoice_paid_server_side(
    client: AsyncClient,
) -> None:
    """B.10: the response carries the *invoice* status, because the app is told to
    trust that and never its own Checkout SDK result."""
    headers = await sign_in(client, "Paid Firm")
    invoice = await _invoice(client, headers)

    order = (
        await client.post(
            f"{BASE}/payments/order", headers=headers, json={"invoice_id": invoice["id"]}
        )
    ).json()["data"]
    assert order["amount_paise"] == invoice["total_paise"]

    payment_id = "pay_TESTPAYMENT01"
    verified = await client.post(
        f"{BASE}/payments/verify",
        headers=headers,
        json={
            "order_id": order["razorpay_order_id"],
            "payment_id": payment_id,
            "signature": razorpay.fake_signature(order["razorpay_order_id"], payment_id),
        },
    )

    assert verified.json()["data"]["invoice_status"] == "paid"


async def test_paid_invoices_cannot_be_edited(client: AsyncClient) -> None:
    """Once money has moved the invoice is an accounting record, not a draft."""
    headers = await sign_in(client, "Ledger Firm")
    invoice = await _invoice(client, headers)

    order = (
        await client.post(
            f"{BASE}/payments/order", headers=headers, json={"invoice_id": invoice["id"]}
        )
    ).json()["data"]
    payment_id = "pay_LEDGER01"
    await client.post(
        f"{BASE}/payments/verify",
        headers=headers,
        json={
            "order_id": order["razorpay_order_id"],
            "payment_id": payment_id,
            "signature": razorpay.fake_signature(order["razorpay_order_id"], payment_id),
        },
    )

    edited = await client.patch(
        f"{BASE}/invoices/{invoice['id']}",
        headers=headers,
        json={"line_items": [{"description": "Revised", "quantity": 1, "rate_paise": 1}]},
    )
    assert edited.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_send_produces_a_real_pdf_and_a_payment_link(client: AsyncClient) -> None:
    headers = await sign_in(client, "Send Firm")
    invoice = await _invoice(client, headers)

    sent = (
        await client.post(f"{BASE}/invoices/{invoice['id']}/send", headers=headers)
    ).json()["data"]
    assert sent["status"] == "sent"
    assert sent["payment_link"]

    pdf = await client.get(f"{BASE}/invoices/{invoice['id']}/pdf", headers=headers)
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")


async def test_invoices_are_not_visible_across_firms(client: AsyncClient) -> None:
    """IC-4 again, on the surface where a leak is most damaging."""
    a_headers = await sign_in(client, "Private A")
    b_headers = await sign_in(client, "Private B")
    invoice = await _invoice(client, a_headers)

    denied = await client.get(f"{BASE}/invoices/{invoice['id']}", headers=b_headers)
    assert denied.json()["error"]["code"] == "INVOICE_NOT_FOUND"


async def _client_login(http: AsyncClient, headers: dict, client_id: str) -> dict:
    """Invite a client and sign in as them — the D.10 client-mode session."""
    invited = (
        await http.post(f"{BASE}/clients/{client_id}/invite", headers=headers)
    ).json()["data"]
    phone = invited["invited_phone"]

    await http.post(f"{BASE}/auth/otp/request", json={"phone": phone})
    verified = await http.post(
        f"{BASE}/auth/otp/verify", json={"phone": phone, "otp": "123456"}
    )
    return {"Authorization": f"Bearer {verified.json()['data']['access_token']}"}


async def test_client_mode_sees_only_their_own_cases(client: AsyncClient) -> None:
    headers = await sign_in(client, "Portal Firm")
    mine = await _client_record(client, headers, "Mine Ltd")
    theirs = await _client_record(client, headers, "Theirs Ltd")

    for client_id, title in ((mine, "My matter"), (theirs, "Another client's matter")):
        await client.post(
            f"{BASE}/cases", headers=headers, json={"title": title, "client_id": client_id}
        )

    portal_headers = await _client_login(client, headers, mine)
    listed = (await client.get(f"{BASE}/portal/cases", headers=portal_headers)).json()

    titles = [case["title"] for case in listed["data"]]
    assert titles == ["My matter"]
    # Plain language, not the internal status string (D.10).
    assert listed["data"][0]["status"] == "In progress"


async def test_client_mode_cannot_reach_staff_surfaces(client: AsyncClient) -> None:
    """The app hides these; the server is what actually enforces it."""
    headers = await sign_in(client, "Locked Firm")
    client_id = await _client_record(client, headers)
    portal_headers = await _client_login(client, headers, client_id)

    for path in ("/cases", "/documents", "/ai/jobs", "/time-entries", "/invoices"):
        response = await client.get(f"{BASE}{path}", headers=portal_headers)
        assert response.json()["error"]["code"] == "FORBIDDEN_ROLE", path


async def test_staff_cannot_use_the_portal_routes(client: AsyncClient) -> None:
    """The gate runs both ways, so a lawyer never sees the sanitized view by accident
    and mistakes it for the full record."""
    headers = await sign_in(client, "Staff Firm")
    response = await client.get(f"{BASE}/portal/cases", headers=headers)
    assert response.json()["error"]["code"] == "FORBIDDEN_ROLE"


async def test_draft_invoices_are_hidden_from_the_client(client: AsyncClient) -> None:
    """A draft is the lawyer still deciding what to charge."""
    headers = await sign_in(client, "Draft Firm")
    client_id = await _client_record(client, headers)
    draft = await _invoice(client, headers, client_id=client_id)
    sent = await _invoice(client, headers, client_id=client_id)
    await client.post(f"{BASE}/invoices/{sent['id']}/send", headers=headers)

    portal_headers = await _client_login(client, headers, client_id)
    listed = (await client.get(f"{BASE}/portal/invoices", headers=portal_headers)).json()

    numbers = [invoice["number"] for invoice in listed["data"]]
    assert sent["number"] in numbers
    assert draft["number"] not in numbers


async def test_client_can_pay_their_own_invoice_but_not_another(
    client: AsyncClient,
) -> None:
    """Paying is the one write a client-mode user must be able to do — and only for
    invoices addressed to them."""
    headers = await sign_in(client, "Pay Firm")
    mine = await _client_record(client, headers, "Payer Ltd")
    theirs = await _client_record(client, headers, "Other Ltd")

    my_invoice = await _invoice(client, headers, client_id=mine)
    their_invoice = await _invoice(client, headers, client_id=theirs)
    for invoice in (my_invoice, their_invoice):
        await client.post(f"{BASE}/invoices/{invoice['id']}/send", headers=headers)

    portal_headers = await _client_login(client, headers, mine)

    allowed = await client.post(
        f"{BASE}/payments/order", headers=portal_headers, json={"invoice_id": my_invoice["id"]}
    )
    assert allowed.json()["data"]["amount_paise"] == my_invoice["total_paise"]

    denied = await client.post(
        f"{BASE}/payments/order",
        headers=portal_headers,
        json={"invoice_id": their_invoice["id"]},
    )
    assert denied.json()["error"]["code"] == "INVOICE_NOT_FOUND"


async def test_unsigned_webhook_is_rejected(client: AsyncClient) -> None:
    """Webhooks are unauthenticated HTTP; without this check anyone could mark every
    invoice on the platform paid."""
    response = await client.post(
        f"{BASE}/payments/webhook",
        json={"event": "payment.captured", "payload": {"payment": {"entity": {}}}},
    )
    assert response.json()["error"]["code"] == "WEBHOOK_SIGNATURE_INVALID"


async def test_invoice_is_dated_in_ist_not_utc(client: AsyncClient) -> None:
    """A tax invoice created at 04:00 UTC belongs to the *next* day in India.

    Dating it in UTC puts it a day early, which near 31 March lands it in the wrong
    financial year — the one thing sequential GST numbering exists to prevent.
    """
    import datetime as dt

    from app.core.india import to_india
    from app.services.invoicing import financial_year

    late_night_utc = dt.datetime(2026, 3, 31, 20, 30, tzinfo=dt.UTC)
    in_india = to_india(late_night_utc)

    assert in_india.date() == dt.date(2026, 4, 1)
    # Same instant, two different financial years — this is the whole point.
    assert financial_year(late_night_utc.date()) == "2025-26"
    assert financial_year(in_india.date()) == "2026-27"


async def test_pdf_renders_a_devanagari_client_name(client: AsyncClient) -> None:
    """Hindi is a first-class language here (D.4.3), so a client may well be named in
    Devanagari. fpdf2's built-in fonts are latin-1 and would raise on this input."""
    headers = await sign_in(client, "Devanagari Firm")
    client_id = await _client_record(client, headers, "शर्मा टेक्सटाइल्स प्राइवेट लिमिटेड")
    invoice = await _invoice(client, headers, client_id=client_id)

    await client.post(f"{BASE}/invoices/{invoice['id']}/send", headers=headers)
    pdf = await client.get(f"{BASE}/invoices/{invoice['id']}/pdf", headers=headers)

    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")
    assert len(pdf.content) > 5000, "an embedded font should make this a real document"
