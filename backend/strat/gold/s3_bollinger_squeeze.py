"""Strategy 3: Bollinger squeeze breakout.

Ported from holmes-lab strategies/au9999_cta/s3_bollinger_squeeze.py.

- Entry: previous bandwidth < 10th percentile of the last 200 bars (squeeze),
  close > upper band, and bandwidth expands >= 30% versus the previous bar.
- Exit: close < middle band, or close touches
  entry-day middle band - 1xATR(14).
- Signals confirmed at close, filled next open; long only.
"""

import backtrader as bt

from backend.strat.common.base import LongOnlyStrategyBase
from backend.strat.common.indicators import BollingerBandwidth, RollingPercentile


class BollingerSqueeze(LongOnlyStrategyBase):
    params = (
        ("bb_period", 20),
        ("bb_dev", 2.0),
        ("squeeze_lookback", 200),
        ("squeeze_percentile", 10.0),
        ("expansion_mult", 1.3),
        ("atr_period", 14),
        ("atr_stop_mult", 1.0),
    )

    def __init__(self):
        super().__init__()
        self.bb = bt.indicators.BollingerBands(
            self.data.close, period=self.p.bb_period, devfactor=self.p.bb_dev
        )
        self.bandwidth = BollingerBandwidth(
            self.data.close, period=self.p.bb_period, devfactor=self.p.bb_dev
        )
        self.bw_percentile = RollingPercentile(
            self.bandwidth,
            period=self.p.squeeze_lookback,
            percentile=self.p.squeeze_percentile,
        )
        self.atr = bt.indicators.ATR(self.data, period=self.p.atr_period)
        self.bw_prev = self.bandwidth(-1)
        self.bw_percentile_prev = self.bw_percentile(-1)

    def risk_per_gram(self):
        return float(self.data.close[0]) - (
            self.bb.mid[0] - self.p.atr_stop_mult * self.atr[0]
        )

    def next(self):
        if not self.position:
            if not self.has_pending_order:
                squeezed = self.bw_prev[0] < self.bw_percentile_prev[0]
                breakout = self.data.close[0] > self.bb.top[0]
                expanding = (
                    self.bandwidth[0] >= self.bw_prev[0] * self.p.expansion_mult
                )
                if squeezed and breakout and expanding:
                    self.buy_next_open(reason="squeeze breakout above upper band")
        else:
            if self.stop_price is None:
                self.stop_price = (
                    self.bb.mid[0] - self.p.atr_stop_mult * self.atr[0]
                )

            if not self.has_pending_order:
                if self.data.close[0] <= self.stop_price:
                    self.sell_next_open(reason="ATR hard stop")
                elif self.data.close[0] < self.bb.mid[0]:
                    self.sell_next_open(reason="close below middle band")

        self.record_series(
            close=self.data.close[0],
            top=self.bb.top[0],
            mid=self.bb.mid[0],
            bottom=self.bb.bot[0],
            bandwidth=self.bandwidth[0],
            percentile=self.bw_percentile[0],
            atr=self.atr[0],
            stop=self.stop_price,
        )
