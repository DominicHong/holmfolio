"""Tests for multi-portfolio summaries and portfolio CRUD."""

from datetime import date
from decimal import Decimal

import pytest
from sqlmodel import select

from backend.db.models import Asset, Portfolio, Position, Price, Transaction
from backend.services.portfolio import PortfolioService
from backend.services.position import PositionService


@pytest.fixture
def multi_portfolio_data(test_db):
    """Create a second portfolio holding AU9999 alongside the main portfolio."""
    cny = test_db._test_cny
    main = test_db._test_portfolio
    assets = test_db._test_assets
    gold = Asset(
        symbol="AU9999.SHG",
        name="Gold Spot AU9999",
        type="gold",
        currency_id=cny.id,
    )
    test_db.add(gold)
    test_db.flush()

    second = Portfolio(
        name="AU9999 Test",
        description="Only AU9999 trades",
        base_currency_id=cny.id,
    )
    test_db.add(second)
    test_db.flush()

    prices = [
        (assets["CNY_CASH"].id, date(2025, 1, 1), Decimal("1")),
        (assets["600036.SH"].id, date(2025, 1, 2), Decimal("35")),
        (assets["600036.SH"].id, date(2025, 1, 5), Decimal("35.2")),
        (assets["600036.SH"].id, date(2025, 3, 10), Decimal("40")),
        (gold.id, date(2025, 1, 2), Decimal("621.99")),
        (gold.id, date(2025, 3, 3), Decimal("671.78")),
        (gold.id, date(2025, 3, 10), Decimal("680")),
    ]
    for asset_id, price_date, price in prices:
        test_db.add(
            Price(
                asset_id=asset_id,
                price_date=price_date,
                price=price,
                price_type="historical",
            )
        )

    transactions = [
        # Main portfolio: cash, stock, and a small gold holding.
        Transaction(
            portfolio_id=main.id,
            asset_id=assets["CNY_CASH"].id,
            action="cash_in",
            trade_date=date(2025, 1, 2),
            quantity=Decimal("50000"),
            price=Decimal("1"),
            amount=Decimal("50000"),
            fees=Decimal("0"),
            currency_id=cny.id,
        ),
        Transaction(
            portfolio_id=main.id,
            asset_id=assets["600036.SH"].id,
            action="buy",
            trade_date=date(2025, 1, 5),
            quantity=Decimal("1000"),
            price=Decimal("35.2"),
            amount=Decimal("35200"),
            fees=Decimal("0"),
            currency_id=cny.id,
        ),
        Transaction(
            portfolio_id=main.id,
            asset_id=gold.id,
            action="buy",
            trade_date=date(2025, 1, 2),
            quantity=Decimal("10"),
            price=Decimal("621.99"),
            amount=Decimal("6219.9"),
            fees=Decimal("0"),
            currency_id=cny.id,
        ),
        # Second portfolio: cash and AU9999 buy/sell only.
        Transaction(
            portfolio_id=second.id,
            asset_id=assets["CNY_CASH"].id,
            action="cash_in",
            trade_date=date(2025, 1, 2),
            quantity=Decimal("100000"),
            price=Decimal("1"),
            amount=Decimal("100000"),
            fees=Decimal("0"),
            currency_id=cny.id,
        ),
        Transaction(
            portfolio_id=second.id,
            asset_id=gold.id,
            action="buy",
            trade_date=date(2025, 1, 2),
            quantity=Decimal("100"),
            price=Decimal("621.99"),
            amount=Decimal("62199"),
            fees=Decimal("0"),
            currency_id=cny.id,
        ),
        Transaction(
            portfolio_id=second.id,
            asset_id=gold.id,
            action="sell",
            trade_date=date(2025, 3, 3),
            quantity=Decimal("40"),
            price=Decimal("671.78"),
            amount=Decimal("26871.2"),
            fees=Decimal("0"),
            currency_id=cny.id,
        ),
    ]
    test_db.add_all(transactions)
    test_db.commit()

    position_service = PositionService(test_db)
    end_date = date(2025, 3, 10)
    position_service.ensure_positions_calculated(main.id, end_date)
    position_service.ensure_positions_calculated(second.id, end_date)

    return {
        "main": main,
        "second": second,
        "gold": gold,
        "assets": assets,
        "end_date": end_date,
    }


