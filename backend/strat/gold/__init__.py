"""Gold CTA strategies (mirrors holmes-lab strategies/au9999_cta)."""

from backend.strat.gold.s1a_ma_cross_trailing import MaCrossTrailingStop
from backend.strat.gold.s3_bollinger_squeeze import BollingerSqueeze

DEFAULT_STRATEGY = "s1a_ma_cross_trailing"

STRATEGIES: dict[str, type] = {
    "s1a_ma_cross_trailing": MaCrossTrailingStop,
    "s3_bollinger_squeeze": BollingerSqueeze,
}

STRATEGY_LABELS: dict[str, str] = {
    "s1a_ma_cross_trailing": "s1a Dual-MA trend + ATR trailing stop",
    "s3_bollinger_squeeze": "s3 Bollinger squeeze breakout",
}

__all__ = [
    "BollingerSqueeze",
    "DEFAULT_STRATEGY",
    "MaCrossTrailingStop",
    "STRATEGIES",
    "STRATEGY_LABELS",
]
