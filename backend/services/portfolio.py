"""Portfolio service for portfolio calculations and statistics."""

from datetime import date, timedelta
from decimal import Decimal
from collections import defaultdict
from sqlmodel import select
from backend.db.models import Asset, AssetTag, Currency, Position, Settings, StockInfo, Tag
from backend.services.base import BaseService
from backend.services.currency import CurrencyService
from backend.services.price import PriceService
from backend.services.calculation import CalculationService
from backend.services.stats_utils import sanitize_matrix, date_range_list
from backend import logger
from backend.data_source import ths_source

# Import PositionService at module level to avoid circular imports
# This is placed at the end of imports
from backend.services.position import PositionService


class PortfolioService(BaseService):
    """Service for portfolio calculations and statistics."""

    def __init__(self, session):
        """Initialize portfolio service."""
        super().__init__(session)
        self.currency_service = CurrencyService(session)
        self.price_service = PriceService(session)
        self.calculation_service = CalculationService(session, self.currency_service)

    def calculate_portfolio_value(
        self, portfolio_id: int, as_of_date: date = None
    ) -> dict:
        """Calculate total portfolio value and store positions on the as_of_date."""
        if as_of_date is None:
            as_of_date = date.today()

        # Try to get positions for the exact date
        positions = self.session.exec(
            select(Position)
            .where(Position.portfolio_id == portfolio_id)
            .where(Position.position_date == as_of_date)
        ).all()

        # If no positions found for the exact date, incrementally calculate missing days
        if not positions:
            position_service = PositionService(self.session)
            position_service.ensure_positions_calculated(portfolio_id, as_of_date)
            positions = self.session.exec(
                select(Position)
                .where(Position.portfolio_id == portfolio_id)
                .where(Position.position_date == as_of_date)
            ).all()

        if not positions:
            return {
                "total_value": Decimal("0"),
                "positions": [],
                "calculation_date": as_of_date,
            }

        # Batch fetch all assets in one query to avoid N+1 problem
        asset_ids = {p.asset_id for p in positions}
        asset_map = self.get_asset_map(asset_ids)
        assets = list(asset_map.values())

        # Batch fetch all exchange rates in one query
        primary_currency = self.currency_service.get_primary_currency()
        currency_ids = {a.currency_id for a in assets if a.currency_id != primary_currency.id}
        rates_map = self.currency_service.get_exchange_rates(
            list(currency_ids), as_of_date, raise_on_missing=True,
        )

        total_value = Decimal("0")
        positions_value = []

        for position in positions:
            asset = asset_map.get(position.asset_id)
            if not asset:
                raise ValueError(f"Asset {position.asset_id} not found")

            if asset.currency_id == primary_currency.id:
                rate = Decimal("1.0")
            else:
                rate = rates_map.get(asset.currency_id)
                if rate is None:
                    raise ValueError(
                        f"Exchange rate not found for currency {asset.currency_id} on {as_of_date}"
                    )

            market_value_primary = position.market_value * rate
            total_pnl_primary = position.total_pnl * rate

            total_value += market_value_primary

            positions_value.append(
                {
                    "asset_id": position.asset_id,
                    "symbol": asset.symbol,
                    "name": asset.name,
                    "quantity": position.quantity,
                    "current_price": position.current_price,
                    "market_value": position.market_value,
                    "market_value_primary": market_value_primary,
                    "total_pnl": position.total_pnl,
                    "total_pnl_primary": total_pnl_primary,
                }
            )

        return {
            "total_value": total_value,
            "positions": positions_value,
            "calculation_date": as_of_date,
        }

    def twr(self, portfolio_id: int, start_date: date, end_date: date) -> dict:
        """Calculate Time-Weighted Return (TWR) for portfolio."""
        return self.calculation_service.calculate_twr(
            portfolio_id, start_date, end_date, self.calculate_portfolio_value
        )

    def _get_risk_free_rate(self) -> float:
        """Get the risk free rate from settings."""
        try:
            setting = self.session.exec(
                select(Settings).where(Settings.key == "risk_free_rate")
            ).first()
            if setting:
                return float(setting.value)
            return 0.0
        except Exception as e:
            logger.exception(f"Error retrieving risk-free rate from settings: {e}")
            return 0.0

    def calculate_portfolio_statistics(
        self, portfolio_id: int, start_date: date, end_date: date, benchmark_id: int = None
    ) -> dict:
        """Calculate portfolio performance statistics during a period."""
        try:
            twr_data = self.twr(portfolio_id, start_date, end_date)
        except Exception as e:
            logger.exception(f"Error calculating twr: {e}")
            period_days = (end_date - start_date).days
            return {
                "time_weighted_return": 0.0,
                "annualized_return": 0.0,
                "beginning_nav": 0.0,
                "ending_nav": 0.0,
                "volatility": 0.0,
                "max_drawdown": 0.0,
                "sharpe_ratio": 0.0,
                "period_days": period_days,
            }

        risk_free_rate = self._get_risk_free_rate()
        return self.calculation_service.calculate_statistics(
            portfolio_id, start_date, end_date, twr_data, risk_free_rate, benchmark_id
        )

    def get_asset_allocation(
        self,
        portfolio_id: int,
        as_of_date: date = None,
        by: str = 'type',
        tag_category_id: int = None
    ) -> dict:
        """Get asset allocation by type, tag, or specific tag category."""
        if as_of_date is None:
            as_of_date = date.today()

        if by not in ['type', 'tag']:
            raise ValueError('Invalid "by" parameter. Must be "type" or "tag".')

        try:
            positions = self.session.exec(
                select(Position)
                .where(Position.portfolio_id == portfolio_id)
                .where(Position.position_date == as_of_date)
            ).all()

            if not positions:
                return {"asset_allocation": {}, "total_value": 0}

            allocation = defaultdict(Decimal)
            total_value = Decimal("0")

            # Batch fetch assets and exchange rates for relevant positions
            relevant_positions = [p for p in positions if p.market_value and p.market_value > 0]
            asset_ids = {p.asset_id for p in relevant_positions}
            asset_map = self.get_asset_map(asset_ids)
            assets = list(asset_map.values())

            currency_ids = {a.currency_id for a in assets}
            rates = self.currency_service.get_exchange_rates(list(currency_ids), as_of_date)

            for position in relevant_positions:
                asset = asset_map.get(position.asset_id)
                if not asset:
                    continue

                rate = rates.get(asset.currency_id, Decimal("1.0"))
                market_value_primary = position.market_value * rate
                total_value += market_value_primary

                if by == 'type':
                    allocation[asset.type] += market_value_primary
                elif by == 'tag':
                    if tag_category_id:
                        asset_tag = self.session.exec(
                            select(AssetTag)
                            .join(Tag)
                            .where(AssetTag.asset_id == asset.id)
                            .where(Tag.category_id == tag_category_id)
                        ).first()

                        if asset_tag and asset_tag.tag:
                            allocation[asset_tag.tag.name] += market_value_primary * (asset_tag.weight / 100)
                        elif asset.type == 'cash':
                            allocation["Cash"] += market_value_primary
                        else:
                            allocation["Unknown"] += market_value_primary
                    else:
                        logger.warning(f"Asset {asset.id} ({asset.symbol}) has no tag_category_id {tag_category_id}")
                        allocation["Unknown"] += market_value_primary

            percentages = {}
            if total_value > 0:
                percentages = {
                    key: float(value / total_value)
                    for key, value in allocation.items()
                }
            return {
                "asset_allocation": percentages,
                "total_value": float(total_value)
            }

        except Exception as e:
            logger.exception(f"Error calculating asset allocation: {e}")
            return {"asset_allocation": {}, "total_value": 0}

    def get_asset_daily_prices(
        self,
        portfolio_id: int,
        start_date: date,
        end_date: date,
        top_n: int = 10,
        asset_id: int | None = None,
    ) -> dict:
        """Fetch daily price series for top N non-cash assets in a portfolio.

        Shared by asset-level calculations (e.g. calculate_asset_beta in
        CalculationService). Fetches positions, selects top assets by market
        value, and retrieves their price history from the Price table.

        Args:
            portfolio_id: The portfolio ID.
            start_date: Start date for the price series.
            end_date: End date for the price series.
            top_n: Number of top assets by market value. Default 10.
            asset_id: Optional specific asset ID to include even if not in top N.

        Returns:
            Dictionary with:
            - "assets": list of dicts with asset_id, symbol, name, market_value,
              daily_prices (list of float), price_dates (list of date)
            - "assets_found": whether any assets were found
        """
        from backend.db.models import Price as PriceModel

        # 1. Get positions on end_date to determine top assets
        portfolio_value = self.calculate_portfolio_value(portfolio_id, end_date)
        positions = portfolio_value.get("positions", [])

        # Filter out cash assets and sort by market value descending
        non_cash_positions = [
            p for p in positions if p.get("market_value_primary", 0) > 0
        ]
        position_asset_ids = {p["asset_id"] for p in non_cash_positions}
        asset_map = self.get_asset_map(position_asset_ids)

        non_cash_positions = [
            p for p in non_cash_positions
            if asset_map.get(p["asset_id"]) and asset_map[p["asset_id"]].type != "cash"
        ]
        non_cash_positions.sort(
            key=lambda p: p.get("market_value_primary", 0), reverse=True
        )

        # Select top N + optionally include the requested asset
        top_positions = non_cash_positions[:top_n]
        top_asset_ids = {p["asset_id"] for p in top_positions}

        if asset_id and asset_id not in top_asset_ids:
            asset_obj = self.session.get(Asset, asset_id)
            if asset_obj and asset_obj.type != "cash":
                specific_pos = next(
                    (p for p in non_cash_positions if p["asset_id"] == asset_id), None
                )
                if specific_pos:
                    top_positions.append(specific_pos)
                    top_asset_ids.add(asset_id)

        if not top_positions:
            return {"assets": [], "assets_found": False}

        # 2. Fetch price history for each selected asset
        result_assets = []
        for pos in top_positions:
            aid = pos["asset_id"]
            prices = self.session.exec(
                select(PriceModel)
                .where(PriceModel.asset_id == aid)
                .where(PriceModel.price_date >= start_date)
                .where(PriceModel.price_date <= end_date)
                .order_by(PriceModel.price_date)
            ).all()

            daily_prices = [float(p.price) for p in prices]
            price_dates = [p.price_date for p in prices]

            result_assets.append({
                "asset_id": aid,
                "symbol": pos["symbol"],
                "name": pos["name"],
                "market_value": float(pos.get("market_value_primary", 0)),
                "daily_prices": daily_prices,
                "price_dates": price_dates,
            })

        # Sort by market value descending
        result_assets.sort(key=lambda x: x["market_value"], reverse=True)

        return {
            "assets": result_assets,
            "assets_found": True,
        }

    def get_tag_daily_returns(
        self,
        portfolio_id: int,
        start_date: date,
        end_date: date,
        tag_category_id: int,
    ) -> dict:
        """Build calendar-aligned daily weighted price returns for each tag.

        Each tag is treated as a virtual sub-portfolio. Instead of tracking
        market value changes (which mix price movements with position-size
        changes from buying/selling), this method computes pure price returns
        for each constituent asset and weights them by the asset's market-value
        proportion within the tag on the previous day.

        This isolates price co-movement from principal (position-size) changes,
        giving a truer picture of how the underlying assets in each tag move
        together or against a benchmark.

        Days where no constituent asset's price changed (e.g. weekends or
        market holidays, when positions carry stale prices) are left as None
        so that non-trading days never enter correlation or beta estimates.

        The formula per day t:
            R_tag(t) = Σ w_i(t-1) × (price_i(t) / price_i(t-1) - 1)
        where:
            w_i(t-1) = mv_i(t-1) × tag_weight_i / Σ(mv_j(t-1) × tag_weight_j)

        Args:
            portfolio_id: The portfolio ID.
            start_date: Start date for the calculation period.
            end_date: End date for the calculation period.
            tag_category_id: Tag category ID to group tags by.

        Returns:
            Dictionary with:
            - "tag_names": list of tag names found in the category
            - "tag_calendar_returns": dict of tag_name -> list[float | None]
              aligned to return_dates (index i = return from
              return_dates[i]-1day to return_dates[i])
            - "return_dates": list of end dates for each return period
            - "asset_tags_found": whether any asset-tag pairs were found
        """
        if start_date > end_date:
            raise ValueError("start_date must not be later than end_date")

        # 1. Fetch all asset-tag relationships for this category
        asset_tags = self.session.exec(
            select(AssetTag, Tag)
            .join(Tag, AssetTag.tag_id == Tag.id)
            .where(Tag.category_id == tag_category_id)
        ).all()

        if not asset_tags:
            return {
                "tag_names": [],
                "tag_calendar_returns": {},
                "return_dates": [],
                "asset_tags_found": False,
            }

        # Build tag -> [(asset_id, weight)] mapping
        tag_assets: dict[str, list[tuple[int, Decimal]]] = defaultdict(list)
        all_asset_ids: set[int] = set()

        for asset_tag, tag in asset_tags:
            tag_assets[tag.name].append((asset_tag.asset_id, asset_tag.weight))
            all_asset_ids.add(asset_tag.asset_id)

        # 2. Fetch all positions in the date range for relevant assets
        positions = self.session.exec(
            select(Position)
            .where(Position.portfolio_id == portfolio_id)
            .where(Position.position_date >= start_date)
            .where(Position.position_date <= end_date)
            .where(Position.asset_id.in_(all_asset_ids))
        ).all()

        # Index positions by (date, asset_id)
        pos_by_date_asset: dict[tuple[date, int], Position] = {}
        for pos in positions:
            pos_by_date_asset[(pos.position_date, pos.asset_id)] = pos

        # 3. Batch fetch assets for currency info
        asset_map = self.get_asset_map(all_asset_ids)
        asset_currency_map = {a_id: a.currency_id for a_id, a in asset_map.items()}

        # 4. Build daily weighted price returns (in primary currency)
        #    Returns are stored keyed by the end date of the return period.
        tag_daily_returns: dict[str, dict[date, float]] = {
            tag: {} for tag in tag_assets
        }

        currency_ids = set(asset_currency_map.values())

        current = start_date + timedelta(days=1)
        while current <= end_date:
            prev_date = current - timedelta(days=1)
            # Exchange rates on prev_date for weight computation
            rates = self.currency_service.get_exchange_rates(
                list(currency_ids), prev_date
            )

            for tag_name, asset_list in tag_assets.items():
                # --- Compute previous-day market values for weights ---
                asset_prev_mv: dict[int, Decimal] = {}
                total_prev_mv = Decimal("0")

                for asset_id, weight in asset_list:
                    prev_pos = pos_by_date_asset.get((prev_date, asset_id))
                    if (
                        prev_pos is None
                        or prev_pos.market_value is None
                        or prev_pos.market_value <= 0
                    ):
                        continue
                    cid = asset_currency_map.get(asset_id)
                    if cid is None:
                        continue
                    rate = rates.get(cid)
                    if rate is None:
                        continue

                    mv_primary = (
                        prev_pos.market_value * rate * (weight / Decimal("100"))
                    )
                    asset_prev_mv[asset_id] = mv_primary
                    total_prev_mv += mv_primary

                if total_prev_mv <= 0:
                    continue

                # --- Compute weighted price return ---
                weighted_return = 0.0
                has_valid = False
                has_price_change = False

                for asset_id, tag_weight in asset_list:
                    prev_mv_primary = asset_prev_mv.get(asset_id)
                    if prev_mv_primary is None:
                        continue

                    prev_pos = pos_by_date_asset.get((prev_date, asset_id))
                    curr_pos = pos_by_date_asset.get((current, asset_id))

                    if prev_pos is None or curr_pos is None:
                        continue
                    if (
                        prev_pos.current_price is None
                        or curr_pos.current_price is None
                    ):
                        continue
                    if prev_pos.current_price <= 0:
                        continue

                    w = float(prev_mv_primary / total_prev_mv)
                    r = float(
                        curr_pos.current_price / prev_pos.current_price - 1
                    )
                    weighted_return += w * r
                    has_valid = True
                    if curr_pos.current_price != prev_pos.current_price:
                        has_price_change = True

                # Skip non-trading days: positions exist for every calendar day
                # but carry stale prices when nothing traded. Recording the
                # resulting all-zero returns would inject spurious shared zeros
                # into the correlation matrix and inflate data point counts.
                if has_valid and has_price_change:
                    tag_daily_returns[tag_name][current] = weighted_return

            current += timedelta(days=1)

        # 5. Build calendar-aligned return arrays
        return_dates = date_range_list(start_date + timedelta(days=1), end_date)

        tag_calendar_returns: dict[str, list[float | None]] = {
            tag: [None] * len(return_dates) for tag in tag_assets
        }
        for tag_name in tag_assets:
            for i, d in enumerate(return_dates):
                ret = tag_daily_returns[tag_name].get(d)
                if ret is not None:
                    tag_calendar_returns[tag_name][i] = ret

        return {
            "tag_names": list(tag_assets.keys()),
            "tag_calendar_returns": tag_calendar_returns,
            "return_dates": return_dates,
            "asset_tags_found": True,
        }

    def calculate_tag_correlation(
        self,
        portfolio_id: int,
        start_date: date,
        end_date: date,
        tag_category_id: int,
    ) -> dict:
        """Calculate correlation matrix between tag-based asset portfolios.

        Each tag is treated as a virtual sub-portfolio. Daily returns use
        weighted price returns: for each day, the return of a tag is the
        weighted sum of its constituent assets' pure price returns, weighted
        by each asset's market-value proportion within the tag on the previous
        day. This isolates price co-movement from position-size changes caused
        by buying and selling.

        Pearson correlation coefficients are then computed from the aligned
        return series.

        Args:
            portfolio_id: The portfolio ID.
            start_date: Start date for the calculation period.
            end_date: End date for the calculation period.
            tag_category_id: Tag category ID to group tags by.

        Returns:
            Dictionary with:
            - "tags": list of tag names in matrix order
            - "correlation_matrix": 2D list of correlation coefficients
            - "insufficient_data_tags": list of tags excluded due to insufficient data
            - "data_points": number of aligned daily returns used
        """
        import numpy as np

        # 1. Get calendar-aligned daily weighted price returns for all tags
        tag_data = self.get_tag_daily_returns(
            portfolio_id, start_date, end_date, tag_category_id
        )

        tag_names = tag_data["tag_names"]
        tag_calendar_returns = tag_data["tag_calendar_returns"]
        return_dates = tag_data["return_dates"]

        if len(tag_names) < 2:
            return {
                "tags": tag_names,
                "correlation_matrix": [],
                "insufficient_data_tags": [],
                "data_points": 0,
                "message": "At least two tags are required to compute correlations.",
            }

        # 2. Helper: align pre-computed returns for a set of tags
        def _align_returns(tag_names_subset: list[str]) -> tuple[list[list[float]], int]:
            """Collect indices where ALL tags have valid returns."""
            returns: dict[str, list[float]] = {t: [] for t in tag_names_subset}
            for i in range(len(return_dates)):
                day_returns = {}
                all_valid = True
                for t in tag_names_subset:
                    ret = tag_calendar_returns[t][i]
                    if ret is None:
                        all_valid = False
                        break
                    day_returns[t] = ret
                if all_valid:
                    for t, r in day_returns.items():
                        returns[t].append(r)
            result = [returns[t] for t in tag_names_subset]
            n = len(result[0]) if result else 0
            return result, n

        # 3. Iteratively prune the sparsest tag until all remaining tags meet the
        #    minimum. A tag that is insufficient only because of another sparse
        #    tag gets a fair chance once that tag is removed, instead of being
        #    wrongly excluded by a single joint pass over all tags.
        min_data_points = 20
        candidate_tags = list(tag_names)
        insufficient_tags = []

        while len(candidate_tags) >= 2:
            _, n = _align_returns(candidate_tags)
            if n >= min_data_points:
                break
            # Drop the tag with the fewest individual valid days — it is the
            # most likely to be limiting the joint alignment.
            individual_counts = {
                t: sum(1 for r in tag_calendar_returns[t] if r is not None)
                for t in candidate_tags
            }
            worst_tag = min(candidate_tags, key=lambda t: individual_counts[t])
            candidate_tags.remove(worst_tag)
            insufficient_tags.append(worst_tag)

        sufficient_tags = candidate_tags

        if len(sufficient_tags) < 2:
            # Need at least 2 tags to compute a correlation matrix. Any
            # leftover tag that survived pruning but cannot be paired is also
            # insufficient for correlation purposes.
            insufficient_tags.extend(sufficient_tags)
            return {
                "tags": [],
                "correlation_matrix": [],
                "insufficient_data_tags": insufficient_tags,
                "data_points": 0,
                "message": f"At least two tags with {min_data_points}+ data points required.",
            }

        # 4. Final aligned returns for the surviving tags
        final_returns, data_points = _align_returns(sufficient_tags)

        # 5. Compute correlation matrix
        returns_array = np.array(final_returns, dtype=float)
        if data_points > 0 and len(sufficient_tags) >= 2:
            with np.errstate(invalid="ignore"):
                corr_matrix = np.corrcoef(returns_array)
            # Replace NaN with 0 (can happen with zero-variance series)
            corr_matrix = sanitize_matrix(corr_matrix)
        else:
            corr_matrix = np.zeros((len(sufficient_tags), len(sufficient_tags)))

        return {
            "tags": sufficient_tags,
            "correlation_matrix": corr_matrix.tolist(),
            "insufficient_data_tags": insufficient_tags,
            "data_points": data_points,
        }

    def _get_stock_position_dicts(self, portfolio_id: int, as_of_date: date) -> list[dict]:
        """Get stock positions for a portfolio on a given date as plain dicts."""
        position_service = PositionService(self.session)
        positions = position_service.get_positions_on_date(portfolio_id, as_of_date)

        stock_positions = []
        for position in positions:
            asset = self.session.get(Asset, position.asset_id)
            if not asset or asset.type != "stock":
                continue

            currency = self.session.get(Currency, asset.currency_id) if asset else None
            currency_data = None
            if currency:
                currency_data = {
                    "id": currency.id,
                    "code": currency.code,
                    "name": currency.name,
                    "symbol": currency.symbol,
                    "is_primary": currency.is_primary,
                }

            stock_positions.append({
                "asset_id": asset.id,
                "symbol": asset.symbol,
                "name": asset.name,
                "current_price": float(position.current_price) if position.current_price else None,
                "currency": currency_data,
                "currency_id": asset.currency_id if asset else None,
            })
        return stock_positions

    @staticmethod
    def _calc_financial_metrics(
        current_price: float | None,
        dividend_after_tax: float,
        total_shares: float,
        ni_to_parent: float,
        equity_to_parent: float,
        exchange_rate: float = 1.0,
    ) -> dict:
        """Calculate dividend yield, PE and PB from raw financial data.

        PE and PB use CNY price because total_shares, ni_to_parent and
        equity_to_parent are already in CNY. Dividend yield is computed in
        the original currency since dividend_after_tax and current_price share
        the same currency.

        PE is negative for loss-making companies (negative ni_to_parent) and
        None when earnings are zero; PB is only computed for positive equity.
        """
        price_cny = current_price * exchange_rate if current_price else None

        dividend_yield = None
        if current_price and current_price > 0:
            dividend_yield = dividend_after_tax / current_price

        pe = None
        if price_cny and total_shares > 0 and ni_to_parent != 0:
            pe = round(price_cny * total_shares / ni_to_parent, 2)

        pb = None
        if price_cny and total_shares > 0 and equity_to_parent > 0:
            pb = round(price_cny * total_shares / equity_to_parent, 2)

        return {
            "dividend_yield": dividend_yield,
            "pe": pe,
            "pb": pb,
        }

    def get_financial_positions(self, portfolio_id: int, as_of_date: date) -> list[dict]:
        """Read cached financial positions from the database.

        If no StockInfo exists for the exact as_of_date, falls back to the
        most recent record before that date for each stock.
        """
        stock_positions = self._get_stock_position_dicts(portfolio_id, as_of_date)
        if not stock_positions:
            return []

        result = []
        for pos in stock_positions:
            # Try exact date first
            stock_info = self.session.exec(
                select(StockInfo).where(
                    StockInfo.asset_id == pos["asset_id"],
                    StockInfo.report_date == as_of_date,
                )
            ).first()

            # Fallback to the most recent record before as_of_date
            if not stock_info:
                stock_info = self.session.exec(
                    select(StockInfo)
                    .where(
                        StockInfo.asset_id == pos["asset_id"],
                        StockInfo.report_date < as_of_date,
                    )
                    .order_by(StockInfo.report_date.desc())
                ).first()

            dividend_after_tax = stock_info.dividend_after_tax if stock_info else 0.0
            total_shares = float(stock_info.total_shares) if stock_info else 0.0
            ni_to_parent = float(stock_info.ni_to_parent) if stock_info else 0.0
            equity_to_parent = float(stock_info.equity_to_parent) if stock_info else 0.0

            rate = Decimal("1.0")
            if pos.get("currency_id"):
                fetched_rate = self.currency_service.get_exchange_rate(
                    pos["currency_id"], as_of_date
                )
                if fetched_rate is not None:
                    rate = fetched_rate

            metrics = self._calc_financial_metrics(
                pos["current_price"],
                dividend_after_tax,
                total_shares,
                ni_to_parent,
                equity_to_parent,
                float(rate),
            )

            result.append({
                "symbol": pos["symbol"],
                "name": pos["name"],
                "current_price": pos["current_price"],
                "dividend_after_tax": dividend_after_tax,
                **metrics,
                "currency": pos["currency"],
            })
        return result

    def fetch_and_save_financial_positions(self, portfolio_id: int, as_of_date: date) -> list[dict]:
        """Fetch financial data from THS, save to database, and return results."""
        stock_positions = self._get_stock_position_dicts(portfolio_id, as_of_date)
        if not stock_positions:
            return []

        symbols = [p["symbol"] for p in stock_positions]

        hkd_cny_rate = 1.0
        hkd_currency = self.session.exec(
            select(Currency).where(Currency.code == "HKD")
        ).first()
        if hkd_currency:
            rate = self.currency_service.get_exchange_rate(hkd_currency.id, as_of_date)
            if rate is not None:
                hkd_cny_rate = float(rate)

        dividend_results = ths_source.get_dividend_after_tax_past_year(
            symbols=symbols,
            as_of_date=as_of_date,
            hkd_cny_rate=hkd_cny_rate,
        )
        dividend_map = {symbol: dividend for symbol, dividend in dividend_results}

        financials = ths_source.get_stock_financials(symbols, as_of_date)

        result = []
        for pos in stock_positions:
            symbol = pos["symbol"]
            dividend_after_tax = dividend_map.get(symbol, 0.0)
            current_price = pos["current_price"]

            fin = financials.get(symbol, {})
            total_shares = fin.get("total_shares", 0.0)
            ni_to_parent = fin.get("ni_to_parent", 0.0)
            equity_to_parent = fin.get("equity_to_parent", 0.0)

            rate = Decimal("1.0")
            if pos.get("currency_id"):
                fetched_rate = self.currency_service.get_exchange_rate(
                    pos["currency_id"], as_of_date
                )
                if fetched_rate is not None:
                    rate = fetched_rate

            metrics = self._calc_financial_metrics(
                current_price,
                dividend_after_tax,
                total_shares,
                ni_to_parent,
                equity_to_parent,
                float(rate),
            )

            stock_info = self.session.exec(
                select(StockInfo).where(
                    StockInfo.asset_id == pos["asset_id"],
                    StockInfo.report_date == as_of_date,
                )
            ).first()

            if stock_info:
                stock_info.dividend_before_tax = 0.0
                stock_info.dividend_after_tax = dividend_after_tax
                stock_info.total_shares = total_shares
                stock_info.ni_to_parent = ni_to_parent
                stock_info.equity_to_parent = equity_to_parent
            else:
                stock_info = StockInfo(
                    asset_id=pos["asset_id"],
                    symbol=symbol,
                    report_date=as_of_date,
                    dividend_before_tax=0.0,
                    dividend_after_tax=dividend_after_tax,
                    total_shares=total_shares,
                    ni_to_parent=ni_to_parent,
                    equity_to_parent=equity_to_parent,
                )
                self.session.add(stock_info)

            result.append({
                "symbol": symbol,
                "name": pos["name"],
                "current_price": current_price,
                "dividend_after_tax": dividend_after_tax,
                **metrics,
                "currency": pos["currency"],
            })

        return result
