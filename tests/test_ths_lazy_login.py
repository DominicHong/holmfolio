"""Tests for lazy THS login: login happens on first API use, not at import."""

from datetime import date
from types import SimpleNamespace

import pandas as pd

from backend import data_source
from backend.data_source import ths_source


def test_init_does_not_login(monkeypatch):
    calls = []
    monkeypatch.setattr(
        data_source, "THS_iFinDLogin", lambda user, password: calls.append(1) or 0
    )
    monkeypatch.setattr(data_source.THSDataSource, "_initialized", False)
    monkeypatch.setattr(data_source.THSDataSource, "_instance", None)

    source = data_source.THSDataSource()

    assert calls == []
    assert source.login_status is None


def test_ensure_login_logs_in_only_when_needed(monkeypatch):
    calls = []
    monkeypatch.setattr(
        data_source, "THS_iFinDLogin", lambda user, password: calls.append(1) or 0
    )
    monkeypatch.setitem(data_source._ENV, "IFIND_USER", "test-user")
    monkeypatch.setitem(data_source._ENV, "IFIND_PASSWORD", "test-password")

    monkeypatch.setattr(ths_source, "login_status", 0)
    ths_source._ensure_login()
    assert calls == []

    monkeypatch.setattr(ths_source, "login_status", None)
    ths_source._ensure_login()
    ths_source._ensure_login()
    assert calls == [1]


def test_api_call_triggers_login(monkeypatch):
    calls = []
    monkeypatch.setattr(
        data_source, "THS_iFinDLogin", lambda user, password: calls.append(1) or 0
    )
    monkeypatch.setitem(data_source._ENV, "IFIND_USER", "test-user")
    monkeypatch.setitem(data_source._ENV, "IFIND_PASSWORD", "test-password")
    monkeypatch.setattr(ths_source, "login_status", None)
    monkeypatch.setattr(
        data_source,
        "THS_HQ",
        lambda *args, **kwargs: SimpleNamespace(
            errorcode=0, data=pd.DataFrame(), errmsg=""
        ),
    )

    df, source = ths_source.fetch_historical_prices(
        "600036.SH", "stock", date(2026, 1, 1), date(2026, 1, 2)
    )

    assert calls == [1]
    assert df.empty
    assert source == ""
