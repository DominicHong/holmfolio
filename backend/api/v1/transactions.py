"""Transaction API endpoints."""

from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select

from backend.db import get_session
from backend.db.models import Transaction, Asset, Currency
from backend.api.models import (
    TransactionResponse,
    CurrencyResponse,
    AddDividendsRequest,
    AddDividendsResponse,
    CheckDividendsRequest,
    CheckDividendsResponse,
)
from backend.services.dividend_check import DividendCheckService

router = APIRouter()


@router.post("/check-dividends", response_model=CheckDividendsResponse)
def check_dividends(data: CheckDividendsRequest, session: Session = Depends(get_session)):
    """Check held assets for dividends that were never recorded as transactions.

    For each asset ever held, the dividend history is compared against the
    recorded ``dividends`` transactions; unrecorded dividends that occurred
    during holding periods are returned as candidates.
    """
    with DividendCheckService(session) as service:
        return service.check_missing_dividends(data.portfolio_id)


@router.post("/add-dividends", response_model=AddDividendsResponse)
def add_dividends(data: AddDividendsRequest, session: Session = Depends(get_session)):
    """Insert the given dividend transactions and recalculate positions up to today."""
    with DividendCheckService(session) as service:
        return service.add_missing_dividends(
            data.portfolio_id, [item.model_dump() for item in data.items]
        )


@router.get("/", response_model=list[TransactionResponse])
def get_transactions(portfolio_id: int, session: Session = Depends(get_session)):
    """Get all transactions for a specific portfolio."""
    query = (
        select(Transaction)
        .where(Transaction.portfolio_id == portfolio_id)
        .order_by(Transaction.trade_date.desc())
    )

    transactions = session.exec(query).all()

    transactions_with_currency = []
    for transaction in transactions:
        asset = session.get(Asset, transaction.asset_id)
        currency = session.get(Currency, transaction.currency_id)

        currency_data = None
        if currency:
            currency_data = CurrencyResponse(
                id=currency.id,
                code=currency.code,
                name=currency.name,
                symbol=currency.symbol,
                is_primary=currency.is_primary
            )

        transaction_data = TransactionResponse(
            id=transaction.id,
            portfolio_id=transaction.portfolio_id,
            trade_date=transaction.trade_date,
            action=transaction.action,
            asset_id=transaction.asset_id,
            quantity=float(transaction.quantity) if transaction.quantity else None,
            price=float(transaction.price) if transaction.price else None,
            amount=float(transaction.amount),
            fees=float(transaction.fees) if transaction.fees else None,
            currency_id=transaction.currency_id,
            notes=transaction.notes,
            created_at=transaction.created_at,
            currency=currency_data
        )

        transactions_with_currency.append(transaction_data)

    return transactions_with_currency


@router.post("/", response_model=Transaction)
def create_transaction(data: dict, session: Session = Depends(get_session)):
    """Create a new transaction."""
    if not data.get("portfolio_id"):
        raise HTTPException(status_code=400, detail="portfolio_id is required")

    trade_date = data.get("trade_date")
    if isinstance(trade_date, str):
        data["trade_date"] = datetime.strptime(trade_date, "%Y-%m-%d").date()

    transaction = Transaction(**data)
    session.add(transaction)
    session.commit()
    session.refresh(transaction)

    return transaction


@router.get("/{transaction_id}", response_model=Transaction)
def get_transaction(transaction_id: int, session: Session = Depends(get_session)):
    """Get a specific transaction."""
    transaction = session.get(Transaction, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


@router.put("/{transaction_id}", response_model=Transaction)
def update_transaction(transaction_id: int, data: dict, session: Session = Depends(get_session)):
    """Update a specific transaction."""
    transaction = session.get(Transaction, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    # Handle date conversion
    trade_date = data.get("trade_date")
    if isinstance(trade_date, str):
        data["trade_date"] = datetime.strptime(trade_date, "%Y-%m-%d").date()

    # Update transaction fields
    for key, value in data.items():
        if hasattr(transaction, key):
            setattr(transaction, key, value)

    session.add(transaction)
    session.commit()
    session.refresh(transaction)
    return transaction


@router.delete("/{transaction_id}")
def delete_transaction(transaction_id: int, session: Session = Depends(get_session)):
    """Delete a specific transaction."""
    transaction = session.get(Transaction, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    session.delete(transaction)
    session.commit()
    return {"message": "Successfully deleted transaction"}


@router.delete("/")
def delete_all_transactions(portfolio_id: int, session: Session = Depends(get_session)):
    """Delete all transactions for a specific portfolio."""
    query = select(Transaction).where(Transaction.portfolio_id == portfolio_id)

    transactions = session.exec(query).all()
    count = len(transactions)

    for transaction in transactions:
        session.delete(transaction)

    session.commit()
    return {"message": f"Successfully deleted {count} transactions"}
