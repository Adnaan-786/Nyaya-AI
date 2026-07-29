from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DeviceIn(BaseModel):
    fcm_token: str = Field(..., min_length=1)
    platform: str = Field(..., pattern="^(android|ios)$")
    app_version: str = Field(..., min_length=1, max_length=30)


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    fcm_token: str
    platform: str
    app_version: str
