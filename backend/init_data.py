"""
Initialize the database with sample data for the Portfolio Tracker
"""

from sqlmodel import Session, select
from datetime import date, timedelta
from decimal import Decimal
import pandas as pd
import os

from backend.db import (
    DATA_PATH,
    create_db_and_tables,
    drop_db_and_tables,
    get_engine,
)
from backend.db.models import (
    Asset,
    Currency,
    Price,
    Portfolio,
    TagCategory,
    Tag,
    AssetTag,
    Benchmark,
)
from backend.services import (
    PositionService,
    TagService,
    DataImportService,
    PriceRateService,
    GoldService,
)
from backend import logger

SEED_DIR = os.environ.get("NICEAMS_SEED_DIR", os.path.join(DATA_PATH, "sample"))


def init_currencies_and_cash_assets():
    """Initialize currencies, exchange rates, cash assets, and cash asset prices"""
    with Session(get_engine()) as session:
        # Initialize currencies
        currencies = [
            Currency(code="CNY", name="Chinese Yuan", symbol="¥", is_primary=True),
            Currency(code="USD", name="US Dollar", symbol="$", is_primary=False),
            Currency(
                code="HKD", name="Hong Kong Dollar", symbol="HK$", is_primary=False
            ),
            Currency(code="EUR", name="Euro", symbol="€", is_primary=False),
        ]
        session.add_all(currencies)
        session.commit()
        for currency in currencies:
            session.refresh(currency)
        logger.info("Currencies initialized successfully")

        # Initialize cash assets
        cash_assets = [
            Asset(
                symbol="CNY_CASH",
                name="CN CASH",
                type="cash",
                currency_id=currencies[0].id,
                isin="CASH_CNY",
            ),
            Asset(
                symbol="USD_CASH",
                name="US CASH",
                type="cash",
                currency_id=currencies[1].id,
                isin="CASH_USD",
            ),
            Asset(
                symbol="HKD_CASH",
                name="HK CASH",
                type="cash",
                currency_id=currencies[2].id,
                isin="CASH_HKD",
            ),
            Asset(
                symbol="EUR_CASH",
                name="EU CASH",
                type="cash",
                currency_id=currencies[3].id,
                isin="CASH_EU",
            ),
        ]
        session.add_all(cash_assets)
        session.commit()
        for cash_asset in cash_assets:
            session.refresh(cash_asset)
        logger.info("Cash assets initialized successfully")

        # Initialize cash asset prices
        prices = [
            Price(
                asset_id=cash_assets[0].id,
                price_date=date(2025, 3, 1),
                price=Decimal("1.0"),
                price_type="historical",
                source="sample",
            ),
            Price(
                asset_id=cash_assets[1].id,
                price_date=date(2025, 3, 1),
                price=Decimal("1.0"),
                price_type="historical",
                source="sample",
            ),
            Price(
                asset_id=cash_assets[2].id,
                price_date=date(2025, 3, 1),
                price=Decimal("1.0"),
                price_type="historical",
                source="sample",
            ),
            Price(
                asset_id=cash_assets[3].id,
                price_date=date(2025, 3, 1),
                price=Decimal("1.0"),
                price_type="historical",
                source="sample",
            ),
        ]
        session.add_all(prices)
        session.commit()
        logger.info("Cash asset prices initialized successfully")


def init_assets():
    """Initialize non-cash assets from CSV file"""
    csv_file_path = os.path.join(SEED_DIR, "assets.csv")

    if not os.path.exists(csv_file_path):
        raise FileNotFoundError(f"Assets CSV file not found: {csv_file_path}")

    # Detect encoding and read CSV
    with open(csv_file_path, "rb") as f:
        file_bytes = f.read()
    encoding = DataImportService.detect_encoding(file_bytes)
    df = pd.read_csv(csv_file_path, encoding=encoding)

    # Filter out cash assets since they're initialized in init_currencies_and_cash_assets()
    df = df[df["type"] != "cash"]

    with Session(get_engine()) as session:
        assets = []
        for _, row in df.iterrows():
            asset = Asset(
                symbol=row["symbol"],
                name=row["name"],
                type=row["type"],
                currency_id=int(row["currency_id"]),
                isin=row["isin"] if pd.notna(row["isin"]) else None,
            )
            assets.append(asset)

        session.add_all(assets)
        session.commit()
        logger.info(
            f"Assets initialized successfully ({len(assets)} non-cash assets from CSV)"
        )


def init_portfolio():
    """Initialize sample portfolio"""
    with Session(get_engine()) as session:
        portfolio = Portfolio(
            name="My Portfolio",
            description="Personal investment portfolio",
            base_currency_id=1,
        )

        session.add(portfolio)
        session.commit()
        logger.info("Portfolio initialized successfully")


