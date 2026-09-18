"""
Test cases for benchmark prices in production database

These tests require a production database connection and are marked as 'production'.
Run with: pytest -m production
Skip with: pytest -m 'not production'
"""

import pytest
from datetime import date
from decimal import Decimal
from sqlmodel import Session, select

from backend.db import get_engine
from backend.db.models import Benchmark, BenchmarkPrice


@pytest.mark.production
class TestBenchmarkPrices:
    """Test cases for benchmark prices in production database"""

    @pytest.mark.parametrize(
        "symbol,expected_price",
        [
            ("000300.SH", Decimal("4629.94")),   # CSI 300
            ("HSI.HK", Decimal("25630.54")),      # Hang Seng Index
        ],
    )
    def test_benchmark_price_on_2025_12_31(self, symbol, expected_price):
        """Test that benchmark price on 2025-12-31 matches the expected value (0.01% tolerance)."""
        engine = get_engine()

        with Session(engine) as session:
            benchmark = session.exec(
                select(Benchmark).where(Benchmark.symbol == symbol)
            ).first()

            assert benchmark is not None, f"Benchmark ({symbol}) should exist in database"

            price = session.exec(
                select(BenchmarkPrice).where(
                    BenchmarkPrice.benchmark_id == benchmark.id,
                    BenchmarkPrice.price_date == date(2025, 12, 31)
                )
            ).first()

            assert price is not None, f"{symbol} price for 2025-12-31 should exist"

            tolerance = expected_price * Decimal("0.0001")  # 0.01% tolerance

            assert abs(price.close - expected_price) <= tolerance, (
                f"{symbol} price on 2025-12-31 should be approximately {expected_price}, "
                f"got {price.close}"
            )