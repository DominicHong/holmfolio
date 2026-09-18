"""
Test cases for PriceService
"""

import pytest
from datetime import date
from decimal import Decimal
from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError

# 使用绝对导入，避免sys.path操作
from backend.db.models import Asset, Price, Currency
from backend.services import PriceService


@pytest.fixture
def price_test_data(test_db: Session):
    """Set up test data for price service tests"""
    # Use pre-initialized asset and currency
    asset = test_db._test_assets["600036.SH"]
    
    # Add test price for 2025-6-30
    price = Price(
        asset_id=asset.id,
        price_date=date(2025, 6, 30),
        price=Decimal("45.95"),
        price_type="historical",
        source="test"
    )
    test_db.add(price)
    test_db.commit()
    test_db.refresh(price)
    
    return asset, price


class TestPriceService:
    """Test cases for PriceService"""
    
    def test_get_latest_price(self, test_db: Session, price_test_data):
        """Test get_latest_price method returns correct price"""
        # Get the asset
        asset, price = price_test_data
        
        # Create PriceService instance
        price_service = PriceService(test_db)
        
        # Get latest price for 2025-6-30
        retrieved_price = price_service.get_latest_price(asset.id, date(2025, 6, 30))
        
        # Verify the price
        assert retrieved_price is not None, "Price should not be None"
        assert retrieved_price.price == Decimal("45.95"), f"Expected price 45.95, got {retrieved_price.price}"
        assert retrieved_price.price_date == date(2025, 6, 30), f"Expected date 2025-06-30, got {retrieved_price.price_date}"
    
    def test_unique_constraint(self, test_db: Session, price_test_data):
        """Test that unique constraint prevents duplicate prices for same asset and date"""
        # Get the asset
        asset, price = price_test_data
        
        # Try to insert a duplicate price
        duplicate_price = Price(
            asset_id=asset.id,
            price_date=date(2025, 6, 30),  # Same date as existing price
            price=Decimal("50.00"),
            price_type="historical",
            source="test_duplicate"
        )
        
        # Add the duplicate price
        test_db.add(duplicate_price)
        
        # Check that committing raises an IntegrityError
        with pytest.raises(IntegrityError):
            test_db.commit()
        
        # Refresh the session
        test_db.rollback()
        
        # Verify that the duplicate price was not added
        prices = test_db.exec(
            select(Price).where(
                Price.asset_id == asset.id,
                Price.price_date == date(2025, 6, 30)
            )
        ).all()
        
        # Should only have one price
        assert len(prices) == 1, f"Expected 1 price, got {len(prices)}"
        assert prices[0].price == Decimal("45.95"), f"Expected price 45.95, got {prices[0].price}"