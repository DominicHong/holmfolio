"""iFind MCP agent client for financial data queries.

Wraps the official ``ifind-finance-data`` skill package shipped under
:file:`backend/ai/ifind-finance-data/` (see its ``SKILL.md`` and
``references/`` docs). The skill talks to the iFind MCP gateway
(``https://api-mcp.51ifind.com:8643``) using natural-language ``query``
arguments, so this agent mirrors :class:`backend.ai.ai_client.AIAgentClient`
in structure and relies on the AI client to turn the free-form MCP answer
into the same structured financial fields the THS ``THS_BD`` path produces
(``total_shares``, ``ni_to_parent``, ``equity_to_parent``).

Auth token resolution:
- Read from the ``IFIND_MCP_KEY`` environment variable (loaded from the
  repo-root ``.env`` via :func:`dotenv.load_dotenv`).
- Written into ``ifind-finance-data/mcp_config.json`` on first use when it is
  missing or still the placeholder (that file is gitignored), so both
  ``call.py`` and ``call-node.js`` keep working.

Reliability features:
- Lazy loading: ``call.py`` is only imported (and the config file only
  touched) on the first actual request, so importing this module is safe
  without a key. Use :attr:`is_configured` to check availability.
- Request throttling: the free tier of the iFind MCP allows at most 2
  concurrent requests per second; a module-level lock + delay paces calls.
- Structured extraction via :mod:`backend.ai.ai_client`: the MCP answer is a
  markdown table, so the AI parses it into a strict JSON schema where every
  number keeps its verbatim unit; unit conversion is done deterministically
  in Python (:meth:`_parse_amount`) instead of trusting the model's arithmetic.
"""

import json
import os
import re
import sys
import threading
import time
from datetime import date
from importlib import util as _import_util
from pathlib import Path

from dotenv import load_dotenv

from backend import logger
from backend.ai.ai_client import ai_agent_client

# Load .env once at module import. Idempotent: existing env vars are not
# overridden, and a missing .env file is a no-op.
load_dotenv()

IFIND_MCP_KEY_ENV = "IFIND_MCP_KEY"
_PLACEHOLDER_TOKEN = "your ifind-mcp key"

# The official skill package (call.py / call-node.js / mcp_config.json).
_SKILL_DIR = Path(__file__).resolve().parent / "ifind-finance-data"
_CONFIG_FILE = _SKILL_DIR / "mcp_config.json"
_CALL_PY = _SKILL_DIR / "call.py"

# Free tier of the iFind MCP allows 2 requests/second; pace ourselves at ~1.7/s.
_REQUEST_INTERVAL = 0.6

_FINANCIAL_KEYS = ("total_shares", "ni_to_parent", "equity_to_parent")

# Server type per symbol suffix: A-shares use the stock server, HK stocks the
# global_stock server (mirrors the THS get_stock_financials split).
_SERVER_BY_SUFFIX = {".SH": "stock", ".SZ": "stock", ".HK": "global_stock"}

_TOOL_BY_SERVER = {"stock": "get_stock_financials", "global_stock": "global_stock_financial"}


