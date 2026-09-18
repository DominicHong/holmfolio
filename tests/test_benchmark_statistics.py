"""Tests for benchmark statistics calculation (beta and excess return)"""

import pytest
import numpy as np
from datetime import date, timedelta
from decimal import Decimal
from sqlmodel import Session

from backend.db.models import Benchmark, BenchmarkPrice, BenchmarkComponent, Currency, Portfolio
from backend.services.calculation import CalculationService


@pytest.fixture
def benchmark_test_db(test_db: Session):
    """Create test data for benchmark statistics tests"""
    cny = test_db._test_cny
    portfolio = test_db._test_portfolio

    benchmark = Benchmark(
        id=1,
        symbol="000300.SH",
        name="CSI 300 Index"
    )
    test_db.add(benchmark)
    test_db.flush()

    return {
        "benchmark": benchmark,
        "portfolio": portfolio,
        "cny": cny,
        "session": test_db,
        "service": CalculationService(test_db)
    }


class TestBenchmarkBeta:
    """Basic test cases for benchmark beta calculation"""

    def test_beta_calculation_basic(self, benchmark_test_db):
        """Test basic beta calculation with perfectly aligned data"""
        data = benchmark_test_db
        benchmark = data["benchmark"]
        service = data["service"]
        session = data["session"]

        benchmark_prices = [
            (date(2025, 1, 1), Decimal("100")),
            (date(2025, 1, 2), Decimal("101")),
            (date(2025, 1, 3), Decimal("103")),
            (date(2025, 1, 4), Decimal("102")),
            (date(2025, 1, 5), Decimal("105")),
        ]
        for price_date, close in benchmark_prices:
            session.add(BenchmarkPrice(
                benchmark_id=benchmark.id,
                price_date=price_date,
                close=close
            ))
        session.commit()

        portfolio_dates = [date(2025, 1, 1), date(2025, 1, 2), date(2025, 1, 3),
                          date(2025, 1, 4), date(2025, 1, 5)]
        nav_history = [1.0, 1.02, 1.04, 1.03, 1.06]

        result = service._calculate_benchmark_statistics(
            benchmark_id=benchmark.id,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 5),
            portfolio_dates=portfolio_dates,
            nav_history=nav_history
        )

        assert "beta" in result
        assert "benchmark_return" in result
        assert isinstance(result["beta"], float)
        assert isinstance(result["benchmark_return"], float)

        assert 0.8 < result["beta"] < 1.2


class TestBenchmarkReturn:
    """Test cases for benchmark return calculation"""

    def test_alignment_with_non_trading_days(self, benchmark_test_db):
        """Test alignment when portfolio has dates that benchmark doesn't (weekends)"""
        data = benchmark_test_db
        benchmark = data["benchmark"]
        service = data["service"]
        session = data["session"]

        benchmark_prices = [
            (date(2025, 1, 1), Decimal("100")),
            (date(2025, 1, 2), Decimal("102")),
            (date(2025, 1, 5), Decimal("105")),
            (date(2025, 1, 6), Decimal("107")),
        ]
        for price_date, close in benchmark_prices:
            session.add(BenchmarkPrice(
                benchmark_id=benchmark.id,
                price_date=price_date,
                close=close
            ))
        session.commit()

        portfolio_dates = [
            date(2025, 1, 1),
            date(2025, 1, 2),
            date(2025, 1, 3),
            date(2025, 1, 4),
            date(2025, 1, 5),
            date(2025, 1, 6),
        ]
        nav_history = [1.0, 1.02, 1.03, 1.04, 1.05, 1.07]

        result = service._calculate_benchmark_statistics(
            benchmark_id=benchmark.id,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 6),
            portfolio_dates=portfolio_dates,
            nav_history=nav_history
        )

        assert "beta" in result
        assert "benchmark_return" in result

        expected_benchmark_return = (102 / 100) * (105 / 102) * (107 / 105) - 1
        assert abs(result["benchmark_return"] - expected_benchmark_return) < 0.001

    def test_benchmark_return_negative(self, benchmark_test_db):
        """Test benchmark return when prices decline"""
        data = benchmark_test_db
        benchmark = data["benchmark"]
        service = data["service"]
        session = data["session"]

        benchmark_prices = [
            (date(2025, 1, 1), Decimal("100")),
            (date(2025, 1, 2), Decimal("98")),
            (date(2025, 1, 3), Decimal("95")),
        ]
        for price_date, close in benchmark_prices:
            session.add(BenchmarkPrice(
                benchmark_id=benchmark.id,
                price_date=price_date,
                close=close
            ))
        session.commit()

        portfolio_dates = [date(2025, 1, 1), date(2025, 1, 2), date(2025, 1, 3)]
        nav_history = [1.0, 0.98, 0.95]

        result = service._calculate_benchmark_statistics(
            benchmark_id=benchmark.id,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 3),
            portfolio_dates=portfolio_dates,
            nav_history=nav_history
        )

        expected_return = (98 / 100) * (95 / 98) - 1
        assert abs(result["benchmark_return"] - expected_return) < 0.001
        assert result["benchmark_return"] < 0


