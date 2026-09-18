"""Tests for the dividend check and backfill service."""

from datetime import date, timedelta
from decimal import Decimal

import akshare as ak
import pandas as pd
import pytest
from sqlmodel import select

from backend.data_source import akshare_source, ths_source
from backend.db.models import Asset, Transaction
from backend.services.dividend_check import DividendCheckService


def add_txn(
    session,
    portfolio,
    asset,
    trade_date,
    action,
    quantity=None,
    price=None,
    amount=None,
    currency_id=None,
    fees=0,
):
    txn = Transaction(
        portfolio_id=portfolio.id,
        trade_date=trade_date,
        action=action,
        asset_id=asset.id,
        quantity=quantity,
        price=price,
        amount=amount if amount is not None else Decimal("0"),
        fees=fees,
        currency_id=currency_id or asset.currency_id,
    )
    session.add(txn)
    session.commit()
    return txn


def fake_history(events):
    def _fake(symbol, asset_type=None, start_year=None):
        return [
            {
                "report_date": event.get("report_date"),
                "record_date": event["record_date"],
                "received_date": event["received_date"],
                "per_share": Decimal(str(event["per_share"])),
                "scheme": event.get("scheme"),
            }
            for event in events
        ]

    return _fake


class TestHoldingIntervals:
    def test_single_interval_still_held(self, test_db):
        asset = test_db._test_assets["600036.SH"]
        add_txn(test_db, test_db._test_portfolio, asset, date(2026, 1, 1), "buy", quantity=100, amount=3000)

        txns = test_db.exec(
            select(Transaction)
            .where(Transaction.portfolio_id == test_db._test_portfolio.id)
        ).all()

        with DividendCheckService(test_db) as service:
            intervals = service._holding_intervals(txns)

        assert intervals == [(date(2026, 1, 1), date.today())]

    def test_sold_then_rebought(self, test_db):
        portfolio = test_db._test_portfolio
        asset = test_db._test_assets["600036.SH"]
        add_txn(test_db, portfolio, asset, date(2026, 1, 1), "buy", quantity=100, amount=3000)
        add_txn(test_db, portfolio, asset, date(2026, 3, 1), "sell", quantity=100, amount=3500)
        add_txn(test_db, portfolio, asset, date(2026, 5, 1), "buy", quantity=50, amount=2000)

        txns = test_db.exec(
            select(Transaction).where(Transaction.portfolio_id == portfolio.id)
        ).all()

        with DividendCheckService(test_db) as service:
            intervals = service._holding_intervals(txns)

        assert intervals == [
            (date(2026, 1, 1), date(2026, 3, 1)),
            (date(2026, 5, 1), date.today()),
        ]

    def test_quantity_as_of_includes_splits(self, test_db):
        portfolio = test_db._test_portfolio
        asset = test_db._test_assets["600036.SH"]
        add_txn(test_db, portfolio, asset, date(2026, 1, 1), "buy", quantity=100, amount=3000)
        add_txn(test_db, portfolio, asset, date(2026, 2, 1), "split", quantity=2)
        add_txn(test_db, portfolio, asset, date(2026, 3, 1), "sell", quantity=150, amount=6000)

        txns = test_db.exec(
            select(Transaction).where(Transaction.portfolio_id == portfolio.id)
        ).all()

        with DividendCheckService(test_db) as service:
            assert service._quantity_as_of(txns, date(2026, 1, 15)) == Decimal("100")
            assert service._quantity_as_of(txns, date(2026, 2, 1)) == Decimal("200")
            assert service._quantity_as_of(txns, date(2026, 3, 1)) == Decimal("50")
            assert service._quantity_as_of(txns, date(2026, 4, 1)) == Decimal("50")


class TestParseHelpers:
    def test_parse_a_share_scheme(self):
        assert akshare_source._parse_a_share_scheme_per_share("10派17.38元(含税)") == Decimal("1.738")
        assert akshare_source._parse_a_share_scheme_per_share("10派8元转12股派39.74元(含税)") == Decimal("0.8")
        assert akshare_source._parse_a_share_scheme_per_share("不分配不转增") is None
        assert akshare_source._parse_a_share_scheme_per_share("10派10.030元(含税)") == Decimal("1.003")

    def test_parse_hk_payout(self):
        assert akshare_source._parse_hk_payout_per_share("每股5.3港元") == Decimal("5.3")
        assert akshare_source._parse_hk_payout_per_share("每股派港币0.3元") == Decimal("0.3")
        assert akshare_source._parse_hk_payout_per_share("不分红") is None


