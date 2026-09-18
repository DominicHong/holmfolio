"""Settings API models."""

from datetime import datetime
from pydantic import BaseModel


class SettingsResponse(BaseModel):
    """Settings response model."""

    key: str
    value: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime
