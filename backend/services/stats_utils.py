"""Shared statistical helper functions for portfolio calculations.

These pure functions are module-level so they can be called from both
instance methods and ``@staticmethod`` contexts without needing ``self``.
"""

from datetime import date, timedelta

import numpy as np


def sanitize_scalar(value, default: float = 0.0) -> float:
    """Validate a numeric scalar, returning *default* for NaN/inf/complex."""
    if np.iscomplex(value) or np.isnan(value) or np.isinf(value):
        return default
    return float(np.real(value))


def sanitize_matrix(arr: np.ndarray, fill: float = 0.0) -> np.ndarray:
    """Replace NaN/inf in an array with *fill* (e.g. for corrcoef output)."""
    return np.nan_to_num(arr, nan=fill, posinf=fill, neginf=fill)


def compound_return(returns) -> float:
    """Compute compounded return ``prod(1 + r) - 1``.

    Accepts a list or 1-D numpy array of period returns.
    """
    arr = np.array(returns, dtype=float)
    return float(np.prod(1 + arr) - 1)


def prices_to_returns(
    prices: list[float],
    dates: list[date],
) -> tuple[list[float], list[date]]:
    """Convert a price series to simple returns indexed by end date.

    ``returns[i] = (prices[i+1] - prices[i]) / prices[i]``.
    Pairs where ``prev_price <= 0`` are dropped.
    """
    returns: list[float] = []
    return_dates: list[date] = []
    for i in range(1, len(prices)):
        prev = prices[i - 1]
        curr = prices[i]
        if prev > 0:
            returns.append((curr - prev) / prev)
            return_dates.append(dates[i])
    return returns, return_dates


def min_data_points_for(frequency: str) -> int:
    """Minimum aligned data points required for beta / correlation by frequency."""
    return {"daily": 20, "weekly": 4, "monthly": 2}.get(frequency, 20)


def date_range_list(start: date, end: date) -> list[date]:
    """Build a list of consecutive dates from *start* to *end* (inclusive)."""
    result: list[date] = []
    current = start
    while current <= end:
        result.append(current)
        current += timedelta(days=1)
    return result


def annualize_return(twr: float, days: int) -> float:
    """Annualize a total return: ``(1 + twr)^(365/days) - 1``."""
    if days > 0:
        return (1 + twr) ** (365 / days) - 1
    return 0.0
