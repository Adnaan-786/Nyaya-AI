from app.config import get_settings
from app.integrations.indian_kanoon.base import IndianKanoonProvider
from app.integrations.indian_kanoon.fixture import FixtureProvider
from app.integrations.indian_kanoon.real import RealIndianKanoonProvider

settings = get_settings()


def get_indian_kanoon_provider() -> IndianKanoonProvider:
    if settings.fake_mode or settings.indian_kanoon_provider == "fixture":
        return FixtureProvider()

    if settings.indian_kanoon_provider == "indiankanoon":
        return RealIndianKanoonProvider()

    raise ValueError(f"Unknown Indian Kanoon provider: {settings.indian_kanoon_provider!r}")
