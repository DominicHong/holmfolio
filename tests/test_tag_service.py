"""Tests for tag service."""

import pytest
from decimal import Decimal
from datetime import date
from sqlmodel import Session, select

from backend.db.models import (
    Asset, Portfolio, Position, Tag, TagCategory, AssetTag
)
from backend.services import TagService


def setup_default_tags(session: Session | None = None):
    """Setup default tag categories and common tags.

    Args:
        session: Optional session to use. If not provided, creates a new session.
    """
    service = TagService(session) if session else None

    try:
        if service is None:
            service = TagService()

        # Create categories
        categories = [
            ("行业", "Industry classification"),
            ("地域", "Geographic region"),
            ("资产类型", "Asset type allocation (Bond, Equity, etc.)"),
            ("风格", "Investment style (价值, 成长, 红利等)"),
        ]

        for name, desc in categories:
            existing = service.get_category_by_name(name)
            if not existing:
                service.create_category(name, desc)

        # Create common tags
        common_tags = [
            # 行业
            ("银行", "行业"),
            ("科技", "行业"),
            ("消费", "行业"),
            ("医药", "行业"),
            ("能源", "行业"),
            # 地域
            ("国内", "地域"),
            ("国外", "地域"),
            ("香港", "地域"),
            ("美国", "地域"),
            # 资产类型
            ("Bond", "资产类型"),
            ("Equity", "资产类型"),
            ("Cash", "资产类型"),
            # 风格
            ("红利股", "风格"),
            ("成长股", "风格"),
            ("价值股", "风格"),
        ]

        for tag_name, category_name in common_tags:
            service.get_or_create_tag(tag_name, category_name)

    finally:
        if session is None and service is not None:
            service.session.close()


class TestTagCategory:
    """Test tag category management."""

    def test_create_category(self, test_db):
        """Test creating a tag category."""
        service = TagService(test_db)

        category = service.create_category("行业", "Industry classification", 1)

        assert category.name == "行业"
        assert category.description == "Industry classification"
        assert category.display_order == 1

    def test_get_category_by_name(self, test_db):
        """Test retrieving category by name."""
        service = TagService(test_db)
        service.create_category("地域")

        found = service.get_category_by_name("地域")
        assert found is not None
        assert found.name == "地域"

        not_found = service.get_category_by_name("不存在")
        assert not_found is None

    def test_get_all_categories(self, test_db):
        """Test getting all categories ordered by display_order."""
        service = TagService(test_db)
        service.create_category("行业", display_order=2)
        service.create_category("地域", display_order=1)
        service.create_category("风格", display_order=3)

        categories = service.get_all_categories()
        assert len(categories) == 3
        assert [c.name for c in categories] == ["地域", "行业", "风格"]


class TestTag:
    """Test tag management."""

    def test_create_tag_without_category(self, test_db):
        """Test creating a tag without category."""
        service = TagService(test_db)

        tag = service.create_tag("红利股", description="高股息股票")

        assert tag.name == "红利股"
        assert tag.description == "高股息股票"
        assert tag.category_id is None

    def test_create_tag_with_category(self, test_db):
        """Test creating a tag with category."""
        service = TagService(test_db)
        category = service.create_category("风格")

        tag = service.create_tag("成长股", category_name="风格")

        assert tag.name == "成长股"
        assert tag.category_id == category.id

    def test_get_or_create_tag(self, test_db):
        """Test get existing or create new tag."""
        service = TagService(test_db)
        service.create_category("行业")

        # Create new
        tag1 = service.get_or_create_tag("银行", "行业")
        assert tag1.name == "银行"

        # Get existing
        tag2 = service.get_or_create_tag("银行", "行业")
        assert tag2.id == tag1.id

    def test_get_tags_by_category(self, test_db):
        """Test getting tags by category."""
        service = TagService(test_db)
        service.create_category("行业")
        service.create_category("地域")

        service.create_tag("银行", "行业")
        service.create_tag("科技", "行业")
        service.create_tag("国内", "地域")

        industry_tags = service.get_tags_by_category("行业")
        assert len(industry_tags) == 2
        assert {t.name for t in industry_tags} == {"银行", "科技"}


