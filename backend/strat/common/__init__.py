"""Shared strategy infrastructure (ported from holmes-lab strategies/common)."""

from backend.strat.common.base import LongOnlyStrategyBase
from backend.strat.common.constants import (
    AU9999_DAILY_CSV,
    COMMISSION_RATE,
    FUND_START_VALUE,
    GOLD_ETF_DAILY_CSV,
    INITIAL_CASH,
    MIN_TRADE_GRAMS,
    POSITION_MODE,
    POSITION_PERCENT,
    RISK_FREE_RATE,
    SLIPPAGE_RATE,
    TRADING_DAYS_PER_YEAR,
)
from backend.strat.common.engine import run_gold_backtest

__all__ = [
    "AU9999_DAILY_CSV",
    "COMMISSION_RATE",
    "FUND_START_VALUE",
    "GOLD_ETF_DAILY_CSV",
    "INITIAL_CASH",
    "LongOnlyStrategyBase",
    "MIN_TRADE_GRAMS",
    "POSITION_MODE",
    "POSITION_PERCENT",
    "RISK_FREE_RATE",
    "SLIPPAGE_RATE",
    "TRADING_DAYS_PER_YEAR",
    "run_gold_backtest",
]
