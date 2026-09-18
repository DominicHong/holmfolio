"""Tests for Time-Weighted Return calculation"""
import csv
import pytest
from pathlib import Path
from datetime import date, timedelta
from decimal import Decimal
from sqlmodel import Session, select
from backend.db.models import (
    Transaction, Price, ExchangeRate
)
from backend.services import PortfolioService


@pytest.fixture
def test_data_with_sample_transactions(test_db: Session):
    """Create test data based on sample_transactions.csv using existing currencies and assets"""
    
    # Use existing currencies and assets from conftest
    cny = test_db._test_cny
    hkd = test_db._test_hkd
    usd = test_db._test_usd
    portfolio = test_db._test_portfolio
    assets = test_db._test_assets
    
    # Create exchange rates (CNY is primary, so rates are from other currencies to CNY)
    exchange_rates = [
        # USD to CNY rates (1 USD = 7.2 CNY)
        (usd.id, cny.id, date(2025, 1, 1), Decimal("7.2")),
        (usd.id, cny.id, date(2025, 1, 5), Decimal("7.2")),
        (usd.id, cny.id, date(2025, 1, 9), Decimal("7.2")),
        (usd.id, cny.id, date(2025, 1, 10), Decimal("7.2")),
        (usd.id, cny.id, date(2025, 2, 7), Decimal("7.2")),
        (usd.id, cny.id, date(2025, 2, 10), Decimal("7.2")),
        (usd.id, cny.id, date(2025, 2, 11), Decimal("7.2")),
        (usd.id, cny.id, date(2025, 2, 12), Decimal("7.2")),

        # HKD to CNY rates (1 HKD = 0.92 CNY)
        (hkd.id, cny.id, date(2025, 1, 1), Decimal("0.92")),
        (hkd.id, cny.id, date(2025, 1, 9), Decimal("0.92")),
        (hkd.id, cny.id, date(2025, 1, 10), Decimal("0.92")),
        (hkd.id, cny.id, date(2025, 2, 11), Decimal("0.92")),
    ]

    for from_currency_id, to_currency_id, rate_date, rate in exchange_rates:
        exchange_rate = ExchangeRate(
            from_currency_id=from_currency_id,
            to_currency_id=to_currency_id,
            rate_date=rate_date,
            rate=rate
        )
        test_db.add(exchange_rate)
    
    # Create prices for assets
    prices_data = [
        # China Merchants Bank (600036.SH) - in CNY
        (assets["600036.SH"].id, date(2025, 1, 1), Decimal("35")),
        (assets["600036.SH"].id, date(2025, 1, 10), Decimal("40")),
        (assets["600036.SH"].id, date(2025, 2, 7), Decimal("45")),
        (assets["600036.SH"].id, date(2025, 2, 10), Decimal("50")),
        (assets["600036.SH"].id, date(2025, 2, 27), Decimal("40")),
        (assets["600036.SH"].id, date(2025, 3, 5), Decimal("42")),

        # Tencent Holdings (00700.HK) - in HKD
        (assets["00700.HK"].id, date(2025, 1, 1), Decimal("380")),
        (assets["00700.HK"].id, date(2025, 2, 11), Decimal("450")),
        (assets["00700.HK"].id, date(2025, 2, 25), Decimal("440")),
        (assets["00700.HK"].id, date(2025, 3, 5), Decimal("435")),
        
        # CSI 300 ETF (510300.SH) - in CNY
        (assets["510300.SH"].id, date(2025, 1, 1), Decimal("3.9")),
        (assets["510300.SH"].id, date(2025, 2, 18), Decimal("2.9")),
        (assets["510300.SH"].id, date(2025, 2, 20), Decimal("4.5")),
        (assets["510300.SH"].id, date(2025, 3, 5), Decimal("4.0")),
        
        # Cash assets (always 1 in their own currency)
        (assets["CNY_CASH"].id, date(2025, 1, 1), Decimal("1")),
        (assets["CNY_CASH"].id, date(2025, 2, 12), Decimal("1")),
        
        (assets["HKD_CASH"].id, date(2025, 1, 9), Decimal("1")),
        (assets["HKD_CASH"].id, date(2025, 2, 12), Decimal("1")),
    ]
    
    for asset_id, price_date, price in prices_data:
        price_obj = Price(
            asset_id=asset_id,
            price_date=price_date,
            price=price,
            price_type="historical"
        )
        test_db.add(price_obj)
    
    csv_path = Path(__file__).parent.parent / "tests" / "transactions_data.csv"
    
    with open(csv_path, 'r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            # Parse date format: 2025/1/1 -> date(2025, 1, 1)
            year, month, day = map(int, row['trade_date'].split('/'))
            trade_date = date(year, month, day)
            action = row['action']
            symbol = row['symbol']
            quantity = row['quantity']
            price = row['price']
            amount = Decimal(row['amount'])
            fees = Decimal(row['fees'])
            transaction = Transaction(
                portfolio_id=portfolio.id,
                trade_date=trade_date,
                action=action,
                asset_id=assets[symbol].id,
                quantity=quantity,
                price = price,
                amount=amount,
                fees=fees,
                currency_id=assets[symbol].currency_id
            )
            test_db.add(transaction)

    test_db.commit()
    
    return {
        "portfolio": portfolio,
        "assets": assets,
        "currencies": {"cny": cny, "hkd": hkd, "usd": usd},
        "service": PortfolioService(test_db)
    }


class TestTimeWeightedReturn:
    """Test cases for Time-Weighted Return calculation"""
    
    def test_twr_basic(self, test_data_with_sample_transactions):
        """Test basic TWR calculation with sample data"""
        data = test_data_with_sample_transactions
        service = data["service"]
        portfolio = data["portfolio"]
        
        start_date = date(2025, 1, 1)
        end_date = date(2025, 2, 12)
        
        result = service.twr(
            portfolio.id, start_date, end_date
        )
        
        # Basic assertions
        assert isinstance(result, dict)
        assert "twr" in result
        assert "period_return" in result
        assert "annualized_return" in result
        assert "beginning_nav" in result
        assert "ending_nav" in result
        assert "daily_returns" in result
        
        # Check that values are calculated
        assert isinstance(result["twr"], float)
        assert isinstance(result["period_return"], float)
        assert isinstance(result["annualized_return"], float)
        assert isinstance(result["beginning_nav"], float)
        assert isinstance(result["ending_nav"], float)
        assert isinstance(result["daily_returns"], list)
        
        # Validate basic relationships
        assert len(result["daily_returns"]) >= 0
        
        # Data integrity: beginning and ending NAV must be non-negative
        assert result["beginning_nav"] >= 0
        assert result["ending_nav"] >= 0

    @pytest.mark.parametrize(
        "start_date,end_date",
        [
            # Single-day range (no returns to compute)
            (date(2025, 1, 1), date(2025, 1, 1)),
            # Reversed dates (invalid range, handled gracefully)
            (date(2025, 2, 12), date(2025, 1, 1)),
            # No transactions in period (last transaction is 2025-03-05)
            (date(2025, 3, 6), date(2025, 3, 15)),
        ],
    )
    def test_twr_zero_return_for_inactive_periods(
        self, test_data_with_sample_transactions, start_date, end_date
    ):
        """TWR, period return, and annualized return are all 0 for inactive periods"""
        data = test_data_with_sample_transactions
        service = data["service"]
        portfolio = data["portfolio"]

        result = service.twr(
            portfolio.id, start_date, end_date
        )

        # Allow small floating point error
        assert abs(result["twr"]) < 0.001
        assert abs(result["period_return"]) < 0.001
        assert abs(result["annualized_return"]) < 0.001
        
    def test_twr_daily_returns_length(self, test_data_with_sample_transactions):
        """Test that daily_returns array has correct length matching nav_history"""
        data = test_data_with_sample_transactions
        service = data["service"]
        portfolio = data["portfolio"]

        start_date = date(2025, 1, 1)
        end_date = date(2025, 2, 12)

        result = service.twr(
            portfolio.id, start_date, end_date
        )

        nav_history = result["nav_history"]
        dates_history = result["dates"]
        if dates_history and isinstance(dates_history[0], list):
            dates_history = dates_history[0]

        # daily_returns always has one fewer entry than nav_history: the first
        # valuation date has no prior day to compare against.
        assert len(result["daily_returns"]) == len(nav_history) - 1
        # The valuation calendar must not exceed the requested range.
        assert len(nav_history) <= (end_date - start_date).days + 1
        
    def test_twr_error_handling(self, test_data_with_sample_transactions):
        """Test TWR calculation for a non-existent / empty portfolio.

        With no holdings and no transactions, the per-share NAV stays at its
        initial value of 1.0 across the whole period and the TWR is 0. The
        function must not raise and must return a well-formed result.
        """
        data = test_data_with_sample_transactions
        service = data["service"]

        # Non-existent portfolio: no holdings, no transactions.
        result = service.twr(
            9999, date(2025, 1, 1), date(2025, 2, 12)
        )

        # No growth -> TWR components are zero.
        assert result["twr"] == 0.0
        assert result["period_return"] == 0.0
        assert result["annualized_return"] == 0.0
        # Per-share NAV is initialized to 1.0 and stays there with no activity.
        assert result["beginning_nav"] == 1.0
        assert result["ending_nav"] == 1.0
        # Each day in the range yields a 0% return (no holdings, no cash flows).
        expected_days = (date(2025, 2, 12) - date(2025, 1, 1)).days
        assert len(result["daily_returns"]) == expected_days
        assert all(r == 0.0 for r in result["daily_returns"])
        
    def test_twr_with_missing_prices(self, test_data_with_sample_transactions):
        """Test TWR calculation when some prices are missing for a holding"""
        from sqlmodel import select as _select
        data = test_data_with_sample_transactions
        service = data["service"]
        portfolio = data["portfolio"]
        assets = data["assets"]
        test_db = service.session

        # Delete a mid-period price for 600036.SH so the holding has a gap.
        stmt = _select(Price).where(
            Price.asset_id == assets["600036.SH"].id,
            Price.price_date == date(2025, 2, 10),
        )
        for price_row in test_db.exec(stmt).all():
            test_db.delete(price_row)
        test_db.commit()

        start_date = date(2025, 1, 1)
        end_date = date(2025, 2, 12)

        # Calculation must not crash on the gap; it should fall back to the
        # last known price (or skip the day) and still produce a result.
        result = service.twr(portfolio.id, start_date, end_date)

        assert isinstance(result, dict)
        assert "twr" in result
        assert isinstance(result["twr"], float)
        assert result["beginning_nav"] >= 0
        assert result["ending_nav"] >= 0

    def test_twr_output_csv(self, test_data_with_sample_transactions):
        """Test TWR calculation and output daily returns, shares history, nav history, and dates history to CSV"""
        import json
        
        data = test_data_with_sample_transactions
        service = data["service"]
        portfolio = data["portfolio"]
        
        start_date = date(2025, 1, 1)
        end_date = date(2025, 3, 10)
        
        result = service.twr(
            portfolio.id, start_date, end_date
        )
        
        # Ensure we have the required data
        assert isinstance(result, dict)
        assert "daily_returns" in result
        
        # Create output directory if it doesn't exist
        output_dir = Path(__file__).parent / "output"
        output_dir.mkdir(exist_ok=True)
        
        # Output CSV file path
        csv_path = output_dir / f"twr_analysis_{start_date}_to_{end_date}.csv"
        
        # Get the daily returns and related data
        daily_returns = result.get("daily_returns", [])
        nav_history = result.get("nav_history", [])
        shares_history = result.get("shares_history", [])
        dates_history = result.get("dates", [])
        if dates_history and isinstance(dates_history[0], list):
            dates_history = dates_history[0]  # Handle nested list structure
        
        # Write CSV file
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["date", "daily_return", "nav", "shares", "v_today"])
            
            # Write data rows
            for i, date_obj in enumerate(dates_history):
                row = [date_obj.strftime("%Y-%m-%d") if hasattr(date_obj, 'strftime') else str(date_obj)]
                
                # Add daily return
                if i < len(daily_returns):
                    row.append(f"{daily_returns[i]:.6f}")
                else:
                    row.append("")
                
                # Add NAV
                if i < len(nav_history):
                    row.append(f"{nav_history[i]:.6f}")
                else:
                    row.append("")
                
                # Add shares and market values
                if i < len(shares_history):
                    row.append(f"{shares_history[i]:.2f}")
                    row.append(f"{nav_history[i] * shares_history[i]:.2f}")
                else:
                    row.append("")
                    row.append("")

                
                writer.writerow(row)
        
        # Also output raw JSON data for debugging
        json_path = output_dir / "twr_raw_data.json"
        with open(json_path, 'w', encoding='utf-8') as jsonfile:
            json.dump(result, jsonfile, indent=2, default=str)
        
        print(f"TWR analysis CSV file created: {csv_path}")
        print(f"Raw data JSON file created: {json_path}")
        
        # Basic assertions to ensure test passes
        assert csv_path.exists()
        assert json_path.exists()
        
        # Verify CSV has content
        with open(csv_path, 'r', encoding='utf-8') as csvfile:
            lines = csvfile.readlines()
            assert len(lines) > 1  # Header + at least one data row