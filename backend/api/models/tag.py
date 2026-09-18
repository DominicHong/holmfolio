"""Tag API models."""

from pydantic import BaseModel, Field
from backend.db.models import Tag, Asset


class AssetTagCreate(BaseModel):
    """Asset tag creation request model."""

    asset_id: int
    tag_id: int
    weight: float = 100.0
    notes: str | None = None


class AssetTagResponse(BaseModel):
    """Asset tag response model."""

    id: int
    asset_id: int
    tag_id: int
    weight: float
    notes: str | None = None
    tag: Tag | None = None
    asset: Asset | None = None
