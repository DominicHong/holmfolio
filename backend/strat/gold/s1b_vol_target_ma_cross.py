"""Strategy 1b: dual moving-average trend + vol-target position sizing.

Ported from holmes-lab strategies/au9999_cta/s1b_vol_target_ma_cross.py.

Timing is identical to s1a:
- Entry: while SMA30 > SMA90 and close > SMA90 trend is up; when flat, buy at
  next open without waiting for a fresh golden cross.
- Trailing stop: stop = max(entry - 2.5xATR(entry day),
  peak close - 2.5xATR(entry day)), ratcheting up only.
- Exit: close touches the stop or a death cross confirms; both fill next open.

The only difference is sizing: the target position factor is
f = min(1, 15% / RV60) rounded to the {25%, 50%, 75%, 100%} grid, where RV60 is
the 60-day realized volatility (sample std of daily returns x sqrt(252)).
Entries size to available cash x f; while long, a grid change rebalances to
equity x f at the next open (up = add, down = partial reduce). Rebalances
neither reset the stop state machine nor count as closed round trips.
"""

import math

import backtrader as bt

from backend.strat.common.base import LongOnlyStrategyBase
from backend.strat.common.constants import MIN_TRADE_GRAMS
from backend.strat.common.indicators import RealizedVolatility


class VolTargetMaCross(LongOnlyStrategyBase):
    params = (
        ("fast_period", 30),
        ("slow_period", 90),
        ("atr_period", 14),
        ("initial_atr_mult", 2.5),  # initial stop distance
        ("trail_atr_mult", 2.5),  # trailing stop distance
        ("target_vol", 0.15),  # target annualized volatility
        ("vol_period", 60),  # realized volatility window
        ("vol_grid", 0.25),  # position factor grid
        ("min_factor", 0.25),  # grid floor
    )

    def __init__(self):
        super().__init__()
        self.ma_fast = bt.indicators.SMA(self.data.close, period=self.p.fast_period)
        self.ma_slow = bt.indicators.SMA(self.data.close, period=self.p.slow_period)
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)
        self.cross_down = bt.indicators.CrossDown(self.ma_fast, self.ma_slow)
        self.rv = RealizedVolatility(self.data.close, period=self.p.vol_period)
        self.entry_atr = None
        self.peak_close = None
        self.signal_factor = 1.0  # target factor confirmed at today's close
        self.position_factor = None  # factor the current position is aligned to
        self._entry_factor = 1.0  # factor the entry order sizes with
        self._pending_rebalance_to = None

    # ---------- position factor ----------
    def factor_for(self, rv: float) -> float:
        """Map RV60 to the gridded target factor; fall back to 1.0 when unready."""
        if rv is None or math.isnan(rv) or rv <= 0:
            return 1.0
        raw = min(1.0, self.p.target_vol / rv)
        steps = math.floor(raw / self.p.vol_grid + 0.5)
        return max(self.p.min_factor, min(1.0, steps * self.p.vol_grid))

    def risk_per_gram(self):
        return self.p.initial_atr_mult * self.atr[0]

    def calc_size(self, price: float) -> float:
        """percent_equity entries scale available cash by the entry factor."""
        if self.p.position_mode != "percent_equity":
            return super().calc_size(price)
        buy_cash = self.broker.getcash() * self._entry_factor
        return self.size_for_cash(buy_cash, price)

    # ---------- signals ----------
    def next(self):
        self.signal_factor = self.factor_for(float(self.rv[0]))
        trend_ok = (
            self.ma_fast[0] > self.ma_slow[0]
            and self.data.close[0] > self.ma_slow[0]
        )

        if not self.position:
            if not self.has_pending_order and trend_ok:
                self._entry_factor = self.signal_factor
                self.buy_next_open(reason=f"trend up entry at {self.signal_factor:.0%} target")
        else:
            if self.stop_price is None:
                self.entry_atr = float(self.atr[0])
                self.peak_close = float(self.data.close[0])
                self.stop_price = (
                    self.entry_price - self.p.initial_atr_mult * self.entry_atr
                )
                if self.position_factor is None:
                    self.position_factor = self._entry_factor

            self.peak_close = max(self.peak_close, float(self.data.close[0]))
            trail = self.peak_close - self.p.trail_atr_mult * self.entry_atr
            self.stop_price = max(self.stop_price, trail)

            if not self.has_pending_order:
                if self.data.close[0] <= self.stop_price:
                    self._pending_rebalance_to = None
                    self.sell_next_open(reason="ATR trailing stop")
                elif self.cross_down[0] > 0:
                    self._pending_rebalance_to = None
                    self.sell_next_open(reason="death cross")
                elif self.signal_factor != self.position_factor:
                    self._pending_rebalance_to = self.signal_factor

        self.record_series(
            close=self.data.close[0],
            fast=self.ma_fast[0],
            slow=self.ma_slow[0],
            atr=self.atr[0],
            rv=self.rv[0],
            factor=self.signal_factor,
            stop=self.stop_price,
        )

    def next_open(self):
        """Execute a pending grid rebalance before the inherited entry logic."""
        if self._pending_rebalance_to is not None:
            self._rebalance_to(self._pending_rebalance_to)
            return
        super().next_open()

    def _rebalance_to(self, target_factor: float):
        """Move the position to equity x target_factor (up = add, down = trim)."""
        self._pending_rebalance_to = None
        if not self.position or self.has_pending_order:
            return
        self.position_factor = target_factor
        price = float(self.data.open[0])
        target_size = self.size_for_cash(self.broker.getvalue() * target_factor, price)
        delta = target_size - self.position.size
        delta = float(int(delta / MIN_TRADE_GRAMS) * MIN_TRADE_GRAMS)
        if abs(delta) < MIN_TRADE_GRAMS:
            return
        if delta > 0:
            # Adds are capped by the cash actually available.
            max_size = self.size_for_cash(self.broker.getcash(), price)
            delta = min(delta, max_size)
            delta = float(int(delta / MIN_TRADE_GRAMS) * MIN_TRADE_GRAMS)
            if delta < MIN_TRADE_GRAMS:
                return
            self.order = self.buy(size=delta)
            self.log(f"ADD {delta:.0f}g @open (target {target_factor:.0%})")
        else:
            self.order = self.sell(size=-delta)
            self.log(f"REDUCE {-delta:.0f}g @open (target {target_factor:.0%})")

    # ---------- callbacks ----------
    def notify_order(self, order):
        """Record every fill; only entries/full exits reset the stop state.

        Grid rebalances (adds / partial reduces) must not touch entry_price,
        stop_price or the entry-day ATR, so the trailing stop keeps running
        from the original entry.
        """
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
                if self.entry_price is None:  # first entry, not a rebalance add
                    self.entry_price = order.executed.price
                    self.entry_date = self.data.datetime.date(0)
                    self.entry_bar = len(self.data)
                    self.entry_commission = order.executed.comm
                    self.stop_price = None
            elif not self.position:  # fully closed, not a partial reduce
                self.entry_price = None
                self.entry_date = None
                self.entry_bar = None
                self.stop_price = None
                self.on_position_closed()
        self.order = None

    def on_position_closed(self):
        self.entry_atr = None
        self.peak_close = None
        self.position_factor = None
        self._pending_rebalance_to = None
