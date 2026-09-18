"""Currency API models."""

from pydantic import BaseModel


class CurrencyResponse(BaseModel):
    """Currency response model."""

    id: int
    code: str
    name: str
    symbol: str
    is_primary: bool
