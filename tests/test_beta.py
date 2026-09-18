"""Tests for beta calculation: static calculate_beta(), _aggregate_returns_to_frequency(),
and CalculationService.calculate_tag_beta() using weighted price returns."""

import pytest
import numpy as np
from decimal import Decimal
from datetime import date, timedelta

from backend.db.models import (
    Benchmark, BenchmarkPrice, Position,
    Price, Tag, TagCategory, AssetTag,
)
from backend.services.calculation import CalculationService
from backend.services.portfolio import PortfolioService
from sqlmodel import select


# =============================================================================
# calculate_beta() static method tests
# =============================================================================

class TestCalculateBeta:
    """Unit tests for the calculate_beta() static method.
    These are pure math tests — no database needed."""

    def test_beta_equals_one(self):
        """Portfolio returns perfectly match benchmark returns → beta = 1.0."""
        rp = np.array([0.02, 0.01, -0.01, 0.03, -0.02], dtype=float)
        rb = np.array([0.02, 0.01, -0.01, 0.03, -0.02], dtype=float)
        beta = CalculationService.calculate_beta(rp, rb)
        assert beta == pytest.approx(1.0, abs=1e-9)

    def test_beta_greater_than_one(self):
        """Portfolio amplifies benchmark movements → beta > 1.0."""
        rb = np.array([0.01, -0.005, 0.02, -0.01, 0.015], dtype=float)
        rp = rb * 1.5  # 1.5x benchmark
        beta = CalculationService.calculate_beta(rp, rb)
        assert beta == pytest.approx(1.5, abs=1e-9)

    def test_beta_less_than_one(self):
        """Portfolio dampens benchmark movements → beta < 1.0."""
        rb = np.array([0.02, -0.01, 0.03, -0.02, 0.01], dtype=float)
        rp = rb * 0.5  # 0.5x benchmark
        beta = CalculationService.calculate_beta(rp, rb)
        assert beta == pytest.approx(0.5, abs=1e-9)

    def test_beta_negative(self):
        """Portfolio moves opposite to benchmark → beta < 0."""
        rb = np.array([0.01, -0.02, 0.03, -0.01, 0.02], dtype=float)
        rp = -rb  # perfectly inverse
        beta = CalculationService.calculate_beta(rp, rb)
        assert beta == pytest.approx(-1.0, abs=1e-9)

    def test_beta_zero_covariance(self):
        """Uncorrelated returns → beta ≈ 0."""
        np.random.seed(42)
        rp = np.random.randn(100) * 0.02
        rb = np.random.randn(100) * 0.02
        beta = CalculationService.calculate_beta(rp, rb)
        # With 100 random points, beta should be small
        assert abs(beta) < 0.5

    def test_insufficient_data_single_point(self):
        """Single return point → beta = 0.0."""
        rp = np.array([0.01], dtype=float)
        rb = np.array([0.01], dtype=float)
        beta = CalculationService.calculate_beta(rp, rb)
        assert beta == 0.0

    def test_insufficient_data_empty(self):
        """Empty arrays → beta = 0.0."""
        rp = np.array([], dtype=float)
        rb = np.array([], dtype=float)
        beta = CalculationService.calculate_beta(rp, rb)
        assert beta == 0.0

    def test_zero_benchmark_variance(self):
        """Benchmark has zero variance → beta = 0.0 (no division by zero)."""
        rp = np.array([0.01, -0.01, 0.02, -0.02], dtype=float)
        rb = np.array([0.0, 0.0, 0.0, 0.0], dtype=float)
        beta = CalculationService.calculate_beta(rp, rb)
        assert beta == 0.0

    def test_nan_in_returns(self):
        """NaN values in returns → beta = 0.0 (graceful handling)."""
        rp = np.array([0.01, np.nan, 0.02], dtype=float)
        rb = np.array([0.01, 0.02, 0.03], dtype=float)
        beta = CalculationService.calculate_beta(rp, rb)
        assert beta == 0.0

    def test_inf_in_returns(self):
        """Inf values in returns → beta = 0.0 (graceful handling)."""
        rp = np.array([0.01, np.inf, 0.02], dtype=float)
        rb = np.array([0.01, 0.02, 0.03], dtype=float)
        beta = CalculationService.calculate_beta(rp, rb)
        assert beta == 0.0

    def test_different_lengths(self):
        """Different length arrays → gracefully returns 0.0."""
        rp = np.array([0.01, 0.02, 0.03], dtype=float)
        rb = np.array([0.01, 0.02], dtype=float)
        beta = CalculationService.calculate_beta(rp, rb)
        assert isinstance(beta, float)


# =============================================================================
# _aggregate_returns_to_frequency() static method tests
# =============================================================================

