"""Unit tests for PortfolioService._calc_financial_metrics (PE/PB/dividend yield)."""

import pytest

from backend.services.portfolio import PortfolioService


def test_pe_positive_for_profitable_company():
    m = PortfolioService._calc_financial_metrics(
        current_price=10.0,
        dividend_after_tax=0.5,
        total_shares=100.0,
        ni_to_parent=200.0,
        equity_to_parent=1000.0,
        exchange_rate=1.0,
    )
    assert m["pe"] == pytest.approx(5.0)
    assert m["pb"] == pytest.approx(1.0)
    assert m["dividend_yield"] == pytest.approx(0.05)


def test_pe_negative_for_loss_making_company():
    m = PortfolioService._calc_financial_metrics(
        current_price=10.0,
        dividend_after_tax=0.0,
        total_shares=100.0,
        ni_to_parent=-200.0,
        equity_to_parent=1000.0,
        exchange_rate=1.0,
    )
    assert m["pe"] == pytest.approx(-5.0)
    assert m["pb"] == pytest.approx(1.0)


def test_pe_none_for_zero_earnings():
    m = PortfolioService._calc_financial_metrics(
        current_price=10.0,
        dividend_after_tax=0.0,
        total_shares=100.0,
        ni_to_parent=0.0,
        equity_to_parent=1000.0,
    )
    assert m["pe"] is None


def test_pb_none_for_negative_equity():
    m = PortfolioService._calc_financial_metrics(
        current_price=10.0,
        dividend_after_tax=0.0,
        total_shares=100.0,
        ni_to_parent=200.0,
        equity_to_parent=-1000.0,
    )
    assert m["pb"] is None


def test_all_none_without_price():
    m = PortfolioService._calc_financial_metrics(
        current_price=None,
        dividend_after_tax=0.0,
        total_shares=100.0,
        ni_to_parent=200.0,
        equity_to_parent=1000.0,
    )
    assert m["pe"] is None
    assert m["pb"] is None
    assert m["dividend_yield"] is None
