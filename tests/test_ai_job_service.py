from app.db.enums import AIJobStatus
from app.services.ai_job_service import (
    ESTIMATED_SECONDS_BY_TYPE,
    TIMEOUT_SECONDS_BY_TYPE,
    wire_status,
)


def test_wire_status_maps_every_internal_state_to_contract_wording():
    # Contract B.7: job states are queued|running|done|failed over the
    # wire, even though the DB enum uses different internal names.
    assert wire_status(AIJobStatus.PENDING) == "queued"
    assert wire_status(AIJobStatus.RUNNING) == "running"
    assert wire_status(AIJobStatus.COMPLETED) == "done"
    assert wire_status(AIJobStatus.FAILED) == "failed"


def test_every_ai_job_status_has_a_wire_mapping():
    from app.services.ai_job_service import STATUS_WIRE_MAP

    assert set(STATUS_WIRE_MAP.keys()) == set(AIJobStatus)


def test_summarize_has_a_timeout_and_estimate_configured():
    assert TIMEOUT_SECONDS_BY_TYPE["summarize"] > 0
    assert ESTIMATED_SECONDS_BY_TYPE["summarize"] > 0
