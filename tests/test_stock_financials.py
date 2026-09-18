"""Test get_stock_financials with real data from THS API.

This test requires a valid THS (TongHuaShun iFinD) login.
Run with: python -m pytest tests/test_stock_financials.py -v -s
"""

import pytest
from datetime import date

from backend.data_source import THSDataSource


@pytest.mark.production
class TestStockFinancialsRealData:
    """Test stock financials fetching with real THS API data."""

    @pytest.fixture(scope="class")
    def ths_data_source(self):
        """Create THSDataSource with real API connection."""
        return THSDataSource()

    def _assert_financials(self, results, as_of_date, expected, tolerance=10000):
        """Assert financials results match expected values."""
        symbols = list(expected.keys())

        print("\n" + "=" * 80)
        print(f"Stock Financials Test Results (as_of_date: {as_of_date}):")
        print("=" * 80)

        for symbol in symbols:
            assert symbol in results, f"Missing result for {symbol}"
            actual = results[symbol]
            exp = expected[symbol]

            print(f"\nSymbol: {symbol}")
            print(f"{'Indicator':<25} {'Expected':<20} {'Actual':<20} {'Diff':<15} {'Status'}")
            print("-" * 80)

            for key in ("total_shares", "equity_to_parent", "ni_to_parent"):
                expected_val = exp[key]
                actual_val = actual[key]
                diff = actual_val - expected_val
                status = "OK" if abs(diff) <= tolerance else "FAIL"
                print(
                    f"{key:<25} {expected_val:<20.2f} {actual_val:<20.2f} "
                    f"{diff:+.2f}        [{status}]"
                )

                assert abs(diff) <= tolerance, (
                    f"{symbol}.{key}: expected {expected_val}, got {actual_val}, "
                    f"diff = {diff}"
                )

        print("\n" + "=" * 80)

    def test_get_stock_financials_20260630(self, ths_data_source):
        """Test get_stock_financials for 2026-06-30.

        Expected values (provided by user, updated after THS data revisions:
        total_shares 9118020607 -> 9092234841 on 2026-08-05; equity and TTM
        ni revised after Tencent's H1 2026 report was ingested):
        - 00700.HK:
            total_shares = 9092234841
            equity_belong_to_parent = 1135853000000.00
            ni_to_parent = 235508000000.00
        - 600036.SH:
            total_shares = 25219845601
            equity_belong_to_parent = 1282355000000.00
            ni_to_parent = 150747000000.00

        Tolerance: 10000 (精确度至万元位)
        """
        symbols = ["00700.HK", "600036.SH"]
        as_of_date = date(2026, 6, 30)

        expected = {
            "00700.HK": {
                "total_shares": 9092234841,
                "equity_to_parent": 1135853000000.00,
                "ni_to_parent": 235508000000.00,
            },
            "600036.SH": {
                "total_shares": 25219845601,
                "equity_to_parent": 1282355000000.00,
                "ni_to_parent": 150747000000.00,
            },
        }

        results = ths_data_source.get_stock_financials(
            symbols=symbols,
            as_of_date=as_of_date,
        )

        self._assert_financials(results, as_of_date, expected, tolerance=1000000)

    def test_get_stock_financials_20260522(self, ths_data_source):
        """Test get_stock_financials for 2026-05-22 (today, within Q2 end).

        Equity and TTM ni should be the same as 2026-06-30 (equity and TTM ni
        now include Tencent's H1 2026 report ingested after the original
        expectations were recorded).
        """
        symbols = ["00700.HK", "600036.SH"]
        as_of_date = date(2026, 5, 22)

        expected = {
            "00700.HK": {
                "total_shares": 9118020607,
                "equity_to_parent": 1135853000000.00,
                "ni_to_parent": 235508000000.00,
            },
            "600036.SH": {
                "total_shares": 25219845601,
                "equity_to_parent": 1282355000000.00,
                "ni_to_parent": 150747000000.00,
            },
        }

        results = ths_data_source.get_stock_financials(
            symbols=symbols,
            as_of_date=as_of_date,
        )

        self._assert_financials(results, as_of_date, expected)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
