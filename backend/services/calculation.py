"""Calculation service for portfolio metrics and TWR."""

import numpy as np
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from sqlmodel import select
from backend.db.models import Transaction, Position, BenchmarkPrice, Benchmark
from backend.services.base import BaseService
from backend.services.currency import CurrencyService
from backend.services.stats_utils import (
    sanitize_scalar,
    compound_return,
    prices_to_returns,
    min_data_points_for,
    date_range_list,
    annualize_return,
)
from backend import logger


class CalculationService(BaseService):
    """Service for portfolio calculations including TWR and statistics."""

    def __init__(self, session, currency_service: CurrencyService | None = None):
        """Initialize with optional currency service."""
        super().__init__(session)
        self.currency_service = currency_service or CurrencyService(session)

    def calculate_twr(
        self,
        portfolio_id: int,
        start_date: date,
        end_date: date,
        portfolio_value_func
    ) -> dict:
        """Calculate Time-Weighted Return (TWR) for portfolio.

        Args:
            portfolio_id: The portfolio ID
            start_date: Start date for calculation
            end_date: End date for calculation
            portfolio_value_func: Function to get portfolio value for a date

        Returns:
            Dictionary with TWR results including daily returns, NAV history, etc.
            daily_returns[i] corresponds to the return from dates[i] to dates[i+1]
            So daily_returns has len(dates) - 1 elements
        """
        try:
            transactions = self.session.exec(
                select(Transaction)
                .where(Transaction.portfolio_id == portfolio_id)
                .where(Transaction.trade_date >= start_date)
                .where(Transaction.trade_date <= end_date)
                .order_by(Transaction.trade_date)
            ).all()

            # Group transactions by date
            daily_transactions = defaultdict(list)
            for transaction in transactions:
                daily_transactions[transaction.trade_date].append(transaction)

            # Initialize variables for TWR calculation
            daily_returns = []
            nav_history = []
            shares_history = []
            dates_history = []

            # External cash flows are added to the portfolio at the end of each day.
            # The first day is only for initialization of navs and shares.
            v_prev = portfolio_value_func(portfolio_id, start_date)["total_value"]
            nav_prev = Decimal("1.0")  # Initial NAV is 1
            shares_prev = v_prev / nav_prev  # Initialize shares
            nav_history.append(float(nav_prev))
            shares_history.append(float(shares_prev))
            dates_history.append(start_date)

            # Start calculation from the second day
            current_date = start_date + timedelta(days=1)

            while current_date <= end_date:
                # Step 1. Prepare data for today
                v_today = portfolio_value_func(portfolio_id, current_date)["total_value"]

                # Step 2. Calculate external net cash flow in primary currency
                delta_cf = Decimal("0")
                for transaction in daily_transactions.get(current_date, []):
                    if transaction.action in ["cash_in"]:
                        amount = self.currency_service.convert_to_primary_currency(
                            transaction.amount, transaction.currency_id, current_date
                        )
                        delta_cf += amount
                    elif transaction.action in ["cash_out"]:
                        amount = self.currency_service.convert_to_primary_currency(
                            transaction.amount, transaction.currency_id, current_date
                        )
                        delta_cf -= amount

                # Step 3. Calculate the nav for current day by 2 methods
                # Method 1: nav_today = (v_today - delta_cf) / shares_prev
                if shares_prev > 0:
                    nav_today = (v_today - delta_cf) / shares_prev
                else:
                    nav_today = nav_prev

                # Method 2: nav_today = nav_prev * (1 + r)
                if v_prev > 0:
                    r = (v_today - delta_cf) / v_prev - 1
                else:
                    r = Decimal("0")
                nav_ref_today = nav_prev * (1 + r)

                # Validate NAV calculations match
                nav_diff = nav_today - nav_ref_today
                if abs(nav_diff) > 0.0001:
                    raise ValueError(
                        f"NAV calculation error on {current_date}. "
                        f"nav_ref:{nav_ref_today}, nav:{nav_today}, diff:{nav_diff}"
                    )

                # Step 4. Modify shares for today
                delta_shares = delta_cf / nav_today
                shares_today = shares_prev + delta_shares

                # Store daily data
                daily_returns.append(float(r))
                shares_history.append(float(shares_today))
                nav_history.append(float(nav_today))
                dates_history.append(current_date)

                # Step 5. Update data for next day
                v_prev = v_today
                shares_prev = shares_today
                nav_prev = nav_today
                current_date += timedelta(days=1)

            # Calculate cumulative TWR
            if len(daily_returns) > 0:
                twr = compound_return(daily_returns)
                period_return = twr
            else:
                twr = 0.0
                period_return = 0.0

            # Annualize return
            days = (end_date - start_date).days
            if days > 0 and len(daily_returns) > 0:
                annualized_return = annualize_return(twr, days)
            else:
                annualized_return = 0.0

            # Beginning/ending NAV per share (the unit this method tracks)
            beginning_nav = float(nav_history[0]) if nav_history else 0.0
            ending_nav = float(nav_history[-1]) if nav_history else 0.0

            return {
                "twr": float(twr),
                "period_return": float(period_return),
                "annualized_return": annualized_return,
                "beginning_nav": beginning_nav,
                "ending_nav": ending_nav,
                "daily_returns": daily_returns,
                "dates": dates_history,
                "nav_history": nav_history,
                "shares_history": shares_history,
            }

        except ValueError:
            # NAV validation failures must propagate instead of being masked
            # as a silent zero-return result.
            raise
        except Exception as e:
            logger.exception("Error in CalculationService.calculate_twr()")
            return {
                "twr": 0.0,
                "period_return": 0.0,
                "annualized_return": 0.0,
                "beginning_nav": 0.0,
                "ending_nav": 0.0,
                "daily_returns": [],
                "nav_history": [],
                "shares_history": [],
                "dates": [],
            }

    def _get_benchmark_prices(
        self,
        benchmark_id: int,
        start_date: date,
        end_date: date,
    ) -> list[BenchmarkPrice]:
        """Get benchmark prices, computing composite prices on-the-fly if needed."""
        benchmark = self.session.get(Benchmark, benchmark_id)
        if not benchmark:
            return []

        if not benchmark.is_composite:
            return self.session.exec(
                select(BenchmarkPrice)
                .where(BenchmarkPrice.benchmark_id == benchmark_id)
                .where(BenchmarkPrice.price_date >= start_date)
                .where(BenchmarkPrice.price_date <= end_date)
                .order_by(BenchmarkPrice.price_date)
            ).all()

        # Composite benchmark: compute prices from components
        if not benchmark.components:
            return []

        component_ids = [c.component_benchmark_id for c in benchmark.components]
        weights = {c.component_benchmark_id: float(c.weight) for c in benchmark.components}

        all_prices = self.session.exec(
            select(BenchmarkPrice)
            .where(BenchmarkPrice.benchmark_id.in_(component_ids))
            .where(BenchmarkPrice.price_date >= start_date)
            .where(BenchmarkPrice.price_date <= end_date)
            .order_by(BenchmarkPrice.price_date)
        ).all()

        prices_by_component: dict[int, list[BenchmarkPrice]] = {}
        for p in all_prices:
            prices_by_component.setdefault(p.benchmark_id, []).append(p)

        date_range = date_range_list(start_date, end_date)

        composite_prices = []
        for d in date_range:
            composite_value = 0.0
            valid = True
            for comp_id in component_ids:
                comp_prices = prices_by_component.get(comp_id, [])
                last_price = None
                first_price = None
                for p in comp_prices:
                    if p.price_date <= d:
                        last_price = float(p.close)
                        if first_price is None:
                            first_price = last_price
                    else:
                        break

                if last_price is None or first_price is None or first_price == 0:
                    valid = False
                    break

                normalized = last_price / first_price
                composite_value += normalized * weights[comp_id]

            if valid:
                composite_prices.append(BenchmarkPrice(
                    benchmark_id=benchmark_id,
                    price_date=d,
                    close=Decimal(str(round(composite_value, 6))),
                    source="composite",
                ))

        return composite_prices

    @staticmethod
    def calculate_beta(
        portfolio_returns: np.ndarray,
        benchmark_returns: np.ndarray,
    ) -> float:
        """Calculate beta coefficient between two aligned return series.

        Beta = Cov(Rp, Rb) / Var(Rb)

        Uses sample covariance (ddof=1) and sample variance (ddof=1).
        Handles edge cases: insufficient data, zero benchmark variance,
        NaN/inf values.

        Args:
            portfolio_returns: 1D numpy array of portfolio/sub-portfolio returns.
            benchmark_returns: 1D numpy array of benchmark returns, aligned
                               index-by-index with portfolio_returns.

        Returns:
            Beta coefficient as float. Returns 0.0 if calculation is invalid.

        Examples:
            >>> rp = np.array([0.01, -0.02, 0.03])
            >>> rb = np.array([0.005, -0.01, 0.02])
            >>> CalculationService.calculate_beta(rp, rb)
            1.5
        """
        try:
            if len(portfolio_returns) < 2 or len(benchmark_returns) < 2:
                return 0.0

            rp = np.array(portfolio_returns, dtype=float)
            rb = np.array(benchmark_returns, dtype=float)

            covariance_matrix = np.cov(rp, rb)
            covariance = covariance_matrix[0, 1]
            benchmark_variance = np.var(rb, ddof=1)

            if benchmark_variance > 0:
                beta = covariance / benchmark_variance
            else:
                beta = 0.0

            return sanitize_scalar(beta, 0.0)

        except Exception:
            return 0.0

    @staticmethod
    def _aggregate_returns_to_frequency(
        daily_returns: list[float],
        dates: list[date],
        frequency: str,
    ) -> tuple[list[float], list[date]]:
        """Aggregate daily returns to a lower frequency (weekly or monthly).

        Each return is grouped by the ISO week (or month) of its end date,
        then compounded within each group:

            period_return = prod(1 + daily_return) - 1

        For example, if three returns have end dates in the same ISO week,
        they are compounded into a single weekly return. The aggregated
        end date for that week is the latest end date within the group.

        Args:
            daily_returns: List of daily returns, aligned with dates.
                daily_returns[i] represents the return from dates[i-1] to
                dates[i]. dates[-1] (the start of the first period) is
                implicit and not in the array.
            dates: List of end dates, one per daily return.
                dates[i] is the end date of the return period represented
                by daily_returns[i].
            frequency: 'weekly' or 'monthly'. 'daily' returns data as-is.

        Returns:
            Tuple of (aggregated_returns, aggregated_end_dates).
            aggregated_end_dates[i] is the latest end date among the
            daily returns that were compounded into aggregated_returns[i].

        Examples:
            >>> returns = [0.01, 0.02, -0.01, 0.03]
            >>> dates = [date(2025,1,6), date(2025,1,7), date(2025,1,8), date(2025,1,9)]
            >>> r, d = CalculationService._aggregate_returns_to_frequency(returns, dates, 'weekly')
        """
        if frequency == "daily" or len(daily_returns) == 0:
            return list(daily_returns), list(dates)

        if len(daily_returns) != len(dates):
            raise ValueError(
                f"daily_returns (len={len(daily_returns)}) and dates (len={len(dates)}) must have same length"
            )

        grouped: dict[tuple, list[float]] = {}
        grouped_end_date: dict[tuple, date] = {}

        for i, (r, d) in enumerate(zip(daily_returns, dates)):
            if frequency == "weekly":
                # Group by ISO week (year, week_number)
                iso = d.isocalendar()
                key = (iso[0], iso[1])
            elif frequency == "monthly":
                key = (d.year, d.month)
            else:
                raise ValueError(f"Unsupported frequency: {frequency}")

            if key not in grouped:
                grouped[key] = []
                grouped_end_date[key] = d
            grouped[key].append(r)
            grouped_end_date[key] = d  # keep the latest date in the period

        # Sort keys chronologically to maintain order
        sorted_keys = sorted(grouped.keys())
        aggregated_returns = []
        aggregated_dates = []

        for key in sorted_keys:
            period_returns = grouped[key]
            if len(period_returns) > 0:
                compounded = compound_return(period_returns)
                aggregated_returns.append(float(compounded))
                aggregated_dates.append(grouped_end_date[key])

        return aggregated_returns, aggregated_dates

    @staticmethod
    def _validate_numeric_value(value, default=0.0):
        """Helper function to validate numeric values."""
        return sanitize_scalar(value, default)

    def _build_benchmark_returns_by_date(
        self,
        benchmark_id: int,
        start_date: date,
        end_date: date,
    ) -> dict[date, float]:
        """Fetch benchmark prices and build a date→daily return mapping.

        Shared by calculate_tag_beta() and calculate_asset_beta().
        Computes daily returns for each benchmark price pair and indexes
        them by the end date. Returns an empty dict if prices are
        insufficient.

        Args:
            benchmark_id: The benchmark ID to fetch prices for.
            start_date: Start date for price range.
            end_date: End date for price range.

        Returns:
            Dict mapping each price date to its daily return.
            Empty dict if fewer than 2 valid price points.
        """
        benchmark_prices = self._get_benchmark_prices(
            benchmark_id, start_date, end_date
        )

        if len(benchmark_prices) < 2:
            return {}

        prices = [float(bp.close) for bp in benchmark_prices]
        dates = [bp.price_date for bp in benchmark_prices]
        returns, return_dates = prices_to_returns(prices, dates)
        return dict(zip(return_dates, returns))

    def _align_aggregate_and_compute_beta(
        self,
        item_returns: list[float],
        item_return_dates: list[date],
        benchmark_returns_by_date: dict[date, float],
        frequency: str,
        min_data_points: int,
    ) -> tuple[float | None, int]:
        """Align item returns with benchmark, aggregate to frequency, compute beta.

        Shared by calculate_tag_beta() and calculate_asset_beta().
        Takes pre-computed item daily returns with their dates, intersects
        them with the benchmark return dates, optionally aggregates both
        series to a lower frequency, and computes the beta coefficient.

        Args:
            item_returns: List of daily returns for the item (tag or asset).
            item_return_dates: End dates for each return, aligned index-wise.
            benchmark_returns_by_date: Dict mapping date → benchmark daily return.
            frequency: 'daily', 'weekly', or 'monthly'.
            min_data_points: Minimum data points required for a valid beta.

        Returns:
            Tuple of (beta, data_points). beta is None if insufficient data.
        """
        # Align item returns with benchmark returns by matching dates
        aligned_item = []
        aligned_dates = []
        aligned_benchmark = []
        for j, d in enumerate(item_return_dates):
            if d in benchmark_returns_by_date:
                aligned_item.append(item_returns[j])
                aligned_dates.append(d)
                aligned_benchmark.append(benchmark_returns_by_date[d])

        # Aggregate to requested frequency
        if frequency != "daily" and len(aligned_item) > 0:
            agg_item, _ = self._aggregate_returns_to_frequency(
                aligned_item, aligned_dates, frequency
            )
            agg_benchmark, _ = self._aggregate_returns_to_frequency(
                aligned_benchmark, aligned_dates, frequency
            )
            n = min(len(agg_item), len(agg_benchmark))
            aligned_item = agg_item[:n]
            aligned_benchmark = agg_benchmark[:n]
            data_points = n
        else:
            data_points = len(aligned_item)

        if data_points >= min_data_points:
            beta = self.calculate_beta(
                np.array(aligned_item, dtype=float),
                np.array(aligned_benchmark, dtype=float),
            )
            return float(beta), data_points
        return None, data_points

    def _calculate_benchmark_statistics(
        self,
        benchmark_id: int,
        start_date: date,
        end_date: date,
        portfolio_dates: list[date],
        nav_history: list[float]
    ) -> dict:
        """Calculate benchmark-related statistics (beta, benchmark return, and excess return).
        Benchmark dates are selected from the portfolio dates over the period.
        The portfolio dates will be interpolated to align with the benchmark dates.

        Args:
            benchmark_id: The benchmark ID
            start_date: Start date for calculation
            end_date: End date for calculation
            portfolio_dates: List of dates corresponding to portfolio NAV history
            nav_history: List of portfolio NAV values

        Returns:
            Dictionary with "beta", "benchmark_return", and "excess_return"
            beta: Beta coefficient of the portfolio relative to the benchmark
            benchmark_return: Return of the benchmark during the adjusted period
            excess_return: portfolio_return - benchmark_return during the adjusted period
        """
        try:
            benchmark_prices = self._get_benchmark_prices(benchmark_id, start_date, end_date)

            if len(benchmark_prices) < 2:
                logger.warning(f"Insufficient benchmark prices for benchmark {benchmark_id}")
                return {"beta": 0.0, "excess_return": 0.0, "benchmark_return": 0.0}

            benchmark_date_to_price = {bp.price_date: float(bp.close) for bp in benchmark_prices}
            benchmark_dates = list(benchmark_date_to_price.keys())

            if len(benchmark_dates) < 2:
                logger.warning(f"Insufficient benchmark returns for benchmark {benchmark_id}")
                return {"beta": 0.0, "excess_return": 0.0, "benchmark_return": 0.0}

            date_to_nav = {portfolio_dates[i]: nav_history[i] for i in range(len(portfolio_dates))}

            aligned_portfolio_returns = []
            aligned_benchmark_returns = []

            for i in range(1, len(benchmark_dates)):
                curr_date = benchmark_dates[i]
                prev_date = benchmark_dates[i - 1]

                if (curr_date in date_to_nav) and (prev_date in date_to_nav):
                    curr_nav = date_to_nav[curr_date]
                    prev_nav = date_to_nav[prev_date]
                    if prev_nav > 0:
                        portfolio_return = (curr_nav - prev_nav) / prev_nav
                    else:
                        continue

                    curr_price = benchmark_date_to_price[curr_date]
                    prev_price = benchmark_date_to_price[prev_date]
                    if prev_price > 0:
                        benchmark_return = (curr_price - prev_price) / prev_price
                    else:
                        continue

                    aligned_portfolio_returns.append(portfolio_return)
                    aligned_benchmark_returns.append(benchmark_return)

            if len(aligned_portfolio_returns) < 2:
                logger.warning(f"Insufficient aligned data points for beta calculation")
                return {"beta": 0.0, "excess_return": 0.0, "benchmark_return": 0.0}

            portfolio_returns = np.array(aligned_portfolio_returns, dtype=float)
            benchmark_returns = np.array(aligned_benchmark_returns, dtype=float)

            beta = self.calculate_beta(portfolio_returns, benchmark_returns)

            benchmark_total_return = compound_return(benchmark_returns)
            benchmark_total_return = sanitize_scalar(benchmark_total_return, 0.0)

            portfolio_total_return = compound_return(portfolio_returns)
            portfolio_total_return = sanitize_scalar(portfolio_total_return, 0.0)
            excess_return = portfolio_total_return - benchmark_total_return

            return {
                "beta": beta,
                "benchmark_return": benchmark_total_return,
                "excess_return": excess_return,
            }

        except Exception as e:
            logger.exception(f"Error calculating benchmark statistics: {e}")
            return {"beta": 0.0, "benchmark_return": 0.0, "excess_return": 0.0}

    def calculate_tag_beta(
        self,
        tag_names: list[str],
        tag_calendar_returns: dict[str, list[float | None]],
        return_dates: list[date],
        asset_tags_found: bool,
        benchmark_id: int,
        start_date: date,
        end_date: date,
        frequency: str = "daily",
    ) -> dict:
        """Calculate beta for each tag against a benchmark.

        Each tag's pre-computed calendar-aligned daily weighted price returns
        are independently aligned with benchmark returns.
        Beta = Cov(R_tag, R_benchmark) / Var(R_benchmark) per tag.

        The weighted price return formula per day t:
            R_tag(t) = Σ w_i(t-1) × (price_i(t) / price_i(t-1) - 1)
        where weights are based on previous-day market values. This isolates
        price movements from position-size changes caused by buying/selling.

        Args:
            tag_names: List of tag names.
            tag_calendar_returns: Dict of tag_name -> list of daily returns
                aligned to return_dates (None where no data).
            return_dates: List of end dates for each return period.
            asset_tags_found: Whether any asset-tag pairs existed.
            benchmark_id: Benchmark ID to calculate beta against.
            start_date: Start date for fetching benchmark prices.
            end_date: End date for fetching benchmark prices.
            frequency: 'daily', 'weekly', or 'monthly'. Default 'daily'.

        Returns:
            Dictionary with:
            - "tags": list of tag names with sufficient data
            - "betas": list of beta values in same order as tags
            - "tag_data_points": list of data point counts, same order as tags
            - "insufficient_data_tags": list of tags excluded
            - "data_points": number of return periods used
            - "frequency": the frequency used
        """
        if frequency not in ("daily", "weekly", "monthly"):
            raise ValueError(
                f"Unsupported frequency: {frequency}. "
                "Must be 'daily', 'weekly', or 'monthly'."
            )

        if not asset_tags_found or not tag_names:
            return {
                "tags": [],
                "betas": [],
                "insufficient_data_tags": [],
                "data_points": 0,
                "frequency": frequency,
            }

        # 1. Get benchmark daily returns indexed by end date
        benchmark_returns_by_date = self._build_benchmark_returns_by_date(
            benchmark_id, start_date, end_date
        )

        if not benchmark_returns_by_date or len(benchmark_returns_by_date) < 2:
            logger.warning(
                f"Insufficient benchmark returns for benchmark {benchmark_id}"
            )
            return {
                "tags": [],
                "betas": [],
                "insufficient_data_tags": [],
                "data_points": 0,
                "frequency": frequency,
                "message": "Insufficient benchmark return data.",
            }

        # 2. For each tag, filter pre-computed returns, align, calculate beta
        min_data_points = min_data_points_for(frequency)
        sufficient_tags = []
        betas = []
        insufficient_tags = []
        data_points_list: list[int] = []

        for tag_name in tag_names:
            returns_list = tag_calendar_returns[tag_name]

            # Filter out None entries to get valid daily returns
            tag_returns = []
            tag_return_dates = []
            for i, r in enumerate(returns_list):
                if r is not None:
                    tag_returns.append(r)
                    tag_return_dates.append(return_dates[i])

            # Align, aggregate, and compute beta
            beta, data_points = self._align_aggregate_and_compute_beta(
                item_returns=tag_returns,
                item_return_dates=tag_return_dates,
                benchmark_returns_by_date=benchmark_returns_by_date,
                frequency=frequency,
                min_data_points=min_data_points,
            )

            if beta is not None:
                sufficient_tags.append(tag_name)
                betas.append(beta)
                data_points_list.append(data_points)
            else:
                insufficient_tags.append(tag_name)

        return {
            "tags": sufficient_tags,
            "betas": betas,
            "tag_data_points": data_points_list,
            "insufficient_data_tags": insufficient_tags,
            "data_points": min(data_points_list) if data_points_list else 0,
            "frequency": frequency,
        }

    def calculate_asset_beta(
        self,
        asset_daily_prices: list[dict],
        benchmark_id: int,
        start_date: date,
        end_date: date,
        frequency: str = "daily",
    ) -> dict:
        """Calculate beta for individual assets against a benchmark.

        Each asset's pre-fetched daily price series is converted to returns,
        aligned with benchmark returns, and beta is computed.

        Args:
            asset_daily_prices: List of dicts from PortfolioService.get_asset_daily_prices,
                each with asset_id, symbol, name, market_value, daily_prices, price_dates.
            benchmark_id: Benchmark ID to calculate beta against.
            start_date: Start date for fetching benchmark prices.
            end_date: End date for fetching benchmark prices.
            frequency: 'daily', 'weekly', or 'monthly'. Default 'daily'.

        Returns:
            Dictionary with:
            - "assets": list of dicts with asset_id, symbol, name, beta,
              market_value, data_points
            - "insufficient_data_assets": list of asset symbols excluded
            - "data_points": number of return periods used
            - "frequency": the frequency used
        """
        if frequency not in ("daily", "weekly", "monthly"):
            raise ValueError(
                f"Unsupported frequency: {frequency}. "
                "Must be 'daily', 'weekly', or 'monthly'."
            )

        if not asset_daily_prices:
            return {
                "assets": [],
                "insufficient_data_assets": [],
                "data_points": 0,
                "frequency": frequency,
            }

        # 1. Get benchmark daily returns indexed by end date
        benchmark_returns_by_date = self._build_benchmark_returns_by_date(
            benchmark_id, start_date, end_date
        )

        if not benchmark_returns_by_date or len(benchmark_returns_by_date) < 2:
            logger.warning(
                f"Insufficient benchmark returns for benchmark {benchmark_id}"
            )
            return {
                "assets": [],
                "insufficient_data_assets": [a["symbol"] for a in asset_daily_prices],
                "data_points": 0,
                "frequency": frequency,
                "message": "Insufficient benchmark return data.",
            }

        # 2. For each asset, compute returns, align with benchmark, calculate beta
        min_data_points = min_data_points_for(frequency)
        result_assets = []
        insufficient_data = []
        data_points_list: list[int] = []

        for asset_info in asset_daily_prices:
            symbol = asset_info["symbol"]
            prices = asset_info["daily_prices"]
            price_dates = asset_info["price_dates"]

            if len(prices) < 2:
                insufficient_data.append(symbol)
                continue

            # Build asset daily returns indexed by end date
            asset_returns, asset_return_dates = prices_to_returns(prices, price_dates)

            # Align, aggregate, and compute beta
            beta, data_points = self._align_aggregate_and_compute_beta(
                item_returns=asset_returns,
                item_return_dates=asset_return_dates,
                benchmark_returns_by_date=benchmark_returns_by_date,
                frequency=frequency,
                min_data_points=min_data_points,
            )

            if beta is not None:
                result_assets.append({
                    "asset_id": asset_info["asset_id"],
                    "symbol": symbol,
                    "name": asset_info["name"],
                    "beta": beta,
                    "market_value": asset_info["market_value"],
                    "data_points": data_points,
                })
                data_points_list.append(data_points)
            else:
                insufficient_data.append(symbol)

        # Sort by market value descending
        result_assets.sort(key=lambda x: x["market_value"], reverse=True)

        return {
            "assets": result_assets,
            "insufficient_data_assets": insufficient_data,
            "data_points": min(data_points_list) if data_points_list else 0,
            "frequency": frequency,
        }

    def _calculate_max_drawdown(self, nav_history: list[float]) -> float:
        """Calculate maximum drawdown using NAV history."""
        if not nav_history or len(nav_history) < 2:
            return 0.0

        try:
            nav_array = np.array(nav_history, dtype=float)

            if np.any(np.isnan(nav_array)) or np.any(np.isinf(nav_array)):
                raise ValueError("NAV history contains NaN or infinite values")

            running_max = np.maximum.accumulate(nav_array)
            drawdown = (nav_array - running_max) / running_max
            max_dd = np.min(drawdown)

            return self._validate_numeric_value(max_dd, 0.0)

        except Exception as e:
            logger.exception(f"Error calculating max drawdown: {e}")
            return 0.0

    def calculate_statistics(
        self,
        portfolio_id: int,
        start_date: date,
        end_date: date,
        twr_data: dict,
        risk_free_rate: float = 0.0,
        benchmark_id: int = None
    ) -> dict:
        """Calculate portfolio performance statistics.

        Args:
            portfolio_id: The portfolio ID
            start_date: Start date for calculation
            end_date: End date for calculation
            twr_data: TWR calculation results
            risk_free_rate: Risk-free rate for Sharpe ratio calculation
            benchmark_id: Optional benchmark ID for beta and excess return calculation

        Returns:
            Dictionary with calculated statistics
        """
        period_days = (end_date - start_date).days
        daily_returns = twr_data.get("daily_returns", [])

        if len(daily_returns) > 1:
            returns_array = np.array(daily_returns, dtype=float)

            # Calculate volatility
            try:
                years = period_days / 365.25
                trading_days_per_year = 240
                volatility = np.std(returns_array, ddof=1) * np.sqrt(trading_days_per_year * years)
                volatility = self._validate_numeric_value(volatility, 0.0)
            except Exception as e:
                logger.exception(f"Error calculating volatility: {e}")
                volatility = 0.0

            # Calculate max drawdown
            try:
                nav_history = twr_data.get("nav_history", [])
                max_drawdown = self._calculate_max_drawdown(nav_history)
            except Exception as e:
                logger.exception(f"Error calculating max drawdown: {e}")
                max_drawdown = 0.0

            # Calculate Sharpe ratio
            try:
                annualized_return = twr_data.get("annualized_return", 0)
                if volatility > 0:
                    sharpe_ratio = (annualized_return - risk_free_rate) / volatility
                    sharpe_ratio = self._validate_numeric_value(sharpe_ratio, 0.0)
                else:
                    sharpe_ratio = 0.0
            except Exception as e:
                logger.exception(f"Error calculating Sharpe ratio: {e}")
                sharpe_ratio = 0.0
        else:
            volatility = 0.0
            max_drawdown = 0.0
            sharpe_ratio = 0.0

        result = {
            "time_weighted_return": self._validate_numeric_value(twr_data.get("twr", 0)),
            "annualized_return": self._validate_numeric_value(twr_data.get("annualized_return", 0)),
            "beginning_nav": self._validate_numeric_value(twr_data.get("beginning_nav", 0)),
            "ending_nav": self._validate_numeric_value(twr_data.get("ending_nav", 0)),
            "volatility": volatility,
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe_ratio,
            "period_days": period_days,
        }

        if benchmark_id and len(daily_returns) > 1:
            try:
                benchmark_stats = self._calculate_benchmark_statistics(
                    benchmark_id, start_date, end_date, twr_data.get("dates", []), twr_data.get("nav_history", [])
                )
                result.update(benchmark_stats)
            except Exception as e:
                logger.exception(f"Error calculating benchmark statistics: {e}")
                result["beta"] = 0.0
                result["excess_return"] = 0.0
                result["benchmark_return"] = 0.0

        return result
