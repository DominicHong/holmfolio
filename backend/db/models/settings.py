"""Settings model."""

from datetime import datetime
from sqlmodel import SQLModel, Field
from backend.db.utils import utcnow


class Settings(SQLModel, table=True):
    """Settings model for storing application configuration."""

    id: int = Field(unique=True, primary_key=True)
    key: str = Field(unique=True, index=True)  # Setting key name
    value: str  # Setting value as string (can store JSON, numbers, etc.)
    description: str | None = None  # Optional description
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
