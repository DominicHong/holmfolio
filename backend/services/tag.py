"""Tag service for asset tag management and statistics."""

from sqlmodel import select, func
from decimal import Decimal
from datetime import date
from typing import Sequence

from backend.db.models import Tag, TagCategory, AssetTag, Asset, Position
from backend import logger
from backend.services.base import BaseService


class TagService(BaseService):
    """Service for managing asset tags and computing tag-based statistics."""

    # =========================================================================
    # Tag Category Management
    # =========================================================================

    def create_category(self, name: str, description: str | None = None,
                        display_order: int = 0) -> TagCategory:
        """Create a new tag category.

        Args:
            name: Category name (e.g., "行业", "地域")
            description: Optional description
            display_order: Order for UI display

        Returns:
            Created TagCategory
        """
        category = TagCategory(
            name=name,
            description=description,
            display_order=display_order
        )
        self.session.add(category)
        self.session.commit()
        logger.info(f"Created tag category: {name}")
        return category

    def get_category_by_name(self, name: str) -> TagCategory | None:
        """Get category by name."""
        statement = select(TagCategory).where(TagCategory.name == name)
        return self.session.exec(statement).first()

    def get_all_categories(self) -> Sequence[TagCategory]:
        """Get all categories ordered by display_order."""
        statement = select(TagCategory).order_by(TagCategory.display_order)
        return self.session.exec(statement).all()

    # =========================================================================
    # Tag Management
    # =========================================================================

    def create_tag(self, name: str, category_name: str | None = None,
                   description: str | None = None, color: str | None = None) -> Tag:
        """Create a new tag.

        Args:
            name: Tag name (e.g., "银行", "大陆")
            category_name: Optional category name
            description: Optional description
            color: Optional color for UI (e.g., "#FF5733")

        Returns:
            Created Tag
        """
        category_id = None
        if category_name:
            category = self.get_category_by_name(category_name)
            if category:
                category_id = category.id

        tag = Tag(
            name=name,
            category_id=category_id,
            description=description,
            color=color
        )
        self.session.add(tag)
        self.session.commit()
        logger.info(f"Created tag: {name}")
        return tag

    def get_or_create_tag(self, name: str, category_name: str | None = None) -> Tag:
        """Get existing tag or create new one."""
        statement = select(Tag).where(Tag.name == name)
        if category_name:
            category = self.get_category_by_name(category_name)
            if category:
                statement = statement.where(Tag.category_id == category.id)

        tag = self.session.exec(statement).first()
        if tag:
            return tag
        return self.create_tag(name, category_name)

    def get_all_tags(self) -> Sequence[Tag]:
        """Get all tags."""
        statement = select(Tag)
        return self.session.exec(statement).all()

    def get_tags_by_category(self, category_name: str) -> Sequence[Tag]:
        """Get all tags in a specific category."""
        category = self.get_category_by_name(category_name)
        if not category:
            return []
        statement = select(Tag).where(Tag.category_id == category.id)
        return self.session.exec(statement).all()

    # =========================================================================
    # Asset Tag Assignment
    # =========================================================================

    def assign_tag_to_asset(self, asset_symbol: str, tag_name: str,
                            weight: Decimal = Decimal("100"),
                            notes: str | None = None,
                            category_name: str | None = None,
                            validate: bool = True) -> AssetTag:
        """Assign a tag to an asset with optional weight.

        Args:
            asset_symbol: Asset symbol (e.g., "600036.SH")
            tag_name: Tag name (e.g., "银行")
            weight: Weight percentage (default 100%)
            notes: Optional notes
            category_name: Optional category for tag lookup
            validate: If True, validates that total weight equals 100%

        Returns:
            Created or updated AssetTag

        Raises:
            ValueError: If validate=True and total weight for the asset in the same category is not 100%
        """
        statement = select(Asset).where(Asset.symbol == asset_symbol)
        asset = self.session.exec(statement).first()
        if not asset:
            raise ValueError(f"Asset not found: {asset_symbol}")

        tag = self.get_or_create_tag(tag_name, category_name)

        if validate:
            AssetTag.validate_category_weights(self.session, asset.id, tag.id, weight)

        statement = select(AssetTag).where(
            AssetTag.asset_id == asset.id,
            AssetTag.tag_id == tag.id
        )
        existing = self.session.exec(statement).first()

        if existing:
            existing.weight = weight
            existing.notes = notes
            self.session.commit()
            logger.info(f"Updated tag '{tag_name}' for asset '{asset_symbol}' with weight {weight}%")
            return existing

        asset_tag = AssetTag(
            asset_id=asset.id,
            tag_id=tag.id,
            weight=weight,
            notes=notes
        )
        self.session.add(asset_tag)
        self.session.commit()
        logger.info(f"Assigned tag '{tag_name}' to asset '{asset_symbol}' with weight {weight}%")
        return asset_tag

    def remove_tag_from_asset(self, asset_symbol: str, tag_name: str) -> bool:
        """Remove a tag from an asset."""
        statement = select(Asset).where(Asset.symbol == asset_symbol)
        asset = self.session.exec(statement).first()
        if not asset:
            return False

        statement = select(Tag).where(Tag.name == tag_name)
        tag = self.session.exec(statement).first()
        if not tag:
            return False

        statement = select(AssetTag).where(
            AssetTag.asset_id == asset.id,
            AssetTag.tag_id == tag.id
        )
        asset_tag = self.session.exec(statement).first()
        if asset_tag:
            self.session.delete(asset_tag)
            self.session.commit()
            logger.info(f"Removed tag '{tag_name}' from asset '{asset_symbol}'")
            return True
        return False

    def get_asset_tags(self, asset_symbol: str) -> Sequence[AssetTag]:
        """Get all tags assigned to an asset."""
        statement = select(Asset).where(Asset.symbol == asset_symbol)
        asset = self.session.exec(statement).first()
        if not asset:
            return []

        statement = select(AssetTag).where(AssetTag.asset_id == asset.id)
        return self.session.exec(statement).all()

    def get_assets_by_tag(self, tag_name: str) -> Sequence[Asset]:
        """Get all assets with a specific tag."""
        statement = select(Tag).where(Tag.name == tag_name)
        tag = self.session.exec(statement).first()
        if not tag:
            return []

        statement = select(Asset).join(AssetTag).where(AssetTag.tag_id == tag.id)
        return self.session.exec(statement).all()

    # =========================================================================
    # Tag Statistics
    # =========================================================================

    def get_portfolio_tag_statistics(self, portfolio_id: int,
                                      position_date: date,
                                      category_name: str | None = None) -> dict:
        """Get tag-based statistics for a portfolio on a specific date.

        Computes the weighted value of each tag based on asset positions
        and their tag weights.

        Args:
            portfolio_id: Portfolio ID
            position_date: Date for position snapshot
            category_name: Optional category to filter tags

        Returns:
            Dictionary with tag statistics
        """
        statement = select(Position).where(
            Position.portfolio_id == portfolio_id,
            Position.position_date == position_date
        )
        positions = self.session.exec(statement).all()

        if not positions:
            return {"total_value": Decimal("0"), "tags": []}

        total_value = sum(
            (pos.market_value or Decimal("0"))
            for pos in positions
        )

        if total_value == 0:
            return {"total_value": Decimal("0"), "tags": []}

        tag_values: dict[int, dict] = {}

        for position in positions:
            asset_value = position.market_value or Decimal("0")
            if asset_value == 0:
                continue

            statement = select(AssetTag).where(AssetTag.asset_id == position.asset_id)
            asset_tags = self.session.exec(statement).all()

            for asset_tag in asset_tags:
                tag = self.session.get(Tag, asset_tag.tag_id)
                if not tag:
                    continue

                if category_name:
                    category = self.session.get(TagCategory, tag.category_id) if tag.category_id else None
                    if not category or category.name != category_name:
                        continue

                weight = asset_tag.weight / Decimal("100")
                weighted_value = asset_value * weight

                if tag.id not in tag_values:
                    category = self.session.get(TagCategory, tag.category_id) if tag.category_id else None
                    tag_values[tag.id] = {
                        "tag_name": tag.name,
                        "category": category.name if category else "未分类",
                        "total_value": Decimal("0"),
                        "asset_count": 0,
                        "assets": set()
                    }

                tag_values[tag.id]["total_value"] += weighted_value
                tag_values[tag.id]["assets"].add(position.asset_id)

        result_tags = []
        for tag_data in tag_values.values():
            tag_data["asset_count"] = len(tag_data["assets"])
            del tag_data["assets"]
            tag_data["percentage"] = (tag_data["total_value"] / total_value * 100).quantize(Decimal("0.01"))
            result_tags.append(tag_data)

        result_tags.sort(key=lambda x: x["total_value"], reverse=True)

        return {
            "total_value": total_value,
            "tags": result_tags
        }

    def get_asset_allocation(self, portfolio_id: int,
                              position_date: date) -> dict:
        """Get asset allocation breakdown (e.g., Bond/Equity split).

        This is a convenience method that uses the "资产类型" category tags.
        """
        return self.get_portfolio_tag_statistics(
            portfolio_id, position_date, category_name="资产类型"
        )

    def get_tag_summary(self) -> dict:
        """Get summary of all tags and their usage."""
        statement = select(TagCategory)
        categories = self.session.exec(statement).all()

        result = {
            "total_tags": 0,
            "total_assignments": 0,
            "categories": []
        }

        for category in categories:
            statement = select(Tag).where(Tag.category_id == category.id)
            tags = self.session.exec(statement).all()

            tag_list = []
            for tag in tags:
                statement = select(func.count(AssetTag.id)).where(AssetTag.tag_id == tag.id)
                count = self.session.exec(statement).one()
                tag_list.append({
                    "name": tag.name,
                    "asset_count": count
                })
                result["total_assignments"] += count

            result["total_tags"] += len(tags)
            result["categories"].append({
                "name": category.name,
                "tag_count": len(tags),
                "tags": sorted(tag_list, key=lambda x: x["asset_count"], reverse=True)
            })

        statement = select(Tag).where(Tag.category_id.is_(None))
        uncategorized = self.session.exec(statement).all()
        if uncategorized:
            tag_list = []
            for tag in uncategorized:
                statement = select(func.count(AssetTag.id)).where(AssetTag.tag_id == tag.id)
                count = self.session.exec(statement).one()
                tag_list.append({
                    "name": tag.name,
                    "asset_count": count
                })
                result["total_assignments"] += count

            result["total_tags"] += len(uncategorized)
            result["categories"].append({
                "name": "未分类",
                "tag_count": len(uncategorized),
                "tags": sorted(tag_list, key=lambda x: x["asset_count"], reverse=True)
            })

        return result
