"""Price update API models."""

from datetime import date
from pydantic import BaseModel, Field


class UpdatePricesRequest(BaseModel):
    """Request model for updating prices and rates."""

    end_date: date = Field(
        default_factory=date.today, description="End date for fetching prices and rates"
    )


class UpdatePricesResponse(BaseModel):
    """Response model for updating prices and rates."""

    success: bool
    message: str
    prices_added: int = 0
    rates_added: int = 0
    benchmark_prices_added: int = 0
    errors: list[str] = []
