"""Shared test configuration for all test modules"""

import sys
from unittest.mock import MagicMock

# Mock the proprietary THS SDK only when it is not installed locally. Production
# tests marked with @pytest.mark.production require the real SDK and are skipped
# automatically when the mock is in effect.
try:
    import iFinDPy  # noqa: F401
    _IFINDPY_AVAILABLE = True
except ModuleNotFoundError:
    sys.modules["iFinDPy"] = MagicMock()
    _IFINDPY_AVAILABLE = False

import pytest
import tempfile
import os
from datetime import date
from decimal import Decimal
from sqlmodel import create_engine, SQLModel, Session
from backend.db.models import Currency, ExchangeRate, Portfolio, Asset


def pytest_collection_modifyitems(config, items):
    """Skip production-only tests when the real THS SDK is unavailable."""
    if _IFINDPY_AVAILABLE:
        return
    skip_prod = pytest.mark.skip(
        reason="iFinDPy not installed; production tests require the real THS SDK."
    )
    for item in items:
        if "production" in item.keywords:
            item.add_marker(skip_prod)


@pytest.fixture
def test_db():
    """Create a fresh test database for each test"""
    # Create a temporary file-based SQLite database
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    
    try:
        engine = create_engine(f"sqlite:///{db_path}")
        SQLModel.metadata.create_all(engine)
        
        with Session(engine) as session:
            # Initialize currencies with CNY as primary
            cny = Currency(code="CNY", name="Chinese Yuan", symbol="¥", is_primary=True)
            hkd = Currency(code="HKD", name="Hong Kong Dollar", symbol="HK$", is_primary=False)
            usd = Currency(code="USD", name="US Dollar", symbol="$", is_primary=False)
            
            session.add_all([cny, hkd, usd])
            session.flush()
            
            # Create portfolio with CNY as base currency
            portfolio = Portfolio(name="Test Portfolio", base_currency_id=cny.id)
            session.add(portfolio)
            session.flush()
            
            # Create basic assets
            assets = [
                Asset(symbol="600036.SH", name="China Merchants Bank", type="stock", currency_id=cny.id),
                Asset(symbol="00700.HK", name="Tencent Holdings", type="stock", currency_id=hkd.id),
                Asset(symbol="510300.SH", name="CSI 300 ETF", type="etf", currency_id=cny.id),
                Asset(symbol="CNY_CASH", name="Chinese Yuan Cash", type="cash", currency_id=cny.id),
                Asset(symbol="HKD_CASH", name="Hong Kong Dollar Cash", type="cash", currency_id=hkd.id),
                Asset(symbol="USD_CASH", name="US Dollar Cash", type="cash", currency_id=usd.id),
            ]
            
            for asset in assets:
                session.add(asset)
            session.flush()
            
            session.commit()
            
            # Store references for tests to use
            session._test_cny = cny
            session._test_hkd = hkd
            session._test_usd = usd
            session._test_portfolio = portfolio
            session._test_assets = {asset.symbol: asset for asset in assets}
            
            yield session
            
    finally:
        # Clean up - close the engine and remove the temporary file
        engine.dispose()
        os.close(db_fd)
        os.unlink(db_path)


@pytest.fixture
def setup_exchange_rates(test_db):
    """Setup exchange rates for HKD and USD to CNY."""
    cny = test_db._test_cny
    hkd = test_db._test_hkd
    usd = test_db._test_usd

    rates = [
        ExchangeRate(from_currency_id=hkd.id, to_currency_id=cny.id,
                     rate_date=date(2024, 1, 1), rate=Decimal("0.92")),
        ExchangeRate(from_currency_id=usd.id, to_currency_id=cny.id,
                     rate_date=date(2024, 1, 1), rate=Decimal("7.20")),
    ]
    for r in rates:
        test_db.add(r)
    test_db.commit()
    return rates


@pytest.fixture
def setup_assets(test_db):
    """Create test assets."""
    cny = test_db._test_cny
    hkd = test_db._test_hkd

    assets = [
        Asset(symbol="TECH1", name="Tech Stock 1", type="stock", currency_id=cny.id),
        Asset(symbol="TECH2", name="Tech Stock 2", type="stock", currency_id=cny.id),
        Asset(symbol="BANK1", name="Bank Stock 1", type="stock", currency_id=cny.id),
        Asset(symbol="BANK2", name="Bank Stock 2", type="stock", currency_id=hkd.id),
        Asset(symbol="CONS1", name="Consumer Stock 1", type="stock", currency_id=cny.id),
    ]
    for a in assets:
        test_db.add(a)
    test_db.commit()

    return {a.symbol: a for a in assets}
