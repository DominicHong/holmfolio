"""Tests for IFindHTTPDataSource, the iFinD HTTP fallback used without iFinDPy.

The HTTP source subclasses THSDataSource and only replaces the network
primitives, so these tests cover the request/response mapping and verify the
inherited high-level logic (dividend tax, financials, price history) works
over HTTP as well.
"""

from datetime import date
from types import SimpleNamespace

import pandas as pd

import backend.data_source as ds


def _fresh_http_source(monkeypatch) -> ds.IFindHTTPDataSource:
    """Build a fresh HTTP source (bypassing the module singleton) with a token."""
    monkeypatch.setattr(ds.IFindHTTPDataSource, "_instance", None)
    source = ds.IFindHTTPDataSource()
    source._access_token = "test-token"
    return source


def test_query_basic_data_builds_indipara_and_parses_table(monkeypatch):
    source = _fresh_http_source(monkeypatch)
    captured = {}

    def fake_post(url, headers, payload):
        captured["url"] = url
        captured["headers"] = headers
        captured["payload"] = payload
        return {
            "errorcode": 0,
            "errmsg": "success",
            "tables": [
                {
                    "thscode": "600036.SH",
                    "table": {"divi_per_share_btax_exspecial": [2.016]},
                }
            ],
        }

    monkeypatch.setattr(source, "_post_json", fake_post)

    result = source._query_basic_data(
        "600036.SH", "divi_per_share_btax_exspecial", "20251231,BB"
    )

    assert captured["url"] == f"{ds.IFIND_HTTP_BASE}/basic_data_service"
    assert captured["headers"]["access_token"] == "test-token"
    assert captured["headers"]["ifindlang"] == "cn"
    assert captured["payload"] == {
        "codes": "600036.SH",
        "indipara": [
            {
                "indicator": "divi_per_share_btax_exspecial",
                "indiparams": ["20251231", "BB"],
            }
        ],
    }
    assert result.errorcode == 0
    assert result.data["thscode"].tolist() == ["600036.SH"]
    assert result.data["divi_per_share_btax_exspecial"].iloc[0] == 2.016


def test_query_basic_data_pairs_params_with_indicators(monkeypatch):
    source = _fresh_http_source(monkeypatch)
    captured = {}

    def fake_post(url, headers, payload):
        captured["payload"] = payload
        return {
            "errorcode": 0,
            "errmsg": "success",
            "tables": [
                {
                    "thscode": "600036.SH",
                    "table": {
                        "total_shares": [25219845601],
                        "equity_belong_to_parent": [1.282355e12],
                    },
                }
            ],
        }

    monkeypatch.setattr(source, "_post_json", fake_post)

    result = source._query_basic_data(
        "600036.SH", "total_shares;equity_belong_to_parent", "2026-06-30;8,1,CNY"
    )

    assert captured["payload"]["indipara"] == [
        {"indicator": "total_shares", "indiparams": ["2026-06-30"]},
        {"indicator": "equity_belong_to_parent", "indiparams": ["8", "1", "CNY"]},
    ]
    row = result.data.iloc[0]
    assert row["total_shares"] == 25219845601
    assert row["equity_belong_to_parent"] == 1.282355e12


def test_query_history_quotes_converts_params_to_functionpara(monkeypatch):
    source = _fresh_http_source(monkeypatch)
    captured = {}

    def fake_post(url, headers, payload):
        captured["url"] = url
        captured["payload"] = payload
        return {
            "errorcode": 0,
            "errmsg": "success",
            "tables": [
                {
                    "thscode": "600036.SH",
                    "table": {"close": [45.1, 45.6]},
                    "time": ["2026-01-02", "2026-01-05"],
                }
            ],
        }

    monkeypatch.setattr(source, "_post_json", fake_post)

    result = source._query_history_quotes(
        "600036.SH", "close", "CPS:2;", "2026-01-01", "2026-01-31"
    )

    assert captured["url"] == f"{ds.IFIND_HTTP_BASE}/cmd_history_quotation"
    assert captured["payload"] == {
        "codes": "600036.SH",
        "indicators": "close",
        "startdate": "2026-01-01",
        "enddate": "2026-01-31",
        "functionpara": {"CPS": "2"},
    }
    assert result.errorcode == 0
    assert list(result.data["time"]) == ["2026-01-02", "2026-01-05"]
    assert list(result.data["close"]) == [45.1, 45.6]


def test_query_history_quotes_omits_empty_functionpara(monkeypatch):
    source = _fresh_http_source(monkeypatch)
    captured = {}

    monkeypatch.setattr(
        source,
        "_post_json",
        lambda url, headers, payload: captured.update(payload=payload)
        or {"errorcode": 0, "errmsg": "", "tables": []},
    )

    source._query_history_quotes("600036.SH", "close", "", "2026-01-01", "2026-01-31")

    assert "functionpara" not in captured["payload"]


def test_request_refreshes_stale_token_once(monkeypatch):
    source = _fresh_http_source(monkeypatch)
    tokens = []

    def fake_post(url, headers, payload):
        tokens.append(headers["access_token"])
        if len(tokens) == 1:
            return {"errorcode": -1010, "errmsg": "access_token expired"}
        return {"errorcode": 0, "errmsg": "success", "tables": []}

    monkeypatch.setattr(source, "_post_json", fake_post)
    monkeypatch.setattr(source, "_get_access_token", lambda: "new-token")

    result = source._request("basic_data_service", {"codes": "600036.SH"})

    assert result["errorcode"] == 0
    assert tokens == ["test-token", "new-token"]


