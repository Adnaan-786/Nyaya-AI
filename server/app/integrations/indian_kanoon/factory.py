"""Which case-law source answers a search.

Keyed off whether `INDIANKANOON_API_KEY` is actually set rather than a separate
provider switch, for the same reason `llm.py` falls back to `fake`: a provider with no
credential cannot work, and the useful behaviour is to degrade to the offline corpus
rather than fail every request. FAKE_MODE forces the fixture provider outright.
"""

from app.core.config import get_settings
from app.integrations.indian_kanoon.base import IndianKanoonProvider
from app.integrations.indian_kanoon.fixture import FixtureProvider
from app.integrations.indian_kanoon.real import RealIndianKanoonProvider

settings = get_settings()


def is_live() -> bool:
    """True when a real case-law index is behind the provider.

    The fixture corpus is synthetic, so this is the gate that decides whether a
    citation is allowed anywhere near a lawyer — see `app/api/ai.py`.
    """
    return not settings.fake_mode and bool(settings.indiankanoon_api_key)


def get_indian_kanoon_provider() -> IndianKanoonProvider:
    return RealIndianKanoonProvider() if is_live() else FixtureProvider()
