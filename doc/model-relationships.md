# Database Model Relationships

ER diagram of all SQLModel entities in `backend/db/models/`.

## Diagram

```mermaid
erDiagram
    CURRENCY ||--o{ EXCHANGE_RATE : "from_currency_id / to_currency_id"
    CURRENCY ||--o{ ASSET : "currency_id"
    CURRENCY ||--o{ TRANSACTION : "currency_id"
    CURRENCY ||--o{ PORTFOLIO : "base_currency_id"
    PORTFOLIO ||--o{ TRANSACTION : "portfolio_id"
    PORTFOLIO ||--o{ POSITION : "portfolio_id"
    ASSET ||--o{ TRANSACTION : "asset_id (no cascade, 409 guard)"
    ASSET ||--o{ PRICE : "asset_id (CASCADE)"
    ASSET ||--o{ POSITION : "asset_id (CASCADE)"
    ASSET ||--o{ ASSET_TAG : "asset_id (CASCADE)"
    ASSET ||--o{ STOCK_INFO : "asset_id (CASCADE)"
    TAG_CATEGORY |o--o{ TAG : "category_id (nullable, detached on delete)"
    TAG ||--o{ ASSET_TAG : "tag_id (CASCADE)"
    BENCHMARK ||--o{ BENCHMARK_PRICE : "benchmark_id"
    BENCHMARK ||--o{ BENCHMARK_COMPONENT : "composite_benchmark_id (CASCADE)"
    BENCHMARK ||--o{ BENCHMARK_COMPONENT : "component_benchmark_id"

    CURRENCY {
        int id PK
        str code UK "CNY, USD, HKD"
        str name
        str symbol
        bool is_primary UK "only one primary"
    }

    EXCHANGE_RATE {
        int id PK
        int from_currency_id FK
        int to_currency_id FK
        date rate_date
        decimal rate
        str source
    }

    ASSET {
        int id PK
        str symbol UK
        str name
        str isin
        str type "stock, bond, fund, etf, cash"
        int currency_id FK
        datetime created_at
    }

    TAG_CATEGORY {
        int id PK
        str name UK
        str description
        int display_order
    }

    TAG {
        int id PK
        str name
        int category_id FK "nullable"
        str description
        str color
    }

    ASSET_TAG {
        int id PK
        int asset_id FK "CASCADE"
        int tag_id FK "CASCADE"
        decimal weight "percentage"
        str notes
    }

    TRANSACTION {
        int id PK
        int portfolio_id FK
        int asset_id FK
        int currency_id FK
        str action "buy, sell, cash_in, cash_out, dividends, split, tax, interest"
        date trade_date
        decimal quantity
        decimal price
        decimal amount
        decimal fees
        str notes
    }

    PRICE {
        int id PK
        int asset_id FK "CASCADE"
        date price_date UK "with asset_id"
        decimal price
        str price_type "real_time, historical, manual"
        str source
    }

    PORTFOLIO {
        int id PK
        str name
        str description
        int base_currency_id FK
    }

    POSITION {
        int id PK
        int portfolio_id FK
        int asset_id FK "CASCADE"
        date position_date UK "with portfolio_id + asset_id"
        decimal quantity
        decimal average_cost
        decimal current_price
        decimal market_value
        decimal total_pnl
    }

    STOCK_INFO {
        int id PK
        int asset_id FK "CASCADE"
        str symbol
        date report_date
        float dividend_before_tax
        float dividend_after_tax
        float total_shares
        float ni_to_parent
        float equity_to_parent
    }

    BENCHMARK {
        int id PK
        str symbol UK
        str name
        bool is_composite
    }

    BENCHMARK_PRICE {
        int id PK
        int benchmark_id FK
        date price_date UK "with benchmark_id"
        decimal close
        str source
    }

    BENCHMARK_COMPONENT {
        int id PK
        int composite_benchmark_id FK "CASCADE"
        int component_benchmark_id FK "self reference"
        decimal weight
    }

    SETTINGS {
        int id PK
        str key UK
        str value
        str description
    }
```

## Entity Overview

| Entity | Purpose |
| --- | --- |
| Currency | Multi-currency master data; exactly one primary currency |
| ExchangeRate | Daily rates: 1 unit of `from_currency` = `rate` units of `to_currency` |
| Asset | Tradeable instruments (stock, bond, fund, etf, cash). Cash assets use the `{CCY}_CASH` symbol convention |
| TagCategory | Tag groupings (行业 / 地域 / 资产类型 / 风格) |
| Tag | Individual tags, optionally grouped in a category |
| AssetTag | Asset-to-tag assignment with a weight (%) per category |
| Portfolio | Top-level container with a base currency |
| Transaction | All money/share flows: buy, sell, cash_in, cash_out, dividends, split, tax, interest |
| Position | Daily portfolio position snapshot per (portfolio, date, asset) |
| Price | Asset price history per (asset, date, type) |
| StockInfo | Per-stock financial indicators from THS |
| Benchmark | Benchmark index, optionally composite (weighted components) |
| BenchmarkPrice | Benchmark index price history |
| BenchmarkComponent | Composite benchmark membership and weights |
| Settings | Standalone key-value application settings |

## Delete / Cascade Behavior

| Delete target | Behavior |
| --- | --- |
| Asset | Blocked with 409 if transactions exist. Otherwise cascades to `asset_tags`, `prices`, `positions`, `stock_infos` (ORM cascade + FK `ON DELETE CASCADE` on fresh databases) |
| Tag | Cascades to its `asset_tags` |
| TagCategory | Tags are detached (`category_id` set to NULL, become "Uncategorized") |
| Benchmark | Cascades to `BenchmarkComponent` (composite side). Known gap: `BenchmarkPrice` rows are **not** cascaded and will raise an integrity error if present |
| Transaction | No children; direct delete. Note: deleting transactions does **not** recalculate or clean up existing Position snapshots |
| Portfolio / Currency | No delete endpoints |

## Notes

- FK `ON DELETE CASCADE` is declared in the models (sqlmodel `Field(ondelete="CASCADE")`). SQLite only enforces it when `PRAGMA foreign_keys=ON`, which `backend/db/base.py` enables on every new connection.
- ORM-level `cascade="all, delete-orphan"` works on existing databases immediately. The FK-level DDL only applies to tables created afterwards (i.e. after `python -m backend.init_data`).
- `Transaction.asset_id` deliberately has no cascade: assets with transactions cannot be deleted (409).
