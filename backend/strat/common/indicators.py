"""Shared custom indicators (ported from holmes-lab strategies/common/indicators.py)."""

import math

import backtrader as bt
import numpy as np

from backend.strat.common.constants import TRADING_DAYS_PER_YEAR


class RealizedVolatility(bt.Indicator):
    """Annualized realized volatility: sample std of daily returns x sqrt(252).

    Matches the documented RV60 convention (ddof=1); the first return is
    undefined, so the first ``period + 1`` bars have no value.
    """

    lines = ("rv",)
    params = (
        ("period", 60),
        ("annualize", float(TRADING_DAYS_PER_YEAR)),
    )

    def __init__(self):
        self.addminperiod(self.p.period + 1)

    def next(self):
        closes = np.asarray(self.data.get(size=self.p.period + 1), dtype=float)
        returns = np.diff(closes) / closes[:-1]
        self.lines.rv[0] = float(np.std(returns, ddof=1) * math.sqrt(self.p.annualize))


class OnBalanceVolume(bt.Indicator):
    """On-balance volume: add volume on up days, subtract on down days."""

    lines = ("obv",)

    def __init__(self):
        self.addminperiod(2)

    def next(self):
        base = self.lines.obv[-1]
        if math.isnan(base):
            base = 0.0
        if self.data.close[0] > self.data.close[-1]:
            self.lines.obv[0] = base + self.data.volume[0]
        elif self.data.close[0] < self.data.close[-1]:
            self.lines.obv[0] = base - self.data.volume[0]
        else:
            self.lines.obv[0] = base


class BollingerBandwidth(bt.Indicator):
    """Bollinger bandwidth = (upper - lower) / middle."""

    lines = ("bw",)
    params = (
        ("period", 20),
        ("devfactor", 2.0),
    )

    def __init__(self):
        self.bb = bt.indicators.BollingerBands(
            self.data, period=self.p.period, devfactor=self.p.devfactor
        )
        self.addminperiod(self.p.period)

    def next(self):
        mid = self.bb.mid[0]
        self.lines.bw[0] = (self.bb.top[0] - self.bb.bot[0]) / mid if mid else 0.0


class RollingPercentile(bt.Indicator):
    """Rolling percentile value (default: 10th percentile of the last 200 bars)."""

    lines = ("pct",)
    params = (
        ("period", 200),
        ("percentile", 10.0),
    )

    def __init__(self):
        self.addminperiod(self.p.period)

    def next(self):
        window = self.data.get(size=self.p.period)
        self.lines.pct[0] = float(np.percentile(window, self.p.percentile))
