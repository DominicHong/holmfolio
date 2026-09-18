"""Transaction API models."""

from datetime import date, datetime
from pydantic import BaseModel
from backend.api.models.currency import CurrencyResponse


class TransactionResponse(BaseModel):
    """Transaction response model."""

    id: int
    portfolio_id: int
    trade_date: date
    action: str
    asset_id: int
    quantity: float | None
    price: float | None
    amount: float
    fees: float | None
    currency_id: int
    notes: str | None
    created_at: datetime
    currency: CurrencyResponse | None


class CheckDividendsRequest(BaseModel):
    """Request model for checking missing dividends."""

    portfolio_id: int


class MissingDividendItem(BaseModel):
    """A dividend detected during a holding period but missing from transactions."""

    asset_id: int
    symbol: str
    name: str
    record_date: date
    received_date: date
    report_date: str | None
    per_share: float
    quantity: float
    amount: float
    currency_id: int
    currency: str
    holding_start: date
    holding_end: date
    scheme: str | None
    notes: str | None


class CheckDividendsResponse(BaseModel):
    """Response model for the dividend check."""

    assets_checked: int
    dividend_events_found: int
    missing: list[MissingDividendItem]


class AddDividendsRequest(BaseModel):
    """Request model for adding missing dividend transactions."""

    portfolio_id: int
    items: list[MissingDividendItem]


class AddDividendsResponse(BaseModel):
    """Response model after backfilling missing dividends."""

    added: int
    positions_recalculated: bool
