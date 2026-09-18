"""Verify iFind MCP financial data against the THS_BD (THSDataSource) path.

The Financial page (``GET /api/v1/portfolios/{id}/financial-positions`` ->
``PortfolioService.fetch_and_save_financial_positions``) computes PE/PB from
``THSDataSource.get_stock_financials`` which calls ``THS_BD`` with indicators
``total_shares`` / ``equity_belong_to_parent`` / per-quarter
``sq_ni_ge``. This script fetches the same three fields
(``total_shares``, ``ni_to_parent``, ``equity_to_parent``) through the iFind
MCP agent (:mod:`backend.ai.ifind_mcp_agent`) and prints a side-by-side
comparison.

Usage (from the repo root):

    python -m backend.ai.verify_ifind_vs_ths \\
        --symbols 00700.HK,600036.SH \\
        --as-of 2026-06-30 \\
        [--tolerance 1000000]

Requirements:
- THS side: iFinDPy SDK installed and the 同花顺 terminal logged in
  (``THSDataSource`` falls back to a reconnect attempt otherwise).
- iFind side: ``IFIND_MCP_KEY`` in ``.env`` (checked via
  ``ifind_mcp_agent.is_configured``) and ``DEEPSEEK_API_KEY`` so the agent
  can parse the free-form MCP answer.

Exit code is 0 when every metric of every symbol is within tolerance
(absolute diff, matching the tolerance convention in
``tests/test_stock_financials.py``), 1 otherwise.
"""

import argparse
import sys
from datetime import date

from backend import logger
from backend.data_source import THSDataSource
from backend.ai.ifind_mcp_agent import ifind_mcp_agent, _FINANCIAL_KEYS


def _metric_label(key: str) -> str:
    return {
        "total_shares": "总股本",
        "ni_to_parent": "归母净利润(近4季)",
        "equity_to_parent": "归母股东权益",
    }.get(key, key)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare iFind MCP vs THS_BD financial data"
    )
    parser.add_argument(
        "--symbols", required=True,
        help="Comma-separated symbols, e.g. 00700.HK,600036.SH",
    )
    parser.add_argument(
        "--as-of", required=True, type=date.fromisoformat,
        help="As-of date in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--tolerance", type=float, default=100_000_000.0,
        help="Absolute tolerance per metric (default 1e8: iFind MCP answers "
             "round money values to 亿/万亿, so ~1e8 is its precision)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]

    if not ifind_mcp_agent.is_configured:
        logger.error("iFind MCP not configured: set IFIND_MCP_KEY in .env")
        return 2

    print("\n" + "=" * 88)
    print(f"Financial data verification: iFind MCP vs THS_BD (as_of: {args.as_of})")
    print("=" * 88)
    print(f"Symbols: {', '.join(symbols)}")
    print(f"Tolerance: {args.tolerance:,.0f} (absolute diff per metric)\n")

    ths_result = THSDataSource().get_stock_financials(symbols, args.as_of)
    if not ths_result:
        logger.error(
            "THS_BD returned no data. Is the 同花顺 terminal logged in?"
        )
        return 2

    print("Fetching iFind MCP financials via the agent...\n")
    mcp_result = ifind_mcp_agent.get_financials(symbols, args.as_of)

    all_ok = True
    any_fail = False
    for symbol in symbols:
        ths = ths_result.get(symbol, {})
        mcp = mcp_result.get(symbol, {})
        print(f"--- {symbol} ---")
        header = (
            f"  {'指标':<16} {'THS_BD':>20} {'iFind MCP':>20} "
            f"{'Diff':>16} {'Rel%':>10}  {'Status'}"
        )
        print(header)
        print("  " + "-" * (len(header) - 2))

        for key in _FINANCIAL_KEYS:
            t = ths.get(key, 0.0) or 0.0
            m = mcp.get(key, 0.0) or 0.0
            diff = m - t
            rel = (diff / t * 100.0) if t else float("inf")
            ok = abs(diff) <= args.tolerance
            status = "OK" if ok else "FAIL"
            print(
                f"  {_metric_label(key):<16} {t:>20,.2f} {m:>20,.2f} "
                f"{diff:>+16,.2f} {rel:>9.4f}%  [{status}]"
            )
            if not ok:
                any_fail = True

        missing_mcp = [k for k in _FINANCIAL_KEYS if k not in mcp]
        missing_ths = [k for k in _FINANCIAL_KEYS if k not in ths]
        if missing_mcp:
            print(f"  Note: iFind MCP missing metrics for {symbol}: {missing_mcp}")
        if missing_ths:
            print(f"  Note: THS_BD missing metrics for {symbol}: {missing_ths}")
        print()

    print("=" * 88)
    if any_fail:
        print("RESULT: FAIL — some metrics differ beyond tolerance")
        all_ok = False
    else:
        print("RESULT: PASS — all metrics within tolerance")
    print("=" * 88)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
