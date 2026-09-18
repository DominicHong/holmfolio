"""Global constants and default configuration for the strategy package.

Ported from holmes-lab strategies/common/constants.py. Strategy-specific
parameters live in each strategy class; do not hardcode global constants there.
"""

from pathlib import Path

from backend.db import DATA_PATH

# ---------- Paths ----------
DATA_DIR = Path(DATA_PATH)
AU9999_DAILY_CSV = DATA_DIR / "AU9999_Daily.csv"
GOLD_ETF_DAILY_CSV = DATA_DIR / "518880.SH.csv"

# ---------- Account ----------
INITIAL_CASH = 1_000_000.0

# ---------- Trading costs (one-way) ----------
COMMISSION_RATE = 0.0002  # commission rate on notional
SLIPPAGE_RATE = 0.0002  # slippage rate on fill price

# ---------- Fund mode ----------
FUND_MODE = True
FUND_START_VALUE = 100.0

# ---------- Position rules ----------
POSITION_MODE = "percent_equity"
FIXED_GRAMS = 100.0
POSITION_PERCENT = 1.0
RISK_PER_TRADE = 0.02
MIN_TRADE_GRAMS = 1.0

# ---------- Backtest window (None = full data range) ----------
BACKTEST_START: str | None = None
BACKTEST_END: str | None = None

# ---------- Performance conventions ----------
TRADING_DAYS_PER_YEAR = 252
RISK_FREE_RATE = 0.0
