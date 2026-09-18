"""Gold trading service.

Seeds and incrementally updates gold daily bars, runs the CTA strategies to
produce signals, and compares the user's gold sub-account NAV against the
strategy model NAV and the AU9999.SHG spot price.
"""

from datetime import date
from decimal import Decimal

import numpy as np
import pandas as pd
from sqlmodel import Session, select

from backend import logger
from backend.db.models import Asset, Price, Settings, Transaction
from backend.services.base import BaseService
from backend.strat.common.constants import COMMISSION_RATE
from backend.strat.common.data_loader import DATASETS, load_daily_csv, update_daily
from backend.strat.common.engine import run_gold_backtest
from backend.strat.gold import DEFAULT_STRATEGY, STRATEGIES, STRATEGY_LABELS

GOLD_DATASET_ASSET_SYMBOLS = {"au9999": "AU9999.SHG", "518880": "518880.SH"}
GOLD_INITIAL_CAPITAL_KEY = "gold_initial_capital"
DEFAULT_GOLD_INITIAL_CAPITAL = 10_000.0
# Match CalculationService.calculate_statistics (Analytics page).
ANALYTICS_TRADING_DAYS_PER_YEAR = 240
DAYS_PER_YEAR = 365.25


class GoldService(BaseService):
    """Business logic for the gold trading module."""

    def __init__(self, session: Session):
        super().__init__(session)

    # ---------- assets ----------
    def list_gold_assets(self) -> list[Asset]:
        return self.session.exec(
            select(Asset).where(Asset.type == "gold").order_by(Asset.symbol)
        ).all()

    def get_gold_asset(self, asset_id: int) -> Asset | None:
        asset = self.session.get(Asset, asset_id)
        if asset is None or asset.type != "gold":
            return None
        return asset

    def get_gold_asset_by_symbol(self, symbol: str) -> Asset | None:
        return self.session.exec(
            select(Asset).where(Asset.symbol == symbol, Asset.type == "gold")
        ).first()

    # ---------- daily bars ----------
    def import_seed_csvs(self) -> dict:
        """Import both seed CSVs into the price table (used by init_data)."""
        added = 0
        errors: list[str] = []
        for key, dataset in DATASETS.items():
            asset = self.get_gold_asset_by_symbol(GOLD_DATASET_ASSET_SYMBOLS[key])
            if asset is None:
                errors.append(f"Gold asset missing for dataset '{key}'")
                continue
            try:
                bars = load_daily_csv(dataset.csv_path)
            except Exception as exc:  # noqa: BLE001 - report and continue
                errors.append(f"{key}: {exc}")
                continue
            added += self._store_bars(asset.id, bars)
        logger.info(f"Gold seed import complete: {added} bars added")
        return {"added": added, "errors": errors}

    def update_prices(self, end: str | date | None = None, source: str = "auto") -> dict:
        """Incrementally update both gold datasets (CSV + price table)."""
        added = 0
        errors: list[str] = []
        for key, dataset in DATASETS.items():
            asset = self.get_gold_asset_by_symbol(GOLD_DATASET_ASSET_SYMBOLS[key])
            if asset is None:
                errors.append(f"Gold asset missing for dataset '{key}'")
                continue
            try:
                incremental = update_daily(key, end=end, source=source)
            except Exception as exc:  # noqa: BLE001 - report and continue
                errors.append(f"{key}: {exc}")
                logger.error(f"Gold price update failed for {key}: {exc}")
                continue
            if incremental.empty:
                continue
            added += self._store_bars(asset.id, incremental)
        return {"added": added, "errors": errors}

    def _store_bars(self, asset_id: int, bars: pd.DataFrame, source: str = "ifind") -> int:
        """Insert bars that are not already stored, returning the count added."""
        if bars.empty:
            return 0
        existing = set(
            self.session.exec(
                select(Price.price_date).where(Price.asset_id == asset_id)
            ).all()
        )
        rows = []
        for row in bars.itertuples(index=False):
            if row.date in existing:
                continue
            rows.append(
                Price(
                    asset_id=asset_id,
                    price_date=row.date,
                    price=Decimal(str(row.close)),
                    open=Decimal(str(row.open)),
                    high=Decimal(str(row.high)),
                    low=Decimal(str(row.low)),
                    volume=Decimal(str(row.volume)),
                    amount=Decimal(str(row.amt)),
                    price_type="historical",
                    source=source,
                )
            )
        if rows:
            self.session.add_all(rows)
            self.commit()
        return len(rows)

    def get_daily_bars(self, asset_id: int) -> pd.DataFrame:
        """Load stored OHLCV bars for an asset, oldest first."""
        prices = self.session.exec(
            select(Price).where(Price.asset_id == asset_id).order_by(Price.price_date)
        ).all()
        records = [
            {
                "date": price.price_date,
                "open": float(price.open),
                "high": float(price.high),
                "low": float(price.low),
                "close": float(price.price),
                "volume": float(price.volume) if price.volume is not None else 0.0,
                "amt": float(price.amount) if price.amount is not None else 0.0,
            }
            for price in prices
            if price.open is not None and price.high is not None and price.low is not None
        ]
        return pd.DataFrame(records, columns=["date", "open", "high", "low", "close", "volume", "amt"])

    @staticmethod
    def _to_engine_frame(bars: pd.DataFrame) -> pd.DataFrame:
        frame = bars.copy()
        frame = frame.set_index(pd.to_datetime(frame.pop("date")))
        frame["openinterest"] = 0.0
        return frame[["open", "high", "low", "close", "volume", "openinterest"]]

    # ---------- signal/model ----------
    def run_model(self, asset_id: int, strategy_key: str) -> dict:
        """Run a strategy over the full bar history for an asset.

        The model account is sized with the configured gold initial capital so
        that every recorded fill holds real units for that account; no
        market-value-to-units conversion is ever applied.
        """
        asset = self.get_gold_asset(asset_id)
        if asset is None:
            raise ValueError(f"Gold asset {asset_id} not found")
        if strategy_key not in STRATEGIES:
            raise ValueError(f"Unknown gold strategy: {strategy_key}")

        bars = self.get_daily_bars(asset_id)
        if bars.empty:
            return {
                "nav_dates": [],
                "nav_values": [],
                "signals": [],
                "fills": [],
                "round_trips": [],
                "model_state": None,
                "series_dates": [],
                "series": {},
            }
        initial_capital = self._get_initial_capital()
        return run_gold_backtest(
            self._to_engine_frame(bars),
            STRATEGIES[strategy_key],
            initial_cash=initial_capital if initial_capital > 0 else DEFAULT_GOLD_INITIAL_CAPITAL,
        )

    def _scope_model_to_window(
        self,
        model: dict,
        bars: pd.DataFrame,
        initial_capital: float,
        start_date: date | None,
        end_date: date | None,
    ) -> dict:
        """Re-simulate the model account inside the window with fresh capital.

        Signal dates and execution prices come from the warm full-history
        backtest, but the account restarts at ``initial_capital`` on the window
        start date: every in-window fill is re-sized against the cash actually
        available at that moment, so units can never exceed the account.
        """
        if bars.empty or model.get("model_state") is None:
            return model

        window_start = start_date or bars["date"].iloc[0]
        window_end = end_date or bars["date"].iloc[-1]
        window_bars = bars[(bars["date"] >= window_start) & (bars["date"] <= window_end)]
        if window_bars.empty:
            return model

        # 1) Replay the recorded fills (date + price) against the window account.
        cash = initial_capital
        units = 0.0
        replay_fills: list[dict] = []
        for fill in model.get("fills", []):
            if not (window_start <= fill["date"] <= window_end):
                continue
            price = float(fill["price"])
            if price <= 0:
                continue
            if fill["action"] == "buy" and units <= 0:
                size = int(cash / (price * (1 + COMMISSION_RATE)))
                if size <= 0:
                    continue
                commission = size * price * COMMISSION_RATE
                cash -= size * price + commission
                units = float(size)
                replay_fills.append(
                    {
                        **fill,
                        "size": units,
                        "commission": commission,
                        "position": units,
                        "cash": cash,
                    }
                )
            elif fill["action"] == "sell" and units > 0:
                proceeds = units * price
                commission = proceeds * COMMISSION_RATE
                cash += proceeds - commission
                replay_fills.append(
                    {
                        **fill,
                        "size": units,
                        "commission": commission,
                        "position": 0.0,
                        "cash": cash,
                    }
                )
                units = 0.0

        # 2) Mark the account daily and record the position percentage.
        fills_by_date: dict[date, list[dict]] = {}
        for fill in replay_fills:
            fills_by_date.setdefault(fill["date"], []).append(fill)

        nav_dates: list[date] = []
        nav_values: list[float] = []
        position_pct_by_date: dict[date, float] = {}
        cash = initial_capital
        units = 0.0
        for row in window_bars.itertuples(index=False):
            for fill in fills_by_date.get(row.date, []):
                cash = fill["cash"]
                units = fill["position"]
            equity = cash + units * float(row.close)
            nav_dates.append(row.date)
            nav_values.append(equity / initial_capital * 100 if initial_capital else 0.0)
            position_pct_by_date[row.date] = (
                units * float(row.close) / equity * 100 if equity else 0.0
            )

        # 3) Annotate signals with the units actually traded in the window.
        replay_by_key = {(fill["date"], fill["action"]): fill for fill in replay_fills}
        signals: list[dict] = []
        for signal in model.get("signals", []):
            in_window = window_start <= signal["signal_date"] <= window_end or (
                signal["exec_date"] is not None
                and window_start <= signal["exec_date"] <= window_end
            )
            if not in_window:
                signals.append(signal)
                continue
            fill = replay_by_key.get((signal["exec_date"], signal["action"]))
            if fill is not None:
                signals.append({**signal, "size": fill["size"], "exec_price": fill["price"]})
            elif signal["exec_date"] is None:
                signals.append({**signal, "size": None})
            else:
                # Executed by the strategy but a no-op for the fresh account.
                signals.append({**signal, "size": 0.0})

        # 4) Rebuild round trips and the final model state for the window.
        round_trips = self._round_trips_from_fills(replay_fills)
        entry_fill = next(
            (fill for fill in reversed(replay_fills) if fill["action"] == "buy"), None
        )
        base_state = model.get("model_state") or {}
        is_live_window = window_end >= (base_state.get("last_bar_date") or window_end)
        model_state = {
            "position_size": units,
            "entry_date": entry_fill["date"] if (entry_fill and units > 0) else None,
            "entry_price": entry_fill["price"] if (entry_fill and units > 0) else None,
            "stop_price": self._series_value_at(model, "stop", window_end),
            "peak_close": None,
            "last_bar_date": window_end,
            "pending_signal": base_state.get("pending_signal") if is_live_window else None,
        }

        series = dict(model.get("series", {}))
        if series.get("position_pct") is not None:
            series["position_pct"] = [
                position_pct_by_date.get(day, value)
                for day, value in zip(
                    model.get("series_dates", []), series.get("position_pct", [])
                )
            ]

        return {
            **model,
            "nav_dates": nav_dates,
            "nav_values": nav_values,
            "fills": replay_fills,
            "round_trips": round_trips,
            "signals": signals,
            "model_state": model_state,
            "series": series,
        }

    @staticmethod
    def _round_trips_from_fills(fills: list[dict]) -> list[dict]:
        """Pair replayed buys/sells into closed round trips for the window."""
        round_trips: list[dict] = []
        entry: dict | None = None
        for fill in fills:
            if fill["action"] == "buy" and entry is None:
                entry = fill
            elif fill["action"] == "sell" and entry is not None:
                gross_return = fill["price"] / entry["price"] - 1
                net_return = (
                    fill["price"]
                    * (1 - COMMISSION_RATE)
                    / (entry["price"] * (1 + COMMISSION_RATE))
                    - 1
                )
                round_trips.append(
                    {
                        "entry_signal_date": entry["date"],
                        "entry_date": entry["date"],
                        "entry_price": entry["price"],
                        "exit_signal_date": fill["date"],
                        "exit_date": fill["date"],
                        "exit_price": fill["price"],
                        "reason": "window replay",
                        "gross_return": gross_return,
                        "net_return": net_return,
                    }
                )
                entry = None
        return round_trips

    @staticmethod
    def _series_value_at(model: dict, key: str, as_of: date) -> float | None:
        value = None
        for day, item in zip(model.get("series_dates", []), model.get("series", {}).get(key, [])):
            if day > as_of:
                break
            value = item
        return value

    def get_signals(self, asset_id: int, strategy_key: str = DEFAULT_STRATEGY) -> dict:
        """Return strategy signals and model state for an asset."""
        model = self.run_model(asset_id, strategy_key)
        return {
            "strategy": strategy_key,
            "strategy_label": STRATEGY_LABELS[strategy_key],
            "signals": model["signals"],
            "round_trips": model["round_trips"],
            "model_state": model["model_state"],
            "series_dates": model["series_dates"],
            "series": model["series"],
        }

    # ---------- user account ----------
    def get_user_position(
        self,
        portfolio_id: int,
        asset_id: int,
        end_date: date | None = None,
    ) -> dict:
        """Replay gold transactions into a position/P&L summary (average cost).

        When ``end_date`` is given, only transactions on/before that date are
        replayed so the reported units are the position held on that date.
        """
        transactions = [
            txn
            for txn in self._get_gold_transactions(portfolio_id, asset_id)
            if end_date is None or txn.trade_date <= end_date
        ]
        quantity = 0.0
        average_cost = 0.0
        realized_pnl = 0.0
        sells = 0
        wins = 0

        for txn in transactions:
            txn_quantity = float(txn.quantity or 0)
            amount = float(txn.amount or 0)
            fees = float(txn.fees or 0)

            if txn.action == "buy":
                total_cost = average_cost * quantity
                quantity += txn_quantity
                average_cost = (total_cost + amount + fees) / quantity if quantity else 0.0
            elif txn.action == "sell":
                sell_quantity = min(txn_quantity, quantity)
                sell_price = float(txn.price) if txn.price is not None else (
                    amount / sell_quantity if sell_quantity else 0.0
                )
                pnl = (sell_price - average_cost) * sell_quantity - fees
                realized_pnl += pnl
                sells += 1
                wins += 1 if pnl > 0 else 0
                quantity -= sell_quantity
                if quantity <= 1e-9:
                    quantity = 0.0

        bars = self.get_daily_bars(asset_id)
        if end_date is not None and not bars.empty:
            bars = bars[bars["date"] <= end_date]
        latest_price = float(bars["close"].iloc[-1]) if not bars.empty else None
        market_value = quantity * latest_price if latest_price is not None else None
        unrealized_pnl = (
            (latest_price - average_cost) * quantity
            if latest_price is not None and quantity
            else 0.0
        )

        return {
            "quantity": quantity,
            "average_cost": average_cost,
            "latest_price": latest_price,
            "market_value": market_value,
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "total_pnl": realized_pnl + unrealized_pnl,
            "sells": sells,
            "win_rate": (wins / sells) if sells else None,
            "transactions": len(transactions),
        }

    def _get_gold_transactions(self, portfolio_id: int, asset_id: int) -> list[Transaction]:
        return self.session.exec(
            select(Transaction)
            .where(
                Transaction.portfolio_id == portfolio_id,
                Transaction.asset_id == asset_id,
            )
            .order_by(Transaction.trade_date)
        ).all()

    def _get_initial_capital(self) -> float:
        setting = self.session.exec(
            select(Settings).where(Settings.key == GOLD_INITIAL_CAPITAL_KEY)
        ).first()
        if setting is None:
            return DEFAULT_GOLD_INITIAL_CAPITAL
        try:
            return float(setting.value)
        except (TypeError, ValueError):
            return DEFAULT_GOLD_INITIAL_CAPITAL

    def _get_risk_free_rate(self) -> float:
        """Risk-free rate from Settings, matching PortfolioService."""
        setting = self.session.exec(
            select(Settings).where(Settings.key == "risk_free_rate")
        ).first()
        if setting is None:
            return 0.0
        try:
            return float(setting.value)
        except (TypeError, ValueError):
            return 0.0

    # ---------- performance comparison ----------
    def get_overview(
        self,
        portfolio_id: int,
        asset_id: int,
        strategy_key: str = DEFAULT_STRATEGY,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict:
        """Signals, model state and normalized NAV comparison for the page."""
        asset = self.get_gold_asset(asset_id)
        if asset is None:
            raise ValueError(f"Gold asset {asset_id} not found")
        if strategy_key not in STRATEGIES:
            raise ValueError(f"Unknown gold strategy: {strategy_key}")

        bars = self.get_daily_bars(asset_id)
        model = self.run_model(asset_id, strategy_key)
        initial_capital = self._get_initial_capital()
        if start_date is not None or end_date is not None:
            model = self._scope_model_to_window(
                model, bars, initial_capital, start_date, end_date
            )

        performance = self._build_performance(
            portfolio_id,
            asset,
            bars,
            model,
            start_date,
            end_date,
            self._get_risk_free_rate(),
        )

        return {
            "strategy": strategy_key,
            "strategy_label": STRATEGY_LABELS[strategy_key],
            "signals": model["signals"],
            "round_trips": model["round_trips"],
            "model_state": model["model_state"],
            "series_dates": model["series_dates"],
            "series": model["series"],
            "performance": performance,
            "user_position": self.get_user_position(portfolio_id, asset_id, end_date),
            "initial_capital": initial_capital,
        }

    def _build_performance(
        self,
        portfolio_id: int,
        asset: Asset,
        bars: pd.DataFrame,
        model: dict,
        start_date: date | None,
        end_date: date | None,
        risk_free_rate: float,
    ) -> dict:
        model_map = dict(zip(model["nav_dates"], model["nav_values"]))
        dates = sorted(model_map)
        if start_date is not None:
            dates = [day for day in dates if day >= start_date]
        if end_date is not None:
            dates = [day for day in dates if day <= end_date]
        if not dates:
            return self._empty_performance(risk_free_rate)

        dates_index = pd.to_datetime(dates)
        asset_close = self._close_series(bars)
        asset_aligned = asset_close.reindex(dates_index).ffill().bfill().to_numpy()

        # Buy & hold of the traded gold asset itself (AU9999.SHG spot when AU9999.SHG
        # is selected; the ETF's own trend when 518880.SH is selected).
        benchmark_values = asset_aligned / asset_aligned[0] * 100
        benchmark_nav = [
            float(value) if np.isfinite(value) else None for value in benchmark_values
        ]

        model_values = np.array([model_map[day] for day in dates], dtype=float)
        model_nav = (model_values / model_values[0] * 100).tolist()

        initial_capital = self._get_initial_capital()
        user_nav = self._user_nav_series(
            portfolio_id, asset.id, dates, asset_aligned, initial_capital
        )

        user_trade_stats = self._user_trade_stats(
            portfolio_id, asset.id, start_date, end_date
        )
        window_round_trips = [
            trip
            for trip in model["round_trips"]
            if trip["exit_date"] is not None
            and (start_date is None or trip["exit_date"] >= start_date)
            and (end_date is None or trip["exit_date"] <= end_date)
        ]
        metrics = {
            "user": self._series_metrics(
                dates,
                user_nav,
                trades=user_trade_stats["sells"],
                win_rate=user_trade_stats["win_rate"],
                realized_pnl=user_trade_stats["realized_pnl"],
                risk_free_rate=risk_free_rate,
            ),
            "model": self._series_metrics(
                dates,
                model_nav,
                trades=len(window_round_trips),
                win_rate=self._win_rate(window_round_trips),
                realized_pnl=None,
                risk_free_rate=risk_free_rate,
            ),
            "benchmark": self._series_metrics(
                dates, benchmark_nav, risk_free_rate=risk_free_rate
            ),
        }

        return {
            "dates": dates,
            "user_nav": user_nav,
            "model_nav": model_nav,
            "benchmark_nav": benchmark_nav,
            "benchmark_symbol": asset.symbol,
            "initial_capital": initial_capital,
            "risk_free_rate": risk_free_rate,
            "metrics": metrics,
        }

    def _user_trade_stats(
        self,
        portfolio_id: int,
        asset_id: int,
        start_date: date | None,
        end_date: date | None,
    ) -> dict:
        """Sell-count / win-rate / realized P&L for sells inside the window.

        The full transaction history is replayed so that the average cost at
        each sell is correct, but only sells within [start_date, end_date] are
        counted, keeping the metrics consistent with the displayed NAV window.
        """
        transactions = self._get_gold_transactions(portfolio_id, asset_id)
        quantity = 0.0
        average_cost = 0.0
        sells = 0
        wins = 0
        realized_pnl = 0.0

        for txn in transactions:
            txn_quantity = float(txn.quantity or 0)
            amount = float(txn.amount or 0)
            fees = float(txn.fees or 0)

            if txn.action == "buy":
                total_cost = average_cost * quantity
                quantity += txn_quantity
                average_cost = (total_cost + amount + fees) / quantity if quantity else 0.0
            elif txn.action == "sell":
                sell_quantity = min(txn_quantity, quantity)
                sell_price = float(txn.price) if txn.price is not None else (
                    amount / sell_quantity if sell_quantity else 0.0
                )
                in_window = (
                    (start_date is None or txn.trade_date >= start_date)
                    and (end_date is None or txn.trade_date <= end_date)
                )
                if in_window:
                    pnl = (sell_price - average_cost) * sell_quantity - fees
                    realized_pnl += pnl
                    sells += 1
                    wins += 1 if pnl > 0 else 0
                quantity -= sell_quantity
                if quantity <= 1e-9:
                    quantity = 0.0

        return {
            "sells": sells,
            "win_rate": (wins / sells) if sells else None,
            "realized_pnl": realized_pnl,
        }

    def _user_nav_series(
        self,
        portfolio_id: int,
        asset_id: int,
        dates: list[date],
        asset_close: np.ndarray,
        initial_capital: float,
    ) -> list[float]:
        transactions = self._get_gold_transactions(portfolio_id, asset_id)
        by_date: dict[date, list[Transaction]] = {}
        for txn in transactions:
            by_date.setdefault(txn.trade_date, []).append(txn)

        cash = initial_capital
        quantity = 0.0
        nav: list[float] = []
        for day, close in zip(dates, asset_close):
            for txn in by_date.get(day, []):
                txn_quantity = float(txn.quantity or 0)
                amount = float(txn.amount or 0)
                fees = float(txn.fees or 0)
                if txn.action == "buy":
                    cash -= amount + fees
                    quantity += txn_quantity
                elif txn.action == "sell":
                    cash += amount - fees
                    quantity -= txn_quantity
                elif txn.action == "dividends":
                    cash += amount - fees
                elif txn.action == "tax":
                    cash -= amount + fees
            nav.append((cash + quantity * float(close)) / initial_capital * 100)
        return nav

    @staticmethod
    def _close_series(bars: pd.DataFrame) -> pd.Series:
        return pd.Series(
            bars["close"].to_numpy(dtype=float),
            index=pd.to_datetime(bars["date"]),
        ).sort_index()

    @staticmethod
    def _win_rate(round_trips: list[dict]) -> float | None:
        returns = [rt["net_return"] for rt in round_trips if rt["net_return"] is not None]
        if not returns:
            return None
        return sum(1 for value in returns if value > 0) / len(returns)

    @staticmethod
    def _series_metrics(
        dates: list[date],
        values: list[float | None],
        trades: int = 0,
        win_rate: float | None = None,
        realized_pnl: float | None = None,
        risk_free_rate: float = 0.0,
    ) -> dict:
        clean = [(day, value) for day, value in zip(dates, values) if value is not None]
        if len(clean) < 2:
            return {
                "total_return": 0.0,
                "annualized_return": None,
                "max_drawdown": 0.0,
                "volatility": 0.0,
                "sharpe": 0.0,
                "trades": trades,
                "win_rate": win_rate,
                "realized_pnl": realized_pnl,
            }

        clean_dates = [day for day, _ in clean]
        series = np.array([value for _, value in clean], dtype=float)
        returns = series[1:] / series[:-1] - 1
        returns = returns[np.isfinite(returns)]

        total_return = float(series[-1] / series[0] - 1)
        days = (clean_dates[-1] - clean_dates[0]).days
        annualized_return = (
            float((1 + total_return) ** (365 / days) - 1)
            if days > 0 and total_return > -1
            else None
        )

        peak = np.maximum.accumulate(series)
        max_drawdown = float(((series - peak) / peak).min())

        # Same volatility/Sharpe convention as CalculationService.calculate_statistics.
        std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
        years = days / DAYS_PER_YEAR
        volatility = (
            std * np.sqrt(ANALYTICS_TRADING_DAYS_PER_YEAR * years) if years > 0 else 0.0
        )
        if volatility > 0 and annualized_return is not None:
            sharpe = float((annualized_return - risk_free_rate) / volatility)
        else:
            sharpe = 0.0

        return {
            "total_return": total_return,
            "annualized_return": annualized_return,
            "max_drawdown": max_drawdown,
            "volatility": float(volatility),
            "sharpe": sharpe,
            "trades": trades,
            "win_rate": win_rate,
            "realized_pnl": realized_pnl,
        }

    @staticmethod
    def _empty_performance(risk_free_rate: float = 0.0) -> dict:
        return {
            "dates": [],
            "user_nav": [],
            "model_nav": [],
            "benchmark_nav": [],
            "benchmark_symbol": "",
            "initial_capital": DEFAULT_GOLD_INITIAL_CAPITAL,
            "risk_free_rate": risk_free_rate,
            "metrics": None,
        }