class TestBenchmarkStatisticsEdgeCases:
    """Edge case tests for benchmark statistics calculation"""

    def test_insufficient_benchmark_prices(self, benchmark_test_db):
        """Test with insufficient benchmark prices (less than 2)"""
        data = benchmark_test_db
        benchmark = data["benchmark"]
        service = data["service"]
        session = data["session"]

        session.add(BenchmarkPrice(
            benchmark_id=benchmark.id,
            price_date=date(2025, 1, 1),
            close=Decimal("100")
        ))
        session.commit()

        result = service._calculate_benchmark_statistics(
            benchmark_id=benchmark.id,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 5),
            portfolio_dates=[date(2025, 1, 1), date(2025, 1, 2)],
            nav_history=[1.0, 1.01]
        )

        assert result["beta"] == 0.0
        assert result["benchmark_return"] == 0.0
        assert result["excess_return"] == 0.0

    def test_no_overlapping_dates(self, benchmark_test_db):
        """Test when portfolio and benchmark have no overlapping dates"""
        data = benchmark_test_db
        benchmark = data["benchmark"]
        service = data["service"]
        session = data["session"]

        benchmark_prices = [
            (date(2025, 1, 1), Decimal("100")),
            (date(2025, 1, 2), Decimal("102")),
        ]
        for price_date, close in benchmark_prices:
            session.add(BenchmarkPrice(
                benchmark_id=benchmark.id,
                price_date=price_date,
                close=close
            ))
        session.commit()

        portfolio_dates = [date(2025, 1, 5), date(2025, 1, 6)]
        nav_history = [1.0, 1.01]

        result = service._calculate_benchmark_statistics(
            benchmark_id=benchmark.id,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 6),
            portfolio_dates=portfolio_dates,
            nav_history=nav_history
        )

        assert result["beta"] == 0.0
        assert result["benchmark_return"] == 0.0
        assert result["excess_return"] == 0.0

    def test_non_existent_benchmark(self, benchmark_test_db):
        """Test with non-existent benchmark ID"""
        data = benchmark_test_db
        service = data["service"]

        result = service._calculate_benchmark_statistics(
            benchmark_id=9999,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 5),
            portfolio_dates=[date(2025, 1, 1), date(2025, 1, 2)],
            nav_history=[1.0, 1.01]
        )

        assert result["beta"] == 0.0
        assert result["benchmark_return"] == 0.0

    def test_single_aligned_data_point(self, benchmark_test_db):
        """Test with only one aligned data point (insufficient for beta)"""
        data = benchmark_test_db
        benchmark = data["benchmark"]
        service = data["service"]
        session = data["session"]

        benchmark_prices = [
            (date(2025, 1, 1), Decimal("100")),
            (date(2025, 1, 2), Decimal("102")),
        ]
        for price_date, close in benchmark_prices:
            session.add(BenchmarkPrice(
                benchmark_id=benchmark.id,
                price_date=price_date,
                close=close
            ))
        session.commit()

        portfolio_dates = [date(2025, 1, 1), date(2025, 1, 2)]
        nav_history = [1.0, 1.02]

        result = service._calculate_benchmark_statistics(
            benchmark_id=benchmark.id,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 2),
            portfolio_dates=portfolio_dates,
            nav_history=nav_history
        )

        assert result["beta"] == 0.0


