"""
Commercial eCourts data provider fallback (eCourtsIndia / Surepass),
used per plan C.1 while the official NAPIX application is pending
approval. Also left unimplemented until an API key is provisioned;
see NapixProvider for the same pattern.
"""

import datetime

import httpx

from app.config import get_settings
from app.core.exceptions import UpstreamUnavailableException
from app.integrations.ecourts.base import ECourtsProvider, NormalizedCase

settings = get_settings()

COMMERCIAL_BASE_URL = "https://api.surepass.io/ecourts/v1"  # placeholder; confirm with vendor


class CommercialProvider(ECourtsProvider):
    async def lookup_cnr(self, cnr: str) -> NormalizedCase:
        if not settings.commercial_ecourts_api_key:
            raise UpstreamUnavailableException(
                message="Commercial eCourts provider is not yet configured.",
            )

        async with httpx.AsyncClient(timeout=settings.ecourts_lookup_timeout_seconds) as client:
            try:
                response = await client.get(
                    f"{COMMERCIAL_BASE_URL}/cnr/{cnr}",
                    headers={"Authorization": f"Bearer {settings.commercial_ecourts_api_key}"},
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise UpstreamUnavailableException(
                    message="Commercial eCourts lookup failed.",
                ) from exc

        raise NotImplementedError(
            "Commercial provider response normalization is pending vendor contract/docs."
        )

    async def case_status(self, cnr: str) -> NormalizedCase:
        return await self.lookup_cnr(cnr)

    async def cause_list(self, court_id: str, date: datetime.date) -> list[NormalizedCase]:
        raise NotImplementedError("Commercial provider cause-list pending vendor docs.")
