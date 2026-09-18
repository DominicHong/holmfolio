"""Currency API endpoints."""

from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select

from backend.db import get_session
from backend.db.models import Currency, ExchangeRate

router = APIRouter()


@router.get("/", response_model=list[Currency])
def get_currencies(session: Session = Depends(get_session)):
    """Get all currencies."""
    currencies = session.exec(select(Currency)).all()
    return currencies


@router.post("/", response_model=Currency)
def create_currency(currency: Currency, session: Session = Depends(get_session)):
    """Create a new currency."""
    session.add(currency)
    session.commit()
    session.refresh(currency)
    return currency


@router.get("/{currency_id}", response_model=Currency)
def get_currency(currency_id: int, session: Session = Depends(get_session)):
    """Get a specific currency."""
    currency = session.get(Currency, currency_id)
    if not currency:
        raise HTTPException(status_code=404, detail="Currency not found")
    return currency


# Exchange Rate endpoints
@router.get("/exchange-rates/", response_model=list[ExchangeRate])
def get_exchange_rates(session: Session = Depends(get_session)):
    """Get all exchange rates."""
    rates = session.exec(select(ExchangeRate)).all()
    return rates


@router.post("/exchange-rates/", response_model=ExchangeRate)
def create_exchange_rate(rate: ExchangeRate, session: Session = Depends(get_session)):
    """Create a new exchange rate."""
    session.add(rate)
    session.commit()
    session.refresh(rate)
    return rate
