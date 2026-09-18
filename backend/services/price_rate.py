"""Price and Exchange Rate Service.

Provides reusable functions for fetching and storing historical prices and exchange rates.
"""

from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
from sqlalchemy import func
from sqlmodel import Session, select

from backend.data_source import akshare_source, ths_source
from backend.db.models import Asset, Currency, ExchangeRate, Price, Benchmark, BenchmarkPrice
from backend.services.base import BaseService
from backend import logger


class PriceRateService(BaseService):
    """Service for fetching and storing prices and exchange rates."""

    # -----------------------------------------------------------------------
    # Generic backfill helper — shared by all three fetch_and_store methods
    # -----------------------------------------------------------------------

    def _fetch_and_store(
        self,
        items: list,
        fetch_fn,
        build_row,
        existing_dates_fn,
        item_label_fn,
        count_key: str,
        processed_key: str,
        fetch_label: str = "data",
        skip_fn=None,
    ) -> dict:
        """Generic fetch-and-store loop shared by prices / rates / benchmarks.

        Args:
            items: List of entities to iterate (e.g. Asset, Currency, Benchmark).
            fetch_fn: callable(item) -> (pd.DataFrame, source:str).
            build_row: callable(item, row: dict, source: str) -> ORM instance.
            existing_dates_fn: callable(item) -> set[date] already stored.
            item_label_fn: callable(item) -> str for logging / processed list.
            count_key: result-dict key for the added-count (e.g. "prices_added").
            processed_key: result-dict key for the processed-labels list.
            fetch_label: human label for log messages (e.g. "prices", "exchange rates").
            skip_fn: optional callable(item) -> bool; when True the item is
                logged as skipped and appended to processed without fetching.
        """
        result = {
            count_key: 0,
            processed_key: [],
            "errors": [],
        }

        for item in items:
            label = item_label_fn(item)

            if skip_fn and skip_fn(item):
                logger.info(f"Skipping {label}")
                result[processed_key].append(label)
                continue

            try:
                logger.info(f"Fetching {fetch_label} for {label}")

                df, source = fetch_fn(item)

                if df.empty:
                    logger.warning(f"No {fetch_label} retrieved for {label}")
                    continue

                existing_dates = existing_dates_fn(item)
                new_data = df[~df["date"].isin(existing_dates)]

                if not new_data.empty:
                    rows = [
                        build_row(item, row, source)
                        for row in new_data.to_dict("records")
                    ]
                    self.session.add_all(rows)
                    self.session.commit()
                    result[count_key] += len(rows)
                    result[processed_key].append(label)
                    logger.info(f"Added {len(rows)} new {fetch_label} for {label}")
                else:
                    result[processed_key].append(label)
                    logger.info(f"No new {fetch_label} to add for {label}")

            except Exception as e:
                error_msg = f"Error fetching {fetch_label} for {label}: {str(e)}"
                logger.error(error_msg)
                result["errors"].append(error_msg)

        return result

    # -----------------------------------------------------------------------
    # Public methods (thin wrappers around _fetch_and_store)
    # -----------------------------------------------------------------------

    def fetch_and_store_exchange_rates(
        self,
        start_date: date,
        end_date: date,
        currency_codes: list[str] = ["USD", "HKD", "EUR"],
    ) -> dict:
        """Fetch and store historical exchange rates for specified currencies.

        The Primary Currency must be CNY. The exchange rates are USD/CNY or HKD/CNY or EUR/CNY.

        Args:
            start_date: Start date for fetching rates
            end_date: End date for fetching rates
            currency_codes: List of currency codes to fetch (must be either ["USD", "HKD", or "EUR"])

        Returns:
            dict: Summary of the operation with keys:
                - rates_added: Total number of exchange rates added
                - currencies_processed: List of currency codes processed
                - errors: List of error messages
        """
        valid_currency_codes = {"USD", "HKD", "EUR"}

        invalid_codes = set(currency_codes) - valid_currency_codes
        if invalid_codes:
            raise ValueError(
                f"Invalid currency codes: {invalid_codes}. Must be a subset of {valid_currency_codes}"
            )

        primary_currency = self.session.exec(
            select(Currency).where(Currency.is_primary == True)
        ).first()
        if not primary_currency:
            return {
                "rates_added": 0,
                "currencies_processed": [],
                "errors": ["Primary currency not found in database"],
            }

        # Resolve currency codes to Currency objects, skip missing ones
        currencies: list[Currency] = []
        for code in currency_codes:
            currency = self.session.exec(
                select(Currency).where(Currency.code == code)
            ).first()
            if currency:
                currencies.append(currency)
            else:
                logger.warning(f"Currency {code} not found in database")

        return self._fetch_and_store(
            items=currencies,
            fetch_fn=lambda c: akshare_source.fetch_exchange_rates(
                currency_code=c.code,
                start_date=start_date,
                end_date=end_date,
            ),
            existing_dates_fn=lambda c: set(
                self.session.exec(
                    select(ExchangeRate.rate_date).where(
                        ExchangeRate.from_currency_id == c.id,
                        ExchangeRate.to_currency_id == primary_currency.id,
                    )
                ).all()
            ),
            build_row=lambda c, row, source: ExchangeRate(
                from_currency_id=c.id,
                to_currency_id=primary_currency.id,
                rate_date=row["date"],
                rate=Decimal(str(row["buy_rate"])),
                source=source,
            ),
            item_label_fn=lambda c: c.code,
            count_key="rates_added",
            processed_key="currencies_processed",
            fetch_label="exchange rates",
        )

    def fetch_and_store_historical_prices(
        self,
        start_date: date,
        end_date: date,
        assets: list[Asset] | None = None,
    ) -> dict:
        """Fetch and store historical prices for assets.

        Args:
            start_date: Start date for fetching prices
            end_date: End date for fetching prices
            assets: List of assets to fetch prices for (default: all non-cash assets)

        Returns:
            dict: Summary of the operation with keys:
                - prices_added: Total number of prices added
                - assets_processed: List of asset symbols processed
                - errors: List of error messages
        """
        if assets is None:
            assets = self.session.exec(
                select(Asset).where(Asset.type.notin_(["cash", "gold"]))
            ).all()
        else:
            assets = [asset for asset in assets if asset.type not in ("cash", "gold")]

        if not assets:
            logger.warning("No non-cash assets found in the database")
            return {"prices_added": 0, "assets_processed": [], "errors": []}

        logger.info(f"Found {len(assets)} non-cash assets to update")

        return self._fetch_and_store(
            items=assets,
            fetch_fn=lambda a: ths_source.fetch_historical_prices(
                symbol=a.symbol,
                asset_type=a.type,
                start_date=start_date,
                end_date=end_date,
                adjust="",
            ),
            existing_dates_fn=lambda a: set(
                self.session.exec(
                    select(Price.price_date).where(Price.asset_id == a.id)
                ).all()
            ),
            build_row=lambda a, row, source: Price(
                asset_id=a.id,
                price_date=row["date"],
                price=Decimal(str(row["close"])),
                price_type="historical",
                source=source,
            ),
            item_label_fn=lambda a: a.symbol,
            count_key="prices_added",
            processed_key="assets_processed",
            fetch_label="prices",
        )

    def fetch_and_store_benchmark_prices(
        self,
        start_date: date,
        end_date: date,
        benchmarks: list[Benchmark] | None = None,
    ) -> dict:
        """Fetch and store historical prices for benchmarks.

        Args:
            start_date: Start date for fetching prices
            end_date: End date for fetching prices
            benchmarks: List of benchmarks to fetch prices for (default: all benchmarks)

        Returns:
            dict: Summary of the operation with keys:
                - prices_added: Total number of prices added
                - benchmarks_processed: List of benchmark symbols processed
                - errors: List of error messages
        """
        if benchmarks is None:
            benchmarks = self.session.exec(select(Benchmark)).all()

        if not benchmarks:
            logger.warning("No benchmarks found in the database")
            return {"prices_added": 0, "benchmarks_processed": [], "errors": []}

        logger.info(f"Found {len(benchmarks)} benchmarks to update")

        return self._fetch_and_store(
            items=benchmarks,
            fetch_fn=lambda b: ths_source.fetch_historical_prices(
                symbol=b.symbol,
                asset_type="index",
                start_date=start_date,
                end_date=end_date,
                adjust="",
            ),
            existing_dates_fn=lambda b: set(
                self.session.exec(
                    select(BenchmarkPrice.price_date).where(
                        BenchmarkPrice.benchmark_id == b.id
                    )
                ).all()
            ),
            build_row=lambda b, row, source: BenchmarkPrice(
                benchmark_id=b.id,
                price_date=row["date"],
                close=Decimal(str(row["close"])),
                source=source,
            ),
            item_label_fn=lambda b: b.symbol,
            count_key="prices_added",
            processed_key="benchmarks_processed",
            fetch_label="benchmark prices",
            skip_fn=lambda b: b.is_composite,
        )

    # -----------------------------------------------------------------------
    # Backfill orchestration
    # -----------------------------------------------------------------------

    def get_max_date(self, model, date_column: str) -> date | None:
        """Get the maximum date stored in a model's date column."""
        return self.session.exec(
            select(func.max(getattr(model, date_column)))
        ).first()

    def backfill_from_latest(self, end_date: date) -> dict | None:
        """Backfill prices/rates/benchmarks from the latest stored date to end_date.

        Computes the minimum of the max dates across Price, ExchangeRate, and
        BenchmarkPrice, then backfills from (min + 1 day) to end_date via
        update_all. Returns None when there is no existing data or everything
        is already up to date; otherwise returns the update_all result dict.
        """
        max_price_date = self.get_max_date(Price, "price_date")
        max_rate_date = self.get_max_date(ExchangeRate, "rate_date")
        max_bm_date = self.get_max_date(BenchmarkPrice, "price_date")

        latest_dates = [
            d for d in (max_price_date, max_rate_date, max_bm_date) if d is not None
        ]
        if not latest_dates:
            logger.info("No price/rate data found, skipping backfill")
            return None

        start_date = min(latest_dates)
        if start_date >= end_date:
            logger.info("Prices and exchange rates are already up to date")
            return None

        start_date += timedelta(days=1)
        logger.info(f"Backfilling prices/rates/benchmarks from {start_date} to {end_date}")

        result = self.update_all(start_date=start_date, end_date=end_date)

        logger.info(
            f"Backfill complete: prices={result['prices_added']}, "
            f"rates={result['rates_added']}, "
            f"benchmarks={result['benchmark_prices_added']}"
        )
        if result.get("errors"):
            for err in result["errors"]:
                logger.warning(f"Backfill error: {err}")

        return result

    def update_all(
        self,
        start_date: date,
        end_date: date,
        currency_codes: list[str] = ["USD", "HKD", "EUR"],
    ) -> dict:
        """Update exchange rates, asset prices, and benchmark prices in one call.

        This is a convenience wrapper around the three fetch_and_store methods,
        used by both the scheduled price update endpoint and the Xueqiu align flow.

        Args:
            start_date: Start date for fetching data
            end_date: End date for fetching data
            currency_codes: List of currency codes to fetch exchange rates for

        Returns:
            dict with keys:
                - prices_added: Total asset prices added
                - rates_added: Total exchange rates added
                - benchmark_prices_added: Total benchmark prices added
                - errors: Combined list of error messages
        """
        logger.info(f"Updating all prices and rates from {start_date} to {end_date}")

        rate_result = self.fetch_and_store_exchange_rates(
            start_date=start_date,
            end_date=end_date,
            currency_codes=currency_codes,
        )

        price_result = self.fetch_and_store_historical_prices(
            start_date=start_date,
            end_date=end_date,
        )

        benchmark_result = self.fetch_and_store_benchmark_prices(
            start_date=start_date,
            end_date=end_date,
        )

        errors = (
            rate_result.get("errors", [])
            + price_result.get("errors", [])
            + benchmark_result.get("errors", [])
        )

        return {
            "prices_added": price_result["prices_added"],
            "rates_added": rate_result["rates_added"],
            "benchmark_prices_added": benchmark_result["prices_added"],
            "errors": errors,
        }
