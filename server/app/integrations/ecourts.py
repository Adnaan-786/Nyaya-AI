"""eCourts case lookup by CNR.

C.6 requires a provider abstraction: NAPIX is the official route but approval "can take
weeks", so a commercial provider is the fallback and FAKE_MODE is the third leg. All
three return the same shape, so the router and the app never learn which one answered.

The fake provider is not a stub returning lorem ipsum — it synthesises plausible Indian
court data deterministically from the CNR, so demos and screenshots look real and the
`hearing_history` exercises the same date handling as live data.
"""

import hashlib
import logging
from datetime import date, timedelta

import httpx

from app.core import envelope
from app.core.config import get_settings
from app.schemas.core import CnrPreviewOut

logger = logging.getLogger(__name__)
settings = get_settings()

_COURTS = [
    ("Bombay High Court", "High Court", "Hon'ble Justice S. R. Deshpande"),
    ("Delhi High Court", "High Court", "Hon'ble Justice A. K. Malhotra"),
    ("City Civil Court, Bengaluru", "District Court", "Sri. R. Venkatesh"),
    ("Saket District Court, New Delhi", "District Court", "Ms. Prerna Singh"),
    ("Madras High Court", "High Court", "Hon'ble Justice K. Balasubramanian"),
]

_CASE_TYPES = [
    ("Criminal Appeal", "Chargesheet filed"),
    ("Civil Suit", "Written statement"),
    ("Writ Petition", "Admission"),
    ("Matrimonial Petition", "Evidence"),
    ("Company Petition", "Final arguments"),
]

_PARTY_POOL = [
    "Ramesh Kumar", "State of Maharashtra", "Sunita Devi", "M/s Arora Textiles Pvt. Ltd.",
    "Union of India", "Anil Deshmukh", "Kavita Nair", "Bharat Finance Ltd.",
]


async def lookup_cnr(cnr: str) -> CnrPreviewOut:
    if settings.fake_mode or not settings.ecourts_api_key:
        return _synthesise(cnr)

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                "https://api.ecourts.gov.in/v1/case",
                params={"cnr": cnr},
                headers={"Authorization": f"Bearer {settings.ecourts_api_key}"},
            )
            response.raise_for_status()
            return _from_provider(cnr, response.json())
    except httpx.HTTPError as exc:
        logger.warning("eCourts lookup failed for %s: %s", cnr, exc)
        # 503 UPSTREAM_UNAVAILABLE — the app shows a retry plus the "Add manually
        # instead" escape hatch (D.6), rather than a dead end.
        raise envelope.upstream_unavailable(
            "eCourts is not responding right now."
        ) from exc


def _from_provider(cnr: str, payload: dict) -> CnrPreviewOut:
    return CnrPreviewOut(
        cnr=cnr,
        title=payload.get("case_title") or cnr,
        case_number=payload.get("case_number"),
        court_name=payload.get("court_name"),
        court_type=payload.get("court_type"),
        judge_name=payload.get("judge_name"),
        case_type=payload.get("case_type"),
        stage=payload.get("stage"),
        parties=payload.get("parties") or [],
        next_hearing_date=payload.get("next_hearing_date"),
    )


def _synthesise(cnr: str) -> CnrPreviewOut:
    """Deterministic from the CNR, so the same code always yields the same case."""
    seed = int(hashlib.sha256(cnr.encode()).hexdigest()[:8], 16)
    court, court_type, judge = _COURTS[seed % len(_COURTS)]
    case_type, stage = _CASE_TYPES[(seed // 7) % len(_CASE_TYPES)]
    petitioner = _PARTY_POOL[(seed // 11) % len(_PARTY_POOL)]
    respondent = _PARTY_POOL[(seed // 13) % len(_PARTY_POOL)]
    if respondent == petitioner:
        respondent = _PARTY_POOL[(seed // 13 + 1) % len(_PARTY_POOL)]

    today = date.today()
    next_hearing = today + timedelta(days=(seed % 21) + 1)

    number_prefix = case_type.split()[0][:3].upper()
    return CnrPreviewOut(
        cnr=cnr,
        title=f"{petitioner} vs {respondent}",
        case_number=f"{number_prefix}/{1000 + (seed % 8999)}/{today.year - (seed % 3)}",
        court_name=court,
        court_type=court_type,
        judge_name=judge,
        case_type=case_type,
        stage=stage,
        parties=[petitioner, respondent],
        next_hearing_date=next_hearing,
    )


def synth_history(cnr: str) -> list[dict]:
    """Past hearings for a synthesised case, kept separate so the router can persist
    them as real Hearing rows when the case is created."""
    seed = int(hashlib.sha256(cnr.encode()).hexdigest()[:8], 16)
    today = date.today()
    return [
        {
            "date": today - timedelta(days=(i + 1) * 45 + (seed % 10)),
            "purpose": ["Framing of issues", "Evidence", "Arguments"][i % 3],
            "outcome_notes": "Adjourned at the request of the respondent.",
        }
        for i in range(3)
    ]
