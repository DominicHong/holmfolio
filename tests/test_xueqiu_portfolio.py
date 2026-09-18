"""Test xueqiu portfolio data against production database.

This test compares values from the production database (via API)
with reference values from xueqiu_portfolio.csv.
"""

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlmodel import Session, select

from backend.db.models import (
    Asset,
    Currency,
    ExchangeRate,
    Portfolio,
    Position,
)
from backend.db import get_engine
from backend.services import CurrencyService, PositionService, PortfolioService


def parse_decimal_value(value: str) -> Decimal:
    """Parse a decimal value from CSV, stripping percentages and parentheses.

    Args:
        value: The string value from CSV (e.g., "-69820.40(-2.79%)")

    Returns:
        Decimal value.
    """
    # Remove any content in parentheses (percentages)
    if "(" in value:
        value = value.split("(")[0]
    return Decimal(value.strip())


def read_reference_values(csv_path: Path) -> dict:
    """Read reference values from xueqiu_portfolio.csv.

    Args:
        csv_path: Path to the CSV file.

    Returns:
        Dictionary containing reference values.
    """
    # Try UTF-8 first, fallback to GBK for Chinese Windows encoding
    try:
        with open(csv_path, "r", encoding="gbk") as f:
            reader = csv.reader(f)
            rows = list(reader)
    except UnicodeDecodeError:
            logger.error(f"Error decoding file {csv_path} with GBK encoding")

    # Row indices are 0-based, but CSV is 1-based in description
    # A股 row is at index 3 (4th row), 港股 row is at index 4 (5th row)
    a_shares_row = rows[3]  # A股
    hk_shares_row = rows[4]  # 港股

    return {
        "a_shares_cumulative_pnl": parse_decimal_value(a_shares_row[3]),  # 第4列: 累积盈亏
        "hk_shares_cumulative_pnl": parse_decimal_value(hk_shares_row[3]),  # 第4列: 累积盈亏
        "a_shares_total_assets": parse_decimal_value(a_shares_row[5]),  # 第6列: 总资产
        "hk_shares_total_assets": parse_decimal_value(hk_shares_row[5]),  # 第6列: 总资产
        "a_shares_cash": parse_decimal_value(a_shares_row[6]),  # 第7列: 现金
        "hk_shares_cash": parse_decimal_value(hk_shares_row[6]),  # 第7列: 现金
    }


