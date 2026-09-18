"""Position service for position calculations and management."""

from datetime import date, timedelta
from decimal import Decimal
from collections import defaultdict
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlmodel import select
from backend.db.models import Asset, Currency, Position, Transaction
from backend.services.base import BaseService
from backend.services.currency import CurrencyService
from backend.services.price import PriceService


class CashFlowTracker:
    """Track cash flows for P&L calculation."""

    def __init__(self):
        self._data = defaultdict(
            lambda: {
                "cash_paid_on_bought": Decimal("0"),
                "cash_received_on_sale": Decimal("0"),
                "dividends_received": Decimal("0"),
            }
        )

    def add(self, asset_id: int, flow_type: str, amount: Decimal) -> None:
        self._data[asset_id][flow_type] += amount

    def get(self, asset_id: int, flow_type: str) -> Decimal:
        return self._data[asset_id][flow_type]


class PositionService(BaseService):
    """Service for position calculations and management."""

    def __init__(self, session):
        """Initialize position service."""
        super().__init__(session)
        self.currency_service = CurrencyService(session)
        self.price_service = PriceService(session)

    def get_first_transaction_date(self, portfolio_id: int) -> date | None:
        """Get the earliest transaction date for a portfolio.

        Returns None when the portfolio has no transactions.
        """
        first_txn = self.session.exec(
            select(Transaction)
            .where(Transaction.portfolio_id == portfolio_id)
            .order_by(Transaction.trade_date)
        ).first()
        return first_txn.trade_date if first_txn else None

    def get_positions_on_date(
        self, portfolio_id: int, on_date: date
    ) -> list[Position]:
        """Get positions from database for a portfolio on a specific date."""
        positions = self.session.exec(
            select(Position)
            .where(Position.portfolio_id == portfolio_id)
            .where(Position.position_date == on_date)
        ).all()
        return positions

    def get_dividends_by_asset(
        self, portfolio_id: int, end_date: date
    ) -> dict[int, Decimal]:
        """Get total cash dividends received per asset up to end_date (inclusive).

        Sums (amount - fees) for all ``dividends`` transactions with
        ``trade_date <= end_date``. The dividend amount is in the asset's
        own currency (the transaction's ``currency_id`` matches the asset's
        currency for dividend transactions).

        Returns:
            A dict mapping ``asset_id`` to total dividends received.
        """
        rows = self.session.exec(
            select(Transaction)
            .where(Transaction.portfolio_id == portfolio_id)
            .where(Transaction.action == "dividends")
            .where(Transaction.trade_date <= end_date)
        ).all()

        totals: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
        for txn in rows:
            fees = txn.fees or Decimal("0")
            totals[txn.asset_id] += txn.amount - fees
        return totals

    def _get_cash_asset(self, currency_id: int) -> Asset | None:
        """Get the cash asset for a given currency."""
        currency = self.session.get(Currency, currency_id)
        if not currency:
            return None

        cash_symbol = f"{currency.code}_CASH"
        cash_asset = self.session.exec(
            select(Asset)
            .where(Asset.symbol == cash_symbol)
            .where(Asset.type == "cash")
        ).first()

        return cash_asset

    def save_positions(self, positions: dict[int, Position]):
        """Save calculated positions to database using upsert to avoid
        autoflush-triggered UNIQUE constraint violations under concurrent access."""
        for position in positions.values():
            stmt = (
                sqlite_insert(Position)
                .values(
                    portfolio_id=position.portfolio_id,
                    asset_id=position.asset_id,
                    position_date=position.position_date,
                    quantity=position.quantity,
                    average_cost=position.average_cost,
                    current_price=position.current_price,
                    market_value=position.market_value,
                    total_pnl=position.total_pnl,
                )
                .on_conflict_do_update(
                    index_elements=["portfolio_id", "position_date", "asset_id"],
                    set_={
                        "quantity": position.quantity,
                        "average_cost": position.average_cost,
                        "current_price": position.current_price,
                        "market_value": position.market_value,
                        "total_pnl": position.total_pnl,
                    },
                )
            )
            self.session.exec(stmt)

        self.session.commit()

    def get_latest_positions(self, portfolio_id: int) -> list[Position]:
        """Get the latest positions for a portfolio."""
        positions = self.session.exec(
            select(Position)
            .where(Position.portfolio_id == portfolio_id)
            .order_by(Position.position_date.desc())
        ).all()

        latest_positions = {}
        for position in positions:
            if position.asset_id not in latest_positions:
                latest_positions[position.asset_id] = position

        return list(latest_positions.values())

    def compute_period_end_positions(
        self,
        portfolio_id: int,
        start_date: date,
        end_date: date,
        save_to_db: bool = True,
    ) -> dict[int, Position]:
        """Calculate the last positions at end_date generated by transactions during a given period.

        Args:
            portfolio_id: The portfolio ID
            start_date: Including transactions on start_date
            end_date: Including transactions on end_date
            save_to_db: Whether to save the calculated positions to the database

        Returns:
            A dictionary of asset_id to Position objects, representing the last positions at end_date.
        """
        transactions = self._fetch_transactions(portfolio_id, start_date, end_date)
        initial_positions = self.get_positions_on_date(portfolio_id, start_date - timedelta(days=1))

        final_positions, init_positions_dict = self._init_positions(
            portfolio_id, end_date, initial_positions
        )
        cash_flows = CashFlowTracker()

        for txn in transactions:
            self._process_transaction(txn, final_positions, cash_flows, end_date)

        self._calculate_metrics(final_positions, init_positions_dict, cash_flows, end_date)

        if save_to_db:
            self.save_positions(final_positions)

        return final_positions

    def recalculate_positions_daily(
        self,
        portfolio_id: int,
        end_date: date,
    ) -> dict:
        """Recalculate and save positions for every day from the first transaction date to end_date.

        Existing positions in the range are deleted first, then positions for every day
        are recomputed by reusing ``compute_period_end_positions`` one day at a time so that
        each day's calculation builds on the previous day's saved snapshot.

        Args:
            portfolio_id: The portfolio ID
            end_date: The last date to compute positions for (inclusive)

        Returns:
            A dictionary with ``start_date``, ``end_date`` and ``days_processed``.
        """
        start_date = self.get_first_transaction_date(portfolio_id)

        if not start_date:
            return {"start_date": None, "end_date": end_date, "days_processed": 0}

        if start_date > end_date:
            return {"start_date": start_date, "end_date": end_date, "days_processed": 0}

        existing_positions = self.session.exec(
            select(Position)
            .where(Position.portfolio_id == portfolio_id)
            .where(Position.position_date >= start_date)
            .where(Position.position_date <= end_date)
        ).all()
        for pos in existing_positions:
            self.session.delete(pos)
        self.session.commit()

        days_processed = 0
        current_date = start_date
        while current_date <= end_date:
            self.compute_period_end_positions(
                portfolio_id=portfolio_id,
                start_date=current_date,
                end_date=current_date,
                save_to_db=True,
            )
            days_processed += 1
            current_date += timedelta(days=1)

        return {
            "start_date": start_date,
            "end_date": end_date,
            "days_processed": days_processed,
        }

    def ensure_positions_calculated(self, portfolio_id: int, end_date: date) -> None:
        """Ensure positions are calculated and saved up to end_date, filling any gaps.

        Queries all existing position dates in the range from the first transaction
        to ``end_date``, finds the earliest missing day, and incrementally calculates
        from that day forward. This handles both trailing gaps and historical holes.
        """
        start_date = self.get_first_transaction_date(portfolio_id)
        if not start_date:
            return

        if start_date > end_date:
            return

        existing_dates = set(
            self.session.exec(
                select(Position.position_date)
                .where(Position.portfolio_id == portfolio_id)
                .where(Position.position_date >= start_date)
                .where(Position.position_date <= end_date)
                .distinct()
            ).all()
        )

        current_date = start_date
        while current_date <= end_date:
            if current_date not in existing_dates:
                break
            current_date += timedelta(days=1)

        if current_date > end_date:
            return

        while current_date <= end_date:
            self.compute_period_end_positions(
                portfolio_id=portfolio_id,
                start_date=current_date,
                end_date=current_date,
                save_to_db=True,
            )
            current_date += timedelta(days=1)

    def _fetch_transactions(
        self, portfolio_id: int, start_date: date, end_date: date
    ) -> list[Transaction]:
        """Fetch transactions for the period."""
        return self.session.exec(
            select(Transaction)
            .where(Transaction.portfolio_id == portfolio_id)
            .where(Transaction.trade_date >= start_date)
            .where(Transaction.trade_date <= end_date)
            .order_by(Transaction.trade_date)
        ).all()

    def _init_positions(
        self, portfolio_id: int, end_date: date, initial_positions: list[Position]
    ) -> tuple[dict[int, Position], dict[int, Position]]:
        """Initialize positions from initial data."""
        final_positions = {}
        init_dict = {}

        for pos in initial_positions or []:
            final_positions[pos.asset_id] = self._create_position(
                portfolio_id,
                pos.asset_id,
                end_date,
                quantity=pos.quantity,
                average_cost=pos.average_cost,
                current_price=pos.current_price,
                market_value=pos.market_value or Decimal("0"),
                total_pnl=pos.total_pnl or Decimal("0"),
            )
            init_dict[pos.asset_id] = pos

        return final_positions, init_dict

    def _create_position(
        self, portfolio_id: int, asset_id: int, position_date: date, **kwargs
    ) -> Position:
        """Factory method to create a Position with defaults."""
        defaults = {
            "quantity": Decimal("0"),
            "average_cost": Decimal("0"),
            "current_price": Decimal("0"),
            "market_value": Decimal("0"),
            "total_pnl": Decimal("0"),
        }
        defaults.update(kwargs)
        return Position(
            portfolio_id=portfolio_id,
            asset_id=asset_id,
            position_date=position_date,
            **defaults
        )

    def _get_or_create_position(
        self, positions: dict[int, Position], portfolio_id: int, asset_id: int, on_date: date
    ) -> Position:
        """Get existing position or create new one."""
        if asset_id not in positions:
            positions[asset_id] = self._create_position(portfolio_id, asset_id, on_date)
        return positions[asset_id]

    def _process_transaction(
        self,
        txn: Transaction,
        positions: dict[int, Position],
        cash_flows: CashFlowTracker,
        on_date: date,
    ) -> None:
        """Process a single transaction."""
        asset_pos = self._get_or_create_position(positions, txn.portfolio_id, txn.asset_id, on_date)

        cash_asset = self._get_cash_asset(txn.currency_id)
        if not cash_asset:
            raise ValueError(f"Cash asset not found for currency {txn.currency_id}")

        cash_pos = self._get_or_create_position(positions, txn.portfolio_id, cash_asset.id, on_date)
        cash_pos.average_cost = Decimal("1.0")

        match txn.action:
            case "buy":
                self._handle_buy(txn, asset_pos, cash_pos, cash_flows)
            case "sell":
                self._handle_sell(txn, asset_pos, cash_pos, cash_flows)
            case "dividends":
                self._handle_dividends(txn, asset_pos, cash_pos, cash_flows)
            case "split":
                self._handle_split(txn, asset_pos, cash_pos, cash_flows)
            case "cash_in":
                self._handle_cash_in(txn, asset_pos, cash_pos, cash_flows)
            case "cash_out":
                self._handle_cash_out(txn, asset_pos, cash_pos, cash_flows)

    def _handle_buy(
        self, txn: Transaction, position: Position, cash_pos: Position, cash_flows: CashFlowTracker
    ) -> None:
        """Handle buy transaction."""
        total_cost = position.average_cost * position.quantity
        fees = txn.fees or Decimal("0")
        position.quantity += txn.quantity
        position.average_cost = (total_cost + txn.amount + fees) / position.quantity

        cash_flows.add(txn.asset_id, "cash_paid_on_bought", txn.amount + fees)
        cash_pos.quantity -= txn.amount + fees

    def _handle_sell(
        self, txn: Transaction, position: Position, cash_pos: Position, cash_flows: CashFlowTracker
    ) -> None:
        """Handle sell transaction."""
        position.quantity -= txn.quantity

        fees = txn.fees or Decimal("0")
        cash_flows.add(txn.asset_id, "cash_received_on_sale", txn.amount - fees)
        cash_pos.quantity += txn.amount - fees

    def _handle_dividends(
        self, txn: Transaction, position: Position, cash_pos: Position, cash_flows: CashFlowTracker
    ) -> None:
        """Handle dividends transaction."""
        fees = txn.fees or Decimal("0")
        cash_flows.add(txn.asset_id, "dividends_received", txn.amount - fees)
        cash_pos.quantity += txn.amount - fees

    def _handle_split(
        self, txn: Transaction, position: Position, cash_pos: Position, cash_flows: CashFlowTracker
    ) -> None:
        """Handle stock split."""
        split_ratio = txn.quantity
        position.quantity *= split_ratio
        position.average_cost /= split_ratio

    def _handle_cash_in(
        self, txn: Transaction, position: Position, cash_pos: Position, cash_flows: CashFlowTracker
    ) -> None:
        """Handle cash in."""
        cash_pos.quantity += txn.amount

    def _handle_cash_out(
        self, txn: Transaction, position: Position, cash_pos: Position, cash_flows: CashFlowTracker
    ) -> None:
        """Handle cash out."""
        cash_pos.quantity -= txn.amount

    def _calculate_metrics(
        self,
        positions: dict[int, Position],
        init_positions: dict[int, Position],
        cash_flows: CashFlowTracker,
        end_date: date,
    ) -> None:
        """Calculate prices, market values and P&L for all positions."""
        asset_ids = list(positions.keys())
        prices = self.price_service.get_latest_prices(asset_ids, end_date)
        asset_map = self.get_asset_map(asset_ids)

        for asset_id, position in positions.items():
            latest_price = prices.get(asset_id)
            if latest_price:
                position.current_price = latest_price.price

            position.market_value = position.quantity * position.current_price
            asset = asset_map.get(asset_id)
            if not asset or asset.type == "cash":
                position.total_pnl = Decimal("0")
            else:
                profit_0 = (
                    init_positions[asset_id].total_pnl if asset_id in init_positions else Decimal("0")
                )
                market_value_0 = (
                    init_positions[asset_id].market_value
                    if asset_id in init_positions
                    else Decimal("0")
                )
                position.total_pnl = (
                    profit_0
                    + position.market_value
                    - market_value_0
                    + cash_flows.get(asset_id, "cash_received_on_sale")
                    + cash_flows.get(asset_id, "dividends_received")
                    - cash_flows.get(asset_id, "cash_paid_on_bought")
                )