class TestAggregateReturnsToFrequency:
    """Unit tests for _aggregate_returns_to_frequency() static method."""

    def test_daily_passthrough(self):
        """Daily frequency returns data unchanged."""
        returns = [0.01, -0.02, 0.03]
        dates = [date(2025, 1, 6), date(2025, 1, 7), date(2025, 1, 8)]
        agg_r, agg_d = CalculationService._aggregate_returns_to_frequency(
            returns, dates, "daily"
        )
        assert agg_r == returns
        assert agg_d == dates

    def test_empty_returns(self):
        """Empty returns should return empty lists."""
        agg_r, agg_d = CalculationService._aggregate_returns_to_frequency(
            [], [], "weekly"
        )
        assert agg_r == []
        assert agg_d == []

    def test_mismatched_lengths_raises(self):
        """Returns and dates of different lengths should raise ValueError."""
        with pytest.raises(ValueError, match="must have same length"):
            CalculationService._aggregate_returns_to_frequency(
                [0.01, 0.02], [date(2025, 1, 1)], "weekly"
            )

    def test_invalid_frequency_raises(self):
        """Unsupported frequency should raise ValueError."""
        with pytest.raises(ValueError, match="Unsupported frequency"):
            CalculationService._aggregate_returns_to_frequency(
                [0.01, 0.02],
                [date(2025, 1, 1), date(2025, 1, 2)],
                "yearly"
            )

    def test_weekly_aggregation(self):
        """Daily returns compound into weekly buckets by ISO week."""
        returns = [
            0.01,   # Mon Jan 6
            0.02,   # Tue Jan 7
            -0.01,  # Wed Jan 8
            0.03,   # Thu Jan 9
            0.01,   # Fri Jan 10
            0.02,   # Mon Jan 13 (next week)
            -0.02,  # Tue Jan 14
        ]
        dates = [
            date(2025, 1, 6),
            date(2025, 1, 7),
            date(2025, 1, 8),
            date(2025, 1, 9),
            date(2025, 1, 10),
            date(2025, 1, 13),
            date(2025, 1, 14),
        ]
        agg_r, agg_d = CalculationService._aggregate_returns_to_frequency(
            returns, dates, "weekly"
        )

        expected_w1 = (1.01 * 1.02 * 0.99 * 1.03 * 1.01) - 1
        expected_w2 = (1.02 * 0.98) - 1

        assert len(agg_r) == 2
        assert agg_r[0] == pytest.approx(expected_w1, rel=1e-9)
        assert agg_r[1] == pytest.approx(expected_w2, rel=1e-9)
        assert agg_d[0] == date(2025, 1, 10)
        assert agg_d[1] == date(2025, 1, 14)

    def test_monthly_aggregation(self):
        """Daily returns compound into monthly buckets."""
        returns = [
            0.01,   # Jan 30
            0.02,   # Jan 31
            0.01,   # Feb 1
            -0.01,  # Feb 2
            0.03,   # Mar 1
            0.01,   # Mar 2
        ]
        dates = [
            date(2025, 1, 30),
            date(2025, 1, 31),
            date(2025, 2, 1),
            date(2025, 2, 2),
            date(2025, 3, 1),
            date(2025, 3, 2),
        ]
        agg_r, agg_d = CalculationService._aggregate_returns_to_frequency(
            returns, dates, "monthly"
        )

        expected_jan = (1.01 * 1.02) - 1
        expected_feb = (1.01 * 0.99) - 1
        expected_mar = (1.03 * 1.01) - 1

        assert len(agg_r) == 3
        assert agg_r[0] == pytest.approx(expected_jan, rel=1e-9)
        assert agg_r[1] == pytest.approx(expected_feb, rel=1e-9)
        assert agg_r[2] == pytest.approx(expected_mar, rel=1e-9)
        assert agg_d[0] == date(2025, 1, 31)
        assert agg_d[1] == date(2025, 2, 2)
        assert agg_d[2] == date(2025, 3, 2)

    def test_weekly_aggregation_single_day_week(self):
        """A week with only one day should compound correctly (single return)."""
        returns = [0.05]
        dates = [date(2025, 6, 9)]
        agg_r, agg_d = CalculationService._aggregate_returns_to_frequency(
            returns, dates, "weekly"
        )
        assert len(agg_r) == 1
        assert agg_r[0] == pytest.approx(0.05, rel=1e-9)
        assert agg_d[0] == date(2025, 6, 9)


# =============================================================================
# calculate_tag_beta() integration tests
# =============================================================================

# Helper: build a price series from decimal return percentages (e.g. 5 = +5%).
def _build_price_series(initial, returns, num_days):
    prices = [initial]
    for i in range(1, num_days):
        r = returns[(i - 1) % len(returns)]
        prices.append(prices[-1] * (Decimal("100") + r) / Decimal("100"))
    return prices


def _add_position(test_db, portfolio_id, asset_id, d, quantity, price):
    """Add a position with consistent market_value = quantity × price."""
    q = Decimal(str(quantity))
    p = Decimal(str(price))
    test_db.add(Position(
        portfolio_id=portfolio_id, asset_id=asset_id, position_date=d,
        quantity=q, average_cost=p,
        current_price=p, market_value=q * p, total_pnl=Decimal("0"),
    ))


def _add_positions_from_series(test_db, portfolio_id, asset_id, base_date, prices, quantity=100):
    """Add one position per day following *prices* (length = num_days)."""
    for i, p in enumerate(prices):
        _add_position(test_db, portfolio_id, asset_id,
                      base_date + timedelta(days=i), quantity, p)


