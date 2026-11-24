"""Strategy 1a: dual MA trend + SMA10 reference band + ATR trailing stop.

Ported from holmes-lab strategies/au9999_cta/s1a_ma_cross_trailing.py.

- Entry: while SMA30 > SMA90 and close > SMA90 trend is up; when flat, buy at
  next open without waiting for a fresh golden cross.
- SMA10 reference band: close above SMA10 but less than 1.5xATR(14) above it
  (the "hugging" zone) means the trend direction is unclear, so no entry is
  taken. Price must either pull back below SMA10 or pull at least 1.5xATR away
  from it to qualify.
- Trailing stop: stop = max(entry - 2.5xATR(entry day),
  peak close - 2.5xATR(entry day)), ratcheting up only.
- Exit: close touches the stop or a death cross confirms; both fill next open.
  The reference band only gates entries, never exits.
- No fixed take-profit, no pyramiding. Long only.
"""

import math

import backtrader as bt

from backend.strat.common.base import LongOnlyStrategyBase


class MaCrossTrailingStop(LongOnlyStrategyBase):
    params = (
        ("fast_period", 30),
        ("slow_period", 90),
        ("atr_period", 14),
        ("initial_atr_mult", 2.5),  # initial stop distance
        ("trail_atr_mult", 2.5),  # trailing stop distance
        ("ref_period", 10),  # SMA reference line period
        ("ref_band_atr", 1.5),  # no-entry band: 0 ~ band x ATR above the line
    )

    def __init__(self):
        super().__init__()
        self.ma_fast = bt.indicators.SMA(self.data.close, period=self.p.fast_period)
        self.ma_slow = bt.indicators.SMA(self.data.close, period=self.p.slow_period)
        self.ma_ref = bt.indicators.SMA(self.data.close, period=self.p.ref_period)
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)
        self.cross_down = bt.indicators.CrossDown(self.ma_fast, self.ma_slow)
        self.entry_atr = None
        self.peak_close = None

    def risk_per_gram(self):
        return self.p.initial_atr_mult * self.atr[0]

    def entry_zone_ok(self) -> bool:
        """SMA reference band: no entry while price hugs the line from above.

        Close below the reference line (a pullback) or at least
        ``ref_band_atr`` ATRs above it (trend established) may enter.
        """
        atr = float(self.atr[0])
        if not math.isfinite(atr) or atr <= 0:
            return True
        distance = (float(self.data.close[0]) - float(self.ma_ref[0])) / atr
        return not (0.0 < distance <= self.p.ref_band_atr)

    def next(self):
        trend_ok = (
            self.ma_fast[0] > self.ma_slow[0]
            and self.data.close[0] > self.ma_slow[0]
        )

        if not self.position:
            if not self.has_pending_order and trend_ok and self.entry_zone_ok():
                self.buy_next_open(reason="trend up re-entry")
        else:
            if self.stop_price is None:
                self.entry_atr = float(self.atr[0])
                self.peak_close = float(self.data.close[0])
                self.stop_price = (
                    self.entry_price - self.p.initial_atr_mult * self.entry_atr
                )

            self.peak_close = max(self.peak_close, float(self.data.close[0]))
            trail = self.peak_close - self.p.trail_atr_mult * self.entry_atr
            self.stop_price = max(self.stop_price, trail)

            if not self.has_pending_order:
                if self.data.close[0] <= self.stop_price:
                    self.sell_next_open(reason="ATR trailing stop")
                elif self.cross_down[0] > 0:
                    self.sell_next_open(reason="death cross")

        self.record_series(
            close=self.data.close[0],
            fast=self.ma_fast[0],
            slow=self.ma_slow[0],
            ref=self.ma_ref[0],
            ref_upper=(
                float(self.ma_ref[0]) + self.p.ref_band_atr * float(self.atr[0])
            ),
            atr=self.atr[0],
            stop=self.stop_price,
        )

    def on_position_closed(self):
        self.entry_atr = None
        self.peak_close = None
