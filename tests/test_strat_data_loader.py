"""Tests for the ported gold daily-bar loader."""

from datetime import date, time

import pandas as pd
import pytest

from backend.strat.common import data_loader
from backend.strat.common.data_loader import Dataset, load_daily_csv, last_csv_date


def _frame(*days):
    return pd.DataFrame(
        [
            {
                "date": day,
                "open": 1.0,
                "high": 1.1,
                "low": 0.9,
                "close": 1.05,
                "volume": 100.0,
                "amt": 1.0,
            }
            for day in days
        ]
    )


def test_load_daily_csv_parses_seed_file():
    bars = load_daily_csv("data/518880.SH.csv")

    assert list(bars.columns) == ["date", "open", "high", "low", "close", "volume", "amt"]
    assert bars["date"].is_monotonic_increasing
    assert bars["date"].iloc[0] == date(2013, 7, 29)
    assert bars["close"].iloc[0] == pytest.approx(2.626)


def test_last_csv_date(tmp_path):
    csv_path = tmp_path / "bars.csv"
    csv_path.write_text(
        "date,open,high,low,close,volume,amt\n"
        "2024/1/2,1,1.1,0.9,1.0,10,0.1\n"
        "2024/1/3,1,1.1,0.9,1.0,10,0.1\n",
        encoding="utf-8",
    )

    assert last_csv_date(csv_path) == date(2024, 1, 3)
    assert last_csv_date(tmp_path / "missing.csv") is None


def test_update_daily_appends_incremental_rows(tmp_path, monkeypatch):
    csv_path = tmp_path / "bars.csv"
    csv_path.write_text(
        "date,open,high,low,close,volume,amt\n2024/1/2,1,1.1,0.9,1.0,10,0.1\n",
        encoding="utf-8",
    )
    dataset = Dataset("test", "TEST.SH", csv_path, time(15, 0))
    calls = []

    def fake_fetch(code, start_date, end_date, source="auto"):
        calls.append((code, start_date, end_date))
        return _frame(date(2024, 1, 3), date(2024, 1, 4))

    monkeypatch.setattr(data_loader, "fetch_daily", fake_fetch)

    added = data_loader.update_daily(dataset, end=date(2024, 1, 5))

    assert calls == [("TEST.SH", date(2024, 1, 3), date(2024, 1, 5))]
    assert list(added["date"]) == [date(2024, 1, 3), date(2024, 1, 4)]
    text = csv_path.read_text(encoding="utf-8")
    assert "2024/1/3" in text and "2024/1/4" in text

    # Nothing left to fetch after the CSV catches up to the requested end date.
    calls.clear()
    assert data_loader.update_daily(dataset, end=date(2024, 1, 4)).empty
    assert calls == []


class FakeSource:
    def __init__(self, frame: pd.DataFrame):
        self.frame = frame
        self.calls = 0

    def fetch_historical_daily(self, code, start_date, end_date):
        self.calls += 1
        return self.frame


def test_fetch_daily_falls_back_to_http(monkeypatch):
    sdk = FakeSource(pd.DataFrame())
    http = FakeSource(_frame(date(2024, 1, 3)))
    monkeypatch.setattr(data_loader, "ths_source", sdk)
    monkeypatch.setattr(data_loader, "ifind_http_source", http)

    result = data_loader.fetch_daily("AU9999.SHG", date(2024, 1, 1), date(2024, 1, 5))

    assert sdk.calls == 1
    assert http.calls == 1
    assert list(result["date"]) == [date(2024, 1, 3)]


def test_fetch_daily_rejects_unknown_source():
    with pytest.raises(ValueError):
        data_loader.fetch_daily("AU9999.SHG", date(2024, 1, 1), date(2024, 1, 5), source="bogus")
