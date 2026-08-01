"""
Official NAPIX/NIC eCourts provider.

Per plan C.1: "NAPIX application (start immediately -- approval can
take weeks; use the commercial API until it lands)." This class is a
real integration point, left unimplemented until `settings.napix_api_key`
is provisioned, so it fails loudly rather than silently returning fake
data in a non-fixture environment.
"""

import datetime

import httpx

from app.config import get_settings
from app.core.exceptions import UpstreamUnavailableException
from app.integrations.ecourts.base import ECourtsProvider, NormalizedCase

settings = get_settings()

NAPIX_BASE_URL = "https://napix.gov.in/ecourts/v1"  # placeholder; confirm on approval


class NapixProvider(ECourtsProvider):
    async def lookup_cnr(self, cnr: str) -> NormalizedCase:
        if not settings.napix_api_key:
            raise UpstreamUnavailableException(
                message="NAPIX eCourts API is not yet configured (pending approval).",
            )

        async with httpx.AsyncClient(timeout=settings.ecourts_lookup_timeout_seconds) as client:
            try:
                response = await client.get(
                    f"{NAPIX_BASE_URL}/cases/{cnr}",
                    headers={"Authorization": f"Bearer {settings.napix_api_key}"},
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise UpstreamUnavailableException(
                    message="NAPIX eCourts lookup failed.",
                ) from exc

        # Real NAPIX response normalization would go here once the
        # actual response schema is available post-approval.
        raise NotImplementedError(
            "NAPIX response normalization is pending API approval/documentation."
        )

    async def case_status(self, cnr: str) -> NormalizedCase:
        return await self.lookup_cnr(cnr)

    async def cause_list(self, court_id: str, date: datetime.date) -> list[NormalizedCase]:
        raise NotImplementedError("NAPIX cause-list endpoint pending API approval.")