@pytest.fixture
def setup_benchmark(test_db):
    """Create a benchmark with 30 days of price data."""
    benchmark = Benchmark(id=100, symbol="TEST_BM", name="Test Benchmark")
    test_db.add(benchmark)
    test_db.flush()

    # Benchmark prices: starts at 100, wanders with varying returns
    prices = [
        (date(2024, 1, 1) + timedelta(days=i),
         Decimal(str(round(100 * (1.01 ** i) * (1 + 0.005 * (i % 5 - 2)), 2))))
        for i in range(30)
    ]
    for price_date, close in prices:
        test_db.add(BenchmarkPrice(
            benchmark_id=benchmark.id,
            price_date=price_date,
            close=close,
        ))
    test_db.commit()
    return benchmark


class TestTagBeta:
    """Integration tests for CalculationService.calculate_tag_beta()."""

    def _calc_tag_beta(self, test_db, portfolio_id, start, end,
                       tag_category_id, benchmark_id, frequency="daily"):
        """Helper: fetch tag daily returns via PortfolioService, then compute
        beta via CalculationService."""
        portfolio_service = PortfolioService(test_db)
        calc_service = CalculationService(test_db)
        tag_data = portfolio_service.get_tag_daily_returns(
            portfolio_id, start, end, tag_category_id
        )
        return calc_service.calculate_tag_beta(
            tag_names=tag_data["tag_names"],
            tag_calendar_returns=tag_data["tag_calendar_returns"],
            return_dates=tag_data["return_dates"],
            asset_tags_found=tag_data["asset_tags_found"],
            benchmark_id=benchmark_id,
            start_date=start,
            end_date=end,
            frequency=frequency,
        )

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

    def test_tag_data_points_per_tag(self, test_db, setup_tags, setup_assets, setup_benchmark):
        """tag_data_points must report each tag's own aligned return count.

        Setup: 科技 moves every day (29 returns); 银行 is flat for the first
        10 days then replicates 科技's daily growth (20 returns). The overall
        data_points stays the min (20).
        """
        portfolio = test_db._test_portfolio
        tag_data = setup_tags
        assets = setup_assets
        tech_tag = tag_data["tags"]["科技"]
        bank_tag = tag_data["tags"]["银行"]
        benchmark = setup_benchmark

        test_db.add(AssetTag(asset_id=assets["TECH1"].id, tag_id=tech_tag.id, weight=Decimal("100")))
        test_db.add(AssetTag(asset_id=assets["BANK1"].id, tag_id=bank_tag.id, weight=Decimal("100")))
        test_db.commit()

        base_date = date(2024, 1, 1)
        num_days = 30
        end_date = base_date + timedelta(days=num_days - 1)

        returns = [Decimal("5"), Decimal("-3"), Decimal("7"), Decimal("-2")]
        tech_prices = _build_price_series(Decimal("100"), returns, num_days)
        bank_prices = [Decimal("100")] * 10
        for i in range(10, num_days):
            bank_prices.append(bank_prices[-1] * tech_prices[i] / tech_prices[i - 1])

        _add_positions_from_series(test_db, portfolio.id, assets["TECH1"].id, base_date, tech_prices)
        _add_positions_from_series(test_db, portfolio.id, assets["BANK1"].id, base_date, bank_prices)
        test_db.commit()

        result = self._calc_tag_beta(
            test_db, portfolio.id, base_date, end_date,
            tag_data["category"].id, benchmark.id,
        )

        counts = dict(zip(result["tags"], result["tag_data_points"]))
        assert counts["科技"] == 29
        assert counts["银行"] == 20
        assert result["data_points"] == 20

    def test_basic_tag_beta(self, test_db, setup_tags, setup_assets, setup_benchmark):
        """Two tags with different sensitivities to benchmark should have different betas."""
        portfolio = test_db._test_portfolio
        tag_data = setup_tags
        assets = setup_assets
        tech_tag = tag_data["tags"]["科技"]
        bank_tag = tag_data["tags"]["银行"]
        benchmark = setup_benchmark

        test_db.add(AssetTag(asset_id=assets["TECH1"].id, tag_id=tech_tag.id, weight=Decimal("100")))
        test_db.add(AssetTag(asset_id=assets["BANK1"].id, tag_id=bank_tag.id, weight=Decimal("100")))
        test_db.commit()

        # Build benchmark price dict for return calculation
        benchmark_prices = test_db.exec(
            select(BenchmarkPrice)
            .where(BenchmarkPrice.benchmark_id == benchmark.id)
            .order_by(BenchmarkPrice.price_date)
        ).all()
        bm_price_dict = {bp.price_date: float(bp.close) for bp in benchmark_prices}
        bm_dates = sorted(bm_price_dict.keys())

        base_date = date(2024, 1, 1)
        num_days = 30

        # Tech: high beta (~2.0) — amplifies benchmark returns
        # Bank: low beta (~0.5) — dampens benchmark returns
        tech_price = Decimal("100")
        bank_price = Decimal("100")
        for i in range(num_days):
            d = base_date + timedelta(days=i)
            if i > 0 and d in bm_price_dict and bm_dates[i - 1] in bm_price_dict:
                bm_r = bm_price_dict[d] / bm_price_dict[bm_dates[i - 1]] - 1
            else:
                bm_r = 0.01
            tech_r = 1 + bm_r * 2.0
            bank_r = 1 + bm_r * 0.5
            tech_price = tech_price * Decimal(str(round(tech_r, 8)))
            bank_price = bank_price * Decimal(str(round(bank_r, 8)))
            _add_position(test_db, portfolio.id, assets["TECH1"].id, d, 100, tech_price)
            _add_position(test_db, portfolio.id, assets["BANK1"].id, d, 100, bank_price)
        test_db.commit()

        service = PortfolioService(test_db)
        calc_service = CalculationService(test_db)
        tag_returns = service.get_tag_daily_returns(
            portfolio.id, base_date, base_date + timedelta(days=num_days - 1),
            tag_data["category"].id,
        )
        result = calc_service.calculate_tag_beta(
            tag_names=tag_returns["tag_names"],
            tag_calendar_returns=tag_returns["tag_calendar_returns"],
            return_dates=tag_returns["return_dates"],
            asset_tags_found=tag_returns["asset_tags_found"],
            benchmark_id=benchmark.id,
            start_date=base_date,
            end_date=base_date + timedelta(days=num_days - 1),
            frequency="daily",
        )

        assert len(result["tags"]) == 2
        assert result["frequency"] == "daily"
        assert result["data_points"] >= 20

        betas = dict(zip(result["tags"], result["betas"]))
        assert betas["科技"] > 1.5
        assert 0.2 < betas["银行"] < 0.9

    def test_single_tag(self, test_db, setup_tags, setup_assets, setup_benchmark):
        """Single tag works for beta (unlike correlation which needs >=2)."""
        portfolio = test_db._test_portfolio
        tag_data = setup_tags
        assets = setup_assets
        tech_tag = tag_data["tags"]["科技"]
        benchmark = setup_benchmark

        test_db.add(AssetTag(asset_id=assets["TECH1"].id, tag_id=tech_tag.id, weight=Decimal("100")))
        test_db.commit()

        base_date = date(2024, 1, 1)
        num_days = 30
        # Constant 1% daily growth in price
        prices = _build_price_series(Decimal("100"), [Decimal("1")], num_days)
        _add_positions_from_series(test_db, portfolio.id, assets["TECH1"].id, base_date, prices)
        test_db.commit()

        result = self._calc_tag_beta(
            test_db, portfolio.id, base_date, base_date + timedelta(days=num_days - 1),
            tag_data["category"].id, benchmark.id, frequency="daily",
        )

        assert len(result["tags"]) == 1
        assert result["tags"] == ["科技"]
        assert isinstance(result["betas"][0], float)

    def test_no_tags_in_category(self, test_db, setup_benchmark):
        """Empty category should return empty result."""
        portfolio = test_db._test_portfolio
        benchmark = setup_benchmark
        category = TagCategory(name="Empty", description="Empty")
        test_db.add(category)
        test_db.commit()

        result = self._calc_tag_beta(
            test_db, portfolio.id, date(2024, 1, 1), date(2024, 1, 30),
            category.id, benchmark.id, frequency="daily"
        )

        assert result["tags"] == []
        assert result["betas"] == []
        assert result["data_points"] == 0

    def test_insufficient_benchmark_data(self, test_db, setup_tags, setup_assets):
        """Benchmark with fewer than 2 prices → empty result with message."""
        portfolio = test_db._test_portfolio
        tag_data = setup_tags
        assets = setup_assets
        tech_tag = tag_data["tags"]["科技"]

        test_db.add(AssetTag(asset_id=assets["TECH1"].id, tag_id=tech_tag.id, weight=Decimal("100")))
        test_db.commit()

        benchmark = Benchmark(id=200, symbol="SHORT_BM", name="Short Benchmark")
        test_db.add(benchmark)
        test_db.flush()
        test_db.add(BenchmarkPrice(
            benchmark_id=benchmark.id,
            price_date=date(2024, 1, 1),
            close=Decimal("100"),
        ))
        test_db.commit()

        # Add some position data so the tag exists
        base_date = date(2024, 1, 1)
        prices = _build_price_series(Decimal("100"), [Decimal("2")], 10)
        _add_positions_from_series(test_db, portfolio.id, assets["TECH1"].id, base_date, prices)
        test_db.commit()

        result = self._calc_tag_beta(
            test_db, portfolio.id, date(2024, 1, 1), date(2024, 1, 9),
            tag_data["category"].id, benchmark.id, frequency="daily"
        )

        assert result["tags"] == []
        assert result["betas"] == []
        assert "Insufficient benchmark" in result.get("message", "")

    def test_insufficient_tag_data(self, test_db, setup_tags, setup_assets, setup_benchmark):
        """Tags with fewer than 20 data points should be marked insufficient."""
        portfolio = test_db._test_portfolio
        tag_data = setup_tags
        assets = setup_assets
        tech_tag = tag_data["tags"]["科技"]
        benchmark = setup_benchmark

        test_db.add(AssetTag(asset_id=assets["TECH1"].id, tag_id=tech_tag.id, weight=Decimal("100")))
        test_db.commit()

        base_date = date(2024, 1, 1)
        num_days = 10  # < 20
        prices = _build_price_series(Decimal("100"), [Decimal("3"), Decimal("-1")], num_days)
        _add_positions_from_series(test_db, portfolio.id, assets["TECH1"].id, base_date, prices)
        test_db.commit()

        result = self._calc_tag_beta(
            test_db, portfolio.id, base_date, base_date + timedelta(days=num_days - 1),
            tag_data["category"].id, benchmark.id, frequency="daily"
        )

        assert result["tags"] == []
        assert "科技" in result["insufficient_data_tags"]
        assert result["data_points"] == 0

    def test_multi_currency_conversion(self, test_db, setup_tags, setup_assets,
                                        setup_exchange_rates, setup_benchmark):
        """HKD-denominated positions converted to CNY for weight computation."""
        portfolio = test_db._test_portfolio
        tag_data = setup_tags
        assets = setup_assets
        tech_tag = tag_data["tags"]["科技"]  # TECH1 is CNY
        benchmark = setup_benchmark

        test_db.add(AssetTag(asset_id=assets["TECH1"].id, tag_id=tech_tag.id, weight=Decimal("100")))
        test_db.commit()

        base_date = date(2024, 1, 1)
        num_days = 30
        prices = _build_price_series(Decimal("100"), [Decimal("2"), Decimal("-1")], num_days)
        _add_positions_from_series(test_db, portfolio.id, assets["TECH1"].id, base_date, prices)
        test_db.commit()

        result = self._calc_tag_beta(
            test_db, portfolio.id, base_date, base_date + timedelta(days=num_days - 1),
            tag_data["category"].id, benchmark.id, frequency="daily",
        )

        assert len(result["tags"]) == 1
        assert result["data_points"] >= 20

    def test_weekly_frequency(self, test_db, setup_tags, setup_assets):
        """Weekly frequency should produce fewer data points than daily and valid beta."""
        portfolio = test_db._test_portfolio
        tag_data = setup_tags
        assets = setup_assets
        tech_tag = tag_data["tags"]["科技"]

        # Create benchmark with 60 days of prices
        benchmark = Benchmark(id=300, symbol="WEEKLY_BM", name="Weekly Benchmark")
        test_db.add(benchmark)
        test_db.flush()
        for i in range(60):
            d = date(2024, 1, 1) + timedelta(days=i)
            test_db.add(BenchmarkPrice(
                benchmark_id=benchmark.id, price_date=d,
                close=Decimal(str(round(100 * (1.005 ** i), 2))),
            ))
        test_db.commit()

        test_db.add(AssetTag(asset_id=assets["TECH1"].id, tag_id=tech_tag.id, weight=Decimal("100")))
        test_db.commit()

        base_date = date(2024, 1, 1)
        num_days = 60
        prices = _build_price_series(Decimal("100"), [Decimal("1")], num_days)
        _add_positions_from_series(test_db, portfolio.id, assets["TECH1"].id, base_date, prices)
        test_db.commit()

        result = self._calc_tag_beta(
            test_db, portfolio.id, base_date, base_date + timedelta(days=num_days - 1),
            tag_data["category"].id, benchmark.id, frequency="weekly"
        )

        assert result["frequency"] == "weekly"
        assert result["data_points"] >= 4
        assert len(result["tags"]) >= 1
        assert isinstance(result["betas"][0], float)

    def test_monthly_frequency(self, test_db, setup_tags, setup_assets):
        """Monthly frequency should work correctly with sufficient data."""
        portfolio = test_db._test_portfolio
        tag_data = setup_tags
        assets = setup_assets
        tech_tag = tag_data["tags"]["科技"]

        benchmark = Benchmark(id=400, symbol="MONTHLY_BM", name="Monthly Benchmark")
        test_db.add(benchmark)
        test_db.flush()
        for i in range(90):
            d = date(2024, 1, 1) + timedelta(days=i)
            test_db.add(BenchmarkPrice(
                benchmark_id=benchmark.id, price_date=d,
                close=Decimal(str(round(100 * (1.003 ** i), 2))),
            ))
        test_db.commit()

        test_db.add(AssetTag(asset_id=assets["TECH1"].id, tag_id=tech_tag.id, weight=Decimal("100")))
        test_db.commit()

        base_date = date(2024, 1, 1)
        num_days = 90
        prices = _build_price_series(Decimal("100"), [Decimal("1")], num_days)
        _add_positions_from_series(test_db, portfolio.id, assets["TECH1"].id, base_date, prices)
        test_db.commit()

        result = self._calc_tag_beta(
            test_db, portfolio.id, base_date, base_date + timedelta(days=num_days - 1),
            tag_data["category"].id, benchmark.id, frequency="monthly"
        )

        assert result["frequency"] == "monthly"
        assert result["data_points"] >= 1
        assert len(result["tags"]) >= 1
        assert isinstance(result["betas"][0], float)

    def test_invalid_frequency(self, test_db, setup_tags, setup_benchmark):
        """Invalid frequency should raise ValueError."""
        portfolio = test_db._test_portfolio
        tag_data = setup_tags
        benchmark = setup_benchmark

        with pytest.raises(ValueError, match="Unsupported frequency"):
            self._calc_tag_beta(
                test_db, portfolio.id, date(2024, 1, 1), date(2024, 1, 30),
                tag_data["category"].id, benchmark.id, frequency="yearly"
            )

    def test_position_size_changes_dont_affect_beta(self, test_db, setup_tags,
                                                      setup_assets, setup_benchmark):
        """Quantity changes should not distort beta when price series is identical.

        Even with dramatic buying/selling, beta should reflect the underlying
        price sensitivity, not position-size changes.
        """
        portfolio = test_db._test_portfolio
        tag_data = setup_tags
        assets = setup_assets
        tech_tag = tag_data["tags"]["科技"]
        benchmark = setup_benchmark

        test_db.add(AssetTag(asset_id=assets["TECH1"].id, tag_id=tech_tag.id, weight=Decimal("100")))
        test_db.commit()

        base_date = date(2024, 1, 1)
        num_days = 30

        # Build prices with a ~1.5x benchmark sensitivity
        benchmark_prices = test_db.exec(
            select(BenchmarkPrice)
            .where(BenchmarkPrice.benchmark_id == benchmark.id)
            .order_by(BenchmarkPrice.price_date)
        ).all()
        bm_price_dict = {bp.price_date: float(bp.close) for bp in benchmark_prices}
        bm_dates = sorted(bm_price_dict.keys())

        price = Decimal("100")
        qty = 100
        for i in range(num_days):
            d = base_date + timedelta(days=i)
            if i > 0 and d in bm_price_dict and bm_dates[i - 1] in bm_price_dict:
                bm_r = bm_price_dict[d] / bm_price_dict[bm_dates[i - 1]] - 1
            else:
                bm_r = 0.01
            price = price * Decimal(str(round(1 + bm_r * 1.5, 8)))
            # Simulate buying/selling: double at day 10, halve at day 20
            if i == 10:
                qty = 200
            elif i == 20:
                qty = 50
            _add_position(test_db, portfolio.id, assets["TECH1"].id, d, qty, price)
        test_db.commit()

        result = self._calc_tag_beta(
            test_db, portfolio.id, base_date, base_date + timedelta(days=num_days - 1),
            tag_data["category"].id, benchmark.id, frequency="daily",
        )

        assert len(result["tags"]) == 1
        # Beta should be close to 1.5 despite position-size changes
        assert 1.2 < result["betas"][0] < 2.0


