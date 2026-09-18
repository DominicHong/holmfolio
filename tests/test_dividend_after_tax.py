"""Test get_dividend_after_tax_past_year with real data from THS API.

This test requires a valid THS (TongHuaShun iFinD) login.
Run with: python -m pytest tests/test_dividend_after_tax.py -v -s
"""

import pytest
from datetime import date

from backend.data_source import THSDataSource


@pytest.mark.production
class TestDividendAfterTaxRealData:
    """Test dividend after tax calculation with real THS API data."""

    @pytest.fixture(scope="class")
    def ths_data_source(self):
        """Create THSDataSource with real API connection."""
        return THSDataSource()

    def test_get_dividend_after_tax_past_year(self, ths_data_source):
        """Test get_dividend_after_tax_past_year with real data.

        Expected values (provided by user):
        - 600036.SH -> 2.016
        - 00177.HK -> 0.5003
        - 00941.HK -> 4.743
        - 03818.HK -> 0.0114
        """
        symbols = ["600036.SH", "00177.HK", "00941.HK", "03818.HK"]
        as_of_date = date(2026, 4, 11)
        hkd_cny_rate = 0.8815

        # Expected results
        expected = {
            "600036.SH": 2.016,
            "00177.HK": 0.5003,
            "00941.HK": 4.743,
            "03818.HK": 0.0114,
        }

        results = ths_data_source.get_dividend_after_tax_past_year(
            symbols=symbols,
            as_of_date=as_of_date,
            hkd_cny_rate=hkd_cny_rate,
        )

        # Convert results to dict for easier comparison
        results_dict = {symbol: dividend for symbol, dividend in results}

        print("\n" + "=" * 60)
        print("Dividend After Tax Test Results:")
        print("=" * 60)
        print(f"{'Symbol':<15} {'Expected':<12} {'Actual':<12} {'Diff':<12}")
        print("-" * 60)

        for symbol in symbols:
            expected_val = expected[symbol]
            actual_val = results_dict.get(symbol, 0.0)
            diff = actual_val - expected_val
            diff_pct = (diff / expected_val * 100) if expected_val != 0 else 0

            status = "OK" if abs(diff) < 0.01 else "FAIL"
            print(
                f"{symbol:<15} {expected_val:<12.4f} {actual_val:<12.4f} "
                f"{diff:+.4f} ({diff_pct:+.2f}%) [{status}]"
            )

        print("=" * 60)

        # Assert results are close to expected values (within 0.01 tolerance)
        for symbol in symbols:
            assert symbol in results_dict, f"Missing result for {symbol}"
            actual = results_dict[symbol]
            expected_val = expected[symbol]
            assert abs(actual - expected_val) < 0.01, (
                f"{symbol}: expected {expected_val}, got {actual}, "
                f"diff = {actual - expected_val}"
            )

    def test_empty_symbols(self, ths_data_source):
        """Test with empty symbols list."""
        results = ths_data_source.get_dividend_after_tax_past_year(
            symbols=[],
            as_of_date=date(2026, 4, 11),
            hkd_cny_rate=0.8815,
        )
        assert results == []


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