def test_portfolio_summary_snapshot_and_combined_holdings(test_db, multi_portfolio_data):
    data = multi_portfolio_data
    summary = PortfolioService(test_db).get_portfolio_summary(data["end_date"])

    assert summary["portfolio_count"] == 2
    assert summary["asset_count"] == 2

    by_name = {item["name"]: item for item in summary["portfolios"]}
    main = by_name["Test Portfolio"]
    second = by_name["AU9999 Test"]

    # Main: 40000 stock + 6800 gold + 8580.10 cash = 55380.10
    assert main["total_value"] == pytest.approx(55380.10)
    assert main["total_pnl"] == pytest.approx(5380.10)
    assert main["cash_value"] == pytest.approx(8580.10)
    assert main["holding_count"] == 2
    assert main["first_transaction_date"] == date(2025, 1, 2)

    # Second: 40800 gold + 64672.20 cash = 105472.20
    assert second["total_value"] == pytest.approx(105472.20)
    assert second["total_pnl"] == pytest.approx(5472.20)
    assert second["cash_value"] == pytest.approx(64672.20)
    assert second["holding_count"] == 1

    assert summary["total_value"] == pytest.approx(160852.30)
    assert summary["total_pnl"] == pytest.approx(10852.30)
    assert summary["total_cash"] == pytest.approx(73252.30)

    # AU9999 is held in both portfolios: quantities share the same unit (grams)
    # and are aggregated, while the stock remains a separate row.
    holdings = {item["symbol"]: item for item in summary["combined_holdings"]}
    assert set(holdings) == {"600036.SH", "AU9999.SHG"}
    assert holdings["600036.SH"]["quantity"] == pytest.approx(1000)
    assert holdings["600036.SH"]["portfolio_count"] == 1
    assert holdings["AU9999.SHG"]["quantity"] == pytest.approx(70)
    assert holdings["AU9999.SHG"]["portfolio_count"] == 2
    assert holdings["AU9999.SHG"]["market_value_primary"] == pytest.approx(47600)

    # Allocation is still expressed as percentages of positive market value.
    allocation = summary["allocation_by_type"]
    assert allocation["stock"] == pytest.approx(40000 / 160852.30)
    assert allocation["gold"] == pytest.approx(47600 / 160852.30)


