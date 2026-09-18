"""Benchmark API endpoints."""

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from backend.db import get_session
from backend.db.models import Benchmark, BenchmarkPrice, BenchmarkComponent
from backend.api.models import BenchmarkResponse, BenchmarkPriceResponse, BenchmarkComponentResponse
from backend.services.calculation import CalculationService

router = APIRouter()


def _build_benchmark_response(benchmark: Benchmark) -> dict:
    """Build benchmark response dict with components."""
    return {
        "id": benchmark.id,
        "symbol": benchmark.symbol,
        "name": benchmark.name,
        "description": benchmark.description,
        "is_composite": benchmark.is_composite,
        "components": [
            BenchmarkComponentResponse(
                id=c.id,
                component_benchmark_id=c.component_benchmark_id,
                weight=float(c.weight),
            )
            for c in (benchmark.components or [])
        ] if benchmark.is_composite else None,
    }


def _validate_components(session: Session, benchmark_id: int, components_data: list[dict]) -> None:
    """Validate component weights sum to 1.0 and references are valid."""
    if not components_data:
        raise HTTPException(status_code=400, detail="Composite benchmark must have at least one component")

    total_weight = sum(Decimal(str(c["weight"])) for c in components_data)
    if abs(total_weight - Decimal("1.0")) > Decimal("0.0001"):
        raise HTTPException(
            status_code=400,
            detail=f"Component weights must sum to 1.0, got {float(total_weight):.4f}"
        )

    seen_ids: set[int] = set()
    for c in components_data:
        component_id = c["component_benchmark_id"]
        if component_id in seen_ids:
            raise HTTPException(status_code=400, detail=f"Duplicate component benchmark {component_id}")
        seen_ids.add(component_id)

        if component_id == benchmark_id:
            raise HTTPException(status_code=400, detail="Benchmark cannot reference itself as a component")
        component = session.get(Benchmark, component_id)
        if not component:
            raise HTTPException(status_code=400, detail=f"Component benchmark {component_id} not found")
        if component.is_composite:
            raise HTTPException(status_code=400, detail=f"Component benchmark {component_id} is a composite benchmark")


@router.get("/", response_model=list[BenchmarkResponse])
def get_benchmarks(session: Session = Depends(get_session)):
    """Get all available benchmarks."""
    benchmarks = session.exec(
        select(Benchmark).options(selectinload(Benchmark.components))
    ).all()
    return [_build_benchmark_response(b) for b in benchmarks]


@router.get("/{benchmark_id}", response_model=BenchmarkResponse)
def get_benchmark(benchmark_id: int, session: Session = Depends(get_session)):
    """Get a specific benchmark by ID."""
    benchmark = session.exec(
        select(Benchmark).where(Benchmark.id == benchmark_id).options(selectinload(Benchmark.components))
    ).first()
    if not benchmark:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    return _build_benchmark_response(benchmark)


@router.post("/", response_model=BenchmarkResponse)
def create_benchmark(benchmark_data: dict, session: Session = Depends(get_session)):
    """Create a new benchmark."""
    components_data = benchmark_data.pop("components", [])
    is_composite = benchmark_data.get("is_composite", False)

    if not is_composite and components_data:
        raise HTTPException(status_code=400, detail="Cannot add components to a non-composite benchmark")

    benchmark = Benchmark(**benchmark_data)
    session.add(benchmark)
    session.commit()
    session.refresh(benchmark)

    if is_composite and components_data:
        _validate_components(session, benchmark.id, components_data)
        for c in components_data:
            component = BenchmarkComponent(
                composite_benchmark_id=benchmark.id,
                component_benchmark_id=c["component_benchmark_id"],
                weight=Decimal(str(c["weight"])),
            )
            session.add(component)
        session.commit()
        session.refresh(benchmark)

    return _build_benchmark_response(benchmark)


