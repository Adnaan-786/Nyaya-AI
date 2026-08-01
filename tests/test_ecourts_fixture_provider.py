import pytest

from app.integrations.ecourts.base import ECourtsProviderError
from app.integrations.ecourts.fixture import (
    FixtureProvider,
    reset_fixture_mutation,
    trigger_fixture_mutation,
)

MUTABLE_CNR = "MH03202410000300"


@pytest.fixture(autouse=True)
def _reset_mutation_state():
    reset_fixture_mutation()
    yield
    reset_fixture_mutation()


@pytest.mark.asyncio
async def test_lookup_cnr_returns_normalized_case():
    provider = FixtureProvider()
    case = await provider.lookup_cnr(MUTABLE_CNR)

    assert case.cnr == MUTABLE_CNR
    assert case.title
    assert case.court_name
    assert len(case.history) >= 1


@pytest.mark.asyncio
async def test_lookup_cnr_unknown_raises_provider_error():
    provider = FixtureProvider()
    with pytest.raises(ECourtsProviderError):
        await provider.lookup_cnr("0000000000000000")


@pytest.mark.asyncio
async def test_mutation_changes_stage_and_adds_history():
    provider = FixtureProvider()

    before = await provider.lookup_cnr(MUTABLE_CNR)
    trigger_fixture_mutation()
    after = await provider.lookup_cnr(MUTABLE_CNR)

    assert after.stage != before.stage
    assert len(after.history) == len(before.history) + 1


@pytest.mark.asyncio
async def test_case_status_delegates_to_lookup_cnr():
    provider = FixtureProvider()

    via_lookup = await provider.lookup_cnr(MUTABLE_CNR)
    via_status = await provider.case_status(MUTABLE_CNR)

    assert via_lookup.cnr == via_status.cnr
    assert via_lookup.stage == via_status.stage


@pytest.mark.asyncio
async def test_cause_list_filters_by_court_name():
    provider = FixtureProvider()
    results = await provider.cause_list("Bombay High Court", __import__("datetime").date.today())

    assert len(results) > 0
    assert all(r.court_name == "Bombay High Court" for r in results)