def test_query_basic_data_preserves_error_namespace(monkeypatch):
    source = _fresh_http_source(monkeypatch)
    monkeypatch.setattr(source, "_get_access_token", lambda: "new-token")
    monkeypatch.setattr(
        source,
        "_post_json",
        lambda url, headers, payload: {"errorcode": -4001, "errmsg": "bad indicator"},
    )

    result = source._query_basic_data("600036.SH", "bogus", None)

    assert result.errorcode == -4001
    assert result.errmsg == "bad indicator"
    assert result.data.empty


def test_fetch_historical_daily_normalizes_bars(monkeypatch):
    source = _fresh_http_source(monkeypatch)

    def fake_post(url, headers, payload):
        return {
            "errorcode": 0,
            "errmsg": "success",
            "tables": [
                {
                    "thscode": "AU9999.SHG",
                    "table": {
                        "open": [480.0, 481.0],
                        "high": [482.0, 483.0],
                        "low": [479.0, 480.0],
                        "close": [481.5, 482.5],
                        "volume": [1000.0, 1100.0],
                        "amount": [4.815e10, 5.3075e10],
                    },
                    "time": ["2026-05-14", "2026-05-15"],
                }
            ],
        }

    monkeypatch.setattr(source, "_post_json", fake_post)

    df = source.fetch_historical_daily(
        "AU9999.SHG", date(2026, 5, 14), date(2026, 5, 15)
    )

    assert list(df.columns) == ["date", "open", "high", "low", "close", "volume", "amt"]
    assert list(df["date"]) == [date(2026, 5, 14), date(2026, 5, 15)]
    # amt is converted from CNY to 亿元.
    assert list(df["amt"]) == [481.5, 530.75]


def test_fetch_historical_prices_reports_http_source(monkeypatch):
    source = _fresh_http_source(monkeypatch)
    monkeypatch.setattr(
        source,
        "_query_history_quotes",
        lambda *args: SimpleNamespace(
            errorcode=0,
            errmsg="",
            data=pd.DataFrame(
                {
                    "thscode": ["600036.SH", "600036.SH"],
                    "time": ["2026-01-02", "2026-01-05"],
                    "close": [45.1, 45.6],
                }
            ),
        ),
    )

    df, source_name = source.fetch_historical_prices(
        "600036.SH", "stock", date(2026, 1, 1), date(2026, 1, 31)
    )

    assert source_name == "ifind_http"
    assert list(df["date"]) == [date(2026, 1, 2), date(2026, 1, 5)]
    assert list(df["close"]) == [45.1, 45.6]


def test_get_dividend_after_tax_past_year_over_http(monkeypatch):
    source = _fresh_http_source(monkeypatch)
    monkeypatch.setattr(
        source, "_resolve_hk_stock_info", lambda symbols: {}
    )
    calls = {"count": 0}

    def fake_query(symbol, indicators, params):
        calls["count"] += 1
        assert symbol == "600036.SH"
        assert indicators == "divi_per_share_btax_exspecial"
        return SimpleNamespace(
            errorcode=0,
            errmsg="",
            data=pd.DataFrame(
                {"thscode": [symbol], "divi_per_share_btax_exspecial": [1.5]}
            ),
        )

    monkeypatch.setattr(source, "_query_basic_data", fake_query)

    # Past the Q1 disclosure deadline (2026-04-30): no probe call, 4 reads.
    results = source.get_dividend_after_tax_past_year(
        ["600036.SH"], date(2026, 5, 20), hkd_cny_rate=1.0
    )

    assert results == [("600036.SH", 6.0)]
    assert calls["count"] == 4


def test_get_stock_financials_over_http(monkeypatch):
    source = _fresh_http_source(monkeypatch)
    monkeypatch.setattr(
        source, "_get_ttm_net_income", lambda symbol, as_of, retry=True: 150.0
    )

    def fake_query(symbols, indicators, params):
        assert symbols == "600036.SH"
        return SimpleNamespace(
            errorcode=0,
            errmsg="",
            data=pd.DataFrame(
                {
                    "thscode": ["600036.SH"],
                    "total_shares": [25219845601],
                    "equity_belong_to_parent": [1.282355e12],
                }
            ),
        )

    monkeypatch.setattr(source, "_query_basic_data", fake_query)

    result = source.get_stock_financials(["600036.SH"], date(2026, 6, 30))

    assert result == {
        "600036.SH": {
            "total_shares": 25219845601,
            "ni_to_parent": 150.0,
            "equity_to_parent": 1.282355e12,
        }
    }


def test_ths_source_matches_sdk_availability():
    """The module-level ths_source follows iFinDPy availability."""
    if ds.IFIND_SDK_AVAILABLE:
        assert isinstance(ds.ths_source, ds.THSDataSource)
        assert not isinstance(ds.ths_source, ds.IFindHTTPDataSource)
    else:
        assert isinstance(ds.ths_source, ds.IFindHTTPDataSource)


def test_http_source_has_own_singleton():
    """IFindHTTPDataSource must not reuse the THS SDK singleton."""
    assert isinstance(ds.ifind_http_source, ds.IFindHTTPDataSource)
    if ds.IFIND_SDK_AVAILABLE:
        assert ds.ifind_http_source is not ds.ths_source
