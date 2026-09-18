"""Parity tests for the ported gold strategies against holmes-lab backtests.

Reference results (holmes-lab strategies/au9999_cta/results, window
2018-01-01 ~ 2026-09-01, one-way commission 0.02% + slippage 0.02%):
- 518880 s1a: 53 closed trades, first 2018-10-22 -> 2018-11-01, final 3.3494x
- AU9999 s1a: 34 closed trades, first 2018-10-19 -> 2018-11-13, final 3.7268x
- s3: 5 closed trades on both assets (2020-07-23 first round trip), plus an
  open position entered 2026-08-07 with a pending sell signal on 2026-09-01.
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


@pytest.mark.parametrize(
    ("csv_path", "exit_dates"),
    [
        (
            "data/518880.SH.csv",
            [
                date(2020, 8, 13),
                date(2022, 12, 6),
                date(2023, 4, 24),
                date(2024, 4, 24),
                date(2025, 10, 29),
            ],
        ),
        (
            "data/AU9999_Daily.csv",
            [
                date(2020, 8, 13),
                date(2022, 12, 7),
                date(2023, 4, 25),
                date(2024, 4, 24),
                date(2025, 10, 29),
            ],
        ),
    ],
)
def test_s3_closed_round_trips_match_reference(csv_path, exit_dates):
    result = _run(csv_path, "s3_bollinger_squeeze")
    trips = result["round_trips"]

    assert len(trips) == 5
    assert [trip["exit_date"] for trip in trips] == exit_dates
    assert trips[0]["entry_date"] == date(2020, 7, 23)


def test_s3_pending_sell_signal_and_open_position():
    result = _run("data/518880.SH.csv", "s3_bollinger_squeeze")
    state = result["model_state"]

    assert state["position_size"] > 0
    assert state["entry_date"] == date(2026, 8, 7)
    assert state["stop_price"] is not None
    assert state["pending_signal"]["signal_date"] == date(2026, 9, 1)
    assert state["pending_signal"]["action"] == "sell"


def test_engine_reports_close_only_round_trips():
    result = _run("data/518880.SH.csv", "s3_bollinger_squeeze")

    assert all(trip["exit_date"] is not None for trip in result["round_trips"])


@pytest.mark.parametrize("strategy_key", ["s1a_ma_cross_trailing", "s3_bollinger_squeeze"])
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