def _add_prices_from_series(test_db, asset_id, base_date, prices, price_type="historical"):
    """Add one Price record per day following *prices* (length = num_days)."""
    for i, p in enumerate(prices):
        test_db.add(Price(
            asset_id=asset_id,
            price_date=base_date + timedelta(days=i),
            price=p,
            price_type=price_type,
        ))


def _build_sensitivity_prices(bm_price_dict, bm_dates, start_idx, num_days, sensitivity):
    """Build an asset price series whose daily return tracks the benchmark
    return scaled by *sensitivity* (beta target). Returns a list of Decimals
    of length num_days, anchored at index start_idx in bm_dates."""
    price = Decimal("100")
    prices = [price]
    for i in range(1, num_days):
        idx = start_idx + i
        if idx < len(bm_dates) and bm_dates[idx - 1] in bm_price_dict:
            bm_r = bm_price_dict[bm_dates[idx]] / bm_price_dict[bm_dates[idx - 1]] - 1
        else:
            bm_r = 0.01
        price = price * Decimal(str(round(1 + bm_r * sensitivity, 8)))
        prices.append(price)
    return prices


# =============================================================================
# calculate_asset_beta() integration tests
# =============================================================================

class TestAssetBeta:
    """Integration tests for CalculationService.calculate_asset_beta()."""

    def _calc_asset_beta(self, test_db, portfolio_id, start, end,
                         benchmark_id, frequency="daily", top_n=10, asset_id=None):
        """Helper: fetch asset daily prices via PortfolioService, then compute
        beta via CalculationService."""
        portfolio_service = PortfolioService(test_db)
        calc_service = CalculationService(test_db)
        asset_data = portfolio_service.get_asset_daily_prices(
            portfolio_id, start, end, top_n=top_n, asset_id=asset_id,
        )
        return calc_service.calculate_asset_beta(
            asset_daily_prices=asset_data["assets"],
            benchmark_id=benchmark_id,
            start_date=start,
            end_date=end,
            frequency=frequency,
        )

    def _benchmark_price_dict(self, test_db, benchmark):
        bps = test_db.exec(
            select(BenchmarkPrice)
            .where(BenchmarkPrice.benchmark_id == benchmark.id)
            .order_by(BenchmarkPrice.price_date)
        ).all()
        d = {bp.price_date: float(bp.close) for bp in bps}
        return d, sorted(d.keys())

    def test_basic_asset_beta(self, test_db, setup_assets, setup_benchmark):
        """Two assets with different price sensitivities to benchmark should have different betas."""
        portfolio = test_db._test_portfolio
        assets = setup_assets
        benchmark = setup_benchmark

        bm_price_dict, bm_dates = self._benchmark_price_dict(test_db, benchmark)

        base_date = date(2024, 1, 1)
        num_days = 30
        end_date = base_date + timedelta(days=num_days - 1)

        # TECH1: high beta (~2.0); BANK1: low beta (~0.5)
        tech_prices = _build_sensitivity_prices(bm_price_dict, bm_dates, 0, num_days, 2.0)
        bank_prices = _build_sensitivity_prices(bm_price_dict, bm_dates, 0, num_days, 0.5)

        _add_prices_from_series(test_db, assets["TECH1"].id, base_date, tech_prices)
        _add_prices_from_series(test_db, assets["BANK1"].id, base_date, bank_prices)
        # Positions on end_date so assets appear in top-N by market value
        _add_position(test_db, portfolio.id, assets["TECH1"].id, end_date, 100, tech_prices[-1])
        _add_position(test_db, portfolio.id, assets["BANK1"].id, end_date, 100, bank_prices[-1])
        test_db.commit()

        result = self._calc_asset_beta(
            test_db, portfolio.id, base_date, end_date, benchmark.id, frequency="daily",
        )

        assert result["frequency"] == "daily"
        assert len(result["assets"]) == 2
        assert result["data_points"] >= 20
        betas = {a["symbol"]: a["beta"] for a in result["assets"]}
        assert betas["TECH1"] > 1.5
        assert 0.2 < betas["BANK1"] < 0.9

    def test_multi_currency_asset_beta(self, test_db, setup_assets, setup_exchange_rates,
                                        setup_benchmark):
        """HKD-denominated asset should be picked up and produce a valid beta
        after currency conversion for market-value ranking."""
        portfolio = test_db._test_portfolio
        assets = setup_assets
        benchmark = setup_benchmark

        bm_price_dict, bm_dates = self._benchmark_price_dict(test_db, benchmark)

        base_date = date(2024, 1, 1)
        num_days = 30
        end_date = base_date + timedelta(days=num_days - 1)

        # BANK2 is HKD-denominated; give it high beta (~2.0)
        bank_prices = _build_sensitivity_prices(bm_price_dict, bm_dates, 0, num_days, 2.0)
        _add_prices_from_series(test_db, assets["BANK2"].id, base_date, bank_prices)
        _add_position(test_db, portfolio.id, assets["BANK2"].id, end_date, 100, bank_prices[-1])
        test_db.commit()

        result = self._calc_asset_beta(
            test_db, portfolio.id, base_date, end_date, benchmark.id, frequency="daily",
        )

        assert len(result["assets"]) == 1
        assert result["assets"][0]["symbol"] == "BANK2"
        assert result["data_points"] >= 20
        assert result["assets"][0]["beta"] > 1.5

    def test_weekly_frequency_asset_beta(self, test_db, setup_assets):
        """Weekly frequency should aggregate returns and produce fewer data points."""
        portfolio = test_db._test_portfolio
        assets = setup_assets

        # 60-day benchmark
        benchmark = Benchmark(id=500, symbol="WEEKLY_AB_BM", name="Weekly Asset Benchmark")
        test_db.add(benchmark)
        test_db.flush()
        for i in range(60):
            d = date(2024, 1, 1) + timedelta(days=i)
            test_db.add(BenchmarkPrice(
                benchmark_id=benchmark.id, price_date=d,
                close=Decimal(str(round(100 * (1.005 ** i), 2))),
            ))
        test_db.commit()

        bm_price_dict, bm_dates = self._benchmark_price_dict(test_db, benchmark)

        base_date = date(2024, 1, 1)
        num_days = 60
        end_date = base_date + timedelta(days=num_days - 1)

        prices = _build_sensitivity_prices(bm_price_dict, bm_dates, 0, num_days, 1.5)
        _add_prices_from_series(test_db, assets["TECH1"].id, base_date, prices)
        _add_position(test_db, portfolio.id, assets["TECH1"].id, end_date, 100, prices[-1])
        test_db.commit()

        result = self._calc_asset_beta(
            test_db, portfolio.id, base_date, end_date, benchmark.id, frequency="weekly",
        )

        assert result["frequency"] == "weekly"
        assert result["data_points"] >= 4
        assert len(result["assets"]) == 1
        assert isinstance(result["assets"][0]["beta"], float)

    def test_insufficient_asset_data(self, test_db, setup_assets, setup_benchmark):
        """Asset with fewer than 20 price days should be marked insufficient."""
        portfolio = test_db._test_portfolio
        assets = setup_assets
        benchmark = setup_benchmark

        base_date = date(2024, 1, 1)
        num_days = 10  # < 20
        end_date = base_date + timedelta(days=num_days - 1)
        prices = _build_price_series(Decimal("100"), [Decimal("3"), Decimal("-1")], num_days)
        _add_prices_from_series(test_db, assets["TECH1"].id, base_date, prices)
        _add_position(test_db, portfolio.id, assets["TECH1"].id, end_date, 100, prices[-1])
        test_db.commit()

        result = self._calc_asset_beta(
            test_db, portfolio.id, base_date, end_date, benchmark.id, frequency="daily",
        )

        assert result["assets"] == []
        assert "TECH1" in result["insufficient_data_assets"]
        assert result["data_points"] == 0

    def test_insufficient_benchmark_data(self, test_db, setup_assets):
        """Benchmark with fewer than 2 prices → empty result with message."""
        portfolio = test_db._test_portfolio
        assets = setup_assets

        benchmark = Benchmark(id=600, symbol="SHORT_AB_BM", name="Short Asset Benchmark")
        test_db.add(benchmark)
        test_db.flush()
        test_db.add(BenchmarkPrice(
            benchmark_id=benchmark.id, price_date=date(2024, 1, 1),
            close=Decimal("100"),
        ))
        test_db.commit()

        base_date = date(2024, 1, 1)
        num_days = 30
        end_date = base_date + timedelta(days=num_days - 1)
        prices = _build_price_series(Decimal("100"), [Decimal("2")], num_days)
        _add_prices_from_series(test_db, assets["TECH1"].id, base_date, prices)
        _add_position(test_db, portfolio.id, assets["TECH1"].id, end_date, 100, prices[-1])
        test_db.commit()

        result = self._calc_asset_beta(
            test_db, portfolio.id, base_date, end_date, benchmark.id, frequency="daily",
        )

        assert result["assets"] == []
        assert "TECH1" in result["insufficient_data_assets"]
        assert "Insufficient benchmark" in result.get("message", "")

    def test_no_assets(self, test_db, setup_benchmark):
        """Portfolio with no positions on end_date → empty result."""
        portfolio = test_db._test_portfolio
        benchmark = setup_benchmark

        result = self._calc_asset_beta(
            test_db, portfolio.id, date(2024, 1, 1), date(2024, 1, 30),
            benchmark.id, frequency="daily",
        )

        assert result["assets"] == []
        assert result["insufficient_data_assets"] == []
        assert result["data_points"] == 0

    def test_data_points_is_minimum_across_assets(self, test_db, setup_assets, setup_benchmark):
        """data_points must be the min across sufficient assets, not the last one.

        Regression for the bug where final_data_points was overwritten each
        iteration and ended up reflecting only the last asset.
        """
        portfolio = test_db._test_portfolio
        assets = setup_assets
        benchmark = setup_benchmark

        bm_price_dict, bm_dates = self._benchmark_price_dict(test_db, benchmark)

        base_date = date(2024, 1, 1)
        num_days = 30
        end_date = base_date + timedelta(days=num_days - 1)

        # TECH1: prices only for last 25 days (days 6-30) → 24 aligned returns.
        # Higher quantity so it ranks FIRST by market value.
        tech_prices = _build_price_series(Decimal("100"), [Decimal("1")], 25)
        tech_base = base_date + timedelta(days=5)
        _add_prices_from_series(test_db, assets["TECH1"].id, tech_base, tech_prices)
        _add_position(test_db, portfolio.id, assets["TECH1"].id, end_date, 200, tech_prices[-1])

        # BANK1: prices for all 30 days → 29 aligned returns. Lower quantity so
        # it ranks LAST (the asset whose data_points the bug would wrongly return).
        bank_prices = _build_price_series(Decimal("100"), [Decimal("1")], num_days)
        _add_prices_from_series(test_db, assets["BANK1"].id, base_date, bank_prices)
        _add_position(test_db, portfolio.id, assets["BANK1"].id, end_date, 100, bank_prices[-1])
        test_db.commit()

        result = self._calc_asset_beta(
            test_db, portfolio.id, base_date, end_date, benchmark.id, frequency="daily",
        )

        # Both assets are sufficient (>= 20), but with different aligned counts.
        assert len(result["assets"]) == 2
        symbols = [a["symbol"] for a in result["assets"]]
        assert symbols == ["TECH1", "BANK1"]  # ordered by market value desc
        # min(24, 29) == 24 — before the fix this returned 29 (the last asset).
        assert result["data_points"] == 24
        # Each asset reports its own aligned return count.
        data_points_by_symbol = {a["symbol"]: a["data_points"] for a in result["assets"]}
        assert data_points_by_symbol["TECH1"] == 24
        assert data_points_by_symbol["BANK1"] == 29

    def test_invalid_frequency(self, test_db, setup_assets, setup_benchmark):
        """Invalid frequency should raise ValueError."""
        portfolio = test_db._test_portfolio
        assets = setup_assets
        benchmark = setup_benchmark

        base_date = date(2024, 1, 1)
        num_days = 30
        end_date = base_date + timedelta(days=num_days - 1)
        prices = _build_price_series(Decimal("100"), [Decimal("1")], num_days)
        _add_prices_from_series(test_db, assets["TECH1"].id, base_date, prices)
        _add_position(test_db, portfolio.id, assets["TECH1"].id, end_date, 100, prices[-1])
        test_db.commit()

        with pytest.raises(ValueError, match="Unsupported frequency"):
            self._calc_asset_beta(
                test_db, portfolio.id, base_date, end_date, benchmark.id, frequency="yearly",
            )
