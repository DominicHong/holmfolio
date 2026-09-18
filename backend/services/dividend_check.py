"""Service for checking and backfilling missing dividend transactions."""

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from sqlmodel import select

from backend import logger
from backend.data_source import akshare_source, ths_source
from backend.db.models import Transaction
from backend.services.base import BaseService
from backend.services.position import PositionService

DIVIDEND_MATCH_WINDOW_DAYS = 60
_MONEY = Decimal("0.01")


def _round_money(value: Decimal) -> Decimal:
    """Round a Decimal to 2 decimal places (half up)."""
    return value.quantize(_MONEY, rounding=ROUND_HALF_UP)


class DividendCheckService(BaseService):
    """Detect dividends that occurred during holding periods but were never recorded."""

    def check_missing_dividends(self, portfolio_id: int) -> dict:
        """Check all ever-held assets for unrecorded dividends.

        For each non-cash asset with buy/sell/split transactions, the
        holding intervals are derived from the transactions and the asset's
        dividend history is fetched via AKShare. A dividend is reported as
        missing when the shares were held on the record date (A股股权登记日
        for A-shares, 除净日 - 1 for HK stocks) and there is no matching
        ``dividends`` transaction (within a 60-day window around the received
        date). The expected amount is computed as shares held at the record
        date times the after-tax dividend per share.

        Args:
            portfolio_id: The portfolio ID.

        Returns:
            Dict with ``assets_checked``, ``dividend_events_found`` and
            ``missing`` (list of candidate dicts).
        """
        transactions = self.session.exec(
            select(Transaction).where(Transaction.portfolio_id == portfolio_id)
        ).all()

        held_txns = [t for t in transactions if t.action in ("buy", "sell", "split")]
        existing_dividends = [t for t in transactions if t.action == "dividends"]

        asset_ids = {t.asset_id for t in held_txns}
        asset_map = self.get_asset_map(asset_ids)

        missing: list[dict] = []
        assets_checked = 0
        dividend_events_found = 0

        for asset_id in asset_ids:
            asset = asset_map.get(asset_id)
            if not asset or asset.type == "cash":
                continue

            asset_txns = sorted(
                [t for t in held_txns if t.asset_id == asset_id],
                key=lambda t: t.trade_date,
            )
            if not asset_txns:
                continue

            assets_checked += 1
            intervals = self._holding_intervals(asset_txns)
            start_year = asset_txns[0].trade_date.year
            history = akshare_source.get_dividend_history(
                asset.symbol, asset.type, start_year
            )
            tax_factor = self._tax_factor(asset.symbol, asset.type)

            for event in history:
                dividend_events_found += 1
                record_date = event["record_date"]
                received_date = event["received_date"]

                if received_date > date.today():
                    continue

                if not any(start <= record_date <= end for start, end in intervals):
                    continue

                quantity = self._quantity_as_of(asset_txns, record_date)
                if quantity <= 0:
                    continue

                per_share = event["per_share"]
                amount = _round_money(quantity * per_share * tax_factor)
                if amount <= 0:
                    continue

                if self._is_already_recorded(existing_dividends, asset_id, received_date):
                    continue

                holding_start, holding_end = next(
                    (start, end)
                    for start, end in intervals
                    if start <= record_date <= end
                )
                currency_code = asset.currency.code if asset.currency else ""
                missing.append(
                    {
                        "asset_id": asset_id,
                        "symbol": asset.symbol,
                        "name": asset.name,
                        "record_date": record_date,
                        "received_date": received_date,
                        "report_date": event.get("report_date"),
                        "per_share": float(per_share),
                        "quantity": float(quantity),
                        "amount": float(amount),
                        "currency_id": asset.currency_id,
                        "currency": currency_code,
                        "holding_start": holding_start,
                        "holding_end": holding_end,
                        "scheme": event.get("scheme"),
                        "notes": (
                            f"Auto-detected dividend, received {received_date} "
                            f"({event.get('scheme')})"
                        ),
                    }
                )

        return {
            "assets_checked": assets_checked,
            "dividend_events_found": dividend_events_found,
            "missing": missing,
        }

    def add_missing_dividends(self, portfolio_id: int, items: list[dict]) -> dict:
        """Insert dividend transactions for the given items and recalculate positions.

        Each item is a dict from :meth:`check_missing_dividends` (``asset_id``,
        ``received_date``, ``per_share``, ``quantity``, ``amount``,
        ``currency_id``, ``notes``). The trade date is the received date
        (A股除权除息日 for A-shares, 派息日 for HK stocks). After inserting,
        positions are fully recalculated up to today via
        :meth:`PositionService.recalculate_positions_daily`.

        Args:
            portfolio_id: The portfolio ID.
            items: List of missing-dividend items to add.

        Returns:
            Dict with ``added`` (count) and ``positions_recalculated``.
        """
        added = 0
        for item in items:
            trade_date = item.get("received_date") or item.get("record_date")
            if isinstance(trade_date, str):
                trade_date = date.fromisoformat(trade_date)

            self.session.add(
                Transaction(
                    portfolio_id=portfolio_id,
                    trade_date=trade_date,
                    action="dividends",
                    asset_id=item["asset_id"],
                    quantity=Decimal(str(item["quantity"])),
                    price=Decimal(str(item["per_share"])),
                    amount=Decimal(str(item["amount"])),
                    fees=Decimal("0"),
                    currency_id=item["currency_id"],
                    notes=item.get("notes"),
                )
            )
            added += 1

        if added:
            self.session.commit()
            PositionService(self.session).recalculate_positions_daily(
                portfolio_id, date.today()
            )

        return {"added": added, "positions_recalculated": added > 0}

    def _holding_intervals(self, txns: list[Transaction]) -> list[tuple[date, date]]:
        """Derive holding intervals (quantity > 0) from buy/sell/split transactions.

        A split multiplies the held quantity by its ratio. An interval starts
        on the date the cumulative quantity first becomes positive and ends on
        the date it returns to zero; an open interval ends today.

        Args:
            txns: Buy/sell/split transactions sorted by trade date.

        Returns:
            List of (start, end) date tuples.
        """
        intervals: list[tuple[date, date]] = []
        quantity = Decimal("0")
        start: date | None = None

        for txn in txns:
            if txn.action == "buy":
                quantity += txn.quantity
            elif txn.action == "sell":
                quantity -= txn.quantity
            elif txn.action == "split":
                quantity *= txn.quantity

            if quantity > 0 and start is None:
                start = txn.trade_date
            elif quantity <= 0 and start is not None:
                intervals.append((start, txn.trade_date))
                start = None

        if start is not None:
            intervals.append((start, date.today()))

        return intervals

    def _quantity_as_of(self, txns: list[Transaction], on_date: date) -> Decimal:
        """Compute the held quantity at the end of ``on_date``.

        Buys add, sells subtract and splits multiply. Transactions after
        ``on_date`` are ignored so that a dividend applies to the shares held
        on the record date.

        Args:
            txns: Buy/sell/split transactions sorted by trade date.
            on_date: The reference date.

        Returns:
            The cumulative quantity on or before ``on_date``.
        """
        quantity = Decimal("0")
        for txn in txns:
            if txn.trade_date > on_date:
                break
            if txn.action == "buy":
                quantity += txn.quantity
            elif txn.action == "sell":
                quantity -= txn.quantity
            elif txn.action == "split":
                quantity *= txn.quantity
        return quantity

    def _is_already_recorded(
        self, dividends: list[Transaction], asset_id: int, received_date: date
    ) -> bool:
        """Return True when a dividends transaction exists near the received date."""
        for txn in dividends:
            if txn.asset_id != asset_id:
                continue
            if abs((txn.trade_date - received_date).days) <= DIVIDEND_MATCH_WINDOW_DAYS:
                return True
        return False

    def _tax_factor(self, symbol: str, asset_type: str) -> Decimal:
        """Return the after-tax factor for a dividend per share.

        A-shares pay the before-tax amount. HK stocks follow the same
        convention as :meth:`THSDataSource.get_dividend_after_tax_past_year`:
        red chips and A+H dual-listed companies have 10% withheld (factor
        0.9); other HK stocks are paid in full. The classification only
        applies to HK stock assets and reads ``data/hk_stock_cache.json``;
        non-stock or non-HK assets always use factor 1.0 and never touch
        the cache.

        Args:
            symbol: Asset symbol.
            asset_type: Asset type (stock, bond, fund, etf, cash).

        Returns:
            The after-tax factor.
        """
        if asset_type != "stock" or not symbol.endswith(".HK"):
            return Decimal("1.0")

        _, (normalized,) = ths_source._normalize_symbols([symbol])
        try:
            info = ths_source._resolve_hk_stock_info([normalized]).get(normalized, {})
        except Exception as e:
            logger.warning(f"Failed to resolve HK stock info for {symbol}: {e}")
            info = {}

        if info.get("is_red_chip") or info.get("is_dual_listed"):
            return Decimal("0.9")
        return Decimal("1.0")
