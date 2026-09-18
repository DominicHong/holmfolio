"""Asset model."""

from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from backend.db.utils import utcnow


class Asset(SQLModel, table=True):
    """Asset model for stocks, bonds, funds, etc."""

    id: int = Field(unique=True, primary_key=True)
    symbol: str = Field(unique=True, index=True)  # Ticker symbol
    name: str
    isin: str | None = None
    type: str  # stock, bond, fund, etf, cash, gold.
    currency_id: int = Field(foreign_key="currency.id")
    created_at: datetime = Field(default_factory=utcnow)

    @staticmethod
    def validate_type(value: str) -> None:
        """Validate that type is one of the allowed values."""
        allowed_types = {"stock", "bond", "fund", "etf", "cash", "gold"}
        if value not in allowed_types:
            raise ValueError(f"type must be one of {allowed_types}, got '{value}'")

    def __setattr__(self, name: str, value) -> None:
        """Override to validate type when it's set."""
        if name == "type":
            self.validate_type(value)
        super().__setattr__(name, value)

    # Relationships
    currency: "Currency" = Relationship()
    transactions: list["Transaction"] = Relationship(back_populates="asset")
    prices: list["Price"] = Relationship(
        back_populates="asset",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    asset_tags: list["AssetTag"] = Relationship(
        back_populates="asset",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    positions: list["Position"] = Relationship(
        back_populates="asset",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    stock_infos: list["StockInfo"] = Relationship(
        back_populates="asset",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
