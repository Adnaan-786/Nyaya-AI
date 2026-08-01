from functools import lru_cache

from app.config import get_settings
from app.integrations.ecourts.base import ECourtsProvider
from app.integrations.ecourts.commercial import CommercialProvider
from app.integrations.ecourts.fixture import FixtureProvider
from app.integrations.ecourts.napix import NapixProvider


@lru_cache
def get_ecourts_provider() -> ECourtsProvider:
    """
    Returns the configured provider. Swapping providers is purely a
    config change (settings.ecourts_provider), never a code change --
    this is the plan C.7 Definition of Done: "provider swap is
    config-only."
    """
    settings = get_settings()

    match settings.ecourts_provider:
        case "napix":
            return NapixProvider()
        case "commercial":
            return CommercialProvider()
        case "fixture" | _:
            return FixtureProvider()
