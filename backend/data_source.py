import json
import re
import urllib.request
from collections.abc import Callable

import akshare as ak
import pandas as pd
from decimal import Decimal
from dotenv import dotenv_values
from backend import logger
from backend.ai.ai_client import ai_agent_client
from iFinDPy import THS_iFinDLogin, THS_HD, THS_HQ, THS_BD
from datetime import date, timedelta
from pathlib import Path

ROOT_PATH = Path(__file__).parent.parent
HK_STOCK_CACHE_FILE = ROOT_PATH / "data" / "hk_stock_cache.json"

_ENV = dotenv_values(ROOT_PATH / ".env")

IFIND_HTTP_BASE = "https://quantapi.51ifind.com/api/v1"
DAILY_BAR_FIELDS = ["open", "high", "low", "close", "volume", "amt"]


class AKShareDataSource:
    """
    Wrapper class for AKShare data fetching with automatic fallback mechanism.
    When one API fails, it automatically tries alternative APIs.
    """

    CURRENCY_SYMBOL_MAP = {
        "USD": "美元",
        "HKD": "港币",
        "EUR": "欧元",
        "GBP": "英镑",
        "JPY": "日元",
        "CAD": "加拿大元",
        "AUD": "澳大利亚元",
        "NZD": "新西兰元",
        "CHF": "瑞士法郎",
        "SGD": "新加坡元",
        "KRW": "韩国元",
        "MOP": "澳门元",
        "THB": "泰国铢",
        "PHP": "菲律宾比索",
        "SEK": "瑞典克朗",
        "DKK": "丹麦克朗",
        "NOK": "挪威克朗",
    }

    def __init__(self):
        self.fallback_map = {
            "stock_zh_a_hist": ["stock_zh_a_daily", "stock_zh_a_hist_tx"],
            "stock_hk_hist": ["stock_hk_daily"],
            "fund_etf_hist_em": ["fund_etf_hist_sina"],
            "bond_zh_hs_daily": [],
        }

        self._fund_dividends_by_year: dict[int, pd.DataFrame] = {}

        self.fallback_configs = {
            "stock_zh_a_daily": {
                "param_map": {},
                "param_filter": ["period"],
            },
            "stock_zh_a_hist_tx": {
                "param_map": {},
                "param_filter": ["period"],
            },
            "stock_hk_daily": {
                "param_map": {},
                "param_filter": ["period", "start_date", "end_date", "adjust"],
            },
            "fund_etf_hist_sina": {
                "param_map": {},
                "param_filter": ["period", "start_date", "end_date", "adjust"],
            },
        }

    def _convert_symbol(self, api_name: str, symbol: str) -> str:
        """
        Convert standard symbol to API-specific format.

        Different AKShare APIs require different symbol formats:
        - A Stock APIs (stock_zh_a_hist, stock_zh_a_daily, stock_zh_a_hist_tx):
        - HK Stock APIs (stock_hk_hist, stock_hk_daily):
        - ETF API (fund_etf_hist_em, fund_etf_hist_sina):

        Args:
            api_name: Name of the AKShare API function
            symbol: Standard symbol with suffix (e.g., "000001.SZ", "00700.HK")

        Returns:
            API-specific symbol format
        """
        # East Money API symbol format
        # No market indicator: e.g., "510050.SH" -> "510050", "159915.SZ" -> "159915"
        # Sina HK API symbol format: e.g., "00700.HK" -> "00700"
        if api_name in (
            "stock_zh_a_hist",
            "stock_hk_hist",
            "stock_hk_daily",
            "fund_etf_hist_em",
        ):
            return (
                symbol.replace(".SH", "")
                .replace(".SZ", "")
                .replace(".BJ", "")
                .replace(".HK", "")
            )

        # Sina and Tencent API A Share symbol format
        # Add lowercase prefix, e.g., "510050.SH" -> "sh510050", "159915.SZ" -> "sz159915"
        if api_name in (
            "stock_zh_a_daily",
            "stock_zh_a_hist_tx",
            "fund_etf_hist_sina",
            "bond_zh_hs_daily",
        ):
            if ".SH" in symbol:
                return "sh" + symbol.replace(".SH", "")
            elif ".SZ" in symbol:
                return "sz" + symbol.replace(".SZ", "")
            elif ".BJ" in symbol:
                return "bj" + symbol.replace(".BJ", "")
            return symbol

        # Unknown API: return symbol as-is
        return symbol

    def _normalize_df(
        self, df: pd.DataFrame, start_date: date, end_date: date
    ) -> pd.DataFrame:
        """
        Normalize DataFrame columns and filter by date range.

        Args:
            df: Raw DataFrame from AKShare
            start_date: Start date for filtering
            end_date: End date for filtering

        Returns:
            Normalized DataFrame with 'date' and 'close' columns
        """
        df = df.rename(columns={"日期": "date", "收盘": "close"})
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]
        return df[["date", "close"]]

    def _try_fetch(self, fetch_func, *args, **kwargs) -> tuple[pd.DataFrame, str]:
        """
        Try to fetch data with a single function.

        Args:
            fetch_func: The AKShare function to call
            *args, **kwargs: Arguments to pass to the function

        Returns:
            Tuple of (DataFrame with data or empty DataFrame if failed, source name)
        """
        try:
            df = fetch_func(*args, **kwargs)
            if df is not None and not df.empty:
                return df, fetch_func.__name__
        except Exception as e:
            logger.debug(f"Fetch failed with {fetch_func.__name__}: {e}")
        return pd.DataFrame(), ""

    def _prepare_fallback_params(self, fallback_name: str, **kwargs) -> dict:
        """
        Prepare parameters for fallback function based on its configuration.

        Args:
            fallback_name: Name of the fallback function
            **kwargs: Original parameters

        Returns:
            Transformed parameters dict for the fallback function
        """
        config = self.fallback_configs.get(fallback_name, {})
        param_map = config.get("param_map", {})
        param_filter = config.get("param_filter", [])

        # Start with original params
        fallback_params = dict(kwargs)

        # Apply parameter name mapping
        for old_key, new_key in param_map.items():
            if old_key in fallback_params:
                value = fallback_params.pop(old_key)
                fallback_params[new_key] = value

        # Apply symbol conversion for the specific API
        if "symbol" in fallback_params:
            original_symbol = fallback_params["symbol"]
            fallback_params["symbol"] = self._convert_symbol(
                fallback_name, original_symbol
            )

        # Filter out unsupported parameters
        for param in param_filter:
            fallback_params.pop(param, None)

        return fallback_params

    def _fetch_with_fallback(
        self, primary_func_name: str, *args, **kwargs
    ) -> tuple[pd.DataFrame, str]:
        """
        Fetch data with automatic fallback to alternative functions.

        Args:
            primary_func_name: Name of the primary AKShare function
            *args, **kwargs: Arguments to pass to the functions

        Returns:
            Tuple of (DataFrame with data or empty DataFrame if all failed, source name)
        """
        # Convert symbol for primary function
        primary_params = dict(kwargs)
        if "symbol" in primary_params:
            original_symbol = primary_params["symbol"]
            primary_params["symbol"] = self._convert_symbol(
                primary_func_name, original_symbol
            )

        # Try primary function
        primary_func = getattr(ak, primary_func_name)
        df, source = self._try_fetch(primary_func, *args, **primary_params)
        if not df.empty:
            return df, source

        # Try fallback functions
        fallback_funcs = self.fallback_map.get(primary_func_name, [])
        for fallback_name in fallback_funcs:
            logger.info(f"Trying fallback function: {fallback_name}")
            try:
                fallback_func = getattr(ak, fallback_name)
                fallback_params = self._prepare_fallback_params(fallback_name, **kwargs)
                df, source = self._try_fetch(fallback_func, **fallback_params)
                if not df.empty:
                    logger.info(
                        f"Successfully fetched data using fallback: {fallback_name}"
                    )
                    return df, source
            except Exception as e:
                logger.debug(f"Fallback {fallback_name} also failed: {e}")
                continue

        logger.warning(f"All fetch attempts failed for {primary_func_name}")
        return pd.DataFrame(), ""

    def fetch_historical_prices(
        self,
        symbol: str,
        asset_type: str,
        start_date: date,
        end_date: date,
        adjust: str = "",
    ) -> tuple[pd.DataFrame, str]:
        """
        Fetch historical daily close prices from AKShare API with fallback support.

        Args:
            symbol: Asset symbol (e.g., "000001.SZ", "00700.HK")
            asset_type: Asset type ("stock" or "etf" or "bond")
            start_date: Start date as datetime.date object
            end_date: End date as datetime.date object
            adjust: Adjustment type ("" for non-adjusted, "qfq" for forward-adjustment, "hfq" for backward-adjustment)

        Returns:
            Tuple of (DataFrame with historical price data containing 'date' and 'close' columns, source name)
        """
        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")

        match (asset_type, symbol):
            # Chinese A-Shares (.SH or .SZ)
            case ("stock", s) if s.endswith(".SH") or s.endswith(".SZ"):
                df, source = self._fetch_with_fallback(
                    "stock_zh_a_hist",
                    symbol=symbol,
                    period="daily",
                    start_date=start_str,
                    end_date=end_str,
                    adjust=adjust,
                )
                if not df.empty:
                    return self._normalize_df(df, start_date, end_date), source
            # Hong Kong Stocks (.HK)
            case ("stock", s) if s.endswith(".HK"):
                df, source = self._fetch_with_fallback(
                    "stock_hk_hist",
                    symbol=symbol,
                    period="daily",
                    start_date=start_str,
                    end_date=end_str,
                    adjust=adjust,
                )
                if not df.empty:
                    return self._normalize_df(df, start_date, end_date), source
            # Chinese ETFs (.SH or .SZ)
            case ("etf", s) if s.endswith(".SH") or s.endswith(".SZ"):
                df, source = self._fetch_with_fallback(
                    "fund_etf_hist_em",
                    symbol=symbol,
                    period="daily",
                    start_date=start_str,
                    end_date=end_str,
                    adjust=adjust,
                )
                if not df.empty:
                    return self._normalize_df(df, start_date, end_date), source
            # HK ETFs (.HK)
            case ("etf", s) if s.endswith(".HK"):
                df, source = self._fetch_with_fallback(
                    "stock_hk_hist",
                    symbol=symbol,
                    period="daily",
                    start_date=start_str,
                    end_date=end_str,
                    adjust=adjust,
                )
                if not df.empty:
                    return self._normalize_df(df, start_date, end_date), source
            # Chinese Bonds (.SH or .SZ)
            case ("bond", s) if s.endswith(".SH") or s.endswith(".SZ"):
                df, source = self._fetch_with_fallback(
                    "bond_zh_hs_daily",
                    symbol=symbol,
                )
                if not df.empty:
                    return self._normalize_df(df, start_date, end_date), source
            # HK Bonds (.HK)
            case ("bond", s) if s.endswith(".HK"):
                df, source = self._fetch_with_fallback(
                    "stock_hk_hist",
                    symbol=symbol,
                    period="daily",
                    start_date=start_str,
                    end_date=end_str,
                    adjust=adjust,
                )
                if not df.empty:
                    return self._normalize_df(df, start_date, end_date), source

        logger.warning(f"No data found for symbol: {symbol}, type: {asset_type}")
        return pd.DataFrame(), ""

    def fetch_exchange_rates(
        self,
        currency_code: str,
        start_date: date,
        end_date: date,
    ) -> tuple[pd.DataFrame, str]:
        """
        Fetch historical exchange rates (XXX/CNY) from Bank of China via Sina Finance.

        Args:
            currency_code: Currency code (e.g., "USD", "HKD", "EUR")
            start_date: Start date as datetime.date object
            end_date: End date as datetime.date object

        Returns:
            Tuple of (DataFrame with exchange rate data, source name)
            DataFrame columns: 'date', 'buy_rate' (中行汇买价)
        """
        if currency_code not in self.CURRENCY_SYMBOL_MAP:
            logger.warning(f"Unsupported currency code: {currency_code}")
            return pd.DataFrame(), ""

        symbol = self.CURRENCY_SYMBOL_MAP[currency_code]
        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")

        try:
            df = ak.currency_boc_sina(
                symbol=symbol,
                start_date=start_str,
                end_date=end_str,
            )
            if df is not None and not df.empty:
                df = df.rename(columns={"日期": "date", "中行汇买价": "buy_rate"})
                df["date"] = pd.to_datetime(df["date"]).dt.date
                df = df[["date", "buy_rate"]]
                df["buy_rate"] = df["buy_rate"]/100
                return df, "currency_boc_sina"
        except Exception as e:
            logger.warning(f"Failed to fetch exchange rates for {currency_code}: {e}")

        return pd.DataFrame(), ""

    @staticmethod
    def _parse_a_share_scheme_per_share(scheme_text: str) -> Decimal | None:
        """Parse the cash dividend per share (before tax) from an A-share scheme text.

        A-share schemes are written per 10 shares, e.g. "10派17.38元(含税)" or
        "10派8元转12股派39.74元(含税)". The cash part is the amount following
        "派" and is divided by 10 to get the per-share value.

        Args:
            scheme_text: Raw scheme text from THS dividend data.

        Returns:
            Cash dividend per share before tax, or None when the text carries
            no cash dividend (e.g. "不分配不转增").
        """
        match = re.search(r"派([\d.]+)元", scheme_text)
        if not match:
            return None
        return Decimal(match.group(1)) / 10

    @staticmethod
    def _parse_hk_payout_per_share(plan_text: str) -> Decimal | None:
        """Parse the cash dividend per share (before tax, in HKD) from an HK payout plan.

        HK payout plans are written per share, e.g. "每股5.3港元" or
        "每股派港币0.3元(相当于港币0.328元)". The HKD amount is preferred
        (the HKD-equivalent is given in parentheses when the dividend is
        declared in another currency); otherwise the plain per-share amount
        is used.

        Args:
            plan_text: Raw payout plan text from THS HK dividend data.

        Returns:
            Cash dividend per share in HKD, or None when no cash amount can
            be parsed (e.g. share-based special distributions).
        """
        for pattern in (r"每股([\d.]+)港元", r"港币([\d.]+)元", r"每股派(?:人民币)?([\d.]+)元"):
            match = re.search(pattern, plan_text)
            if match:
                return Decimal(match.group(1))
        return None

    def _get_a_share_dividend_history(self, symbol: str) -> list[dict]:
        """Get implemented cash-dividend events for an A-share from THS data.

        Uses ``ak.stock_fhps_detail_ths``, which reports per 10-share schemes
        with the record date (A股股权登记日) and the ex-dividend date
        (A股除权除息日). Only rows with progress "实施方案" (implemented)
        and a positive cash dividend are kept; proposals and
        "不分配不转增" rows are dropped.

        Args:
            symbol: A-share symbol, e.g. "600036.SH".

        Returns:
            List of dicts with keys ``report_date``, ``record_date``,
            ``received_date``, ``per_share`` (before tax, CNY) and ``scheme``.
        """
        code = (
            symbol.replace(".SH", "")
            .replace(".SZ", "")
            .replace(".BJ", "")
        )
        try:
            df = ak.stock_fhps_detail_ths(symbol=code)
        except Exception as e:
            logger.warning(f"Failed to fetch THS dividend history for {symbol}: {e}")
            return []

        record_date_col = "A股股权登记日" if "A股股权登记日" in df.columns else "B股股权登记日"
        received_date_col = "A股除权除息日" if "A股除权除息日" in df.columns else "B股除权除息日"

        events: list[dict] = []
        if df is None or df.empty:
            return events

        for _, row in df.iterrows():
            progress = str(row.get("方案进度") or "")
            if progress != "实施方案":
                continue
            scheme = str(row.get("分红方案说明") or "")
            per_share = self._parse_a_share_scheme_per_share(scheme)
            if per_share is None or per_share <= 0:
                continue
            record_date_raw = row.get(record_date_col)
            received_date_raw = row.get(received_date_col)
            record_date = None
            received_date = None
            if pd.notna(record_date_raw):
                record_date = pd.to_datetime(record_date_raw).date()
            if pd.notna(received_date_raw):
                received_date = pd.to_datetime(received_date_raw).date()
            if record_date is None or received_date is None:
                continue
            events.append(
                {
                    "report_date": str(row.get("报告期") or ""),
                    "record_date": record_date,
                    "received_date": received_date,
                    "per_share": per_share,
                    "scheme": scheme,
                }
            )
        return events

    def _get_hk_dividend_history(self, symbol: str) -> list[dict]:
        """Get cash-dividend events for an HK stock from East Money data.

        Uses ``ak.stock_hk_dividend_payout_em`` (5-digit symbol code), where
        the record date is 除净日 - 1 and the received date is 发放日
        (equivalent to THS's 派息日). Special distributions are excluded.

        Args:
            symbol: HK symbol, e.g. "00700.HK".

        Returns:
            List of dicts with keys ``report_date``, ``record_date``,
            ``received_date``, ``per_share`` (before tax, HKD) and ``scheme``.
        """
        code = symbol.replace(".HK", "")
        try:
            df = ak.stock_hk_dividend_payout_em(symbol=code)
        except Exception as e:
            logger.warning(f"Failed to fetch EM HK dividend history for {symbol}: {e}")
            return []

        events: list[dict] = []
        if df is None or df.empty:
            return events

        for _, row in df.iterrows():
            dist_type = str(row.get("分配类型") or "")
            if dist_type == "特别分配":
                continue
            scheme = str(row.get("分红方案") or "")
            per_share = self._parse_hk_payout_per_share(scheme)
            if per_share is None or per_share <= 0:
                continue
            ex_date_raw = row.get("除净日")
            received_date_raw = row.get("发放日")
            ex_date = None
            received_date = None
            if pd.notna(ex_date_raw):
                ex_date = pd.to_datetime(ex_date_raw).date()
            if pd.notna(received_date_raw):
                received_date = pd.to_datetime(received_date_raw).date()
            if ex_date is None or received_date is None:
                continue
            events.append(
                {
                    "report_date": str(row.get("财政年度") or ""),
                    "record_date": ex_date - timedelta(days=1),
                    "received_date": received_date,
                    "per_share": per_share,
                    "scheme": scheme,
                }
            )
        return events

    def _get_fund_dividend_history(
        self, symbol: str, start_year: int = 2000
    ) -> list[dict]:
        """Get cash-dividend events for an A-share-listed fund/ETF.

        Uses ``ak.fund_fh_em`` (天天基金-基金分红), which lists per-year
        dividend records for all fund types (ETF, LOF, open-end, bond funds,
        REITs, QDII). The record date is 权益登记日 and the received date is
        分红发放日. Year snapshots are cached per instance so that multiple
        funds share the same fetches.

        Args:
            symbol: Fund/ETF symbol, e.g. "510900.SH" or "159915.SZ".
            start_year: First year to scan (inclusive).

        Returns:
            List of dicts with keys ``report_date`` (str), ``record_date``,
            ``received_date``, ``per_share`` (CNY per share) and ``scheme``.
        """
        code = (
            symbol.replace(".SH", "")
            .replace(".SZ", "")
            .replace(".BJ", "")
        )
        events: list[dict] = []
        current_year = date.today().year
        for year in range(start_year, current_year + 1):
            df = self._fund_dividends_by_year.get(year)
            if df is None:
                try:
                    df = ak.fund_fh_em(year=str(year))
                except Exception as e:
                    logger.warning(f"Failed to fetch fund dividend history for {symbol} ({year}): {e}")
                    continue
                self._fund_dividends_by_year[year] = df
            if df is None or df.empty:
                continue

            for _, row in df.iterrows():
                if str(row.get("基金代码") or "") != code:
                    continue
                scheme = str(row.get("基金简称") or "")
                per_share = row.get("分红")
                if pd.isna(per_share) or per_share <= 0:
                    continue
                record_date_raw = row.get("权益登记日")
                received_date_raw = row.get("分红发放日")
                record_date = None
                received_date = None
                if pd.notna(record_date_raw):
                    record_date = pd.to_datetime(record_date_raw).date()
                if pd.notna(received_date_raw):
                    received_date = pd.to_datetime(received_date_raw).date()
                if record_date is None or received_date is None:
                    continue
                events.append(
                    {
                        "report_date": str(row.get("除息日期") or "")[:10],
                        "record_date": record_date,
                        "received_date": received_date,
                        "per_share": Decimal(str(per_share)),
                        "scheme": f"{scheme} 分红",
                    }
                )

        events.sort(key=lambda e: e["record_date"])
        return events

    def get_dividend_history(
        self,
        symbol: str,
        asset_type: str | None = None,
        start_year: int | None = None,
    ) -> list[dict]:
        """Get historical cash-dividend events for a symbol via AKShare.

        A-shares use THS dividend data (``stock_fhps_detail_ths``) and HK
        stocks use East Money data (``stock_hk_dividend_payout_em``).
        A-share-listed funds and ETFs use 天天基金 data (``fund_fh_em``).
        Only implemented distributions with a positive cash dividend are
        returned. Each event carries both the record date (shares held on
        that date receive the dividend) and the received date (除权除息日 for
        A-shares, 发放日 for HK stocks, 分红发放日 for funds).

        Bonds and HK-listed funds/ETFs have no AKShare dividend source and
        are skipped without any network call.

        Args:
            symbol: Asset symbol, e.g. "600036.SH" or "00700.HK".
            asset_type: Asset type (stock, bond, fund, etf, cash). When
                given and unsupported (bond, cash, or HK fund/ETF), no fetch
                is attempted.
            start_year: First year to scan for fund dividends (inclusive).

        Returns:
            List of dicts with keys ``report_date`` (str), ``record_date``
            (date), ``received_date`` (date), ``per_share`` (Decimal, before
            tax, in the asset's trading currency) and ``scheme`` (str).
        """
        if symbol.endswith((".SH", ".SZ", ".BJ")):
            if asset_type in ("fund", "etf"):
                return self._get_fund_dividend_history(symbol, start_year or 2000)
            if asset_type is not None and asset_type != "stock":
                logger.debug(
                    f"Skipping dividend history for non-stock asset: {symbol} ({asset_type})"
                )
                return []
            return self._get_a_share_dividend_history(symbol)
        if symbol.endswith(".HK"):
            if asset_type in ("fund", "etf"):
                logger.debug(
                    f"Skipping dividend history for HK-listed fund/ETF (no AKShare source): {symbol}"
                )
                return []
            if asset_type is not None and asset_type != "stock":
                logger.debug(
                    f"Skipping dividend history for non-stock asset: {symbol} ({asset_type})"
                )
                return []
            return self._get_hk_dividend_history(symbol)
        logger.warning(f"Dividend history not supported for symbol: {symbol}")
        return []


