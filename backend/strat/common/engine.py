"""Backtrader engine wrapper for gold strategies.

Ported from holmes-lab strategies/common/engine.py with a signals-first API:
``run_gold_backtest`` returns the normalized model NAV curve, the recorded
signals, the resulting model state and the indicator series needed by the
gold trading page.
"""

from datetime import date

import backtrader as bt
import pandas as pd

from backend.strat.common.base import LongOnlyStrategyBase
from backend.strat.common.constants import (
    COMMISSION_RATE,
    FUND_MODE,
    FUND_START_VALUE,
    INITIAL_CASH,
    SLIPPAGE_RATE,
)


# Any dataset at least this long is safe for the vectorized (runonce) path:
# the deepest warm-up in the gold strategies is the 200-bar squeeze lookback.
MIN_VECTORIZED_BARS = 320


class EquityCurve(bt.Analyzer):
    """Record normalized account NAV (fund value, starting at 100) per bar."""

    def start(self):
        self.dates: list[date] = []
        self.values: list[float] = []
        self.fund_values: list[float] = []

    def next(self):
        self.dates.append(self.strategy.data.datetime.date(0))
        self.values.append(self.strategy.broker.getvalue())
        self.fund_values.append(self.strategy.broker.fundvalue)

    def get_analysis(self):
        return {
            "dates": self.dates,
            "values": self.values,
            "fund_values": self.fund_values,
        }


def make_cerebro(
    data: pd.DataFrame,
    strategy_cls: type[bt.Strategy],
    strategy_params: dict | None = None,
    initial_cash: float = INITIAL_CASH,
) -> bt.Cerebro:
    """Create a Cerebro with the shared gold backtest assumptions."""
    cerebro = bt.Cerebro(stdstats=False, cheat_on_open=True)
    cerebro.addstrategy(strategy_cls, **(strategy_params or {}))
    cerebro.adddata(bt.feeds.PandasData(dataname=data))
    cerebro.broker.setcash(initial_cash)
    cerebro.broker.setcommission(commission=COMMISSION_RATE)
    cerebro.broker.set_slippage_perc(SLIPPAGE_RATE, slip_open=True)
    if FUND_MODE:
        cerebro.broker.set_fundmode(True, fundstartval=FUND_START_VALUE)
    cerebro.addanalyzer(EquityCurve, _name="equity")
    return cerebro


def run_gold_backtest(
    data: pd.DataFrame,
    strategy_cls: type[LongOnlyStrategyBase],
    strategy_params: dict | None = None,
    initial_cash: float = INITIAL_CASH,
) -> dict:
    """Run one strategy over daily bars and return signals, NAV and state.

    Args:
        data: DataFrame indexed by a DatetimeIndex with columns
            open/high/low/close/volume/openinterest.
        strategy_cls: strategy class deriving from LongOnlyStrategyBase.
        strategy_params: optional parameter overrides.
        initial_cash: nominal account size used for position sizing.

    Returns:
        dict with keys: nav_dates, nav_values, signals, fills, round_trips,
        model_state, series_dates, series.
    """
    cerebro = make_cerebro(data, strategy_cls, strategy_params, initial_cash)
    # runonce=False keeps short/incomplete histories safe: the vectorized path
    # indexes past the end when data is shorter than the indicator warm-up.
    # Long histories use the fast vectorized path.
    runonce = len(data) >= MIN_VECTORIZED_BARS
    strategy = cerebro.run(runonce=runonce)[0]

    dates = [timestamp.date() for timestamp in data.index]
    date_to_index = {day: index for index, day in enumerate(dates)}
    opens = data["open"].tolist()

    fills: list[dict] = list(strategy.fills)
    fill_by_key = {(fill["date"], fill["action"]): fill for fill in fills}

    signals: list[dict] = []
    for signal in strategy.signals:
        index = date_to_index.get(signal["signal_date"])
        exec_date = None
        exec_price = None
        if index is not None and index + 1 < len(dates):
            exec_date = dates[index + 1]
            exec_price = float(opens[index + 1])
        fill = fill_by_key.get((exec_date, signal["action"]))
        signals.append(
            {
                "signal_date": signal["signal_date"],
                "action": signal["action"],
                "reason": signal["reason"],
                "exec_date": exec_date,
                # Actual fill price/units when the order executed.
                "exec_price": fill["price"] if fill else exec_price,
                "size": fill["size"] if fill else None,
            }
        )

    round_trips = _build_round_trips(signals)
    equity = strategy.analyzers.equity.get_analysis()
    model_state = _build_model_state(strategy, dates)

    return {
        "nav_dates": equity["dates"],
        "nav_values": equity["fund_values"],
        "signals": signals,
        "fills": fills,
        "round_trips": round_trips,
        "model_state": model_state,
        "series_dates": list(strategy.series_dates),
        "series": {key: list(values) for key, values in strategy.series.items()},
    }


def _build_round_trips(signals: list[dict]) -> list[dict]:
    """Pair buy/sell signals into closed round trips at next-open execution prices."""
    round_trips: list[dict] = []
    entry: dict | None = None

    for signal in signals:
        if signal["action"] == "buy" and entry is None:
            entry = signal
        elif (
            signal["action"] == "sell"
            and entry is not None
            and signal["exec_date"] is not None
        ):
            entry_price = entry["exec_price"]
            exit_price = signal["exec_price"]
            if entry_price and exit_price:
                gross_return = exit_price / entry_price - 1
                net_return = (
                    exit_price
                    * (1 - COMMISSION_RATE - SLIPPAGE_RATE)
                    / (entry_price * (1 + COMMISSION_RATE + SLIPPAGE_RATE))
                    - 1
                )
            else:
                gross_return = None
                net_return = None
            round_trips.append(
                {
                    "entry_signal_date": entry["signal_date"],
                    "entry_date": entry["exec_date"],
                    "entry_price": entry_price,
                    "exit_signal_date": signal["signal_date"],
                    "exit_date": signal["exec_date"],
                    "exit_price": exit_price,
                    "reason": signal["reason"],
                    "gross_return": gross_return,
                    "net_return": net_return,
                }
            )
            entry = None

    return round_trips


def _build_model_state(
    strategy: LongOnlyStrategyBase,
    dates: list[date],
) -> dict:
    """Snapshot the model state after the last bar of the backtest."""
    pending_signal = None
    if strategy.signals:
        last = strategy.signals[-1]
        if last["signal_date"] == dates[-1]:
            pending_signal = {
                "signal_date": last["signal_date"],
                "action": last["action"],
                "reason": last["reason"],
            }

    position_size = float(strategy.position.size) if strategy.position else 0.0
    peak_close = getattr(strategy, "peak_close", None)

    return {
        "position_size": position_size,
        "entry_date": strategy.entry_date,
        "entry_price": strategy.entry_price,
        "stop_price": strategy.stop_price,
        "peak_close": peak_close,
        "last_bar_date": dates[-1] if dates else None,
        "pending_signal": pending_signal,
    }