class TestAssetTagAssignment:
    """Test assigning tags to assets."""

    def test_assign_tag_to_asset(self, test_db):
        """Test assigning a tag to an asset."""
        service = TagService(test_db)
        service.create_category("行业")

        asset_tag = service.assign_tag_to_asset("600036.SH", "银行", category_name="行业")

        assert asset_tag.weight == Decimal("100")
        assert asset_tag.asset.symbol == "600036.SH"
        assert asset_tag.tag.name == "银行"

    def test_assign_tag_with_weight(self, test_db):
        """Test assigning a tag with custom weight - must sum to 100%."""
        service = TagService(test_db)
        service.create_category("资产类型")

        # ETF with 10% Bond + 90% Equity
        # First assign without validation, then validate at the end
        service.assign_tag_to_asset("510300.SH", "Bond", Decimal("10"), category_name="资产类型", validate=False)
        service.assign_tag_to_asset("510300.SH", "Equity", Decimal("90"), category_name="资产类型", validate=True)

        asset_tags = service.get_asset_tags("510300.SH")
        assert len(asset_tags) == 2

        weights = {at.tag.name: at.weight for at in asset_tags}
        assert weights["Bond"] == Decimal("10")
        assert weights["Equity"] == Decimal("90")

    def test_assign_tag_weight_validation_fails(self, test_db):
        """Test that weight validation fails when total is not 100%."""
        service = TagService(test_db)
        service.create_category("资产类型")

        # First tag with 10% (no validation)
        service.assign_tag_to_asset("510300.SH", "Bond", Decimal("10"), category_name="资产类型", validate=False)

        # Second tag with 80% - total would be 90%, should fail when validating
        with pytest.raises(ValueError, match="Total weight for asset .* must be 100%"):
            service.assign_tag_to_asset("510300.SH", "Equity", Decimal("80"), category_name="资产类型", validate=True)

    def test_update_existing_tag_weight(self, test_db):
        """Test updating weight of existing tag assignment."""
        service = TagService(test_db)
        service.create_category("风格")

        # First assign with 100%
        service.assign_tag_to_asset("600036.SH", "红利股", Decimal("100"), category_name="风格")
        # Then update to 80% without validation (partial update scenario)
        service.assign_tag_to_asset("600036.SH", "红利股", Decimal("80"), category_name="风格", validate=False)

        asset_tags = service.get_asset_tags("600036.SH")
        assert len(asset_tags) == 1
        assert asset_tags[0].weight == Decimal("80")

    def test_remove_tag_from_asset(self, test_db):
        """Test removing a tag from an asset."""
        service = TagService(test_db)
        service.create_category("行业")
        service.assign_tag_to_asset("600036.SH", "银行", category_name="行业")

        result = service.remove_tag_from_asset("600036.SH", "银行")
        assert result is True

        asset_tags = service.get_asset_tags("600036.SH")
        assert len(asset_tags) == 0

    def test_get_assets_by_tag(self, test_db):
        """Test getting all assets with a specific tag."""
        service = TagService(test_db)
        service.create_category("地域")

        service.assign_tag_to_asset("600036.SH", "国内", category_name="地域")
        service.assign_tag_to_asset("510300.SH", "国内", category_name="地域")

        assets = service.get_assets_by_tag("国内")
        assert len(assets) == 2
        assert {a.symbol for a in assets} == {"600036.SH", "510300.SH"}


