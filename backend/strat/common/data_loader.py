"""Incremental daily-bar loader for gold datasets.

Ported from holmes-lab strategies/common/data_loader.py. Fetching is delegated
to backend/data_source.py (THS SDK via THS_HD, iFinD HTTP fallback); this
module owns the dataset registry, last-date detection and CSV appending.

CSV layout: date,open,high,low,close,volume,amt with dates as YYYY/M/D.
AU9999: OHLC in CNY/gram, volume in kg, amt in 亿元.
518880.SH: OHLC in CNY/share, volume in shares, amt in 亿元.
"""

import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pandas as pd

from backend import logger
from backend.data_source import ifind_http_source, ths_source
from backend.strat.common.constants import AU9999_DAILY_CSV, GOLD_ETF_DAILY_CSV

CSV_COLUMNS = ["date", "open", "high", "low", "close", "volume", "amt"]


@dataclass(frozen=True)
class Dataset:
    """An incrementally updatable daily-bar dataset."""

    name: str
    ifind_code: str
    csv_path: Path
    market_close: time


DATASETS: dict[str, Dataset] = {
    "au9999": Dataset("au9999", "AU9999.SHG", AU9999_DAILY_CSV, time(15, 30)),
    "518880": Dataset("518880", "518880.SH", GOLD_ETF_DAILY_CSV, time(15, 0)),
}


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {column: pd.Series(dtype="object") for column in CSV_COLUMNS}
    )


def load_daily_csv(csv_path: str | Path) -> pd.DataFrame:
    """Read a daily-bar CSV, returning date/open/high/low/close/volume/amt."""
    df = pd.read_csv(csv_path)
    df.columns = [str(column).strip().lower() for column in df.columns]
    missing = [column for column in CSV_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Daily CSV {csv_path} is missing columns: {missing}")
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    for column in CSV_COLUMNS[1:]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df = df.dropna(subset=CSV_COLUMNS)
    df = df.sort_values("date").drop_duplicates("date", keep="last")
    return df.reset_index(drop=True)


def last_csv_date(csv_path: str | Path) -> date | None:
    """Return the most recent date in a daily CSV, if it exists."""
    path = Path(csv_path)
    if not path.exists():
        return None
    dates = pd.to_datetime(
        pd.read_csv(path)[CSV_COLUMNS[0]], errors="coerce"
    ).dropna()
    return dates.max().date() if len(dates) else None


def _last_closed_day(market_close: time) -> date:
    now = datetime.now()
    if now.time() < market_close:
        return (now - timedelta(days=1)).date()
    return now.date()


def _format_number(value) -> str:
    return f"{float(value):.10g}"


def _append_rows(csv_path: Path, rows: pd.DataFrame) -> None:
    if csv_path.exists():
        lines = csv_path.read_text(encoding="utf-8").splitlines()
        while lines and not lines[-1].strip(",\t "):  # drop trailing blank lines
            lines.pop()
    else:
        lines = []
    if not lines:
        lines = [",".join(CSV_COLUMNS)]
    for row in rows.itertuples(index=False):
        day = row[0]
        cells = [f"{day.year}/{day.month}/{day.day}"] + [
            _format_number(getattr(row, column)) for column in CSV_COLUMNS[1:]
        ]
        lines.append(",".join(cells))
    csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def fetch_daily(
    code: str,
    start_date: date,
    end_date: date,
    source: str = "auto",
) -> pd.DataFrame:
    """Fetch daily bars via iFinD SDK (THS_HD) with HTTP fallback.

    Returns date/open/high/low/close/volume/amt (amt in 亿元); an empty
    DataFrame when unavailable.
    """
    fetchers = {
        "sdk": lambda: ths_source.fetch_historical_daily(code, start_date, end_date),
        "http": lambda: ifind_http_source.fetch_historical_daily(
            code, start_date, end_date
        ),
    }
    if source in fetchers:
        return fetchers[source]()
    if source != "auto":
        raise ValueError(f"Unknown data source: {source}")

    errors: list[str] = []
    for name in ("sdk", "http"):
        try:
            frame = fetchers[name]()
        except Exception as exc:  # noqa: BLE001 - fall back on any fetch failure
            errors.append(f"{name}: {exc}")
            continue
        if not frame.empty:
            return frame
        errors.append(f"{name}: empty result")
    logger.warning(f"Gold daily fetch failed for {code} ({start_date}~{end_date}): {errors}")
    return _empty_frame()


def update_daily(
    dataset: str | Dataset = "au9999",
    end: str | date | None = None,
    source: str = "auto",
    dry_run: bool = False,
) -> pd.DataFrame:
    """Append bars after the CSV's last date, up to the last closed session.

    ``dataset`` is a key of DATASETS or a Dataset instance; ``end`` defaults
    to the most recent closed session based on the dataset's market close.
    Returns the incremental rows (also appended to the CSV unless dry_run).
    """
    ds = DATASETS[dataset] if isinstance(dataset, str) else dataset
    last_date = last_csv_date(ds.csv_path)
    if end is None:
        end_date = _last_closed_day(ds.market_close)
    elif isinstance(end, str):
        end_date = date.fromisoformat(end)
    else:
        end_date = end
    start_date = end_date if last_date is None else last_date + timedelta(days=1)

    if start_date > end_date:
        return _empty_frame()

    incremental = fetch_daily(ds.ifind_code, start_date, end_date, source=source)
    if incremental.empty:
        return incremental
    if last_date is not None:
        incremental = incremental[incremental["date"] > last_date]
    if not dry_run and not incremental.empty:
        _append_rows(ds.csv_path, incremental)
    return incremental.reset_index(drop=True)


def _cli() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    dataset = sys.argv[1] if len(sys.argv) > 1 else "au9999"
    added = update_daily(dataset)
    if added.empty:
        print("No data to update")
    else:
        print(f"Added {len(added)} rows to {DATASETS[dataset].csv_path}")
        print(added.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
