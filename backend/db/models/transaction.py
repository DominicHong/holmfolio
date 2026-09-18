"""Transaction model."""

from datetime import date, datetime
from decimal import Decimal
from sqlmodel import SQLModel, Field, Relationship
from backend.db.utils import utcnow


class Transaction(SQLModel, table=True):
    """Transaction model for all portfolio transactions."""

    id: int = Field(unique=True, primary_key=True)
    portfolio_id: int = Field(foreign_key="portfolio.id")
    trade_date: date
    action: str  # buy, sell, cash_in, cash_out, tax, dividends, split, interest
    asset_id: int = Field(foreign_key="asset.id")  # Required for all transactions
    quantity: Decimal | None = None
    price: Decimal | None = None
    amount: Decimal
    fees: Decimal | None = Field(default=0)
    currency_id: int = Field(foreign_key="currency.id")
    notes: str | None = None
    created_at: datetime = Field(default_factory=utcnow)

    # Relationships
    portfolio: "Portfolio" = Relationship()
    asset: "Asset" = Relationship(back_populates="transactions")
    currency: "Currency" = Relationship(back_populates="transactions")
