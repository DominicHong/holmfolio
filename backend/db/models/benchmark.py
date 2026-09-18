"""Benchmark models."""

from datetime import date
from decimal import Decimal
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import UniqueConstraint


class Benchmark(SQLModel, table=True):
    """Benchmark index model for performance comparison."""

    id: int = Field(unique=True, primary_key=True)
    symbol: str = Field(unique=True, index=True)
    name: str
    description: str | None = None
    is_composite: bool = Field(default=False)

    # Relationships
    prices: list["BenchmarkPrice"] = Relationship(back_populates="benchmark")
    components: list["BenchmarkComponent"] = Relationship(
        back_populates="composite_benchmark",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "foreign_keys": "BenchmarkComponent.composite_benchmark_id",
        },
    )


class BenchmarkPrice(SQLModel, table=True):
    """Historical prices for benchmark indices."""

    id: int = Field(unique=True, primary_key=True)
    benchmark_id: int = Field(foreign_key="benchmark.id")
    price_date: date
    close: Decimal
    source: str | None = None  # ths, akshare, manual, etc.

    __table_args__ = (
        UniqueConstraint("benchmark_id", "price_date", name="uq_benchmark_price_date"),
    )

    # Relationships
    benchmark: Benchmark = Relationship(back_populates="prices")


class BenchmarkComponent(SQLModel, table=True):
    """Components of a composite benchmark with weights."""

    id: int = Field(unique=True, primary_key=True)
    composite_benchmark_id: int = Field(foreign_key="benchmark.id")
    component_benchmark_id: int = Field(foreign_key="benchmark.id")
    weight: Decimal

    # Relationships
    composite_benchmark: Benchmark = Relationship(
        back_populates="components",
        sa_relationship_kwargs={"foreign_keys": "BenchmarkComponent.composite_benchmark_id"},
    )
