"""Gold CTA strategies (mirrors holmes-lab strategies/au9999_cta)."""

from backend.strat.gold.s1a_ma_cross_trailing import MaCrossTrailingStop
from backend.strat.gold.s1b_vol_target_ma_cross import VolTargetMaCross

DEFAULT_STRATEGY = "s1a_ma_cross_trailing"

STRATEGIES: dict[str, type] = {
    "s1a_ma_cross_trailing": MaCrossTrailingStop,
    "s1b_vol_target_ma_cross": VolTargetMaCross,
}

STRATEGY_LABELS: dict[str, str] = {
    "s1a_ma_cross_trailing": "s1a Dual-MA trend + ATR trailing stop",
    "s1b_vol_target_ma_cross": "s1b Dual-MA trend + vol-target position sizing",
}

__all__ = [
    "DEFAULT_STRATEGY",
    "MaCrossTrailingStop",
    "STRATEGIES",
    "STRATEGY_LABELS",
    "VolTargetMaCross",
]
