"""Portfolio API endpoints."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select

from backend.db import get_session
from backend.db.models import Portfolio, Transaction, Position, Settings, Asset, Currency
from backend.api.models import PositionResponse, CurrencyResponse, DividendPositionResponse, FinancialPositionResponse
from backend.services import PortfolioService, PositionService, CurrencyService
from backend.services.calculation import CalculationService

router = APIRouter()


@router.get("/", response_model=list[Portfolio])
def get_portfolios(session: Session = Depends(get_session)):
    """Get all portfolios."""
    portfolios = session.exec(select(Portfolio)).all()
    return portfolios


@router.post("/", response_model=Portfolio)
def create_portfolio(portfolio: Portfolio, session: Session = Depends(get_session)):
    """Create a new portfolio."""
    session.add(portfolio)
    session.commit()
    session.refresh(portfolio)
    return portfolio


@router.get("/{portfolio_id}", response_model=Portfolio)
def get_portfolio(portfolio_id: int, session: Session = Depends(get_session)):
    """Get a specific portfolio."""
    portfolio = session.get(Portfolio, portfolio_id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return portfolio


@router.get("/{portfolio_id}/positions", response_model=list[PositionResponse])
def get_positions(
    portfolio_id: int,
    as_of_date: date | None = None,
    session: Session = Depends(get_session)
):
    """Get positions for a portfolio as of a specific date.

    Returns both currently held positions (``is_history=False``) and
    historical positions (``is_history=True``) — assets that were held in
    the past but have zero quantity on the as_of_date (excluding cash
    assets). Each position also carries its total cash dividends received
    from the earliest transaction up to as_of_date, in both the asset's
    currency (``dividends``) and the portfolio's primary currency
    (``dividends_primary``).
    """
    portfolio = session.get(Portfolio, portfolio_id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    position_service = PositionService(session)

    if as_of_date:
        positions = position_service.get_positions_on_date(portfolio_id, as_of_date)
    else:
        positions = position_service.get_latest_positions(portfolio_id)

    currency_service = CurrencyService(session)

    # Determine the effective date for dividend aggregation. When no
    # as_of_date is given, use the latest position date so dividends are
    # summed up to the same point the positions reflect.
    if as_of_date:
        dividends_as_of = as_of_date
    elif positions:
        dividends_as_of = max(p.position_date for p in positions)
    else:
        dividends_as_of = date.today()

    # Aggregate dividends per asset up to dividends_as_of.
    dividends_by_asset = position_service.get_dividends_by_asset(
        portfolio_id, dividends_as_of
    )

    result = []
    for position in positions:
        asset = session.get(Asset, position.asset_id)
        currency = session.get(Currency, asset.currency_id) if asset else None

        currency_data = None
        if currency:
            currency_data = CurrencyResponse(
                id=currency.id,
                code=currency.code,
                name=currency.name,
                symbol=currency.symbol,
                is_primary=currency.is_primary
            )

        market_value = float(position.market_value) if position.market_value else None
        total_pnl = float(position.total_pnl) if position.total_pnl else None

        market_value_primary = None
        total_pnl_primary = None
        # Dividends default to 0.0 (not None) so the frontend always renders
        # them with the correct currency symbol instead of falling back to ¥.
        dividends_value = 0.0
        dividends_primary = 0.0
        if asset:
            rate = currency_service.get_exchange_rate(asset.currency_id, position.position_date)
            if rate is not None:
                if market_value is not None:
                    market_value_primary = market_value * float(rate)
                if total_pnl is not None:
                    total_pnl_primary = total_pnl * float(rate)

                # Dividends in asset currency, converted to primary currency
                div_total = dividends_by_asset.get(position.asset_id, Decimal("0"))
                dividends_value = float(div_total)
                dividends_primary = dividends_value * float(rate)

        # A position is "history" when it has been fully closed (zero
        # quantity) and is not a cash asset. Cash assets always represent
        # the current cash balance and are never treated as history.
        is_history = False
        if asset and asset.type != "cash":
            if position.quantity is not None and float(position.quantity) == 0.0:
                is_history = True

        result.append(PositionResponse(
            id=position.id,
            portfolio_id=position.portfolio_id,
            asset_id=position.asset_id,
            symbol=asset.symbol if asset else "",
            name=asset.name if asset else "",
            quantity=float(position.quantity),
            average_cost=float(position.average_cost),
            current_price=float(position.current_price) if position.current_price else None,
            market_value=market_value,
            market_value_primary=market_value_primary,
            total_pnl=total_pnl,
            total_pnl_primary=total_pnl_primary,
            position_date=position.position_date,
            currency=currency_data,
            dividends=dividends_value,
            dividends_primary=dividends_primary,
            is_history=is_history
        ))

    return result


@router.get("/{portfolio_id}/financial-positions", response_model=list[FinancialPositionResponse])
def get_financial_positions(
    portfolio_id: int,
    as_of_date: date,
    session: Session = Depends(get_session)
):
    """Get positions with financial information from database.

    Reads cached StockInfo records for the given date.
    """
    portfolio = session.get(Portfolio, portfolio_id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    portfolio_service = PortfolioService(session)
    result = portfolio_service.get_financial_positions(portfolio_id, as_of_date)
    return [FinancialPositionResponse(**r) for r in result]


@router.post("/{portfolio_id}/financial-positions", response_model=list[FinancialPositionResponse])
def fetch_financial_positions(
    portfolio_id: int,
    as_of_date: date,
    session: Session = Depends(get_session)
):
    """Fetch financial data from THS, save to database, and return results."""
    portfolio = session.get(Portfolio, portfolio_id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    portfolio_service = PortfolioService(session)
    result = portfolio_service.fetch_and_save_financial_positions(portfolio_id, as_of_date)
    session.commit()
    return [FinancialPositionResponse(**r) for r in result]


@router.get("/{portfolio_id}/performance-history")
def get_performance_history(
    portfolio_id: int,
    start_date: str,
    end_date: str,
    benchmark_id: int | None = None,
    session: Session = Depends(get_session)
):
    """Get portfolio performance history for charting."""
    if not start_date or not end_date:
        raise HTTPException(status_code=400, detail="Both start_date and end_date are required")

    try:
        portfolio_service = PortfolioService(session)

        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()

        transactions = session.exec(
            select(Transaction)
            .where(Transaction.portfolio_id == portfolio_id)
            .order_by(Transaction.trade_date)
        ).all()

        if not transactions:
            return []

        start = max(start, transactions[0].trade_date)

        # Ensure positions are calculated for the entire range upfront
        position_service = PositionService(session)
        position_service.ensure_positions_calculated(portfolio_id, end)

        performance_data = []
        current_date = start

        twr_result = portfolio_service.twr(portfolio_id, start, end)
        nav_data = {d: nav for d, nav in zip(twr_result["dates"], twr_result["nav_history"])}

        # Get benchmark data if benchmark_id is provided
        benchmark_data = {}
        if benchmark_id:
            calc_service = CalculationService(session)
            benchmark_prices = calc_service._get_benchmark_prices(benchmark_id, start, end)
            benchmark_data = {bp.price_date: float(bp.close) for bp in benchmark_prices}

        while current_date <= end:
            portfolio_value = portfolio_service.calculate_portfolio_value(portfolio_id, current_date)
            nav_value = nav_data.get(current_date, 1.0)

            data_point = {
                "date": current_date.isoformat(),
                "value": float(portfolio_value["total_value"]),
                "nav": float(nav_value)
            }

            # Add benchmark price if available for this date
            if benchmark_id and current_date in benchmark_data:
                data_point["benchmark_price"] = benchmark_data[current_date]

            performance_data.append(data_point)
            current_date += timedelta(days=1)

        return performance_data

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error calculating performance history: {str(e)}")


@router.get("/{portfolio_id}/performance-metrics")
def get_performance_metrics(
    portfolio_id: int,
    start_date: str,
    end_date: str,
    benchmark_id: int | None = None,
    session: Session = Depends(get_session)
):
    """Get portfolio performance metrics (alias for statistics)."""
    portfolio = session.get(Portfolio, portfolio_id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    # Get earliest transaction date and use max(user_start_date, first_transaction_date)
    transactions = session.exec(
        select(Transaction)
        .where(Transaction.portfolio_id == portfolio_id)
        .order_by(Transaction.trade_date)
    ).all()

    if transactions:
        start = max(start, transactions[0].trade_date)

    portfolio_service = PortfolioService(session)

    # Ensure positions are calculated for the entire range upfront
    position_service = PositionService(session)
    position_service.ensure_positions_calculated(portfolio_id, end)

    return portfolio_service.calculate_portfolio_statistics(portfolio_id, start, end, benchmark_id)


@router.get("/{portfolio_id}/recent-returns")
def get_recent_returns(
    portfolio_id: int,
    end_date: str | None = None,
    benchmark_id: int | None = None,
    session: Session = Depends(get_session)
):
    """Get recent returns for different time periods."""
    portfolio = session.get(Portfolio, portfolio_id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    try:
        if end_date:
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
        else:
            end = date.today()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    portfolio_service = PortfolioService(session)

    # Ensure positions are calculated for the entire range upfront
    position_service = PositionService(session)
    position_service.ensure_positions_calculated(portfolio_id, end)

    # Get earliest transaction date for the portfolio
    transactions = session.exec(
        select(Transaction)
        .where(Transaction.portfolio_id == portfolio_id)
        .order_by(Transaction.trade_date)
    ).all()

    first_transaction_date = transactions[0].trade_date if transactions else None

    # Calculate returns for different periods
    period_configs = [
        ("1M", 30, "1 Month"),
        ("3M", 90, "3 Months"),
        ("6M", 180, "6 Months"),
        ("1Y", 365, "1 Year"),
        ("YTD", None, "Year to Date"),
    ]

    returns = []
    for period_key, days, period_label in period_configs:
        try:
            if period_key == "YTD":
                start = date(end.year - 1, 12, 31)
            else:
                start = end - timedelta(days=days)

            # Use max(user_start_date, first_transaction_date) as the effective start date
            if first_transaction_date:
                start = max(start, first_transaction_date)

            # Get TWR data for start and end NAV
            twr_data = portfolio_service.twr(portfolio_id, start, end)
            nav_history = twr_data.get("nav_history", [])
            dates = twr_data.get("dates", [])

            start_nav = nav_history[0] if nav_history else 1.0
            end_nav = nav_history[-1] if nav_history else 1.0

            stats = portfolio_service.calculate_portfolio_statistics(portfolio_id, start, end, benchmark_id)
            
            result = {
                "period": period_label,
                "return": stats.get("time_weighted_return", 0.0),
                "annualized": stats.get("annualized_return", 0.0),
                "start_nav": start_nav,
                "end_nav": end_nav,
            }
            
            if benchmark_id:
                if "excess_return" in stats:
                    result["excess_return"] = stats.get("excess_return", 0.0)
                if "benchmark_return" in stats:
                    result["benchmark_return"] = stats.get("benchmark_return", 0.0)
            
            returns.append(result)
        except Exception as e:
            result = {
                "period": period_label,
                "return": 0.0,
                "annualized": 0.0,
                "start_nav": 1.0,
                "end_nav": 1.0,
                "excess_return": 0.0,
                "benchmark_return": 0.0,
            }
            returns.append(result)

    return returns


@router.post("/{portfolio_id}/recalculate-positions")
def recalculate_positions(
    portfolio_id: int,
    as_of_date: str | None = None,
    session: Session = Depends(get_session)
):
    """Recalculate and save positions for every day from the first transaction date up to as_of_date.

    Existing positions in the range are deleted and replaced with the freshly computed
    daily snapshots, so the database always reflects the latest calculation.
    """
    try:
        if as_of_date:
            target_date = datetime.strptime(as_of_date, "%Y-%m-%d").date()
        else:
            target_date = date.today()

        position_service = PositionService(session)
        result = position_service.recalculate_positions_daily(
            portfolio_id=portfolio_id,
            end_date=target_date,
        )

        if result["days_processed"] == 0:
            return {"message": "No transactions found to recalculate."}

        return {
            "message": (
                f"Successfully recalculated positions for {result['days_processed']} days "
                f"from {result['start_date'].strftime('%Y-%m-%d')} to "
                f"{result['end_date'].strftime('%Y-%m-%d')}."
            )
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error recalculating positions: {str(e)}")


@router.get("/{portfolio_id}/allocation")
def get_asset_allocation(
    portfolio_id: int,
    as_of_date: date | None = None,
    by: str = 'type',
    tag_category_id: int | None = None,
    session: Session = Depends(get_session)
):
    """Get asset allocation for a portfolio."""
    portfolio = session.get(Portfolio, portfolio_id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    portfolio_service = PortfolioService(session)
    return portfolio_service.get_asset_allocation(
        portfolio_id, as_of_date, by, tag_category_id
    )


@router.get("/{portfolio_id}/tag-correlation")
def get_tag_correlation(
    portfolio_id: int,
    start_date: str,
    end_date: str,
    tag_category_id: int,
    session: Session = Depends(get_session)
):
    """Get correlation matrix between tag-based asset portfolios."""
    portfolio = session.get(Portfolio, portfolio_id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    if not start_date or not end_date:
        raise HTTPException(status_code=400, detail="Both start_date and end_date are required")

    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    if start > end:
        raise HTTPException(status_code=400, detail="start_date must not be later than end_date")

    portfolio_service = PortfolioService(session)
    try:
        result = portfolio_service.calculate_tag_correlation(
            portfolio_id, start, end, tag_category_id
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating tag correlation: {str(e)}")


@router.get("/{portfolio_id}/asset-beta")
def get_asset_beta(
    portfolio_id: int,
    start_date: str,
    end_date: str,
    benchmark_id: int,
    asset_id: int | None = None,
    top_n: int = 10,
    frequency: str = "daily",
    session: Session = Depends(get_session)
):
    """Get beta for individual assets against a benchmark.

    Returns the top N non-cash assets by market value along with their
    beta values. If a specific asset_id is provided, that asset's beta
    is also included (even if not in the top N).

    Args:
        portfolio_id: The portfolio ID.
        start_date: Start date (YYYY-MM-DD).
        end_date: End date (YYYY-MM-DD).
        benchmark_id: Benchmark ID to calculate beta against.
        asset_id: Optional specific asset ID to include.
        top_n: Number of top assets by market value. Default 10.
        frequency: 'daily', 'weekly', or 'monthly'. Default 'daily'.
    """
    portfolio = session.get(Portfolio, portfolio_id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    if not start_date or not end_date:
        raise HTTPException(status_code=400, detail="Both start_date and end_date are required")

    if frequency not in ("daily", "weekly", "monthly"):
        raise HTTPException(status_code=400, detail="frequency must be 'daily', 'weekly', or 'monthly'")

    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    if start > end:
        raise HTTPException(status_code=400, detail="start_date must not be later than end_date")

    portfolio_service = PortfolioService(session)
    calculation_service = CalculationService(session)
    try:
        # Step 1: Fetch asset price data (PortfolioService)
        asset_data = portfolio_service.get_asset_daily_prices(
            portfolio_id=portfolio_id,
            start_date=start,
            end_date=end,
            top_n=top_n,
            asset_id=asset_id,
        )
        # Step 2: Calculate beta (CalculationService)
        result = calculation_service.calculate_asset_beta(
            asset_daily_prices=asset_data["assets"],
            benchmark_id=benchmark_id,
            start_date=start,
            end_date=end,
            frequency=frequency,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating asset beta: {str(e)}")


@router.get("/{portfolio_id}/tag-beta")
def get_tag_beta(
    portfolio_id: int,
    start_date: str,
    end_date: str,
    tag_category_id: int,
    benchmark_id: int,
    frequency: str = "daily",
    session: Session = Depends(get_session)
):
    """Get beta for each tag against a benchmark.

    Each tag in the specified category is treated as a virtual sub-portfolio.
    Daily returns use weighted price returns of constituent assets (weighted
    by previous-day market value proportion), isolating price movements from
    position-size changes. Beta = Cov(R_tag, R_benchmark) / Var(R_benchmark)
    is calculated for each tag independently.

    Args:
        portfolio_id: The portfolio ID.
        start_date: Start date (YYYY-MM-DD).
        end_date: End date (YYYY-MM-DD).
        tag_category_id: Tag category ID to group tags by.
        benchmark_id: Benchmark ID to calculate beta against.
        frequency: 'daily', 'weekly', or 'monthly'. Default 'daily'.
    """
    portfolio = session.get(Portfolio, portfolio_id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    if not start_date or not end_date:
        raise HTTPException(status_code=400, detail="Both start_date and end_date are required")

    if frequency not in ("daily", "weekly", "monthly"):
        raise HTTPException(status_code=400, detail="frequency must be 'daily', 'weekly', or 'monthly'")

    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    if start > end:
        raise HTTPException(status_code=400, detail="start_date must not be later than end_date")

    portfolio_service = PortfolioService(session)
    calculation_service = CalculationService(session)
    try:
        tag_data = portfolio_service.get_tag_daily_returns(
            portfolio_id, start, end, tag_category_id
        )
        result = calculation_service.calculate_tag_beta(
            tag_names=tag_data["tag_names"],
            tag_calendar_returns=tag_data["tag_calendar_returns"],
            return_dates=tag_data["return_dates"],
            asset_tags_found=tag_data["asset_tags_found"],
            benchmark_id=benchmark_id,
            start_date=start,
            end_date=end,
            frequency=frequency,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating tag beta: {str(e)}")