class IFindMCPAgent:
    """Agent that queries financial data through the iFind MCP skill package.

    Importing this module is safe without a key: the token is resolved lazily
    and ``call.py`` is imported only on first use. Use :attr:`is_configured`
    to check availability without triggering any network or file I/O.

    The main entry point :meth:`get_financials` returns exactly the same
    structure as ``THSDataSource.get_stock_financials`` (keys
    ``total_shares``, ``ni_to_parent``, ``equity_to_parent``, values in
    shares / CNY) so the two data sources can be compared side by side, e.g.
    by :mod:`backend.ai.verify_ifind_vs_ths`.
    """

    def __init__(self):
        self._call = None
        self._call_lock = threading.Lock()
        self._last_request_at = 0.0

    @property
    def is_configured(self) -> bool:
        """True when an iFind MCP auth token is available for requests."""
        return bool(self._resolve_token())

    # ------------------------------------------------------------------
    # Token / skill bootstrap
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_token() -> str:
        """Return the auth token from the environment or the config file."""
        token = os.environ.get(IFIND_MCP_KEY_ENV, "").strip()
        if token and token != _PLACEHOLDER_TOKEN:
            return token
        try:
            token = json.loads(_CONFIG_FILE.read_text(encoding="utf-8")).get("auth_token", "")
            token = token.strip()
            if token and token != _PLACEHOLDER_TOKEN:
                return token
        except (OSError, ValueError, TypeError):
            pass
        return ""

    def _ensure_config(self) -> None:
        """Write the env token into mcp_config.json when missing/placeholder.

        The file is gitignored (see repo .gitignore), so the raw skill
        scripts (call.py / call-node.js) also work with the same token.
        """
        token = os.environ.get(IFIND_MCP_KEY_ENV, "").strip()
        if not token or token == _PLACEHOLDER_TOKEN:
            return
        try:
            data = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            data = {}
        if data.get("auth_token") == token:
            return
        data["auth_token"] = token
        _CONFIG_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.debug("Wrote iFind MCP token into %s", _CONFIG_FILE)

    def _load_call(self):
        """Import the skill's call.py lazily and return its module."""
        if self._call is not None:
            return self._call

        if not self.is_configured:
            raise RuntimeError(
                f"Missing API key: set {IFIND_MCP_KEY_ENV} in .env "
                f"(iFind MCP portal: https://mcp.51ifind.com)"
            )

        with self._call_lock:
            if self._call is not None:
                return self._call
            if not _CALL_PY.exists():
                raise RuntimeError(f"iFind MCP skill not found: {_CALL_PY}")
            self._ensure_config()
            spec = _import_util.spec_from_file_location("_ifind_call", _CALL_PY)
            if spec is None or spec.loader is None:
                raise RuntimeError(f"Failed to load iFind MCP skill: {_CALL_PY}")
            module = _import_util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # Re-check the token the skill module read from the config file.
            if module.AUTH_TOKEN in (None, "", _PLACEHOLDER_TOKEN):
                raise RuntimeError(
                    f"iFind MCP skill has no valid auth_token in {_CONFIG_FILE}"
                )
            self._call = module
            return module

    def _throttle(self) -> None:
        """Pace requests to respect the iFind MCP free-tier rate limit."""
        with self._call_lock:
            elapsed = time.monotonic() - self._last_request_at
            if elapsed < _REQUEST_INTERVAL:
                time.sleep(_REQUEST_INTERVAL - elapsed)
            self._last_request_at = time.monotonic()

    # ------------------------------------------------------------------
    # Low-level MCP access
    # ------------------------------------------------------------------

    def list_tools(self, server_type: str) -> list[str]:
        """List tool names currently available for a server type."""
        call = self._load_call()
        self._throttle()
        result = call.list_tools(server_type)
        if not result.get("ok"):
            raise RuntimeError(
                f"iFind MCP list_tools({server_type}) failed: {result.get('error')}"
            )
        tools = result["data"]["result"]["tools"]
        return [t["name"] for t in tools if isinstance(t, dict) and t.get("name")]

    def call_tool(self, server_type: str, tool_name: str, params: dict) -> dict:
        """Call an iFind MCP tool directly and return the raw result dict.

        Raises:
            RuntimeError: when the MCP call itself fails (not ok / HTTP error).
        """
        call = self._load_call()
        self._throttle()
        result = call.call(server_type, tool_name, params)
        if not result.get("ok"):
            raise RuntimeError(
                f"iFind MCP call({server_type}, {tool_name}) failed: "
                f"{result.get('error')} status={result.get('status_code')}"
            )
        return result["data"]

    @staticmethod
    def extract_answer_text(result: dict) -> str:
        """Pull the human-readable markdown answer out of a raw MCP result.

        The MCP gateway wraps the answer as
        ``result.content[0].text`` -> JSON string ``{"code":1, "data": ...}``
        where ``data`` is itself a JSON-encoded string containing
        ``{"answer": "<markdown table>", ...}``.
        """
        try:
            content = result["result"]["content"]
            text = content[0]["text"] if isinstance(content, list) else ""
            outer = json.loads(text)
            inner = json.loads(outer["data"]) if isinstance(outer.get("data"), str) else outer
            answer = inner.get("answer", "")
            return answer if isinstance(answer, str) else json.dumps(inner, ensure_ascii=False)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to parse iFind MCP answer envelope: {e}")
            return json.dumps(result, ensure_ascii=False, default=str)

    # ------------------------------------------------------------------
    # Structured financial data (financial page fields)
    # ------------------------------------------------------------------

    def get_financials(
        self, symbols: list[str], as_of_date: date
    ) -> dict[str, dict[str, float]]:
        """Fetch total_shares / ni_to_parent / equity_to_parent via iFind MCP.

        Mirrors ``THSDataSource.get_stock_financials``: results are keyed by
        the original symbol, values in shares / CNY (A-shares) with
        ``ni_to_parent`` as the sum of the four most recent single quarters'
        net income attributable to parent.

        The MCP server is chosen by symbol suffix (``.SZ``/``.SH`` -> stock,
        ``.HK`` -> global_stock) and symbols are batched by server type, max
        5 subjects per query as recommended by the skill docs.

        Returns:
            Dict mapping original symbol to dict with keys total_shares,
            ni_to_parent, equity_to_parent (0.0 when the MCP answer lacks a
            value; only symbols mentioned in the answer are included).

        Raises:
            RuntimeError: when no iFind MCP token is configured.
        """
        if not symbols:
            return {}

        batches: dict[str, list[str]] = {"stock": [], "global_stock": []}
        for symbol in symbols:
            suffix = symbol[-3:].upper() if len(symbol) >= 3 else ""
            batches[_SERVER_BY_SUFFIX.get(suffix, "stock")].append(symbol)

        result: dict[str, dict[str, float]] = {}
        for server_type, batch in batches.items():
            for i in range(0, len(batch), 5):
                chunk = batch[i : i + 5]
                answer = self._query_financials_chunk(server_type, chunk, as_of_date)
                extracted = self._extract_financials(chunk, answer)
                result.update(extracted)
        return result

    def _query_financials_chunk(
        self, server_type: str, symbols: list[str], as_of_date: date
    ) -> str:
        """Build the natural-language query for one chunk and call the MCP."""
        names = "、".join(symbols)
        quarter_dates = self._past_4_quarter_ends(as_of_date)
        quarters = "、".join(d.strftime("%Y-%m-%d") for d in quarter_dates)
        query = (
            f"查询{names}的：1) 截至{as_of_date.strftime('%Y-%m-%d')}的总股本"
            f"（单位：股）；2) 最新报告期的归属于母公司股东的权益合计"
            f"（单位：元）；3) 报告期{quarters}各期的归属于母公司股东的净利润"
            f"（单季度值，单位：元）。A股用人民币CNY计价。"
        )
        tool = _TOOL_BY_SERVER[server_type]
        logger.info(
            f"iFind MCP query -> server={server_type}, tool={tool}, "
            f"symbols={symbols}, as_of={as_of_date}"
        )
        raw = self.call_tool(server_type, tool, {"query": query})
        return self.extract_answer_text(raw)

    @staticmethod
    def _past_4_quarter_ends(as_of_date: date) -> list[date]:
        """Report-end dates of the 4 most recent quarters ending on/before as_of_date.

        Example: 2026-06-30 -> [2026-06-30, 2026-03-31, 2025-12-31, 2025-09-30].
        """
        dates: list[date] = []
        qm = as_of_date.month
        qy = as_of_date.year
        while True:
            em = (3 * ((qm - 1) // 3)) + 3  # quarter end month: 3/6/9/12
            d = date(qy, em, 30 if em == 6 else 31)
            if d <= as_of_date:
                dates.append(d)
            if len(dates) == 4:
                break
            qm = 3 if em == 3 else em - 3
            if em == 3:
                qy -= 1
        return dates

    @staticmethod
    def _parse_amount(text: str | int | float | None) -> float | None:
        """Convert a value with Chinese unit (e.g. "252.1985亿股", "1.2824万亿元") to a number.

        Multipliers: 万亿=1e12, 千亿=1e11, 百亿=1e10, 亿=1e8, 千万=1e7,
        百万=1e6, 万=1e4, 千=1e3. Plain numbers (with optional commas) pass
        through unchanged. Returns None for empty/'-'/'--'/None.
        """
        if text is None:
            return None
        if isinstance(text, (int, float)):
            return float(text)
        s = str(text).strip().replace(",", "").replace("，", "")
        if not s or s in {"-", "--", "—", "无", "暂无", "N/A", "null"}:
            return None
        multipliers = [
            ("万亿", 1e12), ("千亿", 1e11), ("百亿", 1e10), ("十万", 1e5),
            ("亿", 1e8), ("千万", 1e7), ("百万", 1e6), ("万", 1e4), ("千", 1e3),
        ]
        for unit, mult in multipliers:
            if unit in s:
                num_part = re.sub(r"[^\d.\-+]", "", s.split(unit)[0])
                if not num_part:
                    return None
                return float(num_part) * mult
        return float(s) if re.fullmatch(r"-?\d+(\.\d+)?", s) else None

    def _extract_financials(self, symbols: list[str], answer: str) -> dict[str, dict[str, float]]:
        """Parse the free-form MCP answer into structured financial numbers.

        Uses :mod:`backend.ai.ai_client` to map the markdown answer onto a
        strict JSON schema. Every value keeps its verbatim unit string (e.g.
        "252.1985亿股") so the deterministic :meth:`_parse_amount` does the
        unit conversion. ``ni_to_parent`` must be the sum of the four single
        quarters; if the answer provides fewer, the available ones are summed.
        """
        if not ai_agent_client.is_configured:
            logger.warning(
                "DEEPSEEK_API_KEY not configured; cannot parse iFind MCP "
                "answer into structured financials. Raw answer: %s", answer[:200]
            )
            return {}

        system_prompt = (
            "You convert a financial-data answer (a markdown table) into strict JSON. "
            "The user gives the list of symbols and the raw answer text. "
            "Rules:\n"
            "- Reply with ONLY a JSON object; keys are exactly the given symbols.\n"
            "- For each symbol output: total_shares (总股本, verbatim string with its "
            "unit, e.g. \"252.1985亿股\" or \"9092234841\"), equity_to_parent "
            "(归属于母公司股东的权益合计, verbatim string with unit, e.g. \"1.2824万亿元\"), "
            "ni_to_parent (sum of the four single-quarter 归母净利润 values given in the "
            "answer, written in the same unit as the quarterly values, e.g. \"1519.66亿元\"), "
            "report_periods (list of report dates actually used).\n"
            "- Sum the four quarter values yourself when several rows are present; if "
            "fewer are available, sum what exists.\n"
            "- If a field is missing or has no data, use null.\n"
            "- Do not invent numbers; copy them from the answer verbatim. "
            "Unit conversion is handled later, never do it yourself."
        )
        user_prompt = (
            f"Symbols: {json.dumps(symbols, ensure_ascii=False)}\n\n"
            f"Raw iFind MCP answer:\n{answer}"
        )
        data = ai_agent_client.chat_json(system_prompt, user_prompt)
        if not isinstance(data, dict):
            logger.warning(f"Unexpected AI parse result type: {type(data)}")
            return {}

        result: dict[str, dict[str, float]] = {}
        for symbol in symbols:
            entry = data.get(symbol)
            if not isinstance(entry, dict):
                continue
            parsed: dict[str, float] = {}
            for key in _FINANCIAL_KEYS:
                value = self._parse_amount(entry.get(key))
                parsed[key] = value if value is not None else 0.0
            if any(parsed.values()):
                result[symbol] = parsed
        return result


# Module-level singleton. Safe to import without IFIND_MCP_KEY: the token is
# resolved and call.py loaded only on the first actual request.
ifind_mcp_agent = IFindMCPAgent()
