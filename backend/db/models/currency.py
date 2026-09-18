"""Currency and Exchange Rate models."""

from datetime import date
from decimal import Decimal
from sqlmodel import SQLModel, Field, Relationship, Index
from sqlalchemy import UniqueConstraint, text


class Currency(SQLModel, table=True):
    """Currency model for multi-currency support."""

    id: int = Field(unique=True, primary_key=True)
    code: str = Field(unique=True, index=True)  # CNY, USD, HKD, etc.
    name: str
    symbol: str  # ¥, $, HK$, etc.
    is_primary: bool = Field(default=False)

    # Ensure only one currency can be primary
    __table_args__ = (
        Index(
            "uq_currency_is_primary",
            "is_primary",
            unique=True,
            sqlite_where=text("is_primary = 1"),
        ),
    )

    # Relationships
    exchange_rates_from: list["ExchangeRate"] = Relationship(
        back_populates="from_currency",
        sa_relationship_kwargs={"foreign_keys": "ExchangeRate.from_currency_id"},
    )
    exchange_rates_to: list["ExchangeRate"] = Relationship(
        back_populates="to_currency",
        sa_relationship_kwargs={"foreign_keys": "ExchangeRate.to_currency_id"},
    )
    transactions: list["Transaction"] = Relationship(back_populates="currency")


class ExchangeRate(SQLModel, table=True):
    """Exchange rate model for currency pair conversion.

    rate represents: 1 unit of from_currency = rate units of to_currency
    Example: USD/CNY = 7.0 means 1 USD = 7.0 CNY
    """

    id: int = Field(unique=True, primary_key=True)
    from_currency_id: int = Field(foreign_key="currency.id")
    to_currency_id: int = Field(foreign_key="currency.id")
    rate_date: date
    rate: Decimal  # Exchange rate: 1 from_currency = rate to_currency
    source: str | None = None  # Data source (e.g., 'akshare', 'sample')

    # Unique constraint for currency pair and date
    __table_args__ = (
        UniqueConstraint(
            "from_currency_id",
            "to_currency_id",
            "rate_date",
            name="uq_exchange_rate_pair_date",
        ),
    )

    # Relationships
    from_currency: Currency = Relationship(
        back_populates="exchange_rates_from",
        sa_relationship_kwargs={"foreign_keys": "ExchangeRate.from_currency_id"},
    )
    to_currency: Currency = Relationship(
        back_populates="exchange_rates_to",
        sa_relationship_kwargs={"foreign_keys": "ExchangeRate.to_currency_id"},
    )