class TestTagStatistics:
    """Test tag-based statistics."""

    @pytest.fixture
    def setup_portfolio(self, test_db):
        """Setup portfolio with positions for testing."""
        # Get existing assets from test_db
        cny = test_db._test_cny
        hkd = test_db._test_hkd

        # Create additional assets
        assets = [
            Asset(symbol="510900.SH", name="恒生ETF", type="etf", currency_id=cny.id),
        ]
        for asset in assets:
            test_db.add(asset)
        test_db.flush()

        # Get portfolio
        portfolio = test_db._test_portfolio

        # Get asset IDs
        asset_600036 = test_db._test_assets["600036.SH"]
        asset_00700 = test_db._test_assets["00700.HK"]

        # Create positions
        positions = [
            Position(
                portfolio_id=portfolio.id,
                asset_id=asset_600036.id,
                position_date=date(2024, 12, 31),
                quantity=Decimal("1000"),
                average_cost=Decimal("35"),
                market_value=Decimal("35000")
            ),
            Position(
                portfolio_id=portfolio.id,
                asset_id=assets[0].id,  # 510900.SH
                position_date=date(2024, 12, 31),
                quantity=Decimal("5000"),
                average_cost=Decimal("10"),
                market_value=Decimal("50000")
            ),
            Position(
                portfolio_id=portfolio.id,
                asset_id=asset_00700.id,
                position_date=date(2024, 12, 31),
                quantity=Decimal("100"),
                average_cost=Decimal("400"),
                market_value=Decimal("40000")
            ),
        ]
        for pos in positions:
            test_db.add(pos)
        test_db.commit()

        return portfolio

    def test_portfolio_tag_statistics(self, test_db, setup_portfolio):
        """Test getting portfolio tag statistics."""
        service = TagService(test_db)
        portfolio = setup_portfolio

        # Setup categories and tags
        service.create_category("行业")
        service.create_category("地域")
        service.create_category("资产类型")

        # 600036.SH: 银行, 国内, Equity
        service.assign_tag_to_asset("600036.SH", "银行", category_name="行业")
        service.assign_tag_to_asset("600036.SH", "国内", category_name="地域")
        service.assign_tag_to_asset("600036.SH", "Equity", Decimal("100"), category_name="资产类型")

        # 510900.SH: ETF, 国外, 10% Bond + 90% Equity
        service.assign_tag_to_asset("510900.SH", "ETF")
        service.assign_tag_to_asset("510900.SH", "国外", category_name="地域")
        # Assign Bond without validation first, then Equity with validation (total = 100%)
        service.assign_tag_to_asset("510900.SH", "Bond", Decimal("10"), category_name="资产类型", validate=False)
        service.assign_tag_to_asset("510900.SH", "Equity", Decimal("90"), category_name="资产类型", validate=True)

        # 00700.HK: 科技, 香港, Equity
        service.assign_tag_to_asset("00700.HK", "科技", category_name="行业")
        service.assign_tag_to_asset("00700.HK", "香港", category_name="地域")
        service.assign_tag_to_asset("00700.HK", "Equity", Decimal("100"), category_name="资产类型")

        # Get statistics
        stats = service.get_portfolio_tag_statistics(portfolio.id, date(2024, 12, 31))

        # Total value: 35000 + 50000 + 40000 = 125000
        assert stats["total_value"] == Decimal("125000")
        assert len(stats["tags"]) > 0

        # Check 地域 breakdown
        region_stats = service.get_portfolio_tag_statistics(portfolio.id, date(2024, 12, 31), "地域")
        region_values = {t["tag_name"]: t["total_value"] for t in region_stats["tags"]}

        # 国内: 35000 (600036.SH)
        assert region_values["国内"] == Decimal("35000")
        # 国外: 50000 (510900.SH)
        assert region_values["国外"] == Decimal("50000")
        # 香港: 40000 (00700.HK)
        assert region_values["香港"] == Decimal("40000")

    def test_asset_allocation(self, test_db, setup_portfolio):
        """Test asset allocation breakdown."""
        service = TagService(test_db)
        portfolio = setup_portfolio

        service.create_category("资产类型")

        # Setup asset type tags
        service.assign_tag_to_asset("600036.SH", "Equity", Decimal("100"), category_name="资产类型")
        # For 510900.SH: assign Bond without validation, then Equity with validation
        service.assign_tag_to_asset("510900.SH", "Bond", Decimal("10"), category_name="资产类型", validate=False)
        service.assign_tag_to_asset("510900.SH", "Equity", Decimal("90"), category_name="资产类型", validate=True)
        service.assign_tag_to_asset("00700.HK", "Equity", Decimal("100"), category_name="资产类型")

        allocation = service.get_asset_allocation(portfolio.id, date(2024, 12, 31))

        # Bond: 50000 * 10% = 5000
        # Equity: 35000 + 50000 * 90% + 40000 = 35000 + 45000 + 40000 = 120000
        bond_value = next(t["total_value"] for t in allocation["tags"] if t["tag_name"] == "Bond")
        equity_value = next(t["total_value"] for t in allocation["tags"] if t["tag_name"] == "Equity")

        assert bond_value == Decimal("5000")
        assert equity_value == Decimal("120000")


class TestSetupDefaultTags:
    """Test default tags setup."""

    def test_setup_default_tags(self, test_db):
        """Test setting up default tags."""
        setup_default_tags(test_db)

        service = TagService(test_db)

        # Check categories
        categories = service.get_all_categories()
        category_names = {c.name for c in categories}
        assert "行业" in category_names
        assert "地域" in category_names
        assert "资产类型" in category_names
        assert "风格" in category_names

        # Check some common tags
        all_tags = service.get_all_tags()
        tag_names = {t.name for t in all_tags}
        assert "银行" in tag_names
        assert "国内" in tag_names
        assert "Bond" in tag_names
        assert "红利股" in tag_names
