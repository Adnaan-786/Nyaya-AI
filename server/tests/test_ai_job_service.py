"""Admission control for AI jobs: what each limit means to the app that hits it."""

import datetime as dt
import uuid

import pytest
from httpx import AsyncClient

from app.api import ai
from app.core.db import SessionFactory
from app.models import AiJob
from app.schemas.ai import MAX_ESTIMATED_SECONDS
from app.services import ai_job_service
from tests.conftest import BASE, sign_in

pytestmark = pytest.mark.asyncio

JOB_TYPES = ("summarize", "research", "draft", "risk_review")


def test_every_job_type_has_an_estimate_and_a_timeout() -> None:
    for job_type in JOB_TYPES:
        assert ai_job_service.estimate_for(job_type) > 0
        assert ai_job_service.timeout_for(job_type) > 0


def test_no_estimate_outlives_the_window_the_app_polls_for() -> None:
    """B.7: the app polls every 3s for up to 5 min, so an estimate beyond that is a
    promise the app cannot keep."""
    for job_type in JOB_TYPES:
        assert ai_job_service.estimate_for(job_type) <= MAX_ESTIMATED_SECONDS


def test_an_unknown_job_type_still_gets_a_usable_estimate() -> None:
    assert ai_job_service.estimate_for("something_new") > 0
    assert ai_job_service.timeout_for("something_new") > 0


def test_a_timeout_always_exceeds_the_estimate_it_belongs_to() -> None:
    """A timeout under the estimate would kill jobs the app is still patiently
    waiting for."""
    for job_type in JOB_TYPES:
        assert ai_job_service.timeout_for(job_type) > ai_job_service.estimate_for(job_type)


def test_the_plan_table_is_the_one_the_routes_enforce() -> None:
    """The quota test in test_ai.py patches `ai.DAILY_JOB_LIMITS`; that only works
    while it is the same object the service reads."""
    assert ai.DAILY_JOB_LIMITS is ai_job_service.DAILY_JOB_LIMITS


def test_plan_limits_increase_with_the_plan() -> None:
    limits = ai_job_service.DAILY_JOB_LIMITS
    assert limits["solo"] < limits["firm"] < limits["enterprise"]


async def test_the_concurrency_cap_is_a_429_and_not_a_paywall(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Too many jobs in flight clears itself in seconds. Answering it with the 402 the
    daily quota uses would show a paywall to a firm well inside its plan, and no
    upgrade would make the message go away."""
    monkeypatch.setattr(ai_job_service.settings, "ai_max_concurrent_jobs_per_tenant", 0)
    headers = await sign_in(client, "Busy Firm")

    response = await client.post(
        f"{BASE}/ai/research", headers=headers, json={"query": "anything at all"}
    )

    assert response.status_code == 429
    error = response.json()["error"]
    assert error["code"] == "RATE_LIMITED"
    assert int(error["details"]["retry_after_seconds"]) > 0


async def _pin_job_as_running(job_id: str, *, age_seconds: int) -> None:
    """Freeze a job in `running` at a chosen age — the state a worker killed mid-job
    leaves behind, which no request can produce on its own."""
    async with SessionFactory() as session:
        job = await session.get(AiJob, uuid.UUID(job_id))
        job.status = "running"
        job.created_at = dt.datetime.now(dt.UTC) - dt.timedelta(seconds=age_seconds)
        await session.commit()


async def test_a_job_still_plausibly_running_counts_against_the_cap(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ai_job_service.settings, "ai_max_concurrent_jobs_per_tenant", 1)
    headers = await sign_in(client, "InFlight Firm")

    first = await client.post(
        f"{BASE}/ai/research", headers=headers, json={"query": "first question"}
    )
    await _pin_job_as_running(first.json()["data"]["job_id"], age_seconds=1)

    second = await client.post(
        f"{BASE}/ai/research", headers=headers, json={"query": "second question"}
    )

    assert second.status_code == 429


async def test_a_stalled_job_does_not_lock_a_firm_out_forever(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same row, older than any job could legitimately be. It must stop counting, or
    a crashed worker silently ends AI for that firm."""
    monkeypatch.setattr(ai_job_service.settings, "ai_max_concurrent_jobs_per_tenant", 1)
    headers = await sign_in(client, "Stalled Firm")

    first = await client.post(
        f"{BASE}/ai/research", headers=headers, json={"query": "first question"}
    )
    await _pin_job_as_running(
        first.json()["data"]["job_id"],
        age_seconds=ai_job_service.in_flight_window_seconds() + 60,
    )

    second = await client.post(
        f"{BASE}/ai/research", headers=headers, json={"query": "second question"}
    )

    assert second.status_code == 202
