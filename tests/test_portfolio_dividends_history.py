"""Tests for portfolio dividends aggregation and history-position flagging.

These tests cover the ``get_dividends_by_asset`` helper on PositionService
and the ``is_history`` / ``dividends`` / ``dividends_primary`` fields
populated by the ``GET /portfolios/{id}/positions`` endpoint.
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlmodel import Session

from backend.db.models import Asset, Currency, Position, Transaction
from backend.services.position import PositionService


@pytest.fixture
def history_test_data(test_db: Session):
    """Set up transactions that produce both open and closed positions.

    Uses the pre-initialized assets from the conftest ``test_db`` fixture:
        - 600036.SH (CNY stock): bought, dividend received, fully sold -> history
        - 510300.SH (CNY ETF): bought and still held -> current
    """
    cny = test_db._test_cny
    portfolio = test_db._test_portfolio
    stock = test_db._test_assets["600036.SH"]
    etf = test_db._test_assets["510300.SH"]
    cny_cash = test_db._test_assets["CNY_CASH"]

    txns = [
        # Seed cash
        Transaction(
            portfolio_id=portfolio.id,
            trade_date=date(2025, 1, 1),
            action="cash_in",
            asset_id=cny_cash.id,
            quantity=Decimal("100000"),
            price=Decimal("1"),
            amount=Decimal("100000"),
            fees=Decimal("0"),
            currency_id=cny.id,
            notes="seed",
        ),
        # Buy stock
        Transaction(
            portfolio_id=portfolio.id,
            trade_date=date(2025, 1, 5),
            action="buy",
            asset_id=stock.id,
            quantity=Decimal("1000"),
            price=Decimal("35.2"),
            amount=Decimal("35200"),
            fees=Decimal("5"),
            currency_id=cny.id,
            notes="buy stock",
        ),
        # Dividend on the stock (amount 100, fees 1 -> net 99)
        Transaction(
            portfolio_id=portfolio.id,
            trade_date=date(2025, 2, 7),
            action="dividends",
            asset_id=stock.id,
            quantity=Decimal("100"),
            price=Decimal("1"),
            amount=Decimal("100"),
            fees=Decimal("1"),
            currency_id=cny.id,
            notes="dividend",
        ),
        # Sell all stock -> becomes history
        Transaction(
            portfolio_id=portfolio.id,
            trade_date=date(2025, 2, 10),
            action="sell",
            asset_id=stock.id,
            quantity=Decimal("1000"),
            price=Decimal("36"),
            amount=Decimal("36000"),
            fees=Decimal("5"),
            currency_id=cny.id,
            notes="sell stock",
        ),
        # Buy ETF and keep it
        Transaction(
            portfolio_id=portfolio.id,
            trade_date=date(2025, 2, 12),
            action="buy",
            asset_id=etf.id,
            quantity=Decimal("10000"),
            price=Decimal("3.8"),
            amount=Decimal("38000"),
            fees=Decimal("5"),
            currency_id=cny.id,
            notes="buy etf",
        ),
    ]
    test_db.add_all(txns)
    test_db.commit()
    return portfolio, stock, etf, cny_cash


def test_get_dividends_by_asset_sums_net_amount(test_db: Session, history_test_data):
    """``get_dividends_by_asset`` sums (amount - fees) for dividends only."""
    portfolio, stock, etf, cny_cash = history_test_data
    service = PositionService(test_db)
    totals = service.get_dividends_by_asset(portfolio.id, date(2025, 12, 31))

    assert totals[stock.id] == Decimal("99")
    # ETF and cash have no dividends
    assert totals.get(etf.id, Decimal("0")) == Decimal("0")
    assert totals.get(cny_cash.id, Decimal("0")) == Decimal("0")


def test_get_dividends_by_asset_respects_end_date(test_db: Session, history_test_data):
    """Dividends after the end_date are excluded."""
    portfolio, stock, etf, cny_cash = history_test_data
    service = PositionService(test_db)
    # Cutoff before the dividend on 2025-02-07
    totals = service.get_dividends_by_asset(portfolio.id, date(2025, 2, 1))
    assert totals.get(stock.id, Decimal("0")) == Decimal("0")


def test_compute_period_end_positions_produces_history_position(
    test_db: Session, history_test_data
):
    """After selling all shares, the stock position has quantity=0."""
    portfolio, stock, etf, cny_cash = history_test_data
    service = PositionService(test_db)
    positions = service.compute_period_end_positions(
        portfolio_id=portfolio.id,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 3, 1),
        save_to_db=False,
    )

    stock_pos = positions[stock.id]
    assert float(stock_pos.quantity) == 0.0
    assert float(stock_pos.market_value) == 0.0
    # P&L should reflect the realized gain plus the dividend
    assert stock_pos.total_pnl is not None

    etf_pos = positions[etf.id]
    assert float(etf_pos.quantity) == 10000.0


def test_get_positions_on_date_returns_closed_position(test_db: Session, history_test_data):
    """Closed positions (quantity=0) are still saved on each date."""
    portfolio, stock, etf, cny_cash = history_test_data
    service = PositionService(test_db)
    # Calculate and save positions up to 2025-03-01
    service.compute_period_end_positions(
        portfolio_id=portfolio.id,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 3, 1),
        save_to_db=True,
    )
    fetched = service.get_positions_on_date(portfolio.id, date(2025, 3, 1))
    asset_ids = {p.asset_id for p in fetched}
    # The fully-sold stock must still appear with a saved position row
    assert stock.id in asset_ids
    stock_pos = next(p for p in fetched if p.asset_id == stock.id)
    assert float(stock_pos.quantity) == 0.0


def test_get_positions_endpoint_marks_history_and_dividends(test_db: Session, history_test_data):
    """The /portfolios/{id}/positions endpoint flags closed positions and
    attaches dividend totals (in asset and primary currency)."""
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.db import get_session

    portfolio, stock, etf, cny_cash = history_test_data
    service = PositionService(test_db)
    service.compute_period_end_positions(
        portfolio_id=portfolio.id,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 3, 1),
        save_to_db=True,
    )

    # Override the dependency to use the test session
    def override_get_session():
        yield test_db

    app.dependency_overrides[get_session] = override_get_session
    try:
        client = TestClient(app)
        resp = client.get(
            f"/api/v1/portfolios/{portfolio.id}/positions",
            params={"as_of_date": "2025-03-01"},
        )
        assert resp.status_code == 200
        data = resp.json()

        by_symbol = {p["symbol"]: p for p in data}

        # The fully-sold stock is flagged as history and carries its dividend
        stock_pos = by_symbol[stock.symbol]
        assert stock_pos["is_history"] is True
        assert stock_pos["quantity"] == 0.0
        assert stock_pos["dividends"] == 99.0
        # CNY is the primary currency, so dividends_primary equals dividends
        assert stock_pos["dividends_primary"] == 99.0

        # The still-held ETF is not history and has no dividends (0.0, not None,
        # so the frontend always renders the correct currency symbol)
        etf_pos = by_symbol[etf.symbol]
        assert etf_pos["is_history"] is False
        assert etf_pos["quantity"] == 10000.0
        assert etf_pos["dividends"] == 0.0
        assert etf_pos["dividends_primary"] == 0.0

        # Cash is never history
        cash_pos = by_symbol[cny_cash.symbol]
        assert cash_pos["is_history"] is False
    finally:
        app.dependency_overrides.pop(get_session, None)
