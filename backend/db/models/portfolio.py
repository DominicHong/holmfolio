"""Portfolio and Position models."""

from datetime import date, datetime
from decimal import Decimal
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import UniqueConstraint
from backend.db.utils import utcnow


class Portfolio(SQLModel, table=True):
    """Portfolio model for portfolio statistics."""

    id: int = Field(primary_key=True)
    name: str
    description: str | None = None
    base_currency_id: int = Field(foreign_key="currency.id")
    created_at: datetime = Field(default_factory=utcnow)

    # Relationships
    base_currency: "Currency" = Relationship()
    transactions: list["Transaction"] = Relationship(back_populates="portfolio")
    positions: list["Position"] = Relationship(back_populates="portfolio")


class Position(SQLModel, table=True):
    """Asset Position model for a portfolio on a specific date."""

    id: int = Field(unique=True, primary_key=True)
    portfolio_id: int = Field(foreign_key="portfolio.id")
    asset_id: int = Field(foreign_key="asset.id", ondelete="CASCADE")
    position_date: date  # The specific date this position is for
    quantity: Decimal
    average_cost: Decimal
    current_price: Decimal | None = None
    market_value: Decimal | None = None
    total_pnl: Decimal | None = None  # market_value + cash_received_on_sale + dividends_received - cash_paid_on_bought

    # Add unique constraint for portfolio_id, position_date and asset_id
    __table_args__ = (
        UniqueConstraint(
            "portfolio_id", "position_date", "asset_id", name="uq_position_date_asset"
        ),
    )

    # Relationships
    portfolio: "Portfolio" = Relationship(back_populates="positions")
    asset: "Asset" = Relationship(back_populates="positions")