class TestCheckMissingDividends:
    def test_flags_unrecorded_dividend_during_holding(self, test_db, monkeypatch):
        portfolio = test_db._test_portfolio
        asset = test_db._test_assets["600036.SH"]
        add_txn(test_db, portfolio, asset, date(2025, 7, 1), "buy", quantity=1000, amount=35000)

        monkeypatch.setattr(
            akshare_source,
            "get_dividend_history",
            fake_history(
                [
                    {
                        "report_date": "2025年报",
                        "record_date": date(2026, 7, 9),
                        "received_date": date(2026, 7, 10),
                        "per_share": "1.003",
                        "scheme": "10派10.030元(含税)",
                    }
                ]
            ),
        )

        with DividendCheckService(test_db) as service:
            result = service.check_missing_dividends(portfolio.id)

        assert result["assets_checked"] == 1
        assert result["dividend_events_found"] == 1
        assert len(result["missing"]) == 1
        item = result["missing"][0]
        assert item["symbol"] == "600036.SH"
        assert item["name"] == "China Merchants Bank"
        assert item["record_date"] == date(2026, 7, 9)
        assert item["received_date"] == date(2026, 7, 10)
        assert item["per_share"] == 1.003
        assert item["quantity"] == 1000.0
        assert item["amount"] == 1003.0
        assert item["currency"] == "CNY"

    def test_skips_dividend_when_not_held_on_record_date(self, test_db, monkeypatch):
        """Holding only starts on the received date (after the record date)."""
        portfolio = test_db._test_portfolio
        asset = test_db._test_assets["600036.SH"]
        add_txn(test_db, portfolio, asset, date(2026, 7, 10), "buy", quantity=1000, amount=35000)

        monkeypatch.setattr(
            akshare_source,
            "get_dividend_history",
            fake_history(
                [
                    {
                        "record_date": date(2026, 7, 9),
                        "received_date": date(2026, 7, 10),
                        "per_share": "1.003",
                    }
                ]
            ),
        )

        with DividendCheckService(test_db) as service:
            result = service.check_missing_dividends(portfolio.id)

        assert result["assets_checked"] == 1
        assert result["dividend_events_found"] == 1
        assert result["missing"] == []

    def test_skips_dividend_after_sellout(self, test_db, monkeypatch):
        portfolio = test_db._test_portfolio
        asset = test_db._test_assets["600036.SH"]
        add_txn(test_db, portfolio, asset, date(2026, 1, 1), "buy", quantity=100, amount=3000)
        add_txn(test_db, portfolio, asset, date(2026, 7, 5), "sell", quantity=100, amount=4000)

        monkeypatch.setattr(
            akshare_source,
            "get_dividend_history",
            fake_history(
                [
                    {
                        "record_date": date(2026, 7, 9),
                        "received_date": date(2026, 7, 10),
                        "per_share": "1.0",
                    }
                ]
            ),
        )

        with DividendCheckService(test_db) as service:
            result = service.check_missing_dividends(portfolio.id)

        assert result["missing"] == []

    def test_skips_already_recorded_dividend(self, test_db, monkeypatch):
        portfolio = test_db._test_portfolio
        asset = test_db._test_assets["600036.SH"]
        add_txn(test_db, portfolio, asset, date(2025, 7, 1), "buy", quantity=1000, amount=35000)
        add_txn(
            test_db,
            portfolio,
            asset,
            date(2026, 7, 10),
            "dividends",
            quantity=1000,
            price=Decimal("1.003"),
            amount=Decimal("1003.0"),
        )

        monkeypatch.setattr(
            akshare_source,
            "get_dividend_history",
            fake_history(
                [
                    {
                        "record_date": date(2026, 7, 9),
                        "received_date": date(2026, 7, 10),
                        "per_share": "1.003",
                    }
                ]
            ),
        )

        with DividendCheckService(test_db) as service:
            result = service.check_missing_dividends(portfolio.id)

        assert result["missing"] == []

    def test_skips_dividend_not_yet_received(self, test_db, monkeypatch):
        portfolio = test_db._test_portfolio
        asset = test_db._test_assets["600036.SH"]
        add_txn(test_db, portfolio, asset, date(2026, 1, 1), "buy", quantity=100, amount=3000)

        future = date.today() + timedelta(days=10)
        monkeypatch.setattr(
            akshare_source,
            "get_dividend_history",
            fake_history(
                [
                    {
                        "record_date": future - timedelta(days=1),
                        "received_date": future,
                        "per_share": "1.0",
                    }
                ]
            ),
        )

        with DividendCheckService(test_db) as service:
            result = service.check_missing_dividends(portfolio.id)

        assert result["dividend_events_found"] == 1
        assert result["missing"] == []

    def test_hk_red_chip_applies_tax_factor(self, test_db, monkeypatch):
        portfolio = test_db._test_portfolio
        asset = test_db._test_assets["00700.HK"]
        add_txn(test_db, portfolio, asset, date(2026, 1, 1), "buy", quantity=1000, amount=400000)

        monkeypatch.setattr(
            akshare_source,
            "get_dividend_history",
            fake_history(
                [
                    {
                        "record_date": date(2026, 5, 14),
                        "received_date": date(2026, 6, 1),
                        "per_share": "4.5",
                        "scheme": "每股4.5港元",
                    }
                ]
            ),
        )
        monkeypatch.setattr(
            ths_source,
            "_resolve_hk_stock_info",
            lambda symbols: {
                "0700.HK": {"symbol": "0700.HK", "is_red_chip": True, "is_dual_listed": False}
            },
        )

        with DividendCheckService(test_db) as service:
            result = service.check_missing_dividends(portfolio.id)

        assert len(result["missing"]) == 1
        item = result["missing"][0]
        assert item["amount"] == 1000 * 4.5 * 0.9
        assert item["currency"] == "HKD"

    def test_hk_ordinary_stock_no_tax_adjustment(self, test_db, monkeypatch):
        portfolio = test_db._test_portfolio
        asset = test_db._test_assets["00700.HK"]
        add_txn(test_db, portfolio, asset, date(2026, 1, 1), "buy", quantity=1000, amount=400000)

        monkeypatch.setattr(
            akshare_source,
            "get_dividend_history",
            fake_history(
                [
                    {
                        "record_date": date(2026, 5, 14),
                        "received_date": date(2026, 6, 1),
                        "per_share": "4.5",
                    }
                ]
            ),
        )
        monkeypatch.setattr(
            ths_source,
            "_resolve_hk_stock_info",
            lambda symbols: {
                "0700.HK": {"symbol": "0700.HK", "is_red_chip": False, "is_dual_listed": False}
            },
        )

        with DividendCheckService(test_db) as service:
            result = service.check_missing_dividends(portfolio.id)

        assert len(result["missing"]) == 1
        assert result["missing"][0]["amount"] == 1000 * 4.5

    def test_etf_asset_checked_for_fund_dividends(self, test_db, monkeypatch):
        """An A-share ETF is checked via the fund dividend path (not skipped)."""
        portfolio = test_db._test_portfolio
        asset = test_db._test_assets["510300.SH"]
        add_txn(test_db, portfolio, asset, date(2025, 6, 1), "buy", quantity=10000, amount=400000)

        monkeypatch.setattr(
            akshare_source,
            "get_dividend_history",
            fake_history(
                [
                    {
                        "record_date": date(2025, 11, 27),
                        "received_date": date(2025, 11, 28),
                        "per_share": "0.052",
                        "scheme": "CSI 300 ETF 分红",
                    }
                ]
            ),
        )

        with DividendCheckService(test_db) as service:
            result = service.check_missing_dividends(portfolio.id)

        assert len(result["missing"]) == 1
        item = result["missing"][0]
        assert item["symbol"] == "510300.SH"
        assert item["quantity"] == 10000.0
        assert item["amount"] == 10000 * 0.052
        assert item["currency"] == "CNY"

    def test_non_stock_hk_asset_never_consults_hk_cache(self, test_db, monkeypatch):
        """An HK non-stock asset (e.g. ETF) must not touch hk_stock_cache.json
        or the stock dividend interfaces."""
        portfolio = test_db._test_portfolio
        hkd = test_db._test_hkd
        etf = Asset(symbol="2800.HK", name="Tracker Fund", type="etf", currency_id=hkd.id)
        test_db.add(etf)
        test_db.commit()
        test_db.refresh(etf)

        add_txn(test_db, portfolio, etf, date(2026, 1, 1), "buy", quantity=100, amount=20000)

        def _should_not_be_called(*args, **kwargs):
            raise AssertionError(
                "stock dividend interfaces / hk cache must not be used for non-stock assets"
            )

        monkeypatch.setattr(ak, "stock_hk_dividend_payout_em", _should_not_be_called)
        monkeypatch.setattr(ak, "stock_fhps_detail_ths", _should_not_be_called)
        monkeypatch.setattr(ths_source, "_resolve_hk_stock_info", _should_not_be_called)

        with DividendCheckService(test_db) as service:
            result = service.check_missing_dividends(portfolio.id)

        assert result["assets_checked"] == 1
        assert result["dividend_events_found"] == 0
        assert result["missing"] == []


