"""StockInfo model for storing stock financial data."""

from datetime import date, datetime
from sqlmodel import SQLModel, Field, Relationship
from backend.db.utils import utcnow


class StockInfo(SQLModel, table=True):
    """Stock financial information, only for stock-type assets.

    Stores financial indicators fetched from THSDataSource for a given query date.
    """

    id: int = Field(unique=True, primary_key=True)
    asset_id: int = Field(foreign_key="asset.id", ondelete="CASCADE")
    symbol: str
    report_date: date  # the query/as_of date
    dividend_before_tax: float = 0.0
    dividend_after_tax: float = 0.0
    total_shares: float = 0.0
    ni_to_parent: float = 0.0  # 归属于母公司的净利润
    equity_to_parent: float = 0.0  # 归属于母公司的股东权益
    created_at: datetime = Field(default_factory=utcnow)

    # Relationships
    asset: "Asset" = Relationship(back_populates="stock_infos")