def get_non_cash_assets() -> list[Asset]:
    """Get all non-cash assets from the database.

    Gold assets are excluded because their bars are loaded from the seed CSVs
    and updated by the gold data loader rather than by the THS price backfill.
    """
    with Session(get_engine()) as session:
        statement = select(Asset).where(Asset.type.notin_(["cash", "gold"]))
        assets = session.exec(statement).all()
        return assets


def init_fetch_and_store_exchange_rates(
    start_date: date = date(2025, 1, 1),
    end_date: date = date.today(),
):
    """Fetch and store historical exchange rates for USD, HKD, EUR"""
    logger.info("Fetching exchange rates from AKShare...")
    logger.info(
        f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
    )

    with Session(get_engine()) as session:
        price_rate_service = PriceRateService(session)
        result = price_rate_service.fetch_and_store_exchange_rates(
            start_date=start_date,
            end_date=end_date,
            currency_codes=["USD", "HKD", "EUR"],
        )

    logger.info(f"Exchange rate fetching completed! Added {result['rates_added']} rates")
    if result["errors"]:
        for error in result["errors"]:
            logger.error(error)


def init_fetch_and_store_historical_prices(
    start_date: date = date(2025, 1, 1),
    end_date: date = date.today(),
):
    """Fetch and store historical prices for all non-cash assets"""
    logger.info("Fetching historical prices...")
    logger.info(
        f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
    )

    # Get non-cash assets
    assets = get_non_cash_assets()

    if not assets:
        logger.warning("No non-cash assets found in the database")
        return

    with Session(get_engine()) as session:
        price_rate_service = PriceRateService(session)
        result = price_rate_service.fetch_and_store_historical_prices(
            start_date=start_date,
            end_date=end_date,
            assets=assets,
        )

    logger.info(f"Historical price fetching completed! Added {result['prices_added']} prices")
    if result["errors"]:
        for error in result["errors"]:
            logger.error(error)


def init_transactions():
    """Initialize transactions from Xueqiu CSV file"""
    with Session(get_engine()) as session:
        # Get the portfolio that was created in init_portfolio()
        portfolio = session.exec(select(Portfolio)).first()
        if not portfolio or portfolio.id is None:
            raise ValueError("No portfolio found. Please run init_portfolio() first.")

        # Read transactions from Xueqiu CSV file
        csv_file_path = os.path.join(SEED_DIR, "transactions.csv")

        if not os.path.exists(csv_file_path):
            raise FileNotFoundError(f"CSV file not found: {csv_file_path}")

        # Detect encoding and read CSV
        with open(csv_file_path, "rb") as f:
            file_bytes = f.read()
        encoding = DataImportService.detect_encoding(file_bytes)
        df = pd.read_csv(csv_file_path, encoding=encoding)

        import_service = DataImportService(session)
        transactions = import_service.import_xueqiu_transactions_from_dataframe(
            df, portfolio.id
        )

        session.add_all(transactions)
        session.commit()
        logger.info(
            f"Sample transactions initialized successfully from CSV ({len(transactions)} transactions)"
        )

        # Calculate positions for the entire period using PositionService
        logger.info("Calculating positions from transactions...")
        position_service = PositionService(session)

        # Get the date range from transactions
        start_date = min(t.trade_date for t in transactions)
        end_date = max(t.trade_date for t in transactions)

        # Calculate positions for every day during the period
        current_date = start_date
        while current_date <= end_date:
            positions = position_service.compute_period_end_positions(
                portfolio_id=portfolio.id,
                start_date=start_date,
                end_date=current_date,
                save_to_db=True,
            )
            start_date = current_date
            current_date += timedelta(days=1)

        logger.info(f"Successfully calculated {len(positions)} positions")

        # Log summary of positions
        for asset_id, position in positions.items():
            asset = session.get(Asset, asset_id)
            if asset and position.quantity > 0:
                logger.info(
                    f"  {asset.symbol}: {position.quantity} shares @ {position.current_price} = {position.market_value}"
                )


def init_tag_categories():
    """Initialize tag categories from CSV file"""
    csv_file_path = os.path.join(DATA_PATH, "tag_categories.csv")

    if not os.path.exists(csv_file_path):
        raise FileNotFoundError(f"Tag categories CSV file not found: {csv_file_path}")

    df = pd.read_csv(csv_file_path)

    with Session(get_engine()) as session:
        categories = []
        for _, row in df.iterrows():
            category = TagCategory(
                name=row["name"],
                description=row["description"] if pd.notna(row["description"]) else None,
            )
            categories.append(category)

        session.add_all(categories)
        session.commit()
        for category in categories:
            session.refresh(category)
        logger.info(f"Tag categories initialized successfully ({len(categories)} categories from CSV)")