def test_summary_endpoint_route_and_payload(test_db, multi_portfolio_data):
    from fastapi.testclient import TestClient

    from backend.db import get_session
    from backend.main import app

    def override_get_session():
        yield test_db

    app.dependency_overrides[get_session] = override_get_session
    try:
        client = TestClient(app)
        response = client.get(
            "/api/v1/portfolios/summary",
            params={"as_of_date": multi_portfolio_data["end_date"].isoformat()},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["portfolio_count"] == 2
        assert payload["primary_currency"]["code"] == "CNY"
        assert len(payload["portfolios"]) == 2
        assert len(payload["combined_holdings"]) == 2
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_create_portfolio_defaults_to_primary_currency(test_db):
    from fastapi.testclient import TestClient

    from backend.db import get_session
    from backend.main import app

    def override_get_session():
        yield test_db

    app.dependency_overrides[get_session] = override_get_session
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/portfolios/",
            json={"name": "New Portfolio", "description": "created in test"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["name"] == "New Portfolio"
        assert payload["base_currency_id"] == test_db._test_cny.id
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_update_portfolio(test_db):
    from fastapi.testclient import TestClient

    from backend.db import get_session
    from backend.main import app

    portfolio = test_db._test_portfolio

    def override_get_session():
        yield test_db

    app.dependency_overrides[get_session] = override_get_session
    try:
        client = TestClient(app)
        response = client.put(
            f"/api/v1/portfolios/{portfolio.id}",
            json={"name": "Renamed", "description": "updated"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Renamed"
        assert response.json()["description"] == "updated"
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_delete_portfolio_removes_positions_and_transactions(
    test_db, multi_portfolio_data
):
    from fastapi.testclient import TestClient

    from backend.db import get_session
    from backend.main import app

    second = multi_portfolio_data["second"]

    def override_get_session():
        yield test_db

    app.dependency_overrides[get_session] = override_get_session
    try:
        client = TestClient(app)
        response = client.delete(f"/api/v1/portfolios/{second.id}")
        assert response.status_code == 200

        assert test_db.get(Portfolio, second.id) is None
        assert (
            test_db.exec(
                select(Position).where(Position.portfolio_id == second.id)
            ).first()
            is None
        )
        assert (
            test_db.exec(
                select(Transaction).where(Transaction.portfolio_id == second.id)
            ).first()
            is None
        )
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_recalculate_removes_positions_before_moved_first_transaction(
    test_db, multi_portfolio_data
):
    """Editing transactions so they start later must not inherit old positions.

    This reproduces the scenario where the original AU9999 test portfolio had
    transactions in 2025, then all transactions were edited/moved to
    2026-11-06. Recalculation must delete the old 2025 positions instead of
    using them as the initial state for the new transactions.
    """
    data = multi_portfolio_data
    second = data["second"]
    assets = data["assets"]
    cny = test_db._test_cny
    gold = data["gold"]

    old_positions = test_db.exec(
        select(Position)
        .where(Position.portfolio_id == second.id)
        .where(Position.position_date < date(2026, 11, 6))
    ).all()
    assert old_positions

    # Remove the original 2025 transactions and insert a new pair dated later,
    # mirroring the user's edit.
    old_transactions = test_db.exec(
        select(Transaction).where(Transaction.portfolio_id == second.id)
    ).all()
    for transaction in old_transactions:
        test_db.delete(transaction)

    test_db.add(
        Price(
            asset_id=gold.id,
            price_date=date(2026, 11, 6),
            price=Decimal("884.09"),
            price_type="historical",
        )
    )
    test_db.add(
        Transaction(
            portfolio_id=second.id,
            asset_id=assets["CNY_CASH"].id,
            action="cash_in",
            trade_date=date(2026, 11, 6),
            quantity=Decimal("5000000"),
            price=Decimal("1"),
            amount=Decimal("5000000"),
            fees=Decimal("0"),
            currency_id=cny.id,
        )
    )
    test_db.add(
        Transaction(
            portfolio_id=second.id,
            asset_id=gold.id,
            action="buy",
            trade_date=date(2026, 11, 6),
            quantity=Decimal("100"),
            price=Decimal("868.69"),
            amount=Decimal("86869"),
            fees=Decimal("0"),
            currency_id=cny.id,
        )
    )
    test_db.commit()

    result = PositionService(test_db).recalculate_positions_daily(
        second.id, date(2026, 11, 6)
    )
    assert result["days_processed"] == 1
    assert result["start_date"] == date(2026, 11, 6)

    # No stale positions before the new first transaction date.
    stale = test_db.exec(
        select(Position)
        .where(Position.portfolio_id == second.id)
        .where(Position.position_date < date(2026, 11, 6))
    ).all()
    assert stale == []

    latest = {
        position.asset_id: position
        for position in test_db.exec(
            select(Position)
            .where(Position.portfolio_id == second.id)
            .where(Position.position_date == date(2026, 11, 6))
        ).all()
    }
    gold_position = latest[gold.id]
    cash_position = latest[assets["CNY_CASH"].id]

    assert float(gold_position.quantity) == pytest.approx(100)
    assert float(gold_position.average_cost) == pytest.approx(868.69)
    assert float(gold_position.current_price) == pytest.approx(884.09)
    assert float(gold_position.market_value) == pytest.approx(88409)
    assert float(gold_position.total_pnl) == pytest.approx(1540)
    assert float(cash_position.quantity) == pytest.approx(4913131)


def test_recalculate_with_no_transactions_clears_positions(
    test_db, multi_portfolio_data
):
    second = multi_portfolio_data["second"]

    transactions = test_db.exec(
        select(Transaction).where(Transaction.portfolio_id == second.id)
    ).all()
    for transaction in transactions:
        test_db.delete(transaction)
    test_db.commit()

    result = PositionService(test_db).recalculate_positions_daily(
        second.id, date(2025, 3, 10)
    )
    assert result["days_processed"] == 0

    positions = test_db.exec(
        select(Position).where(Position.portfolio_id == second.id)
    ).all()
    assert positions == []


def test_cannot_delete_last_portfolio(test_db):
    from fastapi.testclient import TestClient

    from backend.db import get_session
    from backend.main import app

    portfolio = test_db._test_portfolio

    def override_get_session():
        yield test_db

    app.dependency_overrides[get_session] = override_get_session
    try:
        client = TestClient(app)
        response = client.delete(f"/api/v1/portfolios/{portfolio.id}")
        assert response.status_code == 400
        assert test_db.get(Portfolio, portfolio.id) is not None
    finally:
        app.dependency_overrides.pop(get_session, None)