def get_test_values(session: Session, portfolio_id: int, test_date: date) -> dict:
    """Get test values from database for comparison.

    Args:
        session: Database session.
        portfolio_id: Portfolio ID.
        test_date: Date to test.

    Returns:
        Dictionary containing test values.
    """
    currency_service = CurrencyService(session)
    position_service = PositionService(session)
    portfolio_service = PortfolioService(session)

    # Get positions for the test date
    positions = session.exec(
        select(Position)
        .where(Position.portfolio_id == portfolio_id)
        .where(Position.position_date == test_date)
    ).all()

    if not positions:
        positions_dict = position_service.compute_period_end_positions(
            portfolio_id=portfolio_id,
            start_date=date(1982, 1, 1),
            end_date=test_date,
            save_to_db=True,
        )
        positions = list(positions_dict.values())

    # Get CNY and HKD currencies
    cny_currency = session.exec(select(Currency).where(Currency.code == "CNY")).first()
    hkd_currency = session.exec(select(Currency).where(Currency.code == "HKD")).first()

    cny_currency_id = cny_currency.id if cny_currency else None
    hkd_currency_id = hkd_currency.id if hkd_currency else None

    # Calculate values by currency
    a_shares_cumulative_pnl = Decimal("0")
    hk_shares_cumulative_pnl = Decimal("0")
    a_shares_total_assets = Decimal("0")
    hk_shares_total_assets = Decimal("0")
    a_shares_cash = Decimal("0")
    hk_shares_cash = Decimal("0")

    for position in positions:
        asset = session.get(Asset, position.asset_id)
        if not asset:
            continue

        asset_currency_id = asset.currency_id

        # Check for cash symbols (pattern: {currency_code}_CASH)
        if asset.symbol == "CNY_CASH":
            a_shares_cash = position.market_value or Decimal("0")
        elif asset.symbol == "HKD_CASH":
            hk_shares_cash = position.market_value or Decimal("0")

        # Accumulate by currency
        if asset_currency_id == cny_currency_id:
            a_shares_cumulative_pnl += position.total_pnl or Decimal("0")
            a_shares_total_assets += position.market_value or Decimal("0")
        elif asset_currency_id == hkd_currency_id:
            hk_shares_cumulative_pnl += position.total_pnl or Decimal("0")
            hk_shares_total_assets += position.market_value or Decimal("0")

    # Get portfolio summary for total market value and total P&L
    portfolio_value = portfolio_service.calculate_portfolio_value(portfolio_id, test_date)
    total_market_value = portfolio_value.get("total_value", Decimal("0"))

    # Calculate total P&L: total_market_value - 10251265 (reference cost)
    reference_cost = Decimal("10251265")
    total_pnl = total_market_value - reference_cost

    # Get HKD/CNY exchange rate for the test date
    hkd_cny_rate = Decimal("1.0")
    if hkd_currency_id:
        rate = session.exec(
            select(ExchangeRate)
            .where(ExchangeRate.from_currency_id == hkd_currency_id)
            .where(ExchangeRate.to_currency_id == cny_currency_id)
            .where(ExchangeRate.rate_date <= test_date)
            .order_by(ExchangeRate.rate_date.desc())
        ).first()
        if rate:
            hkd_cny_rate = rate.rate
        else:
            # Try inverse rate
            inverse_rate = session.exec(
                select(ExchangeRate)
                .where(ExchangeRate.from_currency_id == cny_currency_id)
                .where(ExchangeRate.to_currency_id == hkd_currency_id)
                .where(ExchangeRate.rate_date <= test_date)
                .order_by(ExchangeRate.rate_date.desc())
            ).first()
            if inverse_rate and inverse_rate.rate != 0:
                hkd_cny_rate = Decimal("1.0") / inverse_rate.rate

    return {
        "a_shares_cumulative_pnl": a_shares_cumulative_pnl,
        "hk_shares_cumulative_pnl": hk_shares_cumulative_pnl,
        "a_shares_total_assets": a_shares_total_assets,
        "hk_shares_total_assets": hk_shares_total_assets,
        "a_shares_cash": a_shares_cash,
        "hk_shares_cash": hk_shares_cash,
        "total_market_value": total_market_value,
        "total_pnl": total_pnl,
        "hkd_cny_rate": hkd_cny_rate,
    }


@pytest.fixture
def db_session():
    """Create a database session for testing."""
    engine = get_engine()
    with Session(engine) as session:
        yield session


@pytest.fixture
def test_date():
    """Get the test date (latest date in reference data)."""
    # The CSV data is from a specific date, use today as default
    return date.today()


@pytest.fixture
def portfolio_id(db_session):
    """Get the first portfolio ID from database."""
    portfolio = db_session.exec(select(Portfolio)).first()
    if portfolio:
        return portfolio.id
    pytest.skip("No portfolio found in database")


@pytest.fixture
def reference_values():
    """Load reference values from CSV."""
    csv_path = Path(__file__).parent / "xueqiu_portfolio.csv"
    if not csv_path.exists():
        pytest.skip("Reference CSV file not found")
    return read_reference_values(csv_path)


class TestXueqiuPortfolio:
    """Test suite for xueqiu portfolio data validation."""

    @pytest.mark.parametrize(
        "key",
        [
            "a_shares_cumulative_pnl",
            "hk_shares_cumulative_pnl",
            "a_shares_total_assets",
            "hk_shares_total_assets",
            "a_shares_cash",
            "hk_shares_cash",
        ],
    )
    def test_value_matches_reference(self, db_session, portfolio_id, test_date, reference_values, key):
        """Test that the computed value matches the reference value from xueqiu.

        Reference values are xueqiu's display-rounded aggregates (2dp). Xueqiu
        rounds some amounts differently internally (e.g. a HK dividend of
        47682.855 is row-displayed as 47682.86 but its ledger can hold the
        unrounded value), so its displayed cash/total can differ from the sum
        of its own transaction records by up to 0.01. Allow that tolerance.
        """
        test_values = get_test_values(db_session, portfolio_id, test_date)
        assert abs(test_values[key] - reference_values[key]) <= Decimal("0.01")

    def test_total_market_value_calculation(self, db_session, portfolio_id, test_date):
        """Test total market value = A股总资产 + 港股总资产 * HKD/CNY汇率."""
        test_values = get_test_values(db_session, portfolio_id, test_date)

        expected_total = (
            test_values["a_shares_total_assets"]
            + test_values["hk_shares_total_assets"] * test_values["hkd_cny_rate"]
        )
        assert test_values["total_market_value"] == expected_total