class THSDataSource:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if THSDataSource._initialized:
            return

        super().__init__()
        self._login()
        THSDataSource._initialized = True

    def _login(self) -> int:
        """Login to THS using the iFinD credentials from the repo root .env."""
        user = _ENV.get("IFIND_USER")
        password = _ENV.get("IFIND_PASSWORD")
        if not user or not password:
            logger.error(
                "Missing IFIND_USER / IFIND_PASSWORD in .env; THS login skipped"
            )
            self.login_status = -1
            return self.login_status
        self.login_status = THS_iFinDLogin(user, password)
        match self.login_status:
            case 0:
                logger.info("THS logins successfully")
            case -201:
                logger.warning("THS logins again")
            case _:
                logger.error(f"THS login failed: {self.login_status}")
        return self.login_status

    def _reconnect_if_needed(self, error_code: int) -> bool:
        """Reconnect to THS if connection is lost.

        This method attempts to reconnect for any non-zero error code,
        as THS API may return various error codes when disconnected.

        Args:
            error_code: The error code from THS API call.

        Returns:
            True if reconnected successfully, False otherwise.
        """
        if error_code != 0:
            logger.warning(f"THS API error (code: {error_code}), attempting to reconnect...")
            login_status = self._login()
            if login_status == 0:
                logger.info("THS reconnected successfully")
                return True
            else:
                logger.error(f"THS reconnection failed with status: {login_status}")
                return False
        return False

    def _get_past_4_report_dates(self, as_of_date: date) -> list[str]:
        """Get the past 4 quarterly report dates based on as_of_date.

        Args:
            as_of_date: The reference date.

        Returns:
            List of 4 report dates in format YYYYMMDD.
            For example, if as_of_date = 2026-04-11, returns:
            ['20260331', '20251231', '20250930', '20250630']
        """
        year = as_of_date.year
        month = as_of_date.month

        # Determine current quarter end
        if month <= 3:
            # Q1: use previous year Q4, Q3, Q2, Q1
            dates = [
                date(year - 1, 12, 31),
                date(year - 1, 9, 30),
                date(year - 1, 6, 30),
                date(year - 1, 3, 31),
            ]
        elif month <= 6:
            # Q2: use current year Q1, previous year Q4, Q3, Q2
            dates = [
                date(year, 3, 31),
                date(year - 1, 12, 31),
                date(year - 1, 9, 30),
                date(year - 1, 6, 30),
            ]
        elif month <= 9:
            # Q3: use current year Q2, Q1, previous year Q4, Q3
            dates = [
                date(year, 6, 30),
                date(year, 3, 31),
                date(year - 1, 12, 31),
                date(year - 1, 9, 30),
            ]
        else:
            # Q4: use current year Q3, Q2, Q1, previous year Q4
            dates = [
                date(year, 9, 30),
                date(year, 6, 30),
                date(year, 3, 31),
                date(year - 1, 12, 31),
            ]

        return [d.strftime("%Y%m%d") for d in dates]

    def _previous_quarter_end(self, as_of_date: date) -> date:
        """Get the quarter-end date immediately before as_of_date.

        Used to shift the report-date window back one quarter when the latest
        report period has not been published yet.

        Args:
            as_of_date: The reference date.

        Returns:
            The quarter-end date before as_of_date, e.g. as_of 2026-08-04
            returns 2026-06-30.
        """
        year = as_of_date.year
        month = as_of_date.month
        if month <= 3:
            return date(year - 1, 12, 31)
        elif month <= 6:
            return date(year, 3, 31)
        elif month <= 9:
            return date(year, 6, 30)
        return date(year, 9, 30)

    def _disclosure_deadline(
        self,
        symbol: str,
        report_date: str,
        hk_stock_info: dict[str, dict[str, object]],
    ) -> date:
        """Get the statutory disclosure deadline for a report period.

        Reporting rules (both A-share and HK):
        - Q1 (3/31): Apr 30 of the same year
        - Semi-annual (6/30): Aug 31 of the same year
        - Q3 (9/30): Oct 31 of the same year
        - Annual (12/31): A-share -> Apr 30 of the following year;
          HK -> Mar 31 of the following year

        The market rule is chosen per stock: HK stocks and A+H dual-listed
        A-shares use the HK deadlines; other A-shares use the A-share
        deadlines. A+H status is resolved from the HK stock info cache
        (``a_share_symbol`` reverse lookup).

        Args:
            symbol: Stock symbol (normalized THS format, e.g. "600036.SH").
            report_date: Report date in format YYYYMMDD.
            hk_stock_info: HK stock info cache mapping HK symbols to dicts
                with ``a_share_symbol`` keys.

        Returns:
            The statutory disclosure deadline date.
        """
        report = date(
            int(report_date[0:4]),
            int(report_date[4:6]),
            int(report_date[6:8]),
        )
        year, month = report.year, report.month

        # Q1 / semi-annual / Q3 deadlines are identical in both markets
        if month == 3:
            return date(year, 4, 30)
        if month == 6:
            return date(year, 8, 31)
        if month == 9:
            return date(year, 10, 31)

        # Annual report (12/31): HK rule is stricter (Mar 31 vs Apr 30)
        uses_hk_rules = symbol.endswith(".HK") or any(
            info.get("a_share_symbol") == symbol
            for info in hk_stock_info.values()
        )
        if uses_hk_rules:
            return date(year + 1, 3, 31)
        return date(year + 1, 4, 30)

    def _resolve_report_dates_for_symbol(
        self,
        symbol: str,
        as_of_date: date,
        hk_stock_info: dict[str, dict[str, object]],
        probe: Callable[[str, str], float | None],
    ) -> list[str]:
        """Get the past 4 report dates for one symbol, handling the reporting window gap.

        The raw window from :meth:`_get_past_4_report_dates` covers the latest
        4 report periods, but when the most recent report period has not been
        published yet (e.g. on 2026-08-04 the 2026Q2 semi-annual report is
        usually only out by late August), its data is unavailable and the
        window silently covers only 9 months, dropping the quarter from
        one year ago (e.g. 2025Q2). This method detects that case and shifts
        the window back one quarter so the last 12 months are still covered.

        Detection (same logic for Q1 / semi-annual / Q3 / annual reports):
        1. If ``as_of_date`` is already on or past the statutory disclosure
           deadline for the stock's market, the report must be published and
           the window is kept.
        2. Otherwise, probe the latest report period via ``probe``: readable
           data (even a zero value) means the report is published early, so
           the window is kept; ``None`` means the report is not published
           yet, so the window shifts back one quarter.

        Args:
            symbol: Stock symbol (normalized THS format, e.g. "600036.SH").
            as_of_date: The reference date.
            hk_stock_info: HK stock info cache (for A+H deadline selection).
            probe: Callable(symbol, report_date) -> float | None, returning
                readable data or ``None`` when the report period has no
                published data. Currently only the dividend path uses this
                method (:meth:`_get_dividend_or_none`).

        Returns:
            List of 4 report dates in format YYYYMMDD, shifted back one quarter
            when the latest report period is not yet published.
        """
        report_dates = self._get_past_4_report_dates(as_of_date)
        latest = report_dates[0]
        deadline = self._disclosure_deadline(symbol, latest, hk_stock_info)
        if as_of_date >= deadline:
            # Past the statutory deadline: the report must be published.
            return report_dates

        # Before the deadline: readable data means an early (published) report.
        if probe(symbol, latest) is not None:
            return report_dates

        fallback_dates = self._get_past_4_report_dates(
            self._previous_quarter_end(as_of_date)
        )
        logger.info(
            f"No report data published yet for {symbol} on report period "
            f"{latest} (as of {as_of_date}, deadline {deadline}); shifting "
            f"report window back one quarter to "
            f"{fallback_dates[-1]}..{fallback_dates[0]}"
        )
        return fallback_dates

    def _sum_over_report_window(
        self,
        symbol: str,
        as_of_date: date,
        hk_stock_info: dict[str, dict[str, object]],
        probe: Callable[[str, str], float | None],
        read_value: Callable[[str, str], float | None],
    ) -> float:
        """Resolve the report-date window for one symbol and sum a per-quarter value over it.

        Used by the dividend path to total the before-tax dividend over the
        past-4-quarter window (including the deadline-based shift when the
        latest report is unpublished). Quarters whose value is unavailable
        are skipped.

        Args:
            symbol: Stock symbol (normalized THS format, e.g. "600036.SH").
            as_of_date: The reference date.
            hk_stock_info: HK stock info cache (for A+H deadline selection).
            probe: Callable(symbol, report_date) -> float | None used to detect
                whether the latest report period is published.
            read_value: Callable(symbol, report_date) -> float | None reading
                the single-quarter value to sum.

        Returns:
            Sum of the single-quarter values over the resolved 4-report window.
        """
        report_dates = self._resolve_report_dates_for_symbol(
            symbol, as_of_date, hk_stock_info, probe=probe
        )
        total = 0.0
        for report_date in report_dates:
            value = read_value(symbol, report_date)
            if value is not None:
                total += value
        return total

    def _is_a_share(self, symbol: str) -> bool:
        """Check if symbol is A-share (ends with .SH, .SZ, or .BJ).

        Args:
            symbol: Stock symbol.

        Returns:
            True if A-share, False otherwise.
        """
        return symbol.endswith((".SH", ".SZ", ".BJ"))

    def _is_hk_stock(self, symbol: str) -> bool:
        """Check if symbol is Hong Kong stock (ends with .HK).

        Args:
            symbol: Stock symbol.

        Returns:
            True if HK stock, False otherwise.
        """
        return symbol.endswith(".HK")

    def _normalize_symbols(self, symbols: list[str]) -> tuple[dict[str, str], list[str]]:
        """Normalize HK stock symbols for the THS API and map them back to originals.

        THS expects HK symbols in 4-digit form, e.g. 00941.HK -> 0941.HK.

        Args:
            symbols: List of original symbols (e.g. ["600036.SH", "00941.HK"]).

        Returns:
            Tuple of (symbol_mapping, normalized_symbols) where symbol_mapping
            maps each normalized symbol back to its original symbol.
        """
        symbol_mapping = {}
        normalized_symbols = []
        for symbol in symbols:
            if len(symbol) == 8 and symbol.endswith(".HK"):
                normalized = symbol.removeprefix("0")
                symbol_mapping[normalized] = symbol
                normalized_symbols.append(normalized)
            else:
                symbol_mapping[symbol] = symbol
                normalized_symbols.append(symbol)
        return symbol_mapping, normalized_symbols

    def _load_hk_stock_cache(self) -> dict[str, dict[str, object]]:
        """Load HK stock info cache (red chip / A+H dual-listing status) from file.

        The cache maps normalized HK symbols (e.g., "0941.HK") to dicts with
        keys: symbol, is_red_chip, is_dual_listed, a_share_symbol.

        Returns:
            Dict mapping symbol to stock info, or empty dict if the file is
            missing or unreadable.
        """
        try:
            with open(HK_STOCK_CACHE_FILE, encoding="utf-8") as f:
                cache = json.load(f)
            logger.info("Loaded HK stock cache with %d entries", len(cache))
            return cache
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Failed to load HK stock cache: %s", e)
            return {}

    def _save_hk_stock_cache(self, cache: dict[str, dict[str, object]]) -> None:
        """Persist HK stock info cache to file (atomic write).

        Writes to a sibling ``.json.tmp`` file and renames it into place so a
        crash mid-write cannot corrupt the existing cache.

        Args:
            cache: Full cache dict to write.
        """
        try:
            HK_STOCK_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            tmp = HK_STOCK_CACHE_FILE.with_suffix(".json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
            tmp.replace(HK_STOCK_CACHE_FILE)
            logger.info("Saved HK stock cache with %d entries", len(cache))
        except (OSError, TypeError) as e:
            logger.warning("Failed to save HK stock cache: %s", e)

    def _classify_hk_stock_via_ai(
        self, symbol: str
    ) -> dict[str, object] | None:
        """Classify a single HK stock as red chip / A+H dual-listed via the AI agent client.

        Args:
            symbol: Normalized HK symbol, e.g. "0941.HK".

        Returns:
            Dict with keys ``symbol``, ``is_red_chip``, ``is_dual_listed`` and
            ``a_share_symbol``; or ``None`` if the AI call, parsing or
            validation fails (caller falls back to no-tax-adjustment).
        """
        code = symbol.removesuffix(".HK")
        padded_code = code.zfill(5)

        system_prompt = (
            "You are a financial-data assistant specialized in companies listed "
            "on the Hong Kong Stock Exchange. For the HK stock identified by the "
            "user, determine two binary facts and (when applicable) a mainland "
            "A-share symbol:\n"
            "1. is_red_chip: true if the company is a 'red chip' stock (红筹股) "
            "— a HK-listed company with mainland Chinese state-owned / central "
            "SOE controlling background but registered outside mainland China "
            "(e.g. in the Cayman Islands, Bermuda, or Hong Kong). Pure H-shares "
            "(registered in mainland China) are NOT red chips; neither are "
            "private-sector companies with no state-owned background.\n"
            "2. is_dual_listed: true if the same issuer is also listed on the "
            "mainland A-share market (Shanghai .SH or Shenzhen .SZ).\n"
            "3. a_share_symbol: when is_dual_listed is true, the A-share symbol "
            "in the form 'NNNNNN.SH' or 'NNNNNN.SZ' (6 digits + exchange "
            "suffix). Otherwise null.\n\n"
            "Reply with ONLY a JSON object, no markdown, no explanation, in "
            "this exact shape:\n"
            '{"is_red_chip": <bool>, "is_dual_listed": <bool>, '
            '"a_share_symbol": "<string or null>"}'
        )
        user_prompt = (
            f"HK stock symbol: {symbol} (code {code}, also written "
            f"{padded_code}.HK)"
        )

        try:
            result = ai_agent_client.chat_json(system_prompt, user_prompt)
        except Exception as e:
            logger.warning(f"AI classification failed for {symbol}: {e}")
            return None

        if not isinstance(result, dict):
            logger.warning(f"AI returned non-dict for {symbol}: {result!r}")
            return None

        is_red_chip = bool(result.get("is_red_chip", False))
        is_dual_listed = bool(result.get("is_dual_listed", False))
        a_share_symbol = result.get("a_share_symbol")
        if a_share_symbol is not None:
            a_share_symbol = str(a_share_symbol).strip().upper()
            if not re.fullmatch(r"\d{6}\.(SH|SZ|BJ)", a_share_symbol):
                logger.warning(
                    f"AI returned malformed a_share_symbol for {symbol}: "
                    f"{a_share_symbol!r}; treating as not dual-listed"
                )
                is_dual_listed = False
                a_share_symbol = None

        return {
            "symbol": symbol,
            "is_red_chip": is_red_chip,
            "is_dual_listed": is_dual_listed,
            "a_share_symbol": a_share_symbol,
        }

    def _resolve_hk_stock_info(
        self, normalized_symbols: list[str]
    ) -> dict[str, dict[str, object]]:
        """Return HK stock info for the given normalized symbols.

        Reads from the on-disk cache (:data:`HK_STOCK_CACHE_FILE`). Any symbol
        missing from the cache is classified via the AI agent client
        (:func:`ai_agent_client`) and the new entries are persisted back to
        the cache file so subsequent runs skip the AI call. Symbols whose
        classification fails are NOT cached (so the next run can retry) and
        are simply absent from the returned dict, which causes the caller to
        fall back to no tax adjustment (the existing default for unknown HK
        stocks).

        Args:
            normalized_symbols: Normalized HK symbols, e.g. ["0941.HK", "0700.HK"].

        Returns:
            Dict mapping each known symbol to its info dict (keys: symbol,
            is_red_chip, is_dual_listed, a_share_symbol). Missing symbols are
            omitted.
        """
        if not normalized_symbols:
            return self._load_hk_stock_cache()

        cache = self._load_hk_stock_cache()
        missing = [s for s in normalized_symbols if s not in cache]
        if not missing:
            return cache

        if not ai_agent_client.is_configured:
            logger.warning(
                f"DEEPSEEK_API_KEY not configured; skipping AI classification "
                f"for {len(missing)} missing HK symbols: {missing}"
            )
            return cache

        new_entries: dict[str, dict[str, object]] = {}
        for symbol in missing:
            info = self._classify_hk_stock_via_ai(symbol)
            if info is not None:
                new_entries[symbol] = info

        if new_entries:
            cache.update(new_entries)
            self._save_hk_stock_cache(cache)
            logger.info(
                "Added %d new HK stock cache entries via AI", len(new_entries)
            )
        else:
            logger.warning(
                f"AI classification produced no new entries for {missing}"
            )

        return cache

    def _get_dividend_or_none(self, symbol: str, report_date: str, retry: bool = True) -> float | None:
        """Get dividend per share before tax for a report date, excluding special dividends.

        Unlike :meth:`_get_dividend_before_tax` (which collapses "no data" to
        0.0), this returns ``None`` when the report period's dividend data
        cannot be read at all (report not published yet, or THS error), so
        callers can distinguish "published with zero dividend" from "no data
        yet".

        Args:
            symbol: Stock symbol.
            report_date: Report date in format YYYYMMDD.
            retry: Whether to retry with reconnection on failure.

        Returns:
            Dividend per share before tax, excluding special dividends;
            ``None`` if the data cannot be read.
        """
        # "BB" for original currency
        ths_result = THS_BD(symbol, "divi_per_share_btax_exspecial", f"{report_date},BB")
        if ths_result.errorcode != 0:
            if retry and self._reconnect_if_needed(ths_result.errorcode):
                return self._get_dividend_or_none(symbol, report_date, retry=False)
            logger.warning(
                f"Failed to get dividend for {symbol} on {report_date}: {ths_result.errmsg}"
            )
            return None

        try:
            # THS_BD returns a DataFrame with columns like:
            # thscode | dividend_per_share_before_tax
            # 600036.SH | 2.016
            df = ths_result.data

            # Find the dividend column (column name matches the indicator)
            if "divi_per_share_btax_exspecial" not in df.columns:
                logger.warning(f"Unexpected THS_BD result format for {symbol}: {df}")
                return None
            value = df["divi_per_share_btax_exspecial"].iloc[0]
            # None / NaN means the report period has no published data yet
            if value is None or (isinstance(value, float) and pd.isna(value)):
                return None
            return float(value)
        except (IndexError, ValueError, TypeError, KeyError) as e:
            logger.warning(f"Failed to parse dividend for {symbol} on {report_date}: {e}")
            return None

    def _get_dividend_before_tax(self, symbol: str, report_date: str, retry: bool = True) -> float:
        """Get dividend per share before tax for a given report date, excluding special dividends.

        Args:
            symbol: Stock symbol.
            report_date: Report date in format YYYYMMDD.
            retry: Whether to retry with reconnection on failure.

        Returns:
            Dividend per share before tax, excluding special dividends, or 0.0 if failed.
        """
        value = self._get_dividend_or_none(symbol, report_date, retry=retry)
        return value if value is not None else 0.0

    def _get_cumulative_net_income(self, symbol: str, report_date: str, retry: bool = True) -> float | None:
        """Get period-cumulative net income attributable to parent for a report date.

        Use THS_BD(symbol, "ni_attr_to_cs", f"{report_date},1,CNY")

        Args:
            symbol: Stock symbol.
            report_date: Report date in format YYYYMMDD.
            retry: Whether to retry with reconnection on failure.

        Returns:
            Cumulative net income in CNY, or None if failed or not available.
        """
        ths_result = THS_BD(symbol, "ni_attr_to_cs", f"{report_date},1,CNY")
        if ths_result.errorcode != 0:
            if retry and self._reconnect_if_needed(ths_result.errorcode):
                return self._get_cumulative_net_income(symbol, report_date, retry=False)
            logger.warning(
                f"Failed to get cumulative net income for {symbol} on {report_date}: {ths_result.errmsg}"
            )
            return None

        try:
            df = ths_result.data
            if "ni_attr_to_cs" in df.columns:
                value = df["ni_attr_to_cs"].iloc[0]
            else:
                return None

            if value is None or (isinstance(value, float) and pd.isna(value)):
                return None
            return float(value)
        except (IndexError, ValueError, TypeError, KeyError):
            return None

    def _get_ttm_net_income(self, symbol: str, as_of_date: date, retry: bool = True) -> float:
        """Get trailing-12-month net income attributable to parent via ``ni_attr_to_cs``.

        THS only provides single-quarter net income (``sq_ni_ge``) for
        companies that publish quarterly reports. Companies that publish only
        annual and semi-annual reports (common for HK listings) have no
        single-quarter data, so the past-year NI is computed from the
        period-cumulative indicator ``ni_attr_to_cs`` (归母净利润, cumulative
        within the fiscal year):

        - Latest published report is a fiscal-year end: TTM = C(latest)
        - Otherwise: TTM = C(latest) + C(prev fiscal-year end) − C(same period
          one year ago)

        THS labels every annual report with 12/31 of the calendar year in
        which the fiscal year ends, even for HK companies whose fiscal year
        ends in March or June (e.g. the FY2026 annual of 3818.HK, published
        June 2026, is stored under 20261231). Such labels can therefore be
        dated after ``as_of_date`` although the report is already published.
        The current calendar year's quarter-end labels are included in the
        candidates for that reason; THS returns no value for periods whose
        reports have not been published yet, so unpublished labels are
        skipped naturally.

        Args:
            symbol: Stock symbol (normalized THS format, e.g. "600036.SH").
            as_of_date: The reference date.
            retry: Whether to retry with reconnection on failure.

        Returns:
            Trailing-12-month net income in CNY; 0.0 if unavailable.
        """
        # Current calendar year's quarter-end labels on/after as_of_date,
        # most recent first (see docstring on THS's annual-report labeling).
        candidates: list[str] = []
        for month, day in ((12, 31), (9, 30), (6, 30), (3, 31)):
            quarter_end = date(as_of_date.year, month, day)
            if quarter_end >= as_of_date:
                candidates.append(quarter_end.strftime("%Y%m%d"))

        # Past quarter-end report dates, most recent first, ~3 years back.
        ref = as_of_date
        for _ in range(3):
            candidates.extend(self._get_past_4_report_dates(ref))
            ref = self._previous_quarter_end(ref)
        seen = set()
        candidates = [d for d in candidates if not (d in seen or seen.add(d))]

        # Find the most recent published report period.
        latest = None
        latest_val = None
        for d in candidates:
            val = self._get_cumulative_net_income(symbol, d, retry=retry)
            if val is not None:
                latest = d
                latest_val = val
                break
        if latest is None:
            return 0.0

        latest_date = date(
            int(latest[0:4]), int(latest[4:6]), int(latest[6:8])
        )
        if latest_date.month == 12:
            # Latest report is a fiscal-year end (THS labels every annual
            # report with 12/31): it already covers 12 months.
            return latest_val

        same = latest_date.replace(year=latest_date.year - 1)
        same_val = self._get_cumulative_net_income(
            symbol, same.strftime("%Y%m%d"), retry=retry
        )
        if same_val is None:
            return latest_val if latest_val > 0 else 0.0

        # Previous fiscal-year end strictly before the latest report.
        fy_end_val = None
        for d in candidates:
            if d >= latest:
                continue
            dd = date(int(d[0:4]), int(d[4:6]), int(d[6:8]))
            if dd.month == 12:
                fy_end_val = self._get_cumulative_net_income(symbol, d, retry=retry)
                break
        if fy_end_val is None:
            return latest_val if latest_val > 0 else 0.0

        return latest_val + fy_end_val - same_val

    def get_dividend_after_tax_past_year(
        self,
        symbols: list[str],
        as_of_date: date,
        hkd_cny_rate: float,
    ) -> list[tuple[str, float]]:
        """Calculate after-tax dividend for the past year for given symbols, excluding special dividends.

        For each symbol:
        1. A-share: after-tax dividend = before-tax dividend
        2. HK red chip: after-tax dividend = before-tax dividend * 0.9
        3. HK non-red-chip with A+H dual-listing:
           after-tax dividend = A-share before-tax dividend / hkd_cny_rate * 0.9
        4. HK non-red-chip without A+H dual-listing:
           after-tax dividend = before-tax dividend

        HK red chip / A+H dual-listing status is read from
        data/hk_stock_cache.json. HK symbols missing from the cache are
        classified via the AI agent client (DeepSeek V4 Flash) and the results
        are persisted to the cache for future runs. Symbols whose
        classification fails fall back to no tax adjustment.

        Args:
            symbols: List of stock symbols.
            as_of_date: Reference date for calculating past year dividends.
            hkd_cny_rate: HKD to CNY exchange rate.

        Returns:
            List of tuples (symbol, after_tax_dividend).
        """
        # Normalize symbols for the THS API (00941.HK -> 0941.HK)
        symbol_mapping, normalized_symbols = self._normalize_symbols(symbols)

        # Load HK stock info from cache; resolve missing HK entries via the
        # AI agent client and persist new entries back to the cache file.
        hk_symbols = [s for s in normalized_symbols if self._is_hk_stock(s)]
        hk_stock_info = self._resolve_hk_stock_info(hk_symbols)

        results = []

        for normalized_symbol in normalized_symbols:
            original_symbol = symbol_mapping[normalized_symbol]
            # Sum before-tax dividend over the resolved past-4-quarter window
            total_dividend_before_tax = self._sum_over_report_window(
                normalized_symbol,
                as_of_date,
                hk_stock_info,
                probe=self._get_dividend_or_none,
                read_value=self._get_dividend_before_tax,
            )

            # Calculate after-tax dividend based on stock category
            if self._is_a_share(normalized_symbol):
                # A-share: no tax adjustment
                after_tax_dividend = total_dividend_before_tax
            elif self._is_hk_stock(normalized_symbol):
                info = hk_stock_info.get(normalized_symbol, {})
                is_red_chip = info.get("is_red_chip", False)
                is_dual_listed = info.get("is_dual_listed", False)
                a_share_symbol = info.get("a_share_symbol")

                if is_red_chip:
                    # Red chip: apply 10% tax
                    after_tax_dividend = total_dividend_before_tax * 0.9
                elif is_dual_listed and a_share_symbol:
                    # Non-red-chip with A+H dual-listing:
                    # Get A-share dividend, convert to HKD, then apply 10% tax
                    a_share_dividend = self._sum_over_report_window(
                        a_share_symbol,
                        as_of_date,
                        hk_stock_info,
                        probe=self._get_dividend_or_none,
                        read_value=self._get_dividend_before_tax,
                    )
                    after_tax_dividend = (a_share_dividend / hkd_cny_rate) * 0.9
                else:
                    # Non-red-chip without A+H dual-listing: no tax adjustment
                    after_tax_dividend = total_dividend_before_tax
            else:
                # Unknown category, treat as no tax adjustment
                logger.warning(f"Unknown stock category for {normalized_symbol}, treating as no tax")
                after_tax_dividend = total_dividend_before_tax

            # Return result with original symbol (not normalized)
            results.append((original_symbol, after_tax_dividend))
            logger.debug(
                f"Symbol: {original_symbol}, Before tax: {total_dividend_before_tax}, "
                f"After tax: {after_tax_dividend}"
            )

        return results

    def _get_most_recent_year_end(self, as_of_date: date) -> str:
        """Get the most recent year-end (YYYYMMDD) before or on as_of_date.

        Args:
            as_of_date: The reference date.

        Returns:
            Year-end date string in YYYYMMDD format.
        """
        year = as_of_date.year
        year_end = date(year, 12, 31)
        if year_end > as_of_date:
            year_end = date(year - 1, 12, 31)
        return year_end.strftime("%Y%m%d")

    def get_stock_financials(
        self,
        symbols: list[str],
        as_of_date: date,
        retry: bool = True,
    ) -> dict[str, dict[str, float]]:
        """Fetch stock financial indicators from THS.
        All values are in CNY. If CNY is not the original currency, THS converts the value to CNY.

        Fetches total_shares, ni_attr_to_cs (归母净利润, trailing 12 months), and
        equity_belong_to_parent (归母股东权益) for the given symbols.

        ni_attr_to_cs is the trailing-12-month (TTM) net income attributable to
        parent, computed by :meth:`_get_ttm_net_income` from the period-cumulative
        ``ni_attr_to_cs`` indicator. This works for both quarterly reporters and
        companies that publish only annual and semi-annual reports (for which THS
        has no single-quarter data).

        Args:
            symbols: List of stock symbols.
            as_of_date: The query date.
            retry: Whether to retry with reconnection on failure.

        Returns:
            Dict mapping original symbol to dict with keys:
            total_shares, ni_to_parent, equity_to_parent.
            All values are in CNY.
        """
        # Normalize symbols for the THS API (00941.HK -> 0941.HK)
        symbol_mapping, normalized_symbols = self._normalize_symbols(symbols)

        # Calculate TTM NI for each symbol individually because disclosure
        # timing may differ across stocks
        ni_sum = {}
        for sym in normalized_symbols:
            ni_sum[sym] = self._get_ttm_net_income(sym, as_of_date, retry=retry)

        # Build parameters for THS_BD
        # total_shares: query date
        total_shares_param = as_of_date.strftime("%Y-%m-%d")

        # equity_belong_to_parent: latest report period
        # 8: latest report period， 1：consolidated report
        equity_param = "8,1,CNY"

        params = f"{total_shares_param};{equity_param}"
        indicators = "total_shares;equity_belong_to_parent"
        symbols_str = ",".join(normalized_symbols)

        ths_result = THS_BD(symbols_str, indicators, params)
        if ths_result.errorcode != 0:
            if retry and self._reconnect_if_needed(ths_result.errorcode):
                return self.get_stock_financials(symbols, as_of_date, retry=False)
            logger.error(f"Failed to get stock financials: {ths_result.errmsg}")
            return {}

        try:
            df = ths_result.data
            result = {}
            for _, row in df.iterrows():
                thscode = row["thscode"]
                original_symbol = symbol_mapping.get(thscode, thscode)

                total_shares = float(row["total_shares"]) if pd.notna(row.get("total_shares")) else 0.0
                equity_to_parent = float(row["equity_belong_to_parent"]) if pd.notna(row.get("equity_belong_to_parent")) else 0.0

                result[original_symbol] = {
                    "total_shares": total_shares,
                    "ni_to_parent": ni_sum.get(thscode, 0.0),
                    "equity_to_parent": equity_to_parent,
                }

            return result
        except Exception as e:
            logger.error(f"Failed to parse stock financials: {e}")
            return {}

    def fetch_historical_prices(
        self,
        symbol: str,
        asset_type: str,
        start_date: date,
        end_date: date,
        adjust: str = "",
        retry: bool = True,
    ) -> tuple[pd.DataFrame, str]:
        """
        Fetch historical daily close prices from THS（同花顺） Data API.
        Clean Prices for Chinese and HK Bonds(Compatible with Xueqiu)
        Args:
            symbol: Asset symbol (e.g., "000001.SZ", "00700.HK")
            asset_type: Asset type ("stock" or "etf" or "bond" or "index")
            start_date: Start date as datetime.date object
            end_date: End date as datetime.date object
            adjust: Adjustment type ("" for non-adjusted, "qfq" for forward-adjustment, "hfq" for backward-adjustment)
                    No adjustment is applied for bonds.
            retry: Whether to retry with reconnection on failure.

        Returns:
            Tuple of (DataFrame with historical price data containing 'date' and 'close' columns, source name)
        """

        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        # TongHuaShun API requires only 4 digits symbol for HK stocks
        # Remove the first 0 at prefix for HK stocks: 00941.HK -> 0941.HK
        if asset_type == "stock":
            _, (symbol,) = self._normalize_symbols([symbol]) 

        match adjust:
            case "":  # 不复权
                params = ""
            case "qfq":  # 前复权，分红再投
                params = "CPS:2;"  
            case "hfq":  # 后复权，分红再投
                params = "CPS:3;"  
            case _:  # 不复权
                params = ""
        
        match asset_type:
            case "bond":
                ths_result = THS_HQ(symbol, 'close', "PriceType:2", start_str, end_str)
            case _:
                ths_result = THS_HQ(symbol, 'close', params, start_str, end_str)
        
        if ths_result.errorcode != 0:
            if retry and self._reconnect_if_needed(ths_result.errorcode):
                return self.fetch_historical_prices(
                    symbol, asset_type, start_date, end_date, adjust, retry=False
                )
            logger.error(f"THS fetch historical prices failed: {ths_result.errmsg}")
            return pd.DataFrame(), ""
        
        df = ths_result.data.rename(columns={"time": "date"})
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]
        return df[["date", "close"]], "ths"

    def fetch_historical_daily(
        self,
        code: str,
        start_date: date,
        end_date: date,
        retry: bool = True,
    ) -> pd.DataFrame:
        """Fetch daily OHLCV bars from the THS_HD history API.

        Used by the gold data loader for codes such as "AU9999.SHG" and
        "518880.SH" where symbol conventions differ from THS_HQ. Amount is
        converted from CNY to 亿元 to match the seed CSV convention.

        Args:
            code: iFinD code (e.g. "AU9999.SHG", "518880.SH")
            start_date: Start date as datetime.date object
            end_date: End date as datetime.date object
            retry: Whether to retry with reconnection on failure.

        Returns:
            DataFrame with date/open/high/low/close/volume/amt columns,
            or an empty DataFrame when unavailable.
        """
        fields = ";".join(DAILY_BAR_FIELDS)
        ths_result = THS_HD(
            code,
            fields,
            "",
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
        )

        if ths_result.errorcode != 0:
            if retry and self._reconnect_if_needed(ths_result.errorcode):
                return self.fetch_historical_daily(
                    code, start_date, end_date, retry=False
                )
            logger.error(
                f"THS fetch daily bars failed for {code}: {ths_result.errmsg}"
            )
            return pd.DataFrame()

        if ths_result.data is None or ths_result.data.empty:
            return pd.DataFrame()

        return normalize_daily_bars(ths_result.data, start_date, end_date)


