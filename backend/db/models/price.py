"""Price model."""

from datetime import date
from decimal import Decimal
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import UniqueConstraint


class Price(SQLModel, table=True):
    """Price model for historical and real-time prices."""

    id: int = Field(unique=True, primary_key=True)
    asset_id: int = Field(foreign_key="asset.id", ondelete="CASCADE")
    price_date: date
    price: Decimal
    price_type: str  # real_time, historical, manual
    source: str | None = None  # akshare, manual, etc.
    # Optional OHLCV fields, used by daily-bar consumers such as gold strategies.
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    volume: Decimal | None = None
    amount: Decimal | None = None

    # Add unique constraint for asset_id and price_date
    __table_args__ = (
        UniqueConstraint("asset_id", "price_date", name="uq_price_asset_date"),
    )

    # Relationships
    asset: "Asset" = Relationship(back_populates="prices")
