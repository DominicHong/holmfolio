"""Unit tests for THSDataSource._get_ttm_net_income (TTM 归母净利润).

Covers the trailing-12-month NI computation from the period-cumulative
``ni_attr_to_cs`` indicator:

- Quarterly reporters: TTM = C(latest) + C(prev fiscal-year end) - C(same).
- Companies with only annual/semi-annual reports whose latest report is a
  fiscal-year end: TTM = C(latest).
- THS labels every annual report with 12/31 (including HK companies whose
  fiscal year ends in March or June), so a published annual can carry a
  label dated after the as-of date; such labels are found while labels of
  unpublished reports (which return no data) are skipped.
- Missing data falls back to C(latest) or 0.0.
"""

from datetime import date
from unittest.mock import patch

import pandas as pd
import pytest

import backend.data_source as ds
from backend.data_source import ths_source


def _mk_result(value):
    """Build a fake THS_BD result carrying a single ni_attr_to_cs value."""

    class R:
        errorcode = 0
        errmsg = ""

    r = R()
    r.data = pd.DataFrame({"thscode": ["X"], "ni_attr_to_cs": [value]})
    return r


def _run_ttm(symbol, as_of_date, values):
    """Call _get_ttm_net_income with THS_BD mocked to return ``values``.

    ``values`` maps report dates (YYYYMMDD) to ni_attr_to_cs values; any
    other report date returns None (no data).
    """
    with patch.object(
        ds,
        "THS_BD",
        side_effect=lambda sym, indicator, params: _mk_result(
            values.get(params.split(",")[0], None)
        ),
    ):
        return ths_source._get_ttm_net_income(symbol, as_of_date)


def test_quarterly_reporter_latest_q1():
    # 0700.HK as of 2026-06-30: latest published = Q1 2026 (3/31).
    # TTM = C(3/31/26) + C(12/31/25) - C(3/31/25)
    values = {
        "20260331": 58.09e9,
        "20251231": 224.842e9,
        "20250331": 47.82e9,
    }
    assert _run_ttm("0700.HK", date(2026, 6, 30), values) == pytest.approx(235.112e9)


def test_semi_annual_only_latest_is_annual():
    # 0837.HK as of 2026-08-19: semi 2026 and Q1 2026 not published, so the
    # latest published report is the FY2025 annual (12/31) -> TTM = C(12/31/25).
    values = {"20251231": 171.027e6}
    assert _run_ttm("0837.HK", date(2026, 8, 19), values) == pytest.approx(171.027e6)


def test_semi_annual_only_latest_is_semi():
    # 3818.HK as of 2026-08-19: latest published = H1 2026 (stored under the
    # 6/30 label; the FY2026 annual under 20261231 is not in the mock).
    # TTM = C(6/30/26) + C(12/31/25) - C(6/30/25)
    values = {
        "20260630": 203.773e6,
        "20251231": 207.0e6,
        "20250630": 136.965e6,
    }
    assert _run_ttm("3818.HK", date(2026, 8, 19), values) == pytest.approx(273.808e6)


def test_latest_annual_labeled_after_as_of_date():
    # THS stores the FY2026 annual (ended 2026-03-31, published 2026-06) of
    # 3818.HK under the 20261231 label, which is dated after the as-of date.
    # It is the latest published report and already covers 12 months.
    values = {"20261231": -158.04e6}
    assert _run_ttm("3818.HK", date(2026, 8, 19), values) == pytest.approx(-158.04e6)


def test_june_fiscal_year_stock_interim_latest():
    # 0083.HK ends its fiscal year in June, but THS labels the annual with
    # 12/31 (20251231 = FY2025 annual) and the interim with 6/30 (20260630 =
    # H1 FY2026). As of 2026-08-19 the latest published report is the H1
    # FY2026 interim, so TTM = C(6/30/26) + C(12/31/25) - C(6/30/25).
    values = {
        "20260630": 1375.628e6,
        "20251231": 3664.463e6,
        "20250630": 1716.819e6,
    }
    assert _run_ttm("0083.HK", date(2026, 8, 19), values) == pytest.approx(3323.272e6)


def test_missing_same_period_falls_back_to_latest():
    # Latest published (6/30/26) but no value for the same period a year ago:
    # fall back to C(latest) when it is positive.
    values = {"20260630": 100.0}
    assert _run_ttm("3818.HK", date(2026, 8, 19), values) == pytest.approx(100.0)


def test_no_published_data_returns_zero():
    assert _run_ttm("9999.HK", date(2026, 8, 19), {}) == 0.0
