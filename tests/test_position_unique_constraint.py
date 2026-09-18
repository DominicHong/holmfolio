"""Tests for Position unique constraint"""

import pytest
from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError
from datetime import date
from decimal import Decimal
from backend.db.models import Position, Asset, Portfolio, Currency


@pytest.fixture
def position_test_data(test_db: Session):
    """Get pre-initialized test data for position tests"""
    return test_db._test_cny, test_db._test_portfolio, test_db._test_assets["600036.SH"]


def test_position_unique_constraint(test_db: Session, position_test_data):
    """Test that Position unique constraint prevents duplicate entries"""
    # Get test data
    currency, portfolio, asset = position_test_data
    
    # Create a position
    position_date = date(2023, 1, 1)
    position1 = Position(
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        position_date=position_date,
        quantity=Decimal("100"),
        average_cost=Decimal("150.00"),
        current_price=Decimal("160.00"),
        market_value=Decimal("16000.00"),
        total_pnl=Decimal("1000.00")
    )
    
    test_db.add(position1)
    test_db.commit()
    
    # Try to create another position with the same portfolio_id, asset_id, and position_date
    position2 = Position(
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        position_date=position_date,
        quantity=Decimal("200"),
        average_cost=Decimal("155.00"),
        current_price=Decimal("165.00"),
        market_value=Decimal("33000.00"),
        total_pnl=Decimal("2000.00")
    )
    
    test_db.add(position2)
    
    # This should raise an IntegrityError due to the unique constraint
    with pytest.raises(IntegrityError):
        test_db.commit()


def test_position_different_dates_allowed(test_db: Session, position_test_data):
    """Test that positions with different dates are allowed"""
    # Get test data
    currency, portfolio, asset = position_test_data
    
    # Create a position
    position_date1 = date(2023, 1, 1)
    position1 = Position(
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        position_date=position_date1,
        quantity=Decimal("100"),
        average_cost=Decimal("150.00"),
        current_price=Decimal("160.00"),
        market_value=Decimal("16000.00"),
        total_pnl=Decimal("1000.00")
    )
    
    test_db.add(position1)
    test_db.commit()
    
    # Create another position with a different date
    position_date2 = date(2023, 1, 2)
    position2 = Position(
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        position_date=position_date2,
        quantity=Decimal("200"),
        average_cost=Decimal("155.00"),
        current_price=Decimal("165.00"),
        market_value=Decimal("33000.00"),
        total_pnl=Decimal("2000.00")
    )
    
    test_db.add(position2)
    # This should not raise an exception
    test_db.commit()
    
    # Verify both positions exist
    positions = test_db.exec(select(Position)).all()
    assert len(positions) == 2


def test_position_different_assets_allowed(test_db: Session, position_test_data):
    """Test that positions with different assets on the same date are allowed"""
    # Get test data
    currency, portfolio, asset = position_test_data
    
    # Create a position
    position_date = date(2023, 1, 1)
    position1 = Position(
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        position_date=position_date,
        quantity=Decimal("100"),
        average_cost=Decimal("150.00"),
        current_price=Decimal("160.00"),
        market_value=Decimal("16000.00"),
        total_pnl=Decimal("1000.00")
    )
    
    test_db.add(position1)
    test_db.commit()
    
    # Create another asset
    asset2 = Asset(symbol="GOOGL", name="Alphabet Inc.", type="stock", currency_id=currency.id)
    test_db.add(asset2)
    test_db.commit()
    test_db.refresh(asset2)
    
    # Create another position with a different asset
    position2 = Position(
        portfolio_id=portfolio.id,
        asset_id=asset2.id,
        position_date=position_date,
        quantity=Decimal("50"),
        average_cost=Decimal("2500.00"),
        current_price=Decimal("2600.00"),
        market_value=Decimal("130000.00"),
        total_pnl=Decimal("5000.00")
    )
    
    test_db.add(position2)
    # This should not raise an exception
    test_db.commit()
    
    # Verify both positions exist
    positions = test_db.exec(select(Position)).all()
    assert len(positions) == 2


def test_position_different_portfolios_allowed(test_db: Session, position_test_data):
    """Test that positions with different portfolios on the same date are allowed"""
    # Get test data
    currency, portfolio, asset = position_test_data
    
    # Create a position
    position_date = date(2023, 1, 1)
    position1 = Position(
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        position_date=position_date,
        quantity=Decimal("100"),
        average_cost=Decimal("150.00"),
        current_price=Decimal("160.00"),
        market_value=Decimal("16000.00"),
        total_pnl=Decimal("1000.00")
    )
    
    test_db.add(position1)
    test_db.commit()
    
    # Create another portfolio
    portfolio2 = Portfolio(name="Test Portfolio 2", base_currency_id=currency.id)
    test_db.add(portfolio2)
    test_db.commit()
    test_db.refresh(portfolio2)
    
    # Create another position with a different portfolio
    position2 = Position(
        portfolio_id=portfolio2.id,
        asset_id=asset.id,
        position_date=position_date,
        quantity=Decimal("200"),
        average_cost=Decimal("155.00"),
        current_price=Decimal("165.00"),
        market_value=Decimal("33000.00"),
        total_pnl=Decimal("2000.00")
    )
    
    test_db.add(position2)
    # This should not raise an exception
    test_db.commit()
    
    # Verify both positions exist
    positions = test_db.exec(select(Position)).all()
    assert len(positions) == 2