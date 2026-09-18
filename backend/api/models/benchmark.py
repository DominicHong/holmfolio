"""Benchmark API models."""

from datetime import date
from pydantic import BaseModel


class BenchmarkComponentResponse(BaseModel):
    """Benchmark component response model."""

    id: int
    component_benchmark_id: int
    weight: float


class BenchmarkResponse(BaseModel):
    """Benchmark response model."""

    id: int
    symbol: str
    name: str
    description: str | None = None
    is_composite: bool
    components: list[BenchmarkComponentResponse] | None = None


class BenchmarkPriceResponse(BaseModel):
    """Benchmark price response model."""

    id: int
    benchmark_id: int
    price_date: date
    close: float
    source: str | None = None