class IFindHTTPDataSource:
    """iFinD HTTP fallback for daily bars.

    Used when the SDK is unavailable; authenticates with the
    IFIND_DATASOURCE_KEY refresh token from the repo root .env.
    """

    def __init__(self):
        self._access_token: str | None = None

    @property
    def configured(self) -> bool:
        return bool(_ENV.get("IFIND_DATASOURCE_KEY"))

    def _post_json(self, url: str, headers: dict, payload: dict) -> dict:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))

    def _get_access_token(self) -> str | None:
        key = _ENV.get("IFIND_DATASOURCE_KEY")
        if not key:
            logger.error("Missing IFIND_DATASOURCE_KEY in .env; HTTP fallback skipped")
            return None
        token = self._post_json(
            f"{IFIND_HTTP_BASE}/get_access_token",
            {"Content-Type": "application/json", "refresh_token": key},
            {},
        )
        if token.get("errorcode") != 0:
            logger.error(
                f"iFinD HTTP access_token failed (errorcode={token.get('errorcode')}): "
                f"{token.get('errmsg')}"
            )
            return None
        self._access_token = token["data"]["access_token"]
        return self._access_token

    def fetch_historical_daily(
        self,
        code: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """Fetch daily bars over HTTP, mirroring THSDataSource.fetch_historical_daily."""
        access_token = self._access_token or self._get_access_token()
        if not access_token:
            return pd.DataFrame()

        result = self._post_json(
            f"{IFIND_HTTP_BASE}/cmd_history_quotation",
            {
                "Content-Type": "application/json",
                "access_token": access_token,
                "ifindlang": "cn",
            },
            {
                "codes": code,
                "indicators": ",".join(DAILY_BAR_FIELDS),
                "startdate": start_date.strftime("%Y-%m-%d"),
                "enddate": end_date.strftime("%Y-%m-%d"),
            },
        )
        if result.get("errorcode") != 0:
            logger.error(
                f"iFinD HTTP daily bars failed (errorcode={result.get('errorcode')}): "
                f"{result.get('errmsg')}"
            )
            self._access_token = None
            return pd.DataFrame()

        tables = result.get("tables") or []
        if not tables or not tables[0].get("table"):
            return pd.DataFrame()

        table = tables[0]
        df = pd.DataFrame(table["table"])
        df["date"] = table["time"]
        return normalize_daily_bars(df, start_date, end_date)


def normalize_daily_bars(
    df: pd.DataFrame,
    start_date: date,
    end_date: date,
) -> pd.DataFrame:
    """Normalize an iFinD daily-bar response to the seed CSV column layout."""
    df = df.rename(columns={"time": "date", "amount": "amt"}).copy()
    df["date"] = pd.to_datetime(df["date"]).dt.date
    for col in DAILY_BAR_FIELDS:
        if col not in df.columns:
            logger.error(f"iFinD daily bars missing field: {col}")
            return pd.DataFrame()
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=DAILY_BAR_FIELDS)
    df["amt"] = df["amt"] / 1e8
    df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]
    df = df.sort_values("date").drop_duplicates("date", keep="last")
    return df.reset_index(drop=True)[["date", *DAILY_BAR_FIELDS]]


# Global instance for convenience
akshare_source = AKShareDataSource()
ths_source = THSDataSource()
ifind_http_source = IFindHTTPDataSource()
