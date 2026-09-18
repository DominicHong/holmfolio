"""Position API models."""

from datetime import date
from pydantic import BaseModel
from backend.api.models.currency import CurrencyResponse


class PositionResponse(BaseModel):
    """Position response model."""

    id: int
    portfolio_id: int
    asset_id: int
    symbol: str
    name: str
    quantity: float
    average_cost: float
    current_price: float | None
    market_value: float | None
    market_value_primary: float | None
    total_pnl: float | None
    total_pnl_primary: float | None
    position_date: date
    currency: CurrencyResponse | None
    dividends: float | None = None
    dividends_primary: float | None = None
    is_history: bool = False


class DividendPositionResponse(BaseModel):
    """Position response with dividend information."""

    symbol: str
    name: str
    current_price: float | None
    dividend_after_tax: float
    dividend_yield: float | None
    currency: CurrencyResponse | None


class FinancialPositionResponse(BaseModel):
    """Position response with dividend and financial information."""

    symbol: str
    name: str
    current_price: float | None
    dividend_after_tax: float
    dividend_yield: float | None
    pe: float | None
    pb: float | None
    currency: CurrencyResponse | None