@router.put("/{benchmark_id}", response_model=BenchmarkResponse)
def update_benchmark(benchmark_id: int, benchmark_data: dict, session: Session = Depends(get_session)):
    """Update an existing benchmark."""
    db_benchmark = session.exec(
        select(Benchmark).where(Benchmark.id == benchmark_id).options(selectinload(Benchmark.components))
    ).first()
    if not db_benchmark:
        raise HTTPException(status_code=404, detail="Benchmark not found")

    components_data = benchmark_data.pop("components", None)

    # Update scalar fields
    for key, value in benchmark_data.items():
        if key != "id":
            setattr(db_benchmark, key, value)

    # If benchmark is no longer composite, remove all components
    if not db_benchmark.is_composite and db_benchmark.components:
        for c in list(db_benchmark.components):
            session.delete(c)
        session.commit()
        session.refresh(db_benchmark)

    # Update components if provided for a composite benchmark
    if components_data is not None and db_benchmark.is_composite:
        # Delete existing components
        for c in list(db_benchmark.components):
            session.delete(c)
        session.commit()
        session.refresh(db_benchmark)

        if components_data:
            _validate_components(session, benchmark_id, components_data)
            for c in components_data:
                new_component = BenchmarkComponent(
                    composite_benchmark_id=benchmark_id,
                    component_benchmark_id=c["component_benchmark_id"],
                    weight=Decimal(str(c["weight"])),
                )
                session.add(new_component)
            session.commit()
            session.refresh(db_benchmark)

    return _build_benchmark_response(db_benchmark)


@router.delete("/{benchmark_id}")
def delete_benchmark(benchmark_id: int, session: Session = Depends(get_session)):
    """Delete a benchmark."""
    benchmark = session.get(Benchmark, benchmark_id)
    if not benchmark:
        raise HTTPException(status_code=404, detail="Benchmark not found")

    session.delete(benchmark)
    session.commit()
    return {"message": "Benchmark deleted successfully"}


@router.get("/{benchmark_id}/prices", response_model=list[BenchmarkPriceResponse])
def get_benchmark_prices(
    benchmark_id: int,
    start_date: str | None = None,
    end_date: str | None = None,
    session: Session = Depends(get_session)
):
    """Get prices for a benchmark within a date range."""
    benchmark = session.get(Benchmark, benchmark_id)
    if not benchmark:
        raise HTTPException(status_code=404, detail="Benchmark not found")

    s_date = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else date(1970, 1, 1)
    e_date = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else date(2099, 12, 31)

    calc_service = CalculationService(session)
    prices = calc_service._get_benchmark_prices(benchmark_id, s_date, e_date)
    return [
        BenchmarkPriceResponse(
            id=p.id,
            benchmark_id=p.benchmark_id,
            price_date=p.price_date,
            close=float(p.close),
            source=p.source,
        )
        for p in prices
    ]


@router.post("/{benchmark_id}/prices", response_model=BenchmarkPriceResponse)
def add_benchmark_price(
    benchmark_id: int,
    price: BenchmarkPrice,
    session: Session = Depends(get_session)
):
    """Add a price record for a benchmark."""
    benchmark = session.get(Benchmark, benchmark_id)
    if not benchmark:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    if benchmark.is_composite:
        raise HTTPException(status_code=400, detail="Cannot add price to a composite benchmark")

    price.benchmark_id = benchmark_id
    session.add(price)
    session.commit()
    session.refresh(price)
    return price


@router.delete("/{benchmark_id}/prices/{price_id}")
def delete_benchmark_price(
    benchmark_id: int,
    price_id: int,
    session: Session = Depends(get_session)
):
    """Delete a benchmark price record."""
    price = session.get(BenchmarkPrice, price_id)
    if not price or price.benchmark_id != benchmark_id:
        raise HTTPException(status_code=404, detail="Price record not found")

    session.delete(price)
    session.commit()
    return {"message": "Price record deleted successfully"}
