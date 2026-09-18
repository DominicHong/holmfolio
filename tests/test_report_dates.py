"""Unit tests for THSDataSource report-date window handling.

Covers ``_resolve_report_dates_for_symbol`` and ``_disclosure_deadline``:

- Each stock is resolved independently (per-symbol window).
- Before the statutory disclosure deadline for the stock's market, the
  latest report period's dividend is probed: readable data (even a zero
  dividend) means the report is published and the window is kept;
  unreadable data means the report is not out yet and the window shifts
  back one quarter so the last 12 months of dividends are still covered.
- On/after the deadline the window is always kept (no probe needed).
- HK stocks and A+H dual-listed A-shares use the HK deadlines (annual
  report due Mar 31 of the following year); other A-shares use the A-share
  deadlines (annual report due Apr 30).
"""

from datetime import date
from unittest.mock import patch

import pytest

from backend.data_source import ths_source

HK_INFO_AH = {
    "0177.HK": {
        "symbol": "0177.HK",
        "is_red_chip": False,
        "is_dual_listed": True,
        "a_share_symbol": "600377.SH",
    }
}


def _resolve(symbol, as_of_date, hk_stock_info=None, probe_result=None):
    with patch.object(
        ths_source, "_get_dividend_or_none", return_value=probe_result
    ) as mock_probe:
        dates = ths_source._resolve_report_dates_for_symbol(
            symbol, as_of_date, hk_stock_info or {},
            probe=ths_source._get_dividend_or_none,
        )
    return dates, mock_probe


# ---------------------------------------------------------------------------
# _disclosure_deadline rule checks
# ---------------------------------------------------------------------------


def test_deadline_a_share_rules():
    assert ths_source._disclosure_deadline("600036.SH", "20260331", {}) == date(2026, 4, 30)
    assert ths_source._disclosure_deadline("600036.SH", "20260630", {}) == date(2026, 8, 31)
    assert ths_source._disclosure_deadline("600036.SH", "20250930", {}) == date(2025, 10, 31)
    assert ths_source._disclosure_deadline("600036.SH", "20251231", {}) == date(2026, 4, 30)


def test_deadline_hk_stock_uses_hk_rules():
    assert ths_source._disclosure_deadline("0700.HK", "20260331", {}) == date(2026, 4, 30)
    assert ths_source._disclosure_deadline("0700.HK", "20260630", {}) == date(2026, 8, 31)
    assert ths_source._disclosure_deadline("0700.HK", "20250930", {}) == date(2025, 10, 31)
    # HK annual report is due Mar 31 (vs Apr 30 for A-shares)
    assert ths_source._disclosure_deadline("0700.HK", "20251231", {}) == date(2026, 3, 31)


def test_deadline_dual_listed_a_share_uses_hk_rules():
    # 600377.SH is the A-share of 0177.HK (from the cache reverse lookup)
    assert ths_source._disclosure_deadline(
        "600377.SH", "20251231", HK_INFO_AH
    ) == date(2026, 3, 31)
    # Same A-share without the A+H cache entry falls back to A-share rules
    assert ths_source._disclosure_deadline(
        "600377.SH", "20251231", {}
    ) == date(2026, 4, 30)


# ---------------------------------------------------------------------------
# _resolve_report_dates_for_symbol behavior
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("symbol", ["0700.HK", "600036.SH"])
def test_shifts_back_when_semi_annual_report_not_published(symbol):
    # 2026-08-04: 2026Q2 semi-annual report (due Aug 31) not out yet, and no
    # data can be read -> the 2025Q2 dividend must still be covered.
    dates, mock_probe = _resolve(symbol, date(2026, 8, 4), probe_result=None)
    assert dates == ["20260331", "20251231", "20250930", "20250630"]
    mock_probe.assert_called_once_with(symbol, "20260630")


def test_no_shift_when_data_readable_even_if_zero_dividend():
    # Data readable before the deadline (even 0.0 dividend) = report published
    dates, _ = _resolve("600036.SH", date(2026, 8, 4), probe_result=0.0)
    assert dates == ["20260630", "20260331", "20251231", "20250930"]


def test_no_shift_after_deadline_without_probe():
    # 2026-09-10 is past the Aug 31 semi-annual deadline: keep the window
    # and do not probe the data source at all.
    dates, mock_probe = _resolve("600036.SH", date(2026, 9, 10), probe_result=None)
    assert dates == ["20260630", "20260331", "20251231", "20250930"]
    mock_probe.assert_not_called()


def test_q1_report_uses_same_detection_logic():
    # 2026-04-10: Q1 (3/31) report due Apr 30; unreadable -> shift back.
    dates, _ = _resolve("600036.SH", date(2026, 4, 10), probe_result=None)
    assert dates == ["20251231", "20250930", "20250630", "20250331"]
    # Q1 published early -> window kept
    dates, _ = _resolve("600036.SH", date(2026, 4, 10), probe_result=0.0)
    assert dates == ["20260331", "20251231", "20250930", "20250630"]


def test_get_past_4_report_dates_quarter_windows():
    """Raw report-date windows for each quarter (as-of dates in Q1-Q4)."""
    assert ths_source._get_past_4_report_dates(date(2026, 2, 15)) == [
        "20251231", "20250930", "20250630", "20250331",
    ]
    assert ths_source._get_past_4_report_dates(date(2026, 4, 11)) == [
        "20260331", "20251231", "20250930", "20250630",
    ]
    assert ths_source._get_past_4_report_dates(date(2026, 8, 20)) == [
        "20260630", "20260331", "20251231", "20250930",
    ]
    assert ths_source._get_past_4_report_dates(date(2026, 11, 5)) == [
        "20260930", "20260630", "20260331", "20251231",
    ]


def test_hk_annual_report_shifts_before_mar_31_deadline():
    # 2026-03-15: annual report (20251231) due Mar 31 for HK stocks; unreadable
    dates, _ = _resolve("0700.HK", date(2026, 3, 15), probe_result=None)
    assert dates == ["20250930", "20250630", "20250331", "20241231"]


def test_hk_annual_report_kept_on_mar_31_deadline():
    # 2026-03-31 is exactly the HK annual-report deadline: no probe, no shift.
    dates, mock_probe = _resolve("0700.HK", date(2026, 3, 31), probe_result=None)
    assert dates == ["20251231", "20250930", "20250630", "20250331"]
    mock_probe.assert_not_called()


def test_a_share_annual_report_still_probed_after_hk_deadline():
    # Same day 2026-03-31: a non-dual-listed A-share uses the Apr 30 deadline,
    # so it is still before its deadline and must probe (and shift) while the
    # HK / A+H stock above is already past its deadline.
    dates, mock_probe = _resolve("600036.SH", date(2026, 3, 31), probe_result=None)
    assert dates == ["20250930", "20250630", "20250331", "20241231"]
    mock_probe.assert_called_once_with("600036.SH", "20251231")


def test_dual_listed_a_share_uses_hk_deadline():
    # 600377.SH is A+H: HK annual deadline Mar 31 -> no probe, no shift.
    dates, mock_probe = _resolve(
        "600377.SH", date(2026, 3, 31), HK_INFO_AH, probe_result=None
    )
    assert dates == ["20251231", "20250930", "20250630", "20250331"]
    mock_probe.assert_not_called()
