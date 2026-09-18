"""Unit tests for THSDataSource HK stock info cache resolution.

Mocks the AI classification step and the OpenCode endpoint; no network or
real THS SDK required. The THSDataSource singleton is created at import time
(backend.data_source is imported by conftest / other tests); in the mock
environment the THS login simply logs an error and continues, so reusing the
module-level ``ths_source`` instance is safe.
"""

import json
from unittest.mock import patch

from backend.data_source import ths_source, HK_STOCK_CACHE_FILE


def test_resolve_uses_cached_entries_without_ai(tmp_path, monkeypatch):
    cache_file = tmp_path / "hk_stock_cache.json"
    cache_file.write_text(
        json.dumps(
            {
                "0700.HK": {
                    "symbol": "0700.HK",
                    "is_red_chip": False,
                    "is_dual_listed": False,
                    "a_share_symbol": None,
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("backend.data_source.HK_STOCK_CACHE_FILE", cache_file)

    with patch.object(ths_source, "_classify_hk_stock_via_ai") as mock_ai:
        info = ths_source._resolve_hk_stock_info(["0700.HK"])

    mock_ai.assert_not_called()
    assert info["0700.HK"]["is_red_chip"] is False
    assert info["0700.HK"]["is_dual_listed"] is False


def test_resolve_calls_ai_for_missing_and_persists(tmp_path, monkeypatch):
    cache_file = tmp_path / "hk_stock_cache.json"
    cache_file.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("backend.data_source.HK_STOCK_CACHE_FILE", cache_file)

    def fake_classify(symbol):
        return {
            "symbol": symbol,
            "is_red_chip": True,
            "is_dual_listed": True,
            "a_share_symbol": "600938.SH",
        }

    with patch.object(
        ths_source, "_classify_hk_stock_via_ai", side_effect=fake_classify
    ) as mock_ai:
        info = ths_source._resolve_hk_stock_info(["09988.HK", "0700.HK"])

    # Only missing symbol triggers an AI call
    assert mock_ai.call_count == 2
    mock_ai.assert_any_call("09988.HK")
    mock_ai.assert_any_call("0700.HK")
    assert info["09988.HK"]["is_red_chip"] is True
    assert info["09988.HK"]["a_share_symbol"] == "600938.SH"

    # Cache file should now contain both new entries
    persisted = json.loads(cache_file.read_text(encoding="utf-8"))
    assert "09988.HK" in persisted
    assert "0700.HK" in persisted
    assert persisted["09988.HK"]["a_share_symbol"] == "600938.SH"


def test_resolve_does_not_cache_failed_classification(tmp_path, monkeypatch):
    cache_file = tmp_path / "hk_stock_cache.json"
    cache_file.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("backend.data_source.HK_STOCK_CACHE_FILE", cache_file)

    with patch.object(
        ths_source, "_classify_hk_stock_via_ai", return_value=None
    ) as mock_ai:
        info = ths_source._resolve_hk_stock_info(["09988.HK"])

    mock_ai.assert_called_once_with("09988.HK")
    assert "09988.HK" not in info
    # Cache file should remain empty
    persisted = json.loads(cache_file.read_text(encoding="utf-8"))
    assert persisted == {}


def test_resolve_skips_ai_when_api_key_missing(tmp_path, monkeypatch):
    cache_file = tmp_path / "hk_stock_cache.json"
    cache_file.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("backend.data_source.HK_STOCK_CACHE_FILE", cache_file)

    # Pretend the AI client has no API key configured
    with patch("backend.data_source.ai_agent_client") as mock_client:
        mock_client.is_configured = False
        with patch.object(ths_source, "_classify_hk_stock_via_ai") as mock_ai:
            info = ths_source._resolve_hk_stock_info(["09988.HK"])

    mock_ai.assert_not_called()
    assert "09988.HK" not in info
    persisted = json.loads(cache_file.read_text(encoding="utf-8"))
    assert persisted == {}


def test_classify_via_ai_normalizes_a_share_symbol(monkeypatch):
    # ai_agent_client.is_configured is checked in _resolve_hk_stock_info; here we
    # exercise _classify_hk_stock_via_ai directly.
    with patch("backend.data_source.ai_agent_client") as mock_client:
        mock_client.chat_json.return_value = {
            "is_red_chip": False,
            "is_dual_listed": True,
            "a_share_symbol": "  601939.sz  ",
        }
        info = ths_source._classify_hk_stock_via_ai("0939.HK")
    assert info == {
        "symbol": "0939.HK",
        "is_red_chip": False,
        "is_dual_listed": True,
        "a_share_symbol": "601939.SZ",
    }


def test_classify_via_ai_rejects_malformed_a_share_symbol(monkeypatch):
    with patch("backend.data_source.ai_agent_client") as mock_client:
        mock_client.chat_json.return_value = {
            "is_red_chip": False,
            "is_dual_listed": True,
            "a_share_symbol": "601939",  # missing exchange suffix
        }
        info = ths_source._classify_hk_stock_via_ai("0939.HK")
    assert info is not None
    assert info["is_dual_listed"] is False
    assert info["a_share_symbol"] is None


def test_classify_via_ai_returns_none_on_ai_failure(monkeypatch):
    with patch("backend.data_source.ai_agent_client") as mock_client:
        mock_client.chat_json.side_effect = RuntimeError("boom")
        info = ths_source._classify_hk_stock_via_ai("0939.HK")
    assert info is None


def test_original_cache_file_unchanged():
    # Sanity guard: tests must not have overwritten the real data/hk_stock_cache.json
    real = json.loads(HK_STOCK_CACHE_FILE.read_text(encoding="utf-8"))
    assert "0941.HK" in real
    assert real["0941.HK"]["is_red_chip"] is True


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v", "-s"])