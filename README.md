# HolmFolio

HolmFolio is an evidence-based investing personal asset management system built with a Python FastAPI backend and Vue.js 3 frontend. It provides multi-currency portfolio tracking, transaction management, performance analytics (TWR, Sharpe ratio, drawdown, beta, tag correlation), and quantitative trading.

## Table of Contents

- [Features](#features)
  - [Core Features](#core-features)
  - [Technical Features](#technical-features)
- [Project Structure](#project-structure)
- [Installation & Setup](#installation--setup)
  - [Prerequisites](#prerequisites)
  - [Backend Setup](#backend-setup)
  - [Frontend Setup](#frontend-setup)
  - [Full Stack Startup](#full-stack-startup)
- [Usage](#usage)
- [API Documentation](#api-documentation)
- [Database Schema](#database-schema)
- [Data Import Formats](#data-import-formats)
- [Performance Calculations](#performance-calculations)
- [Customization](#customization)
  - [Adding New Asset Types](#adding-new-asset-types)
  - [Adding New Currencies](#adding-new-currencies)
  - [Asset Tagging System](#asset-tagging-system)
- [Testing](#testing)
- [Architecture Notes](#architecture-notes)
- [License](#license)

## Features

### Core Features

- **Multi-currency Support**: Track assets in CNY, USD, HKD, EUR with automatic currency conversion (direct and inverse rate lookups supported)
- **Portfolio Management**: Comprehensive portfolio tracking with positions, transactions, and performance metrics
- **Transaction Processing**: Support for buy/sell/dividends/splits/cash flows with CSV/ZIP import (including Xueqiu/雪球 format)
- **Real-time Pricing**: Integration with AKShare and THS (同花顺) data sources with automatic backfill on startup
- **Advanced Analytics**:
  - Time-Weighted Return (TWR) using fund NAV method
  - Risk metrics: volatility, Sharpe ratio, max drawdown, Sortino ratio, Calmar ratio
  - Beta and Alpha calculations against benchmarks
  - Tag correlation (Pearson) and tag beta analysis
- **Asset Allocation**: Visual breakdown by asset type and custom tag categories
- **Benchmark Comparison**: Compare portfolio performance against market indices, including composite benchmarks
- **Financial Analysis**: Dividend, net income, and equity data tracking via THS, including HK red chip / A+H dual-listing tax adjustment
- **Gold Trading Module**: Daily CTA strategies over gold spot AU9999.SHG / gold ETF 518880.SH (s1a dual-MA + ATR trailing stop, s3 Bollinger squeeze), with strategy signals from real daily bars, real fills recorded as standard transactions, and normalized NAV comparison of user account vs strategy model vs the selected asset's buy-and-hold. Within a selected date range the strategy account restarts at the configured gold initial capital, so every displayed fill/signal unit is an actual held quantity (window-filtered trade metrics).
- **Multi-asset Support**: Stocks, bonds, funds, ETFs, cash, gold. See [Adding New Asset Types](#adding-new-asset-types) for more details.

### Technical Features

- **Frontend**: Vue.js 3 + Element Plus UI + Chart.js for visualizations
- **State Management**: Pinia (6 separate stores) for application state
- **Routing**: Vue Router with web history mode
- **Build Tool**: Vite for development and production builds
- **Backend**: FastAPI + SQLModel + SQLite for robust data management
- **Architecture**: Clean separation of frontend/backend with RESTful APIs
- **Service Layer Pattern**: Business logic in service classes inheriting from `BaseService`, supporting context manager usage
- **Startup Backfill**: On app startup, automatically backfills prices/exchange-rates/benchmark-prices and ensures positions are up to date

## Project Structure

```
holmfolio/
├── .trae/rules/project_rules.md   # Project coding rules
├── .vscode/
├── backend/
│   ├── api/
│   │   ├── models/                # Pydantic request/response models
│   │   └── v1/                    # API v1 endpoints
│   │       ├── assets.py
│   │       ├── benchmarks.py
│   │       ├── currencies.py
│   │       ├── gold.py
│   │       ├── import_export.py
│   │       ├── portfolios.py
│   │       ├── router.py
│   │       ├── settings.py
│   │       ├── tags.py
│   │       └── transactions.py
│   ├── db/
│   │   ├── models/                # SQLModel database models
│   │   │   ├── asset.py
│   │   │   ├── benchmark.py
│   │   │   ├── currency.py
│   │   │   ├── portfolio.py
│   │   │   ├── price.py
│   │   │   ├── settings.py
│   │   │   ├── stock_info.py      # Cached THS financial data
│   │   │   ├── tag.py
│   │   │   └── transaction.py
│   │   ├── base.py                # Engine singleton, session mgmt
│   │   └── utils.py
│   ├── services/                  # Business logic (BaseService pattern)
│   │   ├── base.py
│   │   ├── calculation.py         # TWR, beta, statistics
│   │   ├── currency.py
│   │   ├── data_import.py         # CSV/ZIP import (Xueqiu support)
│   │   ├── gold.py                # Gold bars, signals, NAV comparison
│   │   ├── portfolio.py           # Tag returns, correlation, allocation
│   │   ├── position.py            # CashFlowTracker, upsert positions
│   │   ├── price.py
│   │   ├── price_rate.py          # Backfill orchestration
│   │   └── tag.py
│   ├── strat/                     # Strategy package (holmes-lab layout)
│   │   ├── common/                # base, constants, engine, data_loader
│   │   └── gold/                  # s1a MaCrossTrailingStop, s3 BollingerSqueeze
│   ├── data_source.py             # AKShare + THS + iFinD HTTP data sources
│   ├── init_data.py               # Database initialization
│   ├── main.py                    # FastAPI app + lifespan backfill
│   └── requirements.txt
├── data/                          # Seed and reference data
│   ├── sample/                    # Public demo seeds loaded by init_data.py
│   │   ├── assets.csv
│   │   ├── asset_tags.csv
│   │   └── transactions.csv
│   ├── private/                   # Real seeds (gitignored, optional)
│   ├── sample_portfolio.csv
│   ├── sample_transactions.csv
│   ├── tags.csv
│   ├── tag_categories.csv
│   ├── AU9999_Daily.csv           # Gold spot daily bars (seed + incremental)
│   ├── 518880.SH.csv              # Gold ETF daily bars (seed + incremental)
│   └── hk_stock_cache.json        # HK stock red chip / A+H cache
├── doc/
│   └── return-calculation-algorithms.md  # Detailed TWR/beta algorithm docs
├── frontend/
│   ├── src/
│   │   ├── components/            # Reusable Vue components
│   │   │   ├── AllocationChart.vue
│   │   │   ├── GoldPerformanceChart.vue
│   │   │   ├── GoldSignalChart.vue
│   │   │   ├── PerformanceChart.vue
│   │   │   ├── SharedDataTable.vue
│   │   │   ├── AssetBetaChart.vue
│   │   │   ├── TagBetaChart.vue
│   │   │   └── TagCorrelationChart.vue
│   │   ├── composables/           # Vue composition functions
│   │   │   ├── useLoading.ts
│   │   │   └── useTimeRange.ts
│   │   ├── router/index.ts
│   │   ├── stores/                # Pinia state management
│   │   │   ├── analytics.ts
│   │   │   ├── asset.ts
│   │   │   ├── gold.ts
│   │   │   ├── portfolio.ts
│   │   │   ├── reference.ts
│   │   │   ├── transaction.ts
│   │   │   ├── ui.ts
│   │   │   └── index.ts
│   │   ├── types/models.ts
│   │   ├── utils/
│   │   │   ├── errorHandler.ts
│   │   │   └── formatters.ts
│   │   ├── views/
│   │   │   ├── Dashboard.vue
│   │   │   ├── Portfolio.vue
│   │   │   ├── PositionDetail.vue
│   │   │   ├── Transactions.vue
│   │   │   ├── Assets.vue
│   │   │   ├── Analytics.vue
│   │   │   ├── TagManagement.vue
│   │   │   ├── Financial.vue
│   │   │   ├── Gold.vue
│   │   │   └── Settings.vue
│   │   ├── App.vue
│   │   └── main.ts
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── tests/                         # Test suite
│   ├── conftest.py
│   ├── test_twr.py
│   ├── test_price_service.py
│   ├── test_tag_service.py
│   ├── test_tag_correlation.py
│   ├── test_beta.py
│   ├── test_benchmark_prices.py
│   ├── test_benchmark_statistics.py
│   ├── test_dividend_after_tax.py
│   ├── test_gold_service.py
│   ├── test_strat_data_loader.py
│   ├── test_strat_strategies.py
│   ├── test_stock_financials.py
│   ├── test_position_unique_constraint.py
│   ├── test_xueqiu_portfolio.py
│   └── transactions_data.csv
├── start.bat                      # Windows startup script
├── start.sh                       # Unix startup script
├── pytest.ini
└── README.md
```

## Installation & Setup

### Prerequisites

- Python 3.12+
- Node.js 22+
- npm
- (Optional) Conda environment named `holmfolio`
- (Optional) THS (同花顺) terminal login for historical price/financial data
- (Optional) iFinD account credentials in the repo-root `.env` for gold daily-bar updates: `IFIND_USER`, `IFIND_PASSWORD` (SDK), `IFIND_DATASOURCE_KEY` (HTTP fallback)

### Backend Setup

1. **Install Python dependencies**:

```bash
cd backend
pip install -r requirements.txt
```

2. **Initialize database with sample data**:

```bash
cd ..
python -m backend.init_data
```

By default `init_data` loads the public demo seeds from `data/sample/` (`assets.csv`, `asset_tags.csv`, `transactions.csv`). To initialize with your own seeds instead, point `HOLMFOLIO_SEED_DIR` at a directory containing the same three file names, for example:

```bash
HOLMFOLIO_SEED_DIR=data/private python -m backend.init_data
```

`data/private/` is gitignored and is a good place for real seeds.

3. **Start the FastAPI server**:

```bash
uvicorn backend.main:app --reload
```

The backend API will be available at `http://localhost:8000`.

On startup, the app will:
1. Create database tables
2. Backfill prices, exchange rates, and benchmark prices from the latest stored date to yesterday
3. Incrementally update gold daily bars (AU9999.SHG / 518880.SH) from the iFinD SDK, falling back to the iFinD HTTP API; failures only log and never block startup
4. Ensure positions are calculated up to today for all portfolios

### Frontend Setup

1. **Install Node.js dependencies**:

```bash
cd frontend
npm install
```

2. **Start the development server**:

```bash
npm run dev
```

The frontend will be available at `http://localhost:3000`.

### Full Stack Startup

Use the provided startup scripts to launch both servers:

- Windows: `start.bat`
- Unix/Linux/Mac: `./start.sh`

## Usage

### Dashboard (`/`)

- Portfolio overview: total value, unrealized P&L, asset count, and performance metrics
- Interactive performance chart with 1M/3M/6M/1Y/ALL time ranges (dual y-axis: value + NAV, with benchmark overlay)
- Asset allocation donut chart
- Top positions with current values and P&L
- Recent transactions

### Portfolio (`/portfolio`)

- Current positions with real-time market values (in original and primary currency)
- Unrealized P&L calculations per position
- Position recalculation controls
- Drill-down to position detail (`/positions/:assetId`)

### Transactions (`/transactions`)

- Manual entry of buy/sell/dividend/cash transactions
- CSV/ZIP import (standard and Xueqiu format with auto-encoding detection)
- Filterable and sortable transaction history
- Bulk delete and export

### Assets (`/assets`)

- Asset registry for stocks, bonds, funds, ETFs, cash, gold
- Multi-currency asset metadata
- Tag assignment per asset

### Tag Management (`/tags`)

- Tag category and tag CRUD
- Categories: 行业 (Industry), 地域 (Region), 资产类型 (Asset Type), 风格 (Style)

### Financial (`/financial`)

- Dividend, net income, and equity data (sourced from THS)
- Financial position tracking

### Gold Trading (`/gold`)

- Two gold instruments: AU9999.SHG (SGE spot) and 518880.SH (Huaan Gold ETF), both regular assets that count in portfolio statistics
- Two daily long-only CTA strategies: `s1a_ma_cross_trailing` (SMA30/90 + ATR(14) 2.5x trailing stop, default) and `s3_bollinger_squeeze` (BB20/2.0 + 200-day 10% squeeze + ATR stop)
- Signals are confirmed on close and expected to fill at the next open; the model position, entry price and stop price are always shown
- Signal list for the selected date range (full history and pending signals included), plus a price chart with buy/sell markers, stop overlay and a strategy position (% of equity) bar chart underneath
- Record real fills directly on the page (stored as standard transactions, so they flow into positions and all other modules)
- Normalized NAV comparison (start = 100) of the user's gold account, the strategy model and the selected asset's buy-and-hold (AU9999.SHG spot when AU9999.SHG is selected), with return/drawdown/Sharpe/win-rate metrics computed for the selected date range. Inside a date range the model account starts fresh at the configured initial capital (Settings → Gold Initial Capital), and signal units come from the replayed fills, so they never exceed the available cash; positions are reported as of the window end date.

### Analytics (`/analytics`)

- Performance metrics: TWR, annualized returns, volatility, Sharpe ratio, max drawdown
- Beta and Alpha against benchmarks
- Tag correlation heatmap (Pearson)
- Tag beta bar chart
- Asset beta analysis
- Monthly returns breakdown

### Settings (`/settings`)

- Currency management and exchange rate updates
- Portfolio configuration: tax rates, benchmark indices, risk-free rates

## API Documentation

The FastAPI backend provides comprehensive REST APIs. Visit `http://localhost:8000/docs` for interactive Swagger UI or `http://localhost:8000/redoc` for ReDoc.

### Core Endpoints

| Endpoint                                       | Description                                            |
| ---------------------------------------------- | ------------------------------------------------------ |
| `GET /health`                                  | Health check                                           |
| `/api/v1/currencies`                           | Currency management and exchange rates                 |
| `/api/v1/assets`                               | Asset registry, metadata, and price data               |
| `/api/v1/transactions`                         | Transaction CRUD operations                            |
| `/api/v1/portfolios`                           | Portfolio management                                   |
| `/api/v1/portfolios/{id}/positions`            | Current/as-of positions                                |
| `/api/v1/portfolios/{id}/financial-positions`  | Financial data (dividends, net income, equity)         |
| `/api/v1/portfolios/{id}/performance-history`  | Historical performance time series                     |
| `/api/v1/portfolios/{id}/performance-metrics`  | TWR, Sharpe, drawdown, volatility                      |
| `/api/v1/portfolios/{id}/recent-returns`       | Recent return breakdown                                |
| `/api/v1/portfolios/{id}/allocation`           | Asset allocation by tag category                        |
| `/api/v1/portfolios/{id}/tag-correlation`      | Tag correlation matrix (Pearson)                       |
| `/api/v1/portfolios/{id}/asset-beta`           | Asset beta vs benchmark                                |
| `/api/v1/portfolios/{id}/tag-beta`             | Tag beta vs benchmark                                  |
| `/api/v1/portfolios/{id}/recalculate-positions`| Trigger position recalculation                         |
| `/api/v1/tags`                                 | Tag management                                          |
| `/api/v1/tag-categories`                       | Tag category management                                 |
| `/api/v1/benchmarks`                           | Benchmark indices (including composite)                |
| `/api/v1/import/prices`                        | CSV price data import                                  |
| `/api/v1/import/xueqiu-transactions`          | Xueqiu CSV/ZIP transaction import                       |
| `/api/v1/import/xueqiu-align`                 | Xueqiu align flow (import + price/rate update)         |
| `/api/v1/import/update-prices-and-rates`       | Manual price/rate backfill trigger                     |
| `/api/v1/gold/assets`                          | Gold asset list (AU9999.SHG, 518880.SH)                |
| `/api/v1/gold/signals`                         | Strategy signals and current model state               |
| `/api/v1/gold/overview`                        | Signals + model state + NAV comparison + user position |
| `/api/v1/gold/update-prices`                   | Incremental gold daily-bar update (iFinD)              |
| `/api/v1/settings`                             | Application settings                                    |

## Database Schema

SQLite database at `backend/portfolio.db`.

### Core Tables

| Table                   | Description                                                              |
| ----------------------- | ------------------------------------------------------------------------ |
| **Currency**            | Multi-currency support with exchange rates (partial unique on primary)   |
| **ExchangeRate**        | Historical exchange rates between currencies                              |
| **Asset**               | Security master (stock, bond, etf, fund, cash, gold); cash uses `{CCY}_CASH`  |
| **TagCategory**         | Tag classification categories (行业, 地域, 资产类型, 风格)                    |
| **Tag**                 | Tag definitions (unique on name + category)                              |
| **AssetTag**            | Many-to-many asset↔tag with weights (unique on asset_id + tag_id)         |
| **Transaction**         | All portfolio transactions (buy/sell/cash_in/cash_out/dividends/split/interest/tax) |
| **Price**               | Historical price data (unique on asset_id + price_date); gold bars also carry optional OHLCV/amount |
| **StockInfo**           | Cached THS financial data (dividends, net income, equity, total shares)   |
| **Portfolio**           | Portfolio definitions                                                     |
| **Position**            | Daily portfolio positions (unique on portfolio_id + date + asset_id)     |
| **Benchmark**           | Benchmark indices (supports composite with weighted components)          |
| **BenchmarkComponent**  | Composite benchmark composition (weights must sum to 1.0)                |
| **BenchmarkPrice**     | Benchmark historical prices                                              |
| **Settings**            | Key-value application settings                                           |

### Transaction Types

| Type        | Description                   |
| ----------- | ----------------------------- |
| `buy`       | Purchase of securities        |
| `sell`      | Sale of securities            |
| `cash_in`   | Cash deposits                 |
| `cash_out`  | Cash withdrawals              |
| `dividends` | Dividend payments             |
| `interest`  | Interest income               |
| `split`     | Stock splits and bonus shares |
| `tax`       | Tax payments                  |

## Data Import Formats

### Transactions CSV (Standard)

Required columns: `trade_date`, `action`, `symbol`, `name`, `quantity`, `price`, `fees`, `amount`, `currency`, `notes`

### Xueqiu (雪球) Format

Columns (Chinese): `日期`, `类型`, `代码`, `名称`, `成交价`, `数量`, `金额`, `说明`

- Auto-mapped to English fields
- Symbols cleaned: `SZ` → `.SZ`, `SH` → `.SH`, 5-digit → `.HK`
- Encoding auto-detected (gbk, gb2312, utf-8, utf-8-sig, gb18030)
- ZIP files with `交易记录` + `转账记录` sections supported

### Prices CSV

```csv
symbol,price_date,price
AAPL,2024-01-15,150.00
GOOGL,2024-01-15,2800.00
```

### Exchange Rates CSV

Columns: `currency_code`, `rate_date`, `rate_to_primary`

## Performance Calculations

Detailed algorithm documentation is available in [doc/return-calculation-algorithms.md](doc/return-calculation-algorithms.md).

### Time-Weighted Return (TWR)

Implemented using the **fund NAV method** (`backend/services/calculation.py` → `calculate_twr()`):

- External cash flows (cash_in/cash_out) added at end of day
- `NAV(t) = (V(t) - ΔCF(t)) / S(t-1)`
- Shares adjusted by `ΔS(t) = ΔCF(t) / NAV(t)`
- Daily return `r(t) = (V(t) - ΔCF(t)) / V(t-1) - 1`
- Cumulative `TWR = ∏(1 + r(t)) - 1`
- Annualized return: `(1 + TWR)^(365/days) - 1`

### Tag-Weighted Price Return

Used for tag correlation and tag beta (`backend/services/portfolio.py` → `get_tag_daily_returns()`):

- Each asset's pure price return: `r_i(t) = p_i(t)/p_i(t-1) - 1`
- Weighted by previous day's market value (in primary currency, with tag weights)
- Isolates price movement from buy/sell activity

### Risk Metrics

| Metric               | Description                                     |
| -------------------- | ----------------------------------------------- |
| **Volatility**       | Annualized standard deviation of returns         |
| **Sharpe Ratio**     | Risk-adjusted return                            |
| **Sortino Ratio**    | Downside risk-adjusted return                   |
| **Maximum Drawdown** | Largest peak-to-trough decline                  |
| **Calmar Ratio**     | Return relative to maximum drawdown             |
| **Beta**             | Cov(asset, bench) / Var(bench); supports daily/weekly/monthly aggregation |
| **Alpha**            | Excess return over benchmark                    |
| **Tag Correlation**  | Pearson correlation matrix across tags (min 20 aligned days) |

## Customization

### Adding New Asset Types

1. Update the `Asset` model in `backend/db/models/asset.py`
2. Add asset type options in the frontend components
3. Implement specific logic in `backend/services/` if needed

Supported asset types: `stock`, `bond`, `etf`, `fund`, `cash`, `gold`

### Adding New Currencies

1. Use the Currency management interface in Settings
2. Add exchange rate data via CSV import or manual entry
3. The system automatically handles currency conversions (direct and inverse rates)

Supported currencies: CNY, USD, HKD, EUR (easily extensible)

### Asset Tagging System

Assets support a flexible tagging system for classification and analysis:

**Tag Categories:**

- **行业** - Industry classification (银行, 科技, 消费, etc.)
- **地域** - Geographic region (国内, 国外, 香港, etc.)
- **资产类型** - Asset type allocation (Bond, Equity, Cash)
- **风格** - Investment style (红利股, 成长股, 价值股)

**Features:**

- Multiple tags per asset with weights (e.g., 10% Bond + 90% Equity)
- Portfolio allocation analysis by tag category
- Tag correlation and beta analysis
- Custom tag categories and tags

```python
from backend.services.tag import TagService
from decimal import Decimal

with TagService() as service:
    # Assign multiple tags to an asset
    service.assign_tag_to_asset("600036.SH", "银行", category_name="行业")
    service.assign_tag_to_asset("600036.SH", "国内", category_name="地域")
    service.assign_tag_to_asset("600036.SH", "红利股", category_name="风格")

    # ETF with asset allocation weights
    service.assign_tag_to_asset("510900.SH", "Bond", Decimal("10"), category_name="资产类型")
    service.assign_tag_to_asset("510900.SH", "Equity", Decimal("90"), category_name="资产类型")

    # Get portfolio allocation by tag category
    allocation = service.get_asset_allocation(portfolio_id, date)
    region_stats = service.get_portfolio_tag_statistics(portfolio_id, date, "地域")
```

## Testing

Run the test suite using pytest:

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_twr.py

# Skip tests requiring production database connection
pytest -m "not production"

# Run with coverage
pytest --cov=backend
```

Test configuration (`pytest.ini`):
- `pythonpath = . backend`
- `testpaths = tests`
- `production` marker for tests requiring external data connections

The test fixture (`tests/conftest.py`) creates a temporary SQLite database with 3 currencies (CNY primary), one portfolio, and sample assets.

## Architecture Notes

### Design Principles

- **Separation of Concerns**: Clean frontend/backend architecture with distinct layers
- **Service Layer Pattern**: Business logic in service classes inheriting from `BaseService`, usable as context managers
- **Data Integrity**: Comprehensive validation and unique constraints at the database level
- **Type Safety**: Type-hinted Python backend (built-in types, no `typing` imports); TypeScript frontend
- **Logging**: Console logger (INFO) and file logger (DEBUG to `logs/debug_log.csv`)

### Technology Stack

#### Backend

| Technology      | Purpose                                                  |
| --------------- | -------------------------------------------------------- |
| **FastAPI**     | Modern API framework with automatic documentation        |
| **SQLModel**    | Type-safe database operations with Pydantic integration |
| **Pandas**      | Data manipulation and analysis                           |
| **NumPy/SciPy** | Numerical computations and statistical analysis         |
| **akshare**     | Open-source market data (A-shares, HK, ETFs, bonds)     |
| **pytest**      | Testing framework                                        |

#### Frontend

| Technology          | Purpose                                                |
| ------------------- | ------------------------------------------------------ |
| **Vue.js 3**        | Reactive frontend framework with Composition API      |
| **Element Plus**    | Professional UI component library                      |
| **Chart.js**        | Flexible charting library for financial visualizations |
| **Pinia**           | State management (6 stores)                            |
| **Vue Router**      | Client-side routing (web history mode)                |
| **Vite**            | Build tool and development server                      |

### Data Sources

Two independent data sources (`backend/data_source.py`) with module-level singletons:

- **AKShareDataSource** (`akshare_source`): Open-source via akshare. Used for exchange rates via `currency_boc_sina()` with fallback mechanisms. Covers A-shares, HK stocks, ETFs, bonds.
- **THSDataSource** (`ths_source`): TongHuaShun/同花顺 terminal login (credentials from `.env`). Used for historical stock/ETF prices and financial data (dividends, net income, equity), plus daily OHLCV bars via `THS_HD` for the gold data loader. Has reconnection logic.
- **IFindHTTPDataSource** (`ifind_http_source`): iFinD HTTP fallback for gold daily bars, authenticated with `IFIND_DATASOURCE_KEY`.

### Data Flow

1. **External Data Sources** → `backend/data_source.py` (AKShare + THS + iFinD HTTP)
2. **API Layer** → `backend/api/v1/` (REST endpoints)
3. **Service Layer** → `backend/services/` (business logic)
4. **Database Layer** → `backend/db/` (SQLModel models)
5. **Frontend** → Vue.js components with Pinia state management

## License

This project is for personal use. Please respect the licenses of third-party dependencies.
