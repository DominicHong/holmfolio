"""Tests for tag correlation calculation using weighted price returns."""

import pytest
import numpy as np
from decimal import Decimal
from datetime import date, timedelta

from backend.db.models import (
    Position, Tag, TagCategory, AssetTag
)
from backend.services.portfolio import PortfolioService


# Helper to build a price series with given decimal returns (e.g. 10 = +10%).
def _build_price_series(
    initial: Decimal, returns: list[Decimal], num_days: int,
) -> list[Decimal]:
    prices = [initial]
    for i in range(1, num_days):
        r = returns[(i - 1) % len(returns)]
        prices.append(prices[-1] * (Decimal("100") + r) / Decimal("100"))
    return prices


class TestTagCorrelation:
    """Test tag-based portfolio correlation matrix."""

    @pytest.fixture
    def setup_tags(self, test_db):
        """Setup tag category and tags."""
        category = TagCategory(name="行业", description="Industry")
        test_db.add(category)
        test_db.flush()

        tags = [
            Tag(name="科技", category_id=category.id),
            Tag(name="银行", category_id=category.id),
            Tag(name="消费", category_id=category.id),
        ]
        for t in tags:
            test_db.add(t)
        test_db.commit()

        return {"category": category, "tags": {t.name: t for t in tags}}

    # -- helpers ---------------------------------------------------------------

    @staticmethod
    def _add_position(test_db, portfolio_id, asset_id, d, quantity, price):
        """Add a position with consistent market_value = quantity × price."""
        q = Decimal(str(quantity))
        p = Decimal(str(price))
        test_db.add(Position(
            portfolio_id=portfolio_id, asset_id=asset_id, position_date=d,
            quantity=q, average_cost=p,
            current_price=p, market_value=q * p, total_pnl=Decimal("0"),
        ))

    @staticmethod
    def _add_positions_from_series(
        test_db, portfolio_id, asset_id, base_date, prices, quantity=100,
    ):
        """Add one position per day following *prices* (length = num_days)."""
        for i, p in enumerate(prices):
            TestTagCorrelation._add_position(
                test_db, portfolio_id, asset_id,
                base_date + timedelta(days=i), quantity, p,
            )

    # -- tests -----------------------------------------------------------------

    def test_single_tag_insufficient(self, test_db, setup_tags):
        """Only one tag in category should return message."""
        portfolio = test_db._test_portfolio
        tag_data = setup_tags
        tech_tag = tag_data["tags"]["科技"]
        asset = test_db._test_assets["600036.SH"]

        at = AssetTag(asset_id=asset.id, tag_id=tech_tag.id, weight=Decimal("100"))
        test_db.add(at)
        test_db.commit()

        service = PortfolioService(test_db)
        result = service.calculate_tag_correlation(
            portfolio.id, date(2024, 1, 1), date(2024, 1, 30), tag_data["category"].id
        )

        assert result["tags"] == ["科技"]
        assert result["correlation_matrix"] == []
        assert "At least two tags" in result["message"]

    def test_perfect_positive_correlation(self, test_db, setup_tags, setup_assets):
        """Two tags with identical price-return series → correlation = 1.0."""
        portfolio = test_db._test_portfolio
        tag_data = setup_tags
        assets = setup_assets
        tech_tag = tag_data["tags"]["科技"]
        bank_tag = tag_data["tags"]["银行"]

        test_db.add(AssetTag(asset_id=assets["TECH1"].id, tag_id=tech_tag.id, weight=Decimal("100")))
        test_db.add(AssetTag(asset_id=assets["BANK1"].id, tag_id=bank_tag.id, weight=Decimal("100")))
        test_db.commit()

        # Return series in percent (10 = +10%)
        returns = [Decimal("10"), Decimal("-5"), Decimal("8"), Decimal("-3"), Decimal("12"), Decimal("-7")]
        base_date = date(2024, 1, 1)
        num_days = 30
        prices = _build_price_series(Decimal("100"), returns, num_days)

        self._add_positions_from_series(test_db, portfolio.id, assets["TECH1"].id, base_date, prices)
        self._add_positions_from_series(test_db, portfolio.id, assets["BANK1"].id, base_date, prices)
        test_db.commit()

        service = PortfolioService(test_db)
        result = service.calculate_tag_correlation(
            portfolio.id, base_date, base_date + timedelta(days=num_days - 1),
            tag_data["category"].id,
        )

        assert len(result["tags"]) == 2
        assert result["data_points"] >= 20
        matrix = np.array(result["correlation_matrix"])
        assert matrix[0, 1] == pytest.approx(1.0, abs=1e-9)
        assert matrix[1, 0] == pytest.approx(1.0, abs=1e-9)
        assert matrix[0, 0] == pytest.approx(1.0, abs=1e-9)
        assert matrix[1, 1] == pytest.approx(1.0, abs=1e-9)

    def test_perfect_negative_correlation(self, test_db, setup_tags, setup_assets):
        """Two tags with opposite price-return series → correlation = -1.0."""
        portfolio = test_db._test_portfolio
        tag_data = setup_tags
        assets = setup_assets
        tech_tag = tag_data["tags"]["科技"]
        bank_tag = tag_data["tags"]["银行"]

        test_db.add(AssetTag(asset_id=assets["TECH1"].id, tag_id=tech_tag.id, weight=Decimal("100")))
        test_db.add(AssetTag(asset_id=assets["BANK1"].id, tag_id=bank_tag.id, weight=Decimal("100")))
        test_db.commit()

        returns = [Decimal("10"), Decimal("-5"), Decimal("8"), Decimal("-3"), Decimal("12"), Decimal("-7")]
        base_date = date(2024, 1, 1)
        num_days = 30

        tech_prices = _build_price_series(Decimal("100"), returns, num_days)
        # Bank moves in exactly the opposite direction
        neg_returns = [Decimal(str(-int(r))) for r in returns]
        bank_prices = _build_price_series(Decimal("100"), neg_returns, num_days)

        self._add_positions_from_series(test_db, portfolio.id, assets["TECH1"].id, base_date, tech_prices)
        self._add_positions_from_series(test_db, portfolio.id, assets["BANK1"].id, base_date, bank_prices)
        test_db.commit()

        service = PortfolioService(test_db)
        result = service.calculate_tag_correlation(
            portfolio.id, base_date, base_date + timedelta(days=num_days - 1),
            tag_data["category"].id,
        )

        assert len(result["tags"]) == 2
        matrix = np.array(result["correlation_matrix"])
        assert matrix[0, 1] == pytest.approx(-1.0, abs=1e-6)
        assert matrix[1, 0] == pytest.approx(-1.0, abs=1e-6)

    def test_insufficient_data_points(self, test_db, setup_tags, setup_assets):
        """Tags with fewer than 20 valid data points should be marked insufficient."""
        portfolio = test_db._test_portfolio
        tag_data = setup_tags
        assets = setup_assets
        tech_tag = tag_data["tags"]["科技"]
        bank_tag = tag_data["tags"]["银行"]

        test_db.add(AssetTag(asset_id=assets["TECH1"].id, tag_id=tech_tag.id, weight=Decimal("100")))
        test_db.add(AssetTag(asset_id=assets["BANK1"].id, tag_id=bank_tag.id, weight=Decimal("100")))
        test_db.commit()

        base_date = date(2024, 1, 1)
        num_days = 10  # < 20
        prices = _build_price_series(Decimal("100"), [Decimal("2"), Decimal("-1")], num_days)
        self._add_positions_from_series(test_db, portfolio.id, assets["TECH1"].id, base_date, prices)
        self._add_positions_from_series(test_db, portfolio.id, assets["BANK1"].id, base_date, prices)
        test_db.commit()

        service = PortfolioService(test_db)
        result = service.calculate_tag_correlation(
            portfolio.id, base_date, base_date + timedelta(days=num_days - 1),
            tag_data["category"].id,
        )

        assert result["tags"] == []
        assert result["correlation_matrix"] == []
        assert set(result["insufficient_data_tags"]) == {"科技", "银行"}
        assert "20+ data points" in result["message"]

    def test_multi_currency_conversion(self, test_db, setup_tags, setup_assets, setup_exchange_rates):
        """HKD asset position converted to CNY for weight computation."""
        portfolio = test_db._test_portfolio
        tag_data = setup_tags
        assets = setup_assets
        tech_tag = tag_data["tags"]["科技"]
        bank_tag = tag_data["tags"]["银行"]

        # TECH1 is CNY, BANK2 is HKD
        test_db.add(AssetTag(asset_id=assets["TECH1"].id, tag_id=tech_tag.id, weight=Decimal("100")))
        test_db.add(AssetTag(asset_id=assets["BANK2"].id, tag_id=bank_tag.id, weight=Decimal("100")))
        test_db.commit()

        base_date = date(2024, 1, 1)
        num_days = 30
        returns = [Decimal("3"), Decimal("-2"), Decimal("5"), Decimal("-1")]
        prices = _build_price_series(Decimal("100"), returns, num_days)

        self._add_positions_from_series(test_db, portfolio.id, assets["TECH1"].id, base_date, prices)
        # BANK2 (HKD): same price series, but currency conversion applies to weights
        self._add_positions_from_series(test_db, portfolio.id, assets["BANK2"].id, base_date, prices)
        test_db.commit()

        service = PortfolioService(test_db)
        result = service.calculate_tag_correlation(
            portfolio.id, base_date, base_date + timedelta(days=num_days - 1),
            tag_data["category"].id,
        )

        # Both tags have identical price return series → correlation = 1.0
        assert len(result["tags"]) == 2
        matrix = np.array(result["correlation_matrix"])
        assert matrix[0, 1] == pytest.approx(1.0, abs=1e-9)

    def test_tag_weights_applied(self, test_db, setup_tags, setup_assets):
        """AssetTag weights affect tag returns through market-value weighting."""
        portfolio = test_db._test_portfolio
        tag_data = setup_tags
        assets = setup_assets
        tech_tag = tag_data["tags"]["科技"]
        bank_tag = tag_data["tags"]["银行"]

        # Two assets in tech, one in bank
        test_db.add(AssetTag(asset_id=assets["TECH1"].id, tag_id=tech_tag.id, weight=Decimal("70")))
        test_db.add(AssetTag(asset_id=assets["TECH2"].id, tag_id=tech_tag.id, weight=Decimal("30")))
        test_db.add(AssetTag(asset_id=assets["BANK1"].id, tag_id=bank_tag.id, weight=Decimal("100")))
        test_db.commit()

        base_date = date(2024, 1, 1)
        num_days = 30

        # TECH1 rises, TECH2 falls → tech tag return = 0.7*r1 + 0.3*r2
        r1 = [Decimal("5"), Decimal("-2")]
        r2 = [Decimal("-3"), Decimal("1")]
        tech1_prices = _build_price_series(Decimal("100"), r1, num_days)
        tech2_prices = _build_price_series(Decimal("100"), r2, num_days)
        bank_prices = _build_price_series(Decimal("100"), r1, num_days)  # same as TECH1

        self._add_positions_from_series(test_db, portfolio.id, assets["TECH1"].id, base_date, tech1_prices)
        self._add_positions_from_series(test_db, portfolio.id, assets["TECH2"].id, base_date, tech2_prices)
        self._add_positions_from_series(test_db, portfolio.id, assets["BANK1"].id, base_date, bank_prices)
        test_db.commit()

        service = PortfolioService(test_db)
        result = service.calculate_tag_correlation(
            portfolio.id, base_date, base_date + timedelta(days=num_days - 1),
            tag_data["category"].id,
        )

        assert len(result["tags"]) == 2
        assert result["data_points"] >= 20
        # Not perfectly correlated because tech has mixed returns
        matrix = np.array(result["correlation_matrix"])
        assert -1.0 <= matrix[0, 1] <= 1.0

    def test_overlapping_assets_between_tags(self, test_db, setup_tags, setup_assets):
        """An asset in multiple tags gives both tags the same price returns."""
        portfolio = test_db._test_portfolio
        tag_data = setup_tags
        assets = setup_assets
        tech_tag = tag_data["tags"]["科技"]
        bank_tag = tag_data["tags"]["银行"]

        # Same asset in both tags
        test_db.add(AssetTag(asset_id=assets["TECH1"].id, tag_id=tech_tag.id, weight=Decimal("100")))
        test_db.add(AssetTag(asset_id=assets["TECH1"].id, tag_id=bank_tag.id, weight=Decimal("100")))
        test_db.commit()

        base_date = date(2024, 1, 1)
        num_days = 30
        returns = [Decimal("4"), Decimal("-3"), Decimal("6"), Decimal("-2")]
        prices = _build_price_series(Decimal("100"), returns, num_days)
        self._add_positions_from_series(test_db, portfolio.id, assets["TECH1"].id, base_date, prices)
        test_db.commit()

        service = PortfolioService(test_db)
        result = service.calculate_tag_correlation(
            portfolio.id, base_date, base_date + timedelta(days=num_days - 1),
            tag_data["category"].id,
        )

        # Same return series → correlation = 1.0
        assert len(result["tags"]) == 2
        matrix = np.array(result["correlation_matrix"])
        assert matrix[0, 1] == pytest.approx(1.0, abs=1e-9)
        assert matrix[1, 0] == pytest.approx(1.0, abs=1e-9)

    def test_missing_positions_on_some_days(self, test_db, setup_tags, setup_assets):
        """Missing positions handled via calendar alignment (None → skip day)."""
        portfolio = test_db._test_portfolio
        tag_data = setup_tags
        assets = setup_assets
        tech_tag = tag_data["tags"]["科技"]
        bank_tag = tag_data["tags"]["银行"]

        test_db.add(AssetTag(asset_id=assets["TECH1"].id, tag_id=tech_tag.id, weight=Decimal("100")))
        test_db.add(AssetTag(asset_id=assets["BANK1"].id, tag_id=bank_tag.id, weight=Decimal("100")))
        test_db.commit()

        base_date = date(2024, 1, 1)
        num_days = 30
        returns = [Decimal("5"), Decimal("-3"), Decimal("7"), Decimal("-1")]
        prices = _build_price_series(Decimal("100"), returns, num_days)

        for i in range(num_days):
            d = base_date + timedelta(days=i)
            # Tech has data every day
            self._add_position(test_db, portfolio.id, assets["TECH1"].id, d, 100, prices[i])
            # Bank has data only on even indices (0, 2, 4, ...)
            if i % 2 == 0:
                self._add_position(test_db, portfolio.id, assets["BANK1"].id, d, 100, prices[i])
        test_db.commit()

        service = PortfolioService(test_db)
        result = service.calculate_tag_correlation(
            portfolio.id, base_date, base_date + timedelta(days=num_days - 1),
            tag_data["category"].id,
        )

        # Bank tag only has data on even days → returns only on those days
        # After alignment, fewer than 20 valid data points → insufficient
        assert "银行" in result["insufficient_data_tags"]

    def test_flat_price_days_excluded(self, test_db, setup_tags, setup_assets):
        """Days where no constituent price changed (stale non-trading days)
        must not enter the correlation as shared zero returns.

        Setup: 科技 moves every day; 银行 is flat for the first 10 days then
        replicates 科技's daily growth. Only days 10-29 carry co-movement
        information, so data_points must be 20 (not 29) and the correlation
        must still be 1.0.
        """
        portfolio = test_db._test_portfolio
        tag_data = setup_tags
        assets = setup_assets
        tech_tag = tag_data["tags"]["科技"]
        bank_tag = tag_data["tags"]["银行"]

        test_db.add(AssetTag(asset_id=assets["TECH1"].id, tag_id=tech_tag.id, weight=Decimal("100")))
        test_db.add(AssetTag(asset_id=assets["BANK1"].id, tag_id=bank_tag.id, weight=Decimal("100")))
        test_db.commit()

        base_date = date(2024, 1, 1)
        num_days = 30

        returns = [Decimal("5"), Decimal("-3"), Decimal("7"), Decimal("-2")]
        tech_prices = _build_price_series(Decimal("100"), returns, num_days)
        bank_prices = [Decimal("100")] * 10
        for i in range(10, num_days):
            bank_prices.append(bank_prices[-1] * tech_prices[i] / tech_prices[i - 1])

        self._add_positions_from_series(test_db, portfolio.id, assets["TECH1"].id, base_date, tech_prices)
        self._add_positions_from_series(test_db, portfolio.id, assets["BANK1"].id, base_date, bank_prices)
        test_db.commit()

        service = PortfolioService(test_db)
        result = service.calculate_tag_correlation(
            portfolio.id, base_date, base_date + timedelta(days=num_days - 1),
            tag_data["category"].id,
        )

        assert set(result["tags"]) == {"科技", "银行"}
        assert result["data_points"] == 20
        matrix = np.array(result["correlation_matrix"])
        assert matrix[0, 1] == pytest.approx(1.0, abs=1e-9)
        assert matrix[1, 0] == pytest.approx(1.0, abs=1e-9)

    def test_iterative_pruning_keeps_sufficient_pairs(self, test_db, setup_tags, setup_assets):
        """A tag with sufficient data must not be wrongly dropped because a
        third sparse tag shrinks the joint calendar below the threshold.

        Setup: 科技 and 银行 each have full 30-day series; 消费 has only 5 days.
        The old single-pass alignment would mark all three as insufficient
        (only 5 common days). The iterative pruner should drop 消费 and keep
        科技 + 银行, exposing their true correlation.
        """
        portfolio = test_db._test_portfolio
        tag_data = setup_tags
        assets = setup_assets
        tech_tag = tag_data["tags"]["科技"]
        bank_tag = tag_data["tags"]["银行"]
        cons_tag = tag_data["tags"]["消费"]

        test_db.add(AssetTag(asset_id=assets["TECH1"].id, tag_id=tech_tag.id, weight=Decimal("100")))
        test_db.add(AssetTag(asset_id=assets["BANK1"].id, tag_id=bank_tag.id, weight=Decimal("100")))
        test_db.add(AssetTag(asset_id=assets["CONS1"].id, tag_id=cons_tag.id, weight=Decimal("100")))
        test_db.commit()

        base_date = date(2024, 1, 1)
        num_days = 30
        returns = [Decimal("5"), Decimal("-3"), Decimal("7"), Decimal("-2")]
        prices = _build_price_series(Decimal("100"), returns, num_days)

        # Full series for tech and bank
        self._add_positions_from_series(test_db, portfolio.id, assets["TECH1"].id, base_date, prices)
        self._add_positions_from_series(test_db, portfolio.id, assets["BANK1"].id, base_date, prices)
        # Only 5 days for consumer (well below the 20-point threshold)
        for i in range(5):
            d = base_date + timedelta(days=i)
            self._add_position(test_db, portfolio.id, assets["CONS1"].id, d, 100, prices[i])
        test_db.commit()

        service = PortfolioService(test_db)
        result = service.calculate_tag_correlation(
            portfolio.id, base_date, base_date + timedelta(days=num_days - 1),
            tag_data["category"].id,
        )

        # 消费 is sparse → dropped; 科技 and 银行 survive together.
        assert set(result["tags"]) == {"科技", "银行"}
        assert result["insufficient_data_tags"] == ["消费"]
        assert result["data_points"] >= 20
        # Identical price series → correlation = 1.0
        matrix = np.array(result["correlation_matrix"])
        assert matrix[0, 1] == pytest.approx(1.0, abs=1e-9)

    def test_no_tags_in_category(self, test_db):
        """Empty category should return empty result."""
        portfolio = test_db._test_portfolio
        category = TagCategory(name="Empty", description="Empty category")
        test_db.add(category)
        test_db.commit()

        service = PortfolioService(test_db)
        result = service.calculate_tag_correlation(
            portfolio.id, date(2024, 1, 1), date(2024, 1, 30), category.id
        )

        assert result["tags"] == []
        assert result["correlation_matrix"] == []
        assert result["data_points"] == 0

    def test_position_size_changes_dont_affect_correlation(self, test_db, setup_tags, setup_assets):
        """Buying/selling (quantity changes) should not distort correlation.

        Two tags with identical price series but different quantity patterns
        should still show perfect correlation, because the weighted price return
        algorithm isolates price movements from position-size changes.
        """
        portfolio = test_db._test_portfolio
        tag_data = setup_tags
        assets = setup_assets
        tech_tag = tag_data["tags"]["科技"]
        bank_tag = tag_data["tags"]["银行"]

        test_db.add(AssetTag(asset_id=assets["TECH1"].id, tag_id=tech_tag.id, weight=Decimal("100")))
        test_db.add(AssetTag(asset_id=assets["BANK1"].id, tag_id=bank_tag.id, weight=Decimal("100")))
        test_db.commit()

        base_date = date(2024, 1, 1)
        num_days = 30
        returns = [Decimal("5"), Decimal("-3"), Decimal("7"), Decimal("-2")]
        prices = _build_price_series(Decimal("100"), returns, num_days)

        # Tech: constant quantity
        for i in range(num_days):
            d = base_date + timedelta(days=i)
            self._add_position(test_db, portfolio.id, assets["TECH1"].id, d, 100, prices[i])

        # Bank: quantity fluctuates (simulating buys/sells)
        bank_qty = 100
        for i in range(num_days):
            d = base_date + timedelta(days=i)
            if i == 10:
                bank_qty = 200  # doubled position
            elif i == 20:
                bank_qty = 50   # halved position
            self._add_position(test_db, portfolio.id, assets["BANK1"].id, d, bank_qty, prices[i])
        test_db.commit()

        service = PortfolioService(test_db)
        result = service.calculate_tag_correlation(
            portfolio.id, base_date, base_date + timedelta(days=num_days - 1),
            tag_data["category"].id,
        )

        # Identical price series → correlation = 1.0, unaffected by quantity changes
        assert len(result["tags"]) == 2
        matrix = np.array(result["correlation_matrix"])
        assert matrix[0, 1] == pytest.approx(1.0, abs=1e-9)
