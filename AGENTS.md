# AGENTS.md

Compact guidance for OpenCode sessions working in this repo. Read alongside `README.md` for full feature docs.

## Use English for all documentation, comments, and code

## Shell preference

- **Windows** — prefer Git Bash (`C:\Program Files\Git\bin\bash.exe`). OpenCode's tool is fixed to pwsh, so prefix commands with `& "C:\Program Files\Git\bin\bash.exe" -c "..."` to run in Git Bash. Avoid WSL bash (`C:\WINDOWS\system32\bash.exe`).
- **macOS / Linux** — use the native shell directly (no need for bash.exe wrapping).

## Run everything from the repo root

`pytest.ini` sets `pythonpath = . backend`; `backend/db/base.py` resolves `DATA_PATH` as `<repo_root>/data` and the DB as `backend/portfolio.db`. Running commands from inside `backend/` breaks imports and path resolution.

```bash
# Backend: init DB (wipes backend/portfolio.db and reloads seeds from data/sample/; set HOLMFOLIO_SEED_DIR to use another dir, e.g. data/private/)
python -m backend.init_data

# Backend dev server (http://localhost:8000, Swagger at /docs)
uvicorn backend.main:app --reload

# Frontend (cd into frontend/ once, then):
#   npm install   # first time
#   npm run dev   # http://localhost:3000, auto-opens browser

# Full stack: start.bat (Windows) / start.sh (Unix)
```

## Backend startup is not instant

`backend/main.py` `lifespan` runs on app start: creates tables, backfills prices/exchange-rates/benchmark-prices up to **yesterday**, then ensures positions up to **today**. This hits AKShare + THS external APIs and can be slow / network-dependent. With no existing price rows it logs and skips. Don't assume `uvicorn` is ready the instant it prints the banner.

## THS / iFinDPy SDK is required for the live backend

`backend/data_source.py` does a top-level `from iFinDPy import ...`. Importing it (transitively via `main.py` → `price_rate` service) fails if the THS SDK isn't installed. The repo assumes iFinDPy is available locally; `backend/data_source.py` also instantiates module-level singletons `akshare_source` and `ths_source`.

## Tests

```bash
pytest                              # all non-production tests (addopts=-s, no capture)
pytest tests/test_twr.py            # single file
pytest tests/test_twr.py::test_name # single test
pytest -m "not production"          # explicit skip of production-marked tests
pytest --cov=backend                # coverage
```

- `tests/conftest.py` mocks `iFinDPy` with `MagicMock` only if the real import fails, and auto-skips `@pytest.mark.production` tests when the mock is in effect. When the real SDK is present, production tests run (see `test_benchmark_prices.py`, `test_stock_financials.py`, `test_dividend_after_tax.py`).
- The `test_db` fixture creates a **temp SQLite file per test** with CNY (primary), HKD, USD, one portfolio, and 6 assets (incl. `{CCY}_CASH` cash assets). Don't assume `backend/portfolio.db` is used by tests.
- `addopts = -s`: stdout is not captured; `print` shows up in output.

## No lint / typecheck / format pipeline

- Backend: no ruff/black/mypy config. Python 3.12+ — use built-in generics (`Session | None`, `list[int]`), **no `typing` imports** (this is an established repo convention, see existing services).
- Frontend: only `dev` / `build` / `preview` / `serve` scripts. No `lint`, `typecheck`, or test script. `tsconfig.json` is `strict` with `noUnusedLocals` and `noUnusedParameters`; path alias `@` → `src`. There is no `tsc --noEmit` script — run `npx tsc --noEmit -p frontend/tsconfig.json` if you want a type check.

## Architecture facts that aren't obvious from filenames

- **Service layer**: `backend/services/base.py` `BaseService` — pass an existing `Session` to share a transaction, or omit to let it create its own. Auto commit/rollback fires **only when the service owns the session**. Always use services as context managers (`with XxxService() as svc:`).
- **DB engine is a singleton** in `backend/db/base.py` (`get_engine()`). `init_data.py` calls `drop_db_and_tables()` first — it is destructive.
- **Logger**: `from backend import logger` (console, INFO) and `f_logger` (file, DEBUG → `logs/debug_log.csv`, opened with `mode="w"` so it's truncated on every process start).
- **API surface**: all routes under `/api/v1/...` via `backend/api/v1/router.py`; health check at `/health`.
- **Data sources**: `akshare_source` (AKShare, no login, has fallback maps for failed APIs) and `ths_source` (THS/同花顺, requires terminal login, has reconnection logic) — both module-level singletons in `backend/data_source.py`.
- **HK stock cache**: `data/hk_stock_cache.json` maps normalized HK symbols (e.g. `0941.HK`) to red-chip / A+H dual-listing info (`is_red_chip`, `is_dual_listed`, `a_share_symbol`). `backend/data_source.py` reads it in `get_dividend_after_tax_past_year` to compute HK dividend tax; no AI calls at runtime. Missing entries default to no-tax-adjustment.
- **Cash asset convention**: symbol `{CCY}_CASH` (e.g. `CNY_CASH`).
- **Seed data**: `backend/init_data.py` reads `assets.csv`, `asset_tags.csv`, and `transactions.csv` from `data/sample/` by default; `HOLMFOLIO_SEED_DIR` overrides the directory. `data/private/` (gitignored) holds the owner's real seeds. `tags.csv` / `tag_categories.csv` always come from `data/`.
- **Tag categories are named in Chinese**: 行业 / 地域 / 资产类型 / 风格.
- **Xueqiu import**: auto-detects encoding (gbk/gb2312/utf-8/utf-8-sig/gb18030) and rewrites symbols (`SZ`→`.SZ`, `SH`→`.SH`, 5-digit→`.HK`). ZIP files with `交易记录` + `转账记录` sections supported.

## Workflow conventions

- Commits: **Conventional Commits** (`feat:`, `fix:`, `chore:`, `refactor:`, `docs:`, `test:`, ...). Keep messages concise and match existing `git log` style.
- No CI, no pre-commit hooks — verify locally before committing (`pytest` for backend; `npx tsc --noEmit -p frontend/tsconfig.json` for frontend type changes).
- `*.db`, `logs/`, `tests/output/`, `tests/xueqiu_portfolio.csv`, `data/private/`, and `.env` are gitignored — never commit the SQLite DB or logs.

## Verify before declaring done

For any backend change: `pytest` (or at least the touched test file) from repo root. For frontend type-affecting changes: `npx tsc --noEmit -p frontend/tsconfig.json` from repo root. There is no single `npm run typecheck` shortcut.
