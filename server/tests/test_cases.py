"""Contract behaviour for cases and hearings that the Android client depends on."""

import datetime as dt

import pytest
from httpx import AsyncClient

from tests.conftest import BASE, sign_in

pytestmark = pytest.mark.asyncio

CNR = "MHAU019999992024"


async def test_bad_cnr_returns_cnr_invalid_not_generic_validation(
    client: AsyncClient,
) -> None:
    """B.3 gives a malformed CNR its own code, and the app shows it inline on the
    field rather than as a toast. A generic VALIDATION_ERROR would land in the wrong
    place in the UI."""
    headers = await sign_in(client, "CNR Firm")

    response = await client.post(
        f"{BASE}/cases/lookup-cnr", headers=headers, json={"cnr": "12345"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "CNR_INVALID"


async def test_add_by_cnr_creates_case_with_hearing_history(
    client: AsyncClient,
) -> None:
    headers = await sign_in(client, "History Firm")

    created = await client.post(
        f"{BASE}/cases/from-cnr", headers=headers, json={"cnr": CNR}
    )
    case = created.json()["data"]
    assert case["ecourts_synced"] is True
    assert case["court_name"]

    hearings = (
        await client.get(f"{BASE}/cases/{case['id']}/hearings", headers=headers)
    ).json()["data"]

    # Past hearings arrive as real rows, which is what makes the case feel already
    # known rather than empty on the first open.
    assert len(hearings) >= 3
    assert all(h["source"] == "ecourts" for h in hearings)


async def test_duplicate_cnr_is_rejected(client: AsyncClient) -> None:
    headers = await sign_in(client, "Dupe Firm")

    await client.post(f"{BASE}/cases/from-cnr", headers=headers, json={"cnr": CNR})
    again = await client.post(
        f"{BASE}/cases/from-cnr", headers=headers, json={"cnr": CNR}
    )

    assert again.json()["error"]["code"] == "DUPLICATE_RESOURCE"


async def test_hearing_date_is_a_calendar_date_not_an_instant(
    client: AsyncClient,
) -> None:
    """The single most dangerous bug class in this product.

    A hearing on 2026-08-01 must come back as exactly "2026-08-01" — no time part, no
    Z suffix, nothing a client could convert through a timezone and render as 31 July.
    """
    headers = await sign_in(client, "Date Firm")
    case_id = (
        await client.post(
            f"{BASE}/cases", headers=headers, json={"title": "Date handling"}
        )
    ).json()["data"]["id"]

    created = await client.post(
        f"{BASE}/cases/{case_id}/hearings",
        headers=headers,
        json={"date": "2026-08-01", "purpose": "Evidence"},
    )
    hearing = created.json()["data"]

    assert hearing["date"] == "2026-08-01"
    assert "T" not in hearing["date"]
    assert "Z" not in hearing["date"]
    # Optional time really is optional — a NOT NULL column here would reject this.
    assert hearing["time"] is None


async def test_hearing_time_is_preserved_when_given(client: AsyncClient) -> None:
    headers = await sign_in(client, "Time Firm")
    case_id = (
        await client.post(f"{BASE}/cases", headers=headers, json={"title": "Timed"})
    ).json()["data"]["id"]

    hearing = (
        await client.post(
            f"{BASE}/cases/{case_id}/hearings",
            headers=headers,
            json={"date": "2026-08-01", "time": "10:30:00", "purpose": "Mention"},
        )
    ).json()["data"]

    assert hearing["time"] == "10:30:00"


async def test_manual_case_cannot_be_synced(client: AsyncClient) -> None:
    headers = await sign_in(client, "Manual Firm")
    case_id = (
        await client.post(f"{BASE}/cases", headers=headers, json={"title": "Manual"})
    ).json()["data"]["id"]

    response = await client.post(f"{BASE}/cases/{case_id}/sync", headers=headers)

    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_sync_is_rate_limited_per_case(client: AsyncClient) -> None:
    """B.6: 1/hour/case. add-by-CNR syncs on creation, so the cooldown is already
    running — and the response must carry retry_after_seconds for the app's UI."""
    headers = await sign_in(client, "Sync Firm")
    case_id = (
        await client.post(f"{BASE}/cases/from-cnr", headers=headers, json={"cnr": CNR})
    ).json()["data"]["id"]

    response = await client.post(f"{BASE}/cases/{case_id}/sync", headers=headers)
    error = response.json()["error"]

    assert error["code"] == "RATE_LIMITED"
    assert int(error["details"]["retry_after_seconds"]) > 0


async def test_case_list_is_ordered_by_next_hearing(client: AsyncClient) -> None:
    headers = await sign_in(client, "Order Firm")
    today = dt.date.today()

    for offset in (30, 5, 12):
        await client.post(
            f"{BASE}/cases",
            headers=headers,
            json={
                "title": f"Matter +{offset}d",
                "next_hearing_date": (today + dt.timedelta(days=offset)).isoformat(),
            },
        )

    listed = (await client.get(f"{BASE}/cases", headers=headers)).json()["data"]
    dates = [c["next_hearing_date"] for c in listed if c["next_hearing_date"]]

    # D.6: the list answers "what is coming up", not "what did I add last".
    assert dates == sorted(dates)