def init_tags():
    """Initialize tags from CSV file"""
    csv_file_path = os.path.join(DATA_PATH, "tags.csv")

    if not os.path.exists(csv_file_path):
        raise FileNotFoundError(f"Tags CSV file not found: {csv_file_path}")

    df = pd.read_csv(csv_file_path)

    with Session(get_engine()) as session:
        # Get all categories for lookup
        categories = session.exec(select(TagCategory)).all()
        category_map = {c.name: c.id for c in categories}

        tags = []
        for _, row in df.iterrows():
            category_name = row["category_name"]
            category_id = category_map.get(category_name)

            if category_id is None:
                logger.warning(f"Category '{category_name}' not found for tag '{row['name']}'")
                continue

            tag = Tag(
                name=row["name"],
                category_id=category_id,
            )
            tags.append(tag)

        session.add_all(tags)
        session.commit()
        logger.info(f"Tags initialized successfully ({len(tags)} tags from CSV)")


def init_asset_tags():
    """Initialize asset-tag relationships from CSV file using TagService"""
    csv_file_path = os.path.join(SEED_DIR, "asset_tags.csv")

    if not os.path.exists(csv_file_path):
        raise FileNotFoundError(f"Asset tags CSV file not found: {csv_file_path}")

    df = pd.read_csv(csv_file_path)

    with TagService() as tag_service:
        count = 0
        for _, row in df.iterrows():
            asset_symbol = row["asset_symbol"]
            tag_name = row["tag_name"]
            category_name = row["category_name"]
            weight = Decimal(str(row["weight"]))

            try:
                tag_service.assign_tag_to_asset(
                    asset_symbol=asset_symbol,
                    tag_name=tag_name,
                    weight=weight,
                    category_name=category_name,
                    validate=False
                )
                count += 1
            except ValueError as e:
                logger.warning(f"Failed to assign tag '{tag_name}' to asset '{asset_symbol}': {e}")

    logger.info(f"Asset tags initialized successfully ({count} assignments from CSV)")


def init_benchmarks():
    """Initialize benchmark indices"""
    with Session(get_engine()) as session:
        benchmarks = [
            Benchmark(
                symbol="000300.SH",
                name="CSI 300",
                description="沪深300指数",
            ),
            Benchmark(
                symbol="HSI.HK",
                name="Hang Seng Index",
                description="恒生指数",
            ),
            Benchmark(
                symbol="HSCE.HK",
                name="Hang Seng China Enterprises Index",
                description="恒生中国企业指数",
            ),
            Benchmark(
                symbol="H00300.CSI",
                name="CSI 300 Total",
                description="沪深300全收益",
            ),
        ]
        session.add_all(benchmarks)
        session.commit()
        for benchmark in benchmarks:
            session.refresh(benchmark)
        logger.info(f"Benchmarks initialized successfully ({len(benchmarks)} benchmarks)")


def init_fetch_and_store_benchmark_prices(
    start_date: date = date(2025, 1, 1),
    end_date: date = date.today(),
):
    """Fetch and store historical prices for all benchmarks"""
    logger.info("Fetching benchmark prices from THS...")
    logger.info(
        f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
    )

    with Session(get_engine()) as session:
        price_rate_service = PriceRateService(session)
        result = price_rate_service.fetch_and_store_benchmark_prices(
            start_date=start_date,
            end_date=end_date,
        )

    logger.info(f"Benchmark price fetching completed! Added {result['prices_added']} prices")
    if result["errors"]:
        for error in result["errors"]:
            logger.error(error)


def init_gold_prices():
    """Import the seed daily-bar CSVs for the gold assets."""
    logger.info("Importing gold daily bars from seed CSVs...")
    with Session(get_engine()) as session:
        service = GoldService(session)
        result = service.import_seed_csvs()

    logger.info(f"Gold price import completed! Added {result['added']} bars")
    if result["errors"]:
        for error in result["errors"]:
            logger.error(error)


def main():
    logger.info("Clearing existing data...")
    drop_db_and_tables()

    logger.info("Creating database and tables...")
    create_db_and_tables()

    logger.info("Initializing sample data...")
    init_currencies_and_cash_assets()
    init_fetch_and_store_exchange_rates(start_date=date(2025, 1, 1), end_date=date.today())
    init_assets()
    init_tag_categories()
    init_tags()
    init_asset_tags()
    init_portfolio()
    init_fetch_and_store_historical_prices(start_date=date(2025, 1, 1), end_date=date.today())
    init_gold_prices()
    init_transactions()
    init_benchmarks()
    init_fetch_and_store_benchmark_prices(start_date=date(2025, 1, 1), end_date=date.today())

    logger.info("Database initialization completed successfully!")
    logger.info("You can now start the FastAPI server with: uvicorn backend.main:app --reload")

if __name__ == "__main__":
    main()
