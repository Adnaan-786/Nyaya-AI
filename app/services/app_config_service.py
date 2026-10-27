from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.app_config import SINGLETON_ID, AppConfig


async def get_or_create(session: AsyncSession) -> AppConfig:
    settings = get_settings()
    row = (await session.execute(select(AppConfig).where(AppConfig.id == SINGLETON_ID))).scalar_one_or_none()
    if row is None:
        row = AppConfig(
            id=SINGLETON_ID,
            min_supported_version=settings.app_min_supported_version,
            latest_version=settings.app_latest_version,
            feature_flags={},
            support_email=settings.app_support_email or None,
            support_phone=settings.app_support_phone or None,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return row


async def update(session: AsyncSession, row: AppConfig, **fields) -> AppConfig:
    for key, value in fields.items():
        if value is not None:
            setattr(row, key, value)
    await session.commit()
    await session.refresh(row)
    return row
