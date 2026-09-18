"""Tag and TagCategory models."""

from datetime import datetime
from decimal import Decimal
from sqlmodel import SQLModel, Field, Relationship, select, func
from sqlalchemy import UniqueConstraint
from backend.db.utils import utcnow


class TagCategory(SQLModel, table=True):
    """Tag category for organizing tags (e.g., 行业, 地域, 资产类型)."""

    id: int = Field(unique=True, primary_key=True)
    name: str = Field(unique=True, index=True)  # e.g., "行业", "地域"
    description: str | None = None
    display_order: int = Field(default=0)  # For UI ordering
    created_at: datetime = Field(default_factory=utcnow)

    # Relationships
    tags: list["Tag"] = Relationship(back_populates="category")


class Tag(SQLModel, table=True):
    """Tag definition (e.g., 银行, 国内, 红利股)."""

    id: int = Field(unique=True, primary_key=True)
    name: str = Field(index=True)  # e.g., "银行", "国内"
    category_id: int | None = Field(foreign_key="tagcategory.id", default=None)
    description: str | None = None
    color: str | None = None  # For UI display, e.g., "#FF5733"
    created_at: datetime = Field(default_factory=utcnow)

    # Unique constraint: tag name within a category must be unique
    __table_args__ = (
        UniqueConstraint("name", "category_id", name="uq_tag_name_category"),
    )

    # Relationships
    category: TagCategory | None = Relationship(back_populates="tags")
    asset_tags: list["AssetTag"] = Relationship(
        back_populates="tag",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class AssetTag(SQLModel, table=True):
    """Many-to-many relationship between Asset and Tag with optional weight."""

    id: int = Field(unique=True, primary_key=True)
    asset_id: int = Field(foreign_key="asset.id", ondelete="CASCADE")
    tag_id: int = Field(foreign_key="tag.id", ondelete="CASCADE")
    weight: Decimal = Field(default=Decimal("100"))  # Percentage, default 100%
    notes: str | None = None  # Optional notes for this tag assignment

    # Unique constraint: one asset can only have one entry for each tag
    __table_args__ = (UniqueConstraint("asset_id", "tag_id", name="uq_asset_tag"),)

    # Relationships
    asset: "Asset" = Relationship(back_populates="asset_tags")
    tag: "Tag" = Relationship(back_populates="asset_tags")

    @classmethod
    def validate_category_weights(
        cls,
        session,
        asset_id: int,
        tag_id: int,
        weight: Decimal,
        strict: bool = True,
    ) -> Decimal:
        """Validate that weights for the same asset in the same tag category sum to 100%.

        Args:
            session: Database session
            asset_id: Asset ID
            tag_id: Tag ID
            weight: New weight to validate
            strict: If True, raises error when total != 100%. If False, returns the total.

        Returns:
            The total weight after including the new weight

        Raises:
            ValueError: If strict=True and total weight is not 100%
        """
        # Get the category_id of the current tag
        tag_category_query = select(Tag.category_id).where(Tag.id == tag_id)
        tag_category_result = session.exec(tag_category_query).first()

        if tag_category_result is None:
            # Tag has no category, no validation needed
            return weight

        category_id = tag_category_result

        # Get all existing AssetTags for this asset in the same category (excluding current tag if updating)
        existing_query = (
            select(AssetTag, Tag)
            .join(Tag, AssetTag.tag_id == Tag.id)
            .where(
                AssetTag.asset_id == asset_id,
                Tag.category_id == category_id,
                AssetTag.tag_id != tag_id,
            )
        )
        existing_results = session.exec(existing_query).all()

        # Calculate total weight including the new/updated weight
        total_weight = weight
        for asset_tag, _ in existing_results:
            total_weight += asset_tag.weight

        if strict and total_weight != Decimal("100"):
            raise ValueError(
                f"Total weight for asset {asset_id} in category {category_id} must be 100%, "
                f"got {total_weight}%"
            )

        return total_weight

    @classmethod
    def check_category_weights_complete(
        cls, session, asset_id: int, category_id: int
    ) -> bool:
        """Check if the total weight for an asset in a category equals 100%."""
        total_query = (
            select(func.sum(AssetTag.weight))
            .join(Tag, AssetTag.tag_id == Tag.id)
            .where(AssetTag.asset_id == asset_id, Tag.category_id == category_id)
        )
        total_result = session.exec(total_query).first()
        total_weight = total_result or Decimal("0")

        return total_weight == Decimal("100")

    def save_with_validation(self, session, strict: bool = True) -> None:
        """Save the AssetTag with weight validation."""
        self.validate_category_weights(
            session, self.asset_id, self.tag_id, self.weight, strict=strict
        )
        session.add(self)
        session.commit()
        session.refresh(self)