class TestHkDataSource:
    def test_em_source_parses_payouts(self, monkeypatch):
        fake_df = pd.DataFrame(
            {
                "最新公告日期": ["2026-03-18"],
                "财政年度": ["2025"],
                "分红方案": ["每股派港币5.3元"],
                "分配类型": ["年度分配"],
                "除净日": ["2026-05-15"],
                "截至过户日": ["2026/05/19-2026/05/20"],
                "发放日": ["2026-06-01"],
            }
        )
        monkeypatch.setattr(ak, "stock_hk_dividend_payout_em", lambda symbol: fake_df)

        events = akshare_source.get_dividend_history("00700.HK")

        assert len(events) == 1
        assert events[0]["record_date"] == date(2026, 5, 14)
        assert events[0]["received_date"] == date(2026, 6, 1)
        assert events[0]["per_share"] == Decimal("5.3")
        assert events[0]["report_date"] == "2025"

    def test_em_source_skips_special_distribution(self, monkeypatch):
        fake_df = pd.DataFrame(
            {
                "最新公告日期": ["2026-03-18", "2026-05-01"],
                "财政年度": ["2025", "2026"],
                "分红方案": ["每股派港币5.3元", "每100股派1股"],
                "分配类型": ["年度分配", "特别分配"],
                "除净日": ["2026-05-15", "2026-05-20"],
                "截至过户日": ["2026/05/19-2026/05/20", "2026/05/21-2026/05/22"],
                "发放日": ["2026-06-01", "2026-06-05"],
            }
        )
        monkeypatch.setattr(ak, "stock_hk_dividend_payout_em", lambda symbol: fake_df)

        events = akshare_source.get_dividend_history("00700.HK")

        assert len(events) == 1
        assert events[0]["received_date"] == date(2026, 6, 1)

    def test_non_stock_assets_skipped_without_fetch(self, monkeypatch):
        """Bonds and HK funds/ETFs are skipped before any stock dividend interface is called."""
        def _should_not_be_called(*args, **kwargs):
            raise AssertionError("stock dividend interfaces must not be called for unsupported assets")

        monkeypatch.setattr(ak, "stock_fhps_detail_ths", _should_not_be_called)
        monkeypatch.setattr(ak, "stock_hk_dividend_payout_em", _should_not_be_called)
        monkeypatch.setattr(ak, "fund_fh_em", lambda year: pd.DataFrame())

        assert akshare_source.get_dividend_history("019547.SH", "bond") == []
        assert akshare_source.get_dividend_history("2800.HK", "fund") == []
        assert akshare_source.get_dividend_history("2800.HK", "etf") == []

    def test_fund_dividend_history_parsed_from_fund_fh_em(self, monkeypatch):
        akshare_source._fund_dividends_by_year.clear()
        fake_year_data = {
            "2024": pd.DataFrame(
                {
                    "基金代码": ["510900", "510050"],
                    "基金简称": ["华夏恒生ETF", "上证50ETF华夏"],
                    "权益登记日": [date(2024, 11, 28), date(2024, 11, 29)],
                    "除息日期": [date(2024, 11, 29), date(2024, 12, 2)],
                    "分红": [0.052, 0.055],
                    "分红发放日": [date(2024, 12, 3), date(2024, 12, 5)],
                }
            ),
            "2026": pd.DataFrame(
                {
                    "基金代码": ["510900"],
                    "基金简称": ["华夏恒生ETF"],
                    "权益登记日": [date(2026, 6, 24)],
                    "除息日期": [date(2026, 6, 25)],
                    "分红": [0.06],
                    "分红发放日": [date(2026, 6, 30)],
                }
            ),
        }
        monkeypatch.setattr(ak, "fund_fh_em", lambda year: fake_year_data.get(year, pd.DataFrame()))

        events = akshare_source.get_dividend_history("510900.SH", "etf", 2024)

        assert len(events) == 2
        assert events[0]["record_date"] == date(2024, 11, 28)
        assert events[0]["received_date"] == date(2024, 12, 3)
        assert events[0]["per_share"] == Decimal("0.052")
        assert "华夏恒生ETF" in events[0]["scheme"]
        assert events[0]["report_date"] == "2024-11-29"
        assert events[1]["received_date"] == date(2026, 6, 30)

    def test_fund_dividends_by_year_shared_across_calls(self, monkeypatch):
        akshare_source._fund_dividends_by_year.clear()
        calls: list[str] = []

        def _fake_fh(year):
            calls.append(year)
            return pd.DataFrame(
                {
                    "基金代码": ["510900"],
                    "基金简称": ["华夏恒生ETF"],
                    "权益登记日": [date(2026, 6, 24)],
                    "除息日期": [date(2026, 6, 25)],
                    "分红": [0.06],
                    "分红发放日": [date(2026, 6, 30)],
                }
            )

        monkeypatch.setattr(ak, "fund_fh_em", _fake_fh)

        akshare_source.get_dividend_history("510900.SH", "etf", 2025)
        akshare_source.get_dividend_history("510050.SH", "etf", 2024)

        assert sorted(calls) == ["2024", "2025", "2026"]

    def test_a_share_history_parsed_from_ths_dataframe(self, monkeypatch):
        fake_df = pd.DataFrame(
            {
                "报告期": ["2025年报", "2025中报"],
                "分红方案说明": ["10派10.030元(含税)", "10派1元(含税)"],
                "A股股权登记日": [date(2026, 7, 9), date(2026, 1, 15)],
                "A股除权除息日": [date(2026, 7, 10), date(2026, 1, 16)],
                "方案进度": ["实施方案", "股东大会预案"],
            }
        )
        monkeypatch.setattr(ak, "stock_fhps_detail_ths", lambda symbol: fake_df)

        events = akshare_source.get_dividend_history("600036.SH")

        assert len(events) == 1
        assert events[0]["record_date"] == date(2026, 7, 9)
        assert events[0]["received_date"] == date(2026, 7, 10)
        assert events[0]["per_share"] == Decimal("1.003")


