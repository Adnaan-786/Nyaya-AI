from pydantic import BaseModel, ConfigDict


class AppConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    min_supported_version: str
    latest_version: str
    feature_flags: dict
    status_banner: str | None = None
    support_email: str | None = None
    support_phone: str | None = None


class AppConfigUpdateIn(BaseModel):
    min_supported_version: str | None = None
    latest_version: str | None = None
    feature_flags: dict | None = None
    status_banner: str | None = None
    support_email: str | None = None
    support_phone: str | None = None
