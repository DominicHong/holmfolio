"""Tests for the gold trading service."""

from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
import pytest
from sqlmodel import select

from backend.db.models import Asset, Price, Settings, Transaction
from backend.services import GoldService, PriceRateService


@pytest.fixture
def gold_data(test_db):
    """Create a gold asset with four daily bars and a buy/sell transaction pair."""
    cny = test_db._test_cny
    portfolio = test_db._test_portfolio

    asset = Asset(symbol="AU9999.SHG", name="Gold Spot", type="gold", currency_id=cny.id)
    test_db.add(asset)
    test_db.commit()
    test_db.refresh(asset)

    closes = {
        date(2024, 1, 2): 480.0,
        date(2024, 1, 3): 485.0,
        date(2024, 1, 4): 500.0,
        date(2024, 1, 5): 490.0,
    }
    for day, close in closes.items():
        test_db.add(
            Price(
                asset_id=asset.id,
                price_date=day,
                price=Decimal(str(close)),
                open=Decimal(str(close - 1)),
                high=Decimal(str(close + 2)),
                low=Decimal(str(close - 2)),
                volume=Decimal("1000"),
                amount=Decimal("48"),
                price_type="historical",
                source="test",
            )
        )
    test_db.commit()

    test_db.add_all(
        [
            Transaction(
                portfolio_id=portfolio.id,
                asset_id=asset.id,
                trade_date=date(2024, 1, 3),
                action="buy",
                quantity=Decimal("100"),
                price=Decimal("480"),
                amount=Decimal("48000"),
                fees=Decimal("10"),
                currency_id=cny.id,
            ),
            Transaction(
                portfolio_id=portfolio.id,
                asset_id=asset.id,
                trade_date=date(2024, 1, 4),
                action="sell",
                quantity=Decimal("40"),
                price=Decimal("500"),
                amount=Decimal("20000"),
                fees=Decimal("5"),
                currency_id=cny.id,
            ),
        ]
    )
    test_db.commit()
    return asset, portfolio