class TestExcessReturn:
    """Test cases for excess return calculation"""

    def test_excess_return_with_misaligned_dates(self, benchmark_test_db):
        """Test excess return when portfolio and benchmark have different date ranges"""
        data = benchmark_test_db
        benchmark = data["benchmark"]
        service = data["service"]
        session = data["session"]

        benchmark_prices = [
            (date(2025, 1, 1), Decimal("100")),
            (date(2025, 1, 2), Decimal("102")),
            (date(2025, 1, 5), Decimal("155")),
            (date(2025, 1, 6), Decimal("188")),
        ]
        for price_date, close in benchmark_prices:
            session.add(BenchmarkPrice(
                benchmark_id=benchmark.id,
                price_date=price_date,
                close=close
            ))
        session.commit()

        portfolio_dates = [
            date(2025, 1, 1),
            date(2025, 1, 2),
            date(2025, 1, 3),
            date(2025, 1, 4),
            date(2025, 1, 5),
            date(2025, 1, 6),
        ]
        nav_history = [1.0, 1.02, 1.03, 1.04, 1.06, 1.09]

        result = service._calculate_benchmark_statistics(
            benchmark_id=benchmark.id,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 6),
            portfolio_dates=portfolio_dates,
            nav_history=nav_history
        )

        expected_benchmark_return = (102 / 100) * (155 / 102) * (188 / 155) - 1
        expected_portfolio_return = (1.02 / 1.0) * (1.06 / 1.02) * (1.09 / 1.06) - 1
        expected_excess = expected_portfolio_return - expected_benchmark_return

        assert abs(result["excess_return"] - expected_excess) < 0.00001

    def test_excess_return_zero(self, benchmark_test_db):
        """Test zero excess return when portfolio matches benchmark exactly"""
        data = benchmark_test_db
        benchmark = data["benchmark"]
        service = data["service"]
        session = data["session"]

        benchmark_prices = [
            (date(2025, 1, 1), Decimal("100")),
            (date(2025, 1, 2), Decimal("102")),
            (date(2025, 1, 3), Decimal("104")),
            (date(2025, 1, 4), Decimal("106")),
        ]
        for price_date, close in benchmark_prices:
            session.add(BenchmarkPrice(
                benchmark_id=benchmark.id,
                price_date=price_date,
                close=close
            ))
        session.commit()

        portfolio_dates = [date(2025, 1, 1), date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 4)]
        nav_history = [1.0, 1.02, 1.04, 1.06]

        result = service._calculate_benchmark_statistics(
            benchmark_id=benchmark.id,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 4),
            portfolio_dates=portfolio_dates,
            nav_history=nav_history
        )

        assert abs(result["excess_return"]) < 0.001

    def test_excess_return_both_negative(self, benchmark_test_db):
        """Test excess return when both portfolio and benchmark have negative returns"""
        data = benchmark_test_db
        benchmark = data["benchmark"]
        service = data["service"]
        session = data["session"]

        benchmark_prices = [
            (date(2025, 1, 1), Decimal("100")),
            (date(2025, 1, 2), Decimal("95")),
            (date(2025, 1, 3), Decimal("90")),
            (date(2025, 1, 4), Decimal("85")),
        ]
        for price_date, close in benchmark_prices:
            session.add(BenchmarkPrice(
                benchmark_id=benchmark.id,
                price_date=price_date,
                close=close
            ))
        session.commit()

        portfolio_dates = [date(2025, 1, 1), date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 4)]
        nav_history = [1.0, 0.96, 0.92, 0.88]

        result = service._calculate_benchmark_statistics(
            benchmark_id=benchmark.id,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 4),
            portfolio_dates=portfolio_dates,
            nav_history=nav_history
        )

        expected_benchmark_return = (95 / 100) * (90 / 95) * (85 / 90) - 1
        expected_portfolio_return = (0.96 / 1.0) * (0.92 / 0.96) * (0.88 / 0.92) - 1
        expected_excess = expected_portfolio_return - expected_benchmark_return

        assert abs(result["excess_return"] - expected_excess) < 0.001
        assert result["benchmark_return"] < 0
        assert result["excess_return"] > 0


    def test_excess_return_with_mixed_returns(self, benchmark_test_db):
        """Test excess return with mixed positive and negative daily returns"""
        data = benchmark_test_db
        benchmark = data["benchmark"]
        service = data["service"]
        session = data["session"]

        benchmark_prices = [
            (date(2025, 1, 1), Decimal("100")),
            (date(2025, 1, 2), Decimal("105")),
            (date(2025, 1, 3), Decimal("100")),
            (date(2025, 1, 4), Decimal("110")),
            (date(2025, 1, 5), Decimal("105")),
        ]
        for price_date, close in benchmark_prices:
            session.add(BenchmarkPrice(
                benchmark_id=benchmark.id,
                price_date=price_date,
                close=close
            ))
        session.commit()

        portfolio_dates = [
            date(2025, 1, 1),
            date(2025, 1, 2),
            date(2025, 1, 3),
            date(2025, 1, 4),
            date(2025, 1, 5),
        ]
        nav_history = [1.0, 1.08, 1.02, 1.12, 1.06]

        result = service._calculate_benchmark_statistics(
            benchmark_id=benchmark.id,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 5),
            portfolio_dates=portfolio_dates,
            nav_history=nav_history
        )

        expected_benchmark_return = (105 / 100) * (100 / 105) * (110 / 100) * (105 / 110) - 1
        expected_portfolio_return = (1.08 / 1.0) * (1.02 / 1.08) * (1.12 / 1.02) * (1.06 / 1.12) - 1
        expected_excess = expected_portfolio_return - expected_benchmark_return

        assert abs(result["excess_return"] - expected_excess) < 0.001


