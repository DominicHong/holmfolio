"""Long-only strategy base class.

Ported from holmes-lab strategies/common/base.py with two NiceAMS additions:
- ``on_signal`` hook and a ``signals`` list so signal generation can be
  captured without changing the trading logic;
- per-bar indicator series recording (``record_series``) for charting.

Shared behaviour:
- long only: exits always ``close()``, never reverse to short;
- signals confirmed at close, filled at next open (backtrader market order);
- position sizing (fixed grams / available-cash percentage / risk budget);
- order state management and position-lifecycle bookkeeping.
"""

from datetime import date

import backtrader as bt

from backend.strat.common.constants import (
    COMMISSION_RATE,
    FIXED_GRAMS,
    MIN_TRADE_GRAMS,
    POSITION_MODE,
    POSITION_PERCENT,
    RISK_PER_TRADE,
    SLIPPAGE_RATE,
)


class LongOnlyStrategyBase(bt.Strategy):
    params = (
        ("position_mode", POSITION_MODE),
        ("fixed_grams", FIXED_GRAMS),
        ("position_percent", POSITION_PERCENT),
        ("risk_per_trade", RISK_PER_TRADE),
        ("verbose", False),
    )

    def __init__(self):
        self.order = None
        self.entry_price = None
        self.entry_date: date | None = None
        self.entry_bar = None
        self.entry_commission = 0.0
        self.stop_price = None
        self._pending_entry = False
        self._entry_reason = ""

        # Signal, fill and indicator-series recording (NiceAMS additions)
        self.signals: list[dict] = []
        self.fills: list[dict] = []
        self.series: dict[str, list[float | None]] = {}
        self.series_dates: list[date] = []

    # ---------- logging ----------
    def log(self, message: str):
        if self.p.verbose:
            print(f"{self.data.datetime.date(0)} {self.__class__.__name__}: {message}")

    # ---------- recording ----------
    def on_signal(self, action: str, reason: str) -> None:
        """Called when a new buy/sell intent is registered at bar close."""
        self.signals.append(
            {
                "signal_date": self.data.datetime.date(0),
                "action": action,
                "reason": reason,
            }
        )

    def record_series(self, **values) -> None:
        """Append one value per key for the current bar (used for charting).

        ``position_pct`` is always recorded: the model's position market value
        as a percentage of account equity (0 when flat, ~100 when all-in).
        """
        self.series_dates.append(self.data.datetime.date(0))
        equity = self.broker.getvalue()
        position_value = (
            abs(float(self.position.size)) * float(self.data.close[0])
            if self.position
            else 0.0
        )
        values["position_pct"] = (position_value / equity * 100.0) if equity else 0.0
        for key, value in values.items():
            series = self.series.setdefault(key, [None] * (len(self.series_dates) - 1))
            series.append(None if value is None else float(value))

    # ---------- position sizing ----------
    def risk_per_gram(self) -> float | None:
        """Override in subclasses: stop-loss distance per unit for risk_budget mode."""
        return None

    def size_for_cash(self, buy_cash: float, price: float) -> float:
        """Convert a cash budget into units including slippage and commission."""
        cost_per_gram = price * (1.0 + SLIPPAGE_RATE) * (1.0 + COMMISSION_RATE)
        grams = buy_cash / cost_per_gram
        return float(int(grams / MIN_TRADE_GRAMS) * MIN_TRADE_GRAMS)

    def calc_size(self, price: float) -> float:
        mode = self.p.position_mode
        if mode == "fixed_grams":
            return float(int(self.p.fixed_grams / MIN_TRADE_GRAMS) * MIN_TRADE_GRAMS)
        if mode == "risk_budget":
            risk_per_gram = self.risk_per_gram()
            if not risk_per_gram or risk_per_gram <= 0:
                return 0.0
            grams = self.broker.getvalue() * self.p.risk_per_trade / risk_per_gram
            return float(int(grams / MIN_TRADE_GRAMS) * MIN_TRADE_GRAMS)
        # percent_equity: size derived from available cash and fill price
        buy_cash = self.broker.getcash() * self.p.position_percent
        return self.size_for_cash(buy_cash, price)

    @property
    def has_pending_order(self) -> bool:
        return self.order is not None

    # ---------- order placement ----------
    def buy_next_open(self, reason: str = ""):
        """Register an entry intent; sized and submitted at next bar open."""
        if self.position or self.has_pending_order or self._pending_entry:
            return
        self._pending_entry = True
        self._entry_reason = reason
        self.on_signal("buy", reason)

    def next_open(self):
        """cheat_on_open: size the pending entry using the actual open price."""
        if not self._pending_entry:
            return
        self._pending_entry = False
        if self.position or self.has_pending_order:
            return
        size = self.calc_size(float(self.data.open[0]))
        if size <= 0:
            return
        self.order = self.buy(size=size)
        self.log(f"BUY {size:.0f}g @open ({self._entry_reason})")

    def sell_next_open(self, reason: str = ""):
        if not self.position or self.has_pending_order:
            return
        self.order = self.close()
        self.on_signal("sell", reason)
        self.log(f"SELL {self.position.size:.0f}g @next open ({reason})")

    # ---------- callbacks ----------
    def notify_order(self, order):
        if order.status in (order.Submitted, order.Accepted):
            return
        if order.status == order.Completed:
            self.fills.append(
                {
                    "date": self.data.datetime.date(0),
                    "action": "buy" if order.isbuy() else "sell",
                    "price": float(order.executed.price),
                    "size": abs(float(order.executed.size)),
                    "commission": float(order.executed.comm),
                    "position": float(self.position.size),
                }
            )
            if order.isbuy():
                self.entry_price = order.executed.price
                self.entry_date = self.data.datetime.date(0)
                self.entry_bar = len(self.data)
                self.entry_commission = order.executed.comm
                self.stop_price = None
            else:
                self.entry_price = None
                self.entry_date = None
                self.entry_bar = None
                self.stop_price = None
                self.on_position_closed()
        self.order = None

    def on_position_closed(self):
        """Override in subclasses: clear state maintained while in a position."""
