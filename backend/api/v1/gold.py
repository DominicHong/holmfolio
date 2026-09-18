"""Gold trading API endpoints."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from backend.db import get_session
from backend.services.gold import GoldService
from backend.strat.gold import DEFAULT_STRATEGY
from backend.api.models.gold import (
    GoldAssetResponse,
    GoldOverviewResponse,
    GoldSignalsResponse,
    UpdateGoldPricesResponse,
)

router = APIRouter()


@router.get("/assets", response_model=list[GoldAssetResponse])
def list_gold_assets(session: Session = Depends(get_session)):
    """List assets of type gold."""
    with GoldService(session) as service:
        return service.list_gold_assets()


@router.get("/signals", response_model=GoldSignalsResponse)
def get_gold_signals(
    asset_id: int,
    strategy: str = DEFAULT_STRATEGY,
    session: Session = Depends(get_session),
):
    """Get strategy signals and current model state for a gold asset."""
    try:
        with GoldService(session) as service:
            return service.get_signals(asset_id, strategy)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/overview", response_model=GoldOverviewResponse)
def get_gold_overview(
    portfolio_id: int,
    asset_id: int,
    strategy: str = DEFAULT_STRATEGY,
    start_date: date | None = None,
    end_date: date | None = None,
    session: Session = Depends(get_session),
):
    """Signals, model state and normalized NAV comparison for the gold page."""
    try:
        with GoldService(session) as service:
            asset = service.get_gold_asset(asset_id)
            if asset is None:
                raise HTTPException(status_code=404, detail="Gold asset not found")
            result = service.get_overview(
                portfolio_id, asset_id, strategy, start_date, end_date
            )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return {**result, "asset": asset}


@router.post("/update-prices", response_model=UpdateGoldPricesResponse)
def update_gold_prices(
    end: date | None = None,
    source: str = "auto",
    session: Session = Depends(get_session),
):
    """Incrementally update gold daily bars (iFinD SDK, HTTP fallback)."""
    if source not in ("auto", "sdk", "http"):
        raise HTTPException(status_code=400, detail="source must be auto, sdk or http")
    with GoldService(session) as service:
        return service.update_prices(end=end, source=source)