class TestCompositeBenchmark:
    """Test cases for composite benchmark price computation and statistics."""

    def test_composite_benchmark_prices(self, benchmark_test_db):
        """Test that composite benchmark prices are computed correctly from components."""
        data = benchmark_test_db
        session = data["session"]
        service = data["service"]

        # Create two component benchmarks with different price levels
        benchmark_a = Benchmark(id=10, symbol="A", name="Benchmark A")
        benchmark_b = Benchmark(id=11, symbol="B", name="Benchmark B")
        session.add_all([benchmark_a, benchmark_b])
        session.flush()

        # Prices for A: starts at 100
        for i, close in enumerate([Decimal("100"), Decimal("102"), Decimal("104"), Decimal("103"), Decimal("105")]):
            session.add(BenchmarkPrice(benchmark_id=benchmark_a.id, price_date=date(2025, 1, 1) + timedelta(days=i), close=close))

        # Prices for B: starts at 20000 (different magnitude)
        for i, close in enumerate([Decimal("20000"), Decimal("20200"), Decimal("20400"), Decimal("20300"), Decimal("20500")]):
            session.add(BenchmarkPrice(benchmark_id=benchmark_b.id, price_date=date(2025, 1, 1) + timedelta(days=i), close=close))

        session.commit()

        # Create composite benchmark: 50% A + 50% B
        composite = Benchmark(id=20, symbol="COMP", name="Composite", is_composite=True)
        session.add(composite)
        session.flush()

        session.add(BenchmarkComponent(composite_benchmark_id=composite.id, component_benchmark_id=benchmark_a.id, weight=Decimal("0.5")))
        session.add(BenchmarkComponent(composite_benchmark_id=composite.id, component_benchmark_id=benchmark_b.id, weight=Decimal("0.5")))
        session.commit()

        prices = service._get_benchmark_prices(composite.id, date(2025, 1, 1), date(2025, 1, 5))

        assert len(prices) == 5
        # Day 1: both at 1.0 -> composite = 1.0
        assert abs(float(prices[0].close) - 1.0) < 0.0001
        # Day 2: A=1.02, B=1.01 -> composite = 0.5*1.02 + 0.5*1.01 = 1.015
        assert abs(float(prices[1].close) - 1.015) < 0.0001
        # Day 3: A=1.04, B=1.02 -> composite = 0.5*1.04 + 0.5*1.02 = 1.03
        assert abs(float(prices[2].close) - 1.03) < 0.0001
        # Day 5: A=1.05, B=1.025 -> composite = 0.5*1.05 + 0.5*1.025 = 1.0375
        assert abs(float(prices[4].close) - 1.0375) < 0.0001

    def test_composite_benchmark_statistics(self, benchmark_test_db):
        """Test beta and excess return calculation for composite benchmark."""
        data = benchmark_test_db
        session = data["session"]
        service = data["service"]

        benchmark_a = Benchmark(id=30, symbol="A2", name="Benchmark A2")
        benchmark_b = Benchmark(id=31, symbol="B2", name="Benchmark B2")
        session.add_all([benchmark_a, benchmark_b])
        session.flush()

        # A: +2% each day
        for i, close in enumerate([Decimal("100"), Decimal("102"), Decimal("104"), Decimal("106"), Decimal("108")]):
            session.add(BenchmarkPrice(benchmark_id=benchmark_a.id, price_date=date(2025, 1, 1) + timedelta(days=i), close=close))

        # B: +1% each day
        for i, close in enumerate([Decimal("100"), Decimal("101"), Decimal("102"), Decimal("103"), Decimal("104")]):
            session.add(BenchmarkPrice(benchmark_id=benchmark_b.id, price_date=date(2025, 1, 1) + timedelta(days=i), close=close))

        session.commit()

        # Composite: 50% A + 50% B
        composite = Benchmark(id=40, symbol="COMP2", name="Composite 2", is_composite=True)
        session.add(composite)
        session.flush()

        session.add(BenchmarkComponent(composite_benchmark_id=composite.id, component_benchmark_id=benchmark_a.id, weight=Decimal("0.5")))
        session.add(BenchmarkComponent(composite_benchmark_id=composite.id, component_benchmark_id=benchmark_b.id, weight=Decimal("0.5")))
        session.commit()

        # Portfolio NAV that exactly matches composite price movements
        portfolio_dates = [date(2025, 1, 1), date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 4), date(2025, 1, 5)]
        # Composite prices: 1.0, 0.5*1.02+0.5*1.01=1.015, 0.5*1.04+0.5*1.02=1.03, 0.5*1.06+0.5*1.03=1.045, 0.5*1.08+0.5*1.04=1.06
        nav_history = [1.0, 1.015, 1.03, 1.045, 1.06]

        result = service._calculate_benchmark_statistics(
            benchmark_id=composite.id,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 5),
            portfolio_dates=portfolio_dates,
            nav_history=nav_history
        )

        assert "beta" in result
        assert "benchmark_return" in result
        assert "excess_return" in result
        assert abs(result["beta"] - 1.0) < 0.02
        assert abs(result["excess_return"]) < 0.005

    def test_composite_benchmark_forward_fill(self, benchmark_test_db):
        """Test that missing component prices are forward-filled in composite calculation."""
        data = benchmark_test_db
        session = data["session"]
        service = data["service"]

        benchmark_a = Benchmark(id=50, symbol="A3", name="Benchmark A3")
        benchmark_b = Benchmark(id=51, symbol="B3", name="Benchmark B3")
        session.add_all([benchmark_a, benchmark_b])
        session.flush()

        # A has prices on all days
        session.add(BenchmarkPrice(benchmark_id=benchmark_a.id, price_date=date(2025, 1, 1), close=Decimal("100")))
        session.add(BenchmarkPrice(benchmark_id=benchmark_a.id, price_date=date(2025, 1, 2), close=Decimal("101")))
        session.add(BenchmarkPrice(benchmark_id=benchmark_a.id, price_date=date(2025, 1, 3), close=Decimal("102")))

        # B missing price on Jan 2
        session.add(BenchmarkPrice(benchmark_id=benchmark_b.id, price_date=date(2025, 1, 1), close=Decimal("200")))
        session.add(BenchmarkPrice(benchmark_id=benchmark_b.id, price_date=date(2025, 1, 3), close=Decimal("202")))

        session.commit()

        composite = Benchmark(id=60, symbol="COMP3", name="Composite 3", is_composite=True)
        session.add(composite)
        session.flush()

        session.add(BenchmarkComponent(composite_benchmark_id=composite.id, component_benchmark_id=benchmark_a.id, weight=Decimal("0.5")))
        session.add(BenchmarkComponent(composite_benchmark_id=composite.id, component_benchmark_id=benchmark_b.id, weight=Decimal("0.5")))
        session.commit()

        prices = service._get_benchmark_prices(composite.id, date(2025, 1, 1), date(2025, 1, 3))

        assert len(prices) == 3
        # Day 1: both at 1.0 -> composite = 1.0
        assert abs(float(prices[0].close) - 1.0) < 0.0001
        # Day 2: A=1.01, B forward-filled to 1.0 -> composite = 0.5*1.01 + 0.5*1.0 = 1.005
        assert abs(float(prices[1].close) - 1.005) < 0.0001
        # Day 3: A=1.02, B=1.01 -> composite = 0.5*1.02 + 0.5*1.01 = 1.015
        assert abs(float(prices[2].close) - 1.015) < 0.0001