class TestGoldService:
    def test_user_position_average_cost_and_pnl(self, test_db, gold_data):
        asset, portfolio = gold_data

        with GoldService(test_db) as service:
            position = service.get_user_position(portfolio.id, asset.id)

        assert position["quantity"] == pytest.approx(60.0)
        assert position["average_cost"] == pytest.approx((48000 + 10) / 100)
        assert position["realized_pnl"] == pytest.approx((500 - 480.1) * 40 - 5)
        assert position["unrealized_pnl"] == pytest.approx((490 - 480.1) * 60)
        assert position["total_pnl"] == pytest.approx(791 + 594)
        assert position["sells"] == 1
        assert position["win_rate"] == pytest.approx(1.0)

    def test_overview_normalized_nav_curves(self, test_db, gold_data):
        asset, portfolio = gold_data
        test_db.add(
            Settings(key="gold_initial_capital", value="1000000", description="test")
        )
        test_db.commit()

        with GoldService(test_db) as service:
            result = service.get_overview(
                portfolio.id,
                asset.id,
                "s1a_ma_cross_trailing",
                start_date=date(2024, 1, 2),
                end_date=date(2024, 1, 5),
            )

        performance = result["performance"]
        assert performance["dates"] == [
            date(2024, 1, 2),
            date(2024, 1, 3),
            date(2024, 1, 4),
            date(2024, 1, 5),
        ]
        assert performance["user_nav"] == pytest.approx(
            [100.0, 100.049, 100.1985, 100.1385]
        )
        assert performance["benchmark_nav"] == pytest.approx(
            [100.0, 485 / 480 * 100, 500 / 480 * 100, 490 / 480 * 100]
        )
        assert performance["benchmark_symbol"] == "AU9999.SHG"
        assert performance["metrics"]["user"]["total_return"] == pytest.approx(
            100.1385 / 100 - 1
        )
        assert performance["metrics"]["user"]["trades"] == 1
        assert performance["metrics"]["user"]["win_rate"] == pytest.approx(1.0)
        assert performance["metrics"]["user"]["realized_pnl"] == pytest.approx(791.0)
        assert performance["metrics"]["model"] is not None

    def test_metrics_trades_respect_date_window(self, test_db, gold_data):
        asset, portfolio = gold_data

        with GoldService(test_db) as service:
            result = service.get_overview(
                portfolio.id,
                asset.id,
                "s1a_ma_cross_trailing",
                start_date=date(2024, 1, 2),
                end_date=date(2024, 1, 3),
            )

        user_metrics = result["performance"]["metrics"]["user"]
        assert user_metrics["trades"] == 0
        assert user_metrics["win_rate"] is None
        assert user_metrics["realized_pnl"] == pytest.approx(0.0)

    def test_sharpe_uses_settings_risk_free_rate(self, test_db, gold_data):
        asset, portfolio = gold_data
        params = {"start_date": date(2024, 1, 2), "end_date": date(2024, 1, 5)}

        with GoldService(test_db) as service:
            baseline = service.get_overview(
                portfolio.id, asset.id, "s1a_ma_cross_trailing", **params
            )

        test_db.add(Settings(key="risk_free_rate", value="0.02", description="test"))
        test_db.commit()

        with GoldService(test_db) as service:
            shifted = service.get_overview(
                portfolio.id, asset.id, "s1a_ma_cross_trailing", **params
            )

        assert shifted["performance"]["risk_free_rate"] == pytest.approx(0.02)
        base_metric = baseline["performance"]["metrics"]["benchmark"]
        shift_metric = shifted["performance"]["metrics"]["benchmark"]
        expected = base_metric["sharpe"] - 0.02 / shift_metric["volatility"]
        assert shift_metric["sharpe"] == pytest.approx(expected)

    def test_benchmark_follows_selected_asset(self, test_db, gold_data):
        _, portfolio = gold_data
        cny = test_db._test_cny
        etf = Asset(symbol="518880.SH", name="Gold ETF", type="gold", currency_id=cny.id)
        test_db.add(etf)
        test_db.commit()
        test_db.refresh(etf)

        closes = {
            date(2024, 1, 2): 8.0,
            date(2024, 1, 3): 8.2,
            date(2024, 1, 4): 8.4,
            date(2024, 1, 5): 8.1,
        }
        for day, close in closes.items():
            test_db.add(
                Price(
                    asset_id=etf.id,
                    price_date=day,
                    price=Decimal(str(close)),
                    open=Decimal(str(close)),
                    high=Decimal(str(close)),
                    low=Decimal(str(close)),
                    volume=Decimal("1000"),
                    amount=Decimal("8"),
                    price_type="historical",
                    source="test",
                )
            )
        test_db.commit()

        with GoldService(test_db) as service:
            result = service.get_overview(
                portfolio.id,
                etf.id,
                "s1a_ma_cross_trailing",
                start_date=date(2024, 1, 2),
                end_date=date(2024, 1, 5),
            )

        performance = result["performance"]
        assert performance["benchmark_symbol"] == "518880.SH"
        assert performance["benchmark_nav"] == pytest.approx(
            [100.0, 8.2 / 8.0 * 100, 8.4 / 8.0 * 100, 8.1 / 8.0 * 100]
        )

    def test_strategy_position_uses_configured_capital_and_fills(self, test_db):
        cny = test_db._test_cny
        asset = Asset(symbol="AU9999.SHG", name="Gold Spot", type="gold", currency_id=cny.id)
        test_db.add(asset)
        test_db.commit()
        test_db.refresh(asset)

        day = date(2023, 1, 2)
        price = 400.0
        inserted = 0
        while inserted < 400:
            if day.weekday() < 5:
                price *= 1.002
                test_db.add(
                    Price(
                        asset_id=asset.id,
                        price_date=day,
                        price=Decimal(str(round(price, 4))),
                        open=Decimal(str(round(price - 1, 4))),
                        high=Decimal(str(round(price + 2, 4))),
                        low=Decimal(str(round(price - 3, 4))),
                        volume=Decimal("1000"),
                        amount=Decimal("40"),
                        price_type="historical",
                        source="test",
                    )
                )
                inserted += 1
            day += timedelta(days=1)
        test_db.commit()

        test_db.add(
            Settings(key="gold_initial_capital", value="1000000", description="test")
        )
        test_db.commit()

        with GoldService(test_db) as service:
            baseline = service.run_model(asset.id, "s1a_ma_cross_trailing")

        assert baseline["model_state"]["position_size"] > 0
        assert baseline["fills"]
        last_fill = baseline["fills"][-1]
        assert last_fill["position"] == pytest.approx(
            baseline["model_state"]["position_size"]
        )
        first_buy = next(fill for fill in baseline["fills"] if fill["action"] == "buy")
        assert first_buy["size"] * first_buy["price"] <= 1_000_000

        setting = test_db.exec(
            select(Settings).where(Settings.key == "gold_initial_capital")
        ).first()
        setting.value = "10000"
        test_db.add(setting)
        test_db.commit()

        with GoldService(test_db) as service:
            small = service.run_model(asset.id, "s1a_ma_cross_trailing")
            overview = service.get_overview(
                test_db._test_portfolio.id, asset.id, "s1a_ma_cross_trailing"
            )

        # Units come from actual fills at the configured account size.
        assert small["model_state"]["position_size"] == pytest.approx(
            baseline["model_state"]["position_size"] / 100, abs=1
        )
        first_buy_small = next(fill for fill in small["fills"] if fill["action"] == "buy")
        assert first_buy_small["size"] * first_buy_small["price"] <= 10_000
        assert overview["model_state"]["position_size"] == pytest.approx(
            small["model_state"]["position_size"]
        )

        # A window-scoped account restarts from the configured capital, so the
        # first in-window buy can never exceed it (regardless of the model's
        # compounded equity before the window).
        with GoldService(test_db) as service:
            windowed = service.get_overview(
                test_db._test_portfolio.id,
                asset.id,
                "s1a_ma_cross_trailing",
                start_date=date(2023, 1, 2),
                end_date=date(2024, 12, 31),
            )

        window_buys = [
            signal
            for signal in windowed["signals"]
            if signal["exec_date"] and signal["action"] == "buy" and signal["size"]
        ]
        assert window_buys
        assert window_buys[0]["size"] * window_buys[0]["exec_price"] <= 10_000
        # A window covering the full history reproduces the engine account.
        assert windowed["model_state"]["position_size"] == pytest.approx(
            small["model_state"]["position_size"]
        )

        # A window ending before the first fill reports a flat position.
        with GoldService(test_db) as service:
            early = service.get_overview(
                test_db._test_portfolio.id,
                asset.id,
                "s1a_ma_cross_trailing",
                end_date=date(2023, 1, 10),
            )
        assert early["model_state"]["position_size"] == 0.0
        assert early["model_state"]["entry_price"] is None

    def test_get_signals_on_short_history(self, test_db, gold_data):
        asset, _ = gold_data

        with GoldService(test_db) as service:
            signals = service.get_signals(asset.id, "s3_bollinger_squeeze")

        assert signals["strategy"] == "s3_bollinger_squeeze"
        assert signals["signals"] == []
        assert signals["model_state"]["position_size"] == 0.0

    def test_update_prices_stores_incremental_rows(self, test_db, gold_data, monkeypatch):
        asset, _ = gold_data
        frame = pd.DataFrame(
            [
                {
                    "date": date(2024, 1, 8),
                    "open": 491.0,
                    "high": 495.0,
                    "low": 488.0,
                    "close": 493.0,
                    "volume": 1200.0,
                    "amt": 59.0,
                }
            ]
        )
        monkeypatch.setattr(
            "backend.services.gold.update_daily",
            lambda dataset, end=None, source="auto": frame,
        )

        with GoldService(test_db) as service:
            result = service.update_prices()

        # The 518880 dataset has no asset in the fixture, so only AU9999.SHG is stored.
        assert result["added"] == 1
        assert len(result["errors"]) == 1

        stored = test_db.exec(
            select(Price).where(
                Price.asset_id == asset.id,
                Price.price_date == date(2024, 1, 8),
            )
        ).all()
        assert len(stored) == 1
        assert stored[0].open == Decimal("491.0")

    def test_asset_type_gold_is_allowed(self, test_db):
        cny = test_db._test_cny
        asset = Asset(symbol="518880.SH", name="Gold ETF", type="gold", currency_id=cny.id)
        test_db.add(asset)
        test_db.commit()

        assert asset.id is not None


class TestPriceRateServiceGoldExclusion:
    def test_backfill_skips_gold_assets(self, test_db, gold_data, monkeypatch):
        calls: list[str] = []

        def fake_fetch(symbol, asset_type, start_date, end_date, adjust="", retry=True):
            calls.append(symbol)
            return pd.DataFrame(), ""

        monkeypatch.setattr(
            "backend.services.price_rate.ths_source",
            type("FakeTHS", (), {"fetch_historical_prices": staticmethod(fake_fetch)})(),
        )

        with PriceRateService(test_db) as service:
            service.fetch_and_store_historical_prices(date(2024, 1, 1), date(2024, 1, 5))

        assert "AU9999.SHG" not in calls
        assert calls  # non-gold assets are still fetched
