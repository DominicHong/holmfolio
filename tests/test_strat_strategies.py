"""Parity tests for the ported gold strategies against holmes-lab backtests.

Reference results (holmes-lab strategies/au9999_cta, window
2018-01-01 ~ 2026-09-01, one-way commission 0.02% + slippage 0.02%):
- 518880 s1a: 53 closed trades, first 2018-10-22 -> 2018-11-01, final 3.3494x
- AU9999 s1a: 34 closed trades, first 2018-10-19 -> 2018-11-13, final 3.7268x
- 518880 s1b: 53 closed trades, first 2018-10-22 -> 2018-11-01, final 3.0545x
- AU9999 s1b: 34 closed trades, first 2018-10-19 -> 2018-11-13, final 3.4653x
"""

from datetime import date

import pandas as pd
import pytest

from backend.strat.common.data_loader import load_daily_csv
from backend.strat.common.engine import run_gold_backtest
from backend.strat.gold import STRATEGIES

START = date(2018, 1, 1)
END = date(2026, 9, 1)


def _run(csv_path: str, strategy_key: str) -> dict:
    bars = load_daily_csv(csv_path)
    bars = bars[(bars["date"] >= START) & (bars["date"] <= END)]
    frame = bars.set_index(pd.to_datetime(bars.pop("date")))
    frame["openinterest"] = 0.0
    return run_gold_backtest(frame, STRATEGIES[strategy_key])


def test_s1a_518880_round_trips_match_reference():
    result = _run("data/518880.SH.csv", "s1a_ma_cross_trailing")
    trips = result["round_trips"]

    assert len(trips) == 53
    assert trips[0]["entry_date"] == date(2018, 10, 22)
    assert trips[0]["exit_date"] == date(2018, 11, 1)
    assert result["nav_values"][-1] == pytest.approx(334.937, rel=1e-4)


def test_s1a_au9999_round_trips_match_reference():
    result = _run("data/AU9999_Daily.csv", "s1a_ma_cross_trailing")
    trips = result["round_trips"]

    assert len(trips) == 34
    assert trips[0]["entry_date"] == date(2018, 10, 19)
    assert trips[0]["exit_date"] == date(2018, 11, 13)
    assert result["nav_values"][-1] == pytest.approx(372.684, rel=1e-4)


def test_s1b_518880_round_trips_match_reference():
    result = _run("data/518880.SH.csv", "s1b_vol_target_ma_cross")
    trips = result["round_trips"]

    assert len(trips) == 53
    assert trips[0]["entry_date"] == date(2018, 10, 22)
    assert trips[0]["exit_date"] == date(2018, 11, 1)
    assert result["nav_values"][-1] == pytest.approx(305.455, rel=1e-4)


def test_s1b_au9999_round_trips_match_reference():
    result = _run("data/AU9999_Daily.csv", "s1b_vol_target_ma_cross")
    trips = result["round_trips"]

    assert len(trips) == 34
    assert trips[0]["entry_date"] == date(2018, 10, 19)
    assert trips[0]["exit_date"] == date(2018, 11, 13)
    assert result["nav_values"][-1] == pytest.approx(346.530, rel=1e-4)


@pytest.mark.parametrize("csv_path", ["data/518880.SH.csv", "data/AU9999_Daily.csv"])
def test_s1b_vol_target_scales_position(csv_path):
    result = _run(csv_path, "s1b_vol_target_ma_cross")
    position_pct = result["series"]["position_pct"]
    positive_pct = [value for value in position_pct if value > 0]

    # Target factors stay on the {25%, 50%, 75%, 100%} grid and high-volatility
    # periods actually de-risk (the smallest positive position is ~25%).
    assert set(result["series"]["factor"]) <= {0.25, 0.5, 0.75, 1.0}
    assert max(position_pct) > 90.0
    assert min(positive_pct) < 60.0


@pytest.mark.parametrize("csv_path", ["data/518880.SH.csv", "data/AU9999_Daily.csv"])
def test_s1b_rebalances_do_not_count_as_round_trips(csv_path):
    """Grid rebalances are fills only; only signal exits close round trips."""
    result = _run(csv_path, "s1b_vol_target_ma_cross")
    partial_sells = [
        fill
        for fill in result["fills"]
        if fill["action"] == "sell" and fill["position"] > 0
    ]
    sell_signals = [signal for signal in result["signals"] if signal["action"] == "sell"]

    assert partial_sells
    assert len(sell_signals) == len(result["round_trips"])
    assert all(signal["size"] is not None for signal in sell_signals)


def test_engine_reports_close_only_round_trips():
    result = _run("data/518880.SH.csv", "s1b_vol_target_ma_cross")

    assert all(trip["exit_date"] is not None for trip in result["round_trips"])


@pytest.mark.parametrize(
    "strategy_key", ["s1a_ma_cross_trailing", "s1b_vol_target_ma_cross"]
)
def test_engine_records_model_position_percentage(strategy_key):
    result = _run("data/518880.SH.csv", strategy_key)
    position_pct = result["series"]["position_pct"]

    assert len(position_pct) == len(result["series_dates"])
    assert min(position_pct) == pytest.approx(0.0)
    # All-in percent_equity entries put nearly the whole equity to work.
    assert max(position_pct) > 90.0


def test_engine_records_fills_and_signal_units():
    result = _run("data/518880.SH.csv", "s1a_ma_cross_trailing")
    fills = result["fills"]

    assert fills
    assert all(fill["size"] > 0 for fill in fills)

    running = 0.0
    for fill in fills:
        running += fill["size"] if fill["action"] == "buy" else -fill["size"]
        assert fill["position"] == pytest.approx(running)
    assert fills[-1]["position"] == pytest.approx(result["model_state"]["position_size"])

    executed = [signal for signal in result["signals"] if signal["exec_date"] is not None]
    assert executed
    assert all(signal["size"] is not None for signal in executed)
    assert all(
        signal["size"] is None
        for signal in result["signals"]
        if signal["exec_date"] is None
    )


def test_engine_sizes_fills_to_initial_cash():
    result = _run("data/518880.SH.csv", "s1a_ma_cross_trailing")
    first_buy = next(fill for fill in result["fills"] if fill["action"] == "buy")

    # 1,000,000 nominal account: deployed notional cannot exceed the cash.
    assert first_buy["size"] * first_buy["price"] <= 1_000_000
