"""Import/Export API endpoints."""

import io
from datetime import date, timedelta
from decimal import Decimal
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from sqlmodel import Session, select
import pandas as pd

from backend.db import get_session
from backend.db.models import Asset, Currency, Price, Transaction
from backend.api.models import UpdatePricesRequest, UpdatePricesResponse
from backend.services import DataImportService, PriceRateService
from backend import logger

router = APIRouter()


@router.post("/prices/")
async def import_prices(file: UploadFile = File(...), session: Session = Depends(get_session)):
    """Import prices from CSV file."""
    try:
        contents = await file.read()
        df = pd.read_csv(io.StringIO(contents.decode('utf-8')))

        required_columns = ['symbol', 'price_date', 'price']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise HTTPException(status_code=400, detail=f"Missing required columns: {missing_columns}")

        prices = []
        for _, row in df.iterrows():
            asset = session.exec(select(Asset).where(Asset.symbol == row['symbol'])).first()
            if not asset:
                continue

            price = Price(
                asset_id=asset.id,
                price_date=pd.to_datetime(row['price_date']).date(),
                price=Decimal(str(row['price'])),
                price_type='historical',
                source='csv_import'
            )
            prices.append(price)

        session.add_all(prices)
        session.commit()

        return {"message": f"Successfully imported {len(prices)} prices"}

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error importing CSV: {str(e)}")


@router.post("/xueqiu-transactions/")
async def import_xueqiu_transactions(
    portfolio_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session)
):
    """Import transactions from Xueqiu (雪球) CSV file."""
    try:
        contents = await file.read()
        encoding = DataImportService.detect_encoding(contents)
        df = pd.read_csv(io.StringIO(contents.decode(encoding)))

        import_service = DataImportService(session)
        transactions = import_service.import_xueqiu_transactions_from_dataframe(df, portfolio_id)

        session.add_all(transactions)
        session.commit()

        return {
            "message": f"Successfully imported {len(transactions)} transactions from Xueqiu",
            "count": len(transactions)
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error importing Xueqiu transactions: {str(e)}")


@router.post("/xueqiu-align/")
async def align_xueqiu_portfolio(
    portfolio_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session)
):
    """Align portfolio to Xueqiu data from a zip archive.

    This endpoint will:
    1. Delete all existing transactions for the portfolio
    2. Extract and parse the CSV from the zip file
    3. Import trade records (交易记录) and transfer records (转账记录)
    4. Update asset prices and exchange rates up to today
    5. Recalculate positions up to today
    """
    try:
        contents = await file.read()
        import_service = DataImportService(session)
        result = import_service.align_portfolio_from_xueqiu(contents, portfolio_id)

        start_date = result.get("start_date")
        end_date = result.get("end_date")

        message = (
            f"Successfully aligned portfolio: deleted {result['deleted_count']} transactions, "
            f"imported {result['total_imported']} transactions "
            f"({result['trade_count']} trades + {result['transfer_count']} transfers), "
            f"recalculated {result['days_processed']} days "
            f"from {start_date.strftime('%Y-%m-%d') if start_date else 'N/A'} to "
            f"{end_date.strftime('%Y-%m-%d') if end_date else 'N/A'}."
        )
        price_errors = result.get("price_update_errors", [])
        if price_errors:
            message += f" Warning: {len(price_errors)} price/rate update error(s) occurred."

        return {
            "message": message,
            **result
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error aligning Xueqiu portfolio: {str(e)}")


@router.post("/update-prices-and-rates/", response_model=UpdatePricesResponse)
def update_prices_and_rates(
    request: UpdatePricesRequest,
    session: Session = Depends(get_session)
):
    """Fetch and store historical prices for all non-cash assets and exchange rates."""
    try:
        primary_currency = session.exec(
            select(Currency).where(Currency.is_primary == True)
        ).first()
        if not primary_currency or primary_currency.code != "CNY":
            return UpdatePricesResponse(
                success=False,
                message="Primary currency must be CNY",
                errors=["No primary currency or CNY is not primary currency"]
            )

        first_transaction = session.exec(
            select(Transaction).order_by(Transaction.trade_date)
        ).first()

        if not first_transaction:
            return UpdatePricesResponse(
                success=True,
                message="No transactions found, skipping price and rate update",
                prices_added=0,
                rates_added=0,
                benchmark_prices_added=0,
                errors=[],
            )

        start_date = first_transaction.trade_date

        logger.info(f"Updating prices and rates from {start_date} to {request.end_date}")

        price_rate_service = PriceRateService(session)
        update_result = price_rate_service.update_all(
            start_date=start_date,
            end_date=request.end_date,
        )

        return UpdatePricesResponse(
            success=True,
            message=(
                f"Successfully added {update_result['prices_added']} prices, "
                f"{update_result['rates_added']} exchange rates, and "
                f"{update_result['benchmark_prices_added']} benchmark prices"
            ),
            prices_added=update_result["prices_added"],
            rates_added=update_result["rates_added"],
            benchmark_prices_added=update_result["benchmark_prices_added"],
            errors=update_result["errors"],
        )

    except Exception as e:
        logger.exception("Error updating prices and rates")
        return UpdatePricesResponse(
            success=False,
            message=f"Error updating prices and rates: {str(e)}",
            errors=[str(e)]
        )
