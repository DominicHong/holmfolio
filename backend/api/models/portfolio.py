"""Portfolio API models."""

from datetime import date

from pydantic import BaseModel, Field

from backend.api.models.currency import CurrencyResponse


class PortfolioCreate(BaseModel):
    """Payload for creating a portfolio."""

    name: str = Field(min_length=1)
    description: str | None = None
    base_currency_id: int | None = None


class PortfolioUpdate(BaseModel):
    """Payload for updating a portfolio."""

    name: str | None = Field(default=None, min_length=1)
    description: str | None = None


class PortfolioSnapshotResponse(BaseModel):
    """Current snapshot for a single portfolio."""

    id: int
    name: str
    description: str | None = None
    total_value: float
    total_pnl: float
    cash_value: float
    holding_count: int
    value_weight: float
    first_transaction_date: date | None = None


class CombinedHoldingResponse(BaseModel):
    """A non-cash asset aggregated across all portfolios."""

    asset_id: int
    symbol: str
    name: str
    type: str
    currency_code: str
    currency_symbol: str
    quantity: float
    market_value: float
    market_value_primary: float
    total_pnl_primary: float
    portfolio_count: int


class PortfolioSummaryResponse(BaseModel):
    """Aggregate snapshot across all portfolios."""

    as_of_date: date
    primary_currency: CurrencyResponse
    portfolios: list[PortfolioSnapshotResponse]
    total_value: float
    total_pnl: float
    total_cash: float
    portfolio_count: int
    asset_count: int
    allocation_by_type: dict[str, float]
    combined_holdings: list[CombinedHoldingResponse]