class TestAddMissingDividends:
    def test_adds_nothing_for_empty_items(self, test_db):
        portfolio = test_db._test_portfolio

        with DividendCheckService(test_db) as service:
            result = service.add_missing_dividends(portfolio.id, [])

        assert result == {"added": 0, "positions_recalculated": False}
        txns = test_db.exec(
            select(Transaction).where(Transaction.portfolio_id == portfolio.id)
        ).all()
        assert txns == []

    def test_adds_transactions_and_recalculates(self, test_db):
        portfolio = test_db._test_portfolio
        asset = test_db._test_assets["600036.SH"]
        add_txn(test_db, portfolio, asset, date(2026, 7, 1), "buy", quantity=1000, amount=35000)

        item = {
            "asset_id": asset.id,
            "symbol": "600036.SH",
            "name": "China Merchants Bank",
            "record_date": date(2026, 7, 9),
            "received_date": date(2026, 7, 10),
            "report_date": "2025年报",
            "per_share": 1.003,
            "quantity": 1000.0,
            "amount": 1003.0,
            "currency_id": asset.currency_id,
            "currency": "CNY",
            "holding_start": date(2026, 7, 1),
            "holding_end": date.today(),
            "scheme": "10派10.030元(含税)",
            "notes": "Auto-detected dividend, received 2026-07-10 (10派10.030元(含税))",
        }

        with DividendCheckService(test_db) as service:
            result = service.add_missing_dividends(portfolio.id, [item])

        assert result == {"added": 1, "positions_recalculated": True}

        dividends = test_db.exec(
            select(Transaction)
            .where(Transaction.portfolio_id == portfolio.id)
            .where(Transaction.action == "dividends")
        ).all()
        assert len(dividends) == 1
        txn = dividends[0]
        assert txn.trade_date == date(2026, 7, 10)
        assert txn.asset_id == asset.id
        assert txn.quantity == Decimal("1000")
        assert txn.price == Decimal("1.003")
        assert txn.amount == Decimal("1003.0")
        assert txn.fees == Decimal("0")
        assert txn.currency_id == asset.currency_id

        from backend.services.position import PositionService

        with PositionService(test_db) as position_service:
            latest = position_service.get_latest_positions(portfolio.id)

        cash_pos = next(p for p in latest if p.asset_id == test_db._test_assets["CNY_CASH"].id)
        assert cash_pos.quantity == Decimal("-35000") + Decimal("1003")
