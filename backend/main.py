"""Main FastAPI application entry point."""

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone

from sqlmodel import Session, select

from backend.db import create_db_and_tables, get_engine
from backend.db.models import Portfolio
from backend.services.price_rate import PriceRateService
from backend.services.position import PositionService
from backend.services.gold import GoldService
from backend.api.v1.router import api_router
from backend import logger


def _ensure_prices_and_rates() -> None:
    """Backfill prices, exchange rates, and benchmark prices up to today."""
    with Session(get_engine()) as session:
        today = date.today()
        # THS only provides historical (end-of-day) data, so backfill up to yesterday
        end_date = today - timedelta(days=1)
        service = PriceRateService(session)
        service.backfill_from_latest(end_date)


def _ensure_gold_prices() -> None:
    """Incrementally update gold daily bars up to the last closed session.

    Network/SDK failures are logged and ignored so startup is never blocked.
    """
    try:
        with Session(get_engine()) as session:
            service = GoldService(session)
            result = service.update_prices()
        if result["added"]:
            logger.info(f"Gold price update complete: {result['added']} bars added")
        for error in result["errors"]:
            logger.warning(f"Gold price update error: {error}")
    except Exception as exc:  # noqa: BLE001 - gold updates must not block startup
        logger.error(f"Gold price update failed: {exc}")


def _ensure_positions() -> None:
    """Ensure positions are calculated up to today for all portfolios."""
    with Session(get_engine()) as session:
        today = date.today()
        portfolios = session.exec(select(Portfolio)).all()

        if not portfolios:
            logger.info("No portfolios found, skipping position check")
            return

        for portfolio in portfolios:
            logger.info(
                f"Ensuring positions for portfolio {portfolio.id} ({portfolio.name})"
            )
            service = PositionService(session)
            service.ensure_positions_calculated(portfolio.id, today)

        logger.info("Position check complete")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan manager for the FastAPI application."""
    create_db_and_tables()
    _ensure_prices_and_rates()
    _ensure_gold_prices()
    _ensure_positions()
    yield


app = FastAPI(
    title="Portfolio Tracker API",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all API routes
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc)}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
