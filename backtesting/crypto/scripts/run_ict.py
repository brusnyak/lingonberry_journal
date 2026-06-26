"""
TrIct backtest: forex + crypto across 3 non-overlapping 30-day windows.

Windows (IS only — OOS: May 24 – Jun 23 2026 untouched):
  W1: Sep 15 – Oct 15 2025
  W2: Dec 01 – Dec 31 2025
  W3: Mar 01 – Mar 31 2026

Usage:
    python -m backtesting.crypto.scripts.run_ict
    python -m backtesting.crypto.scripts.run_ict --crypto   # crypto-only
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import pandas as pd

from backtesting.engine.runner import run
from backtesting.engine.data import load_data
from backtesting.engine.costs import ForexCosts, CryptoCosts
from backtesting.crypto.strategies.ict import TrIct

# ── Pairs ─────────────────────────────────────────────────────────────────────

FOREX_PAIRS = [
    ("GBPAUD",  "forex",     None),
    ("EURUSD",  "forex",     None),
    ("XAUUSD",  "commodity", None),
]

CRYPTO_PAIRS = [
    ("DOGEUSDT",  "crypto", "binance"),
    ("BTCUSDT",   "crypto", "binance"),
    ("ETHUSDT",   "crypto", "binance"),
    ("SOLUSDT",   "crypto", "binance"),
]

WINDOWS = [
    ("2025-09-15", "2025-10-15", "W1"),
    ("2025-12-01", "2025-12-31", "W2"),
    ("2026-03-01", "2026-03-31", "W3"),
]
INITIAL_EQUITY = 10_000.0
CONTEXT_DAYS = 7


def _costs_for(pair: str, asset_type: str, exchange: str | None) -> ForexCosts | CryptoCosts:
    if asset_type == "crypto":
        return CryptoCosts(leverage=50)
    return ForexCosts()


def _load(pair: str, asset_type: str, exchange: str | None, start: str, end: str) -> dict:
    ctx_start = (date.fromisoformat(start) - timedelta(days=CONTEXT_DAYS)).isoformat()
    kw = {"exchange": exchange} if exchange else {}
    return {
        "5":  load_data(pair, "5",  start=ctx_start, end=end, asset_type=asset_type, **kw),
        "30": load_data(pair, "30", start=ctx_start, end=end, asset_type=asset_type, **kw),
    }


def run_backtest(pairs: list[tuple], label: str) -> None:
    hdr = f"{'Pair':<10} {'Win':<4} {'N':>5} {'WR%':>6} {'PF':>6} {'MaxDD%':>8} {'AvgR':>7}"
    print(f"\n  [{label}]")
    print(hdr)
    print("-" * len(hdr))

    for pair, asset_type, exchange in pairs:
        for start, end, wlabel in WINDOWS:
            try:
                data = _load(pair, asset_type, exchange, start, end)
            except Exception as e:
                print(f"{pair:<10} {wlabel:<4}  load error: {e}")
                continue

            df5 = data["5"]
            if "ts" in df5.columns and not df5.empty:
                mask = (df5["ts"] >= pd.Timestamp(start, tz="UTC")) & \
                       (df5["ts"] <= pd.Timestamp(end, tz="UTC"))
                data["5"] = df5[mask].reset_index(drop=True)

            if data["5"].empty or data["30"].empty:
                print(f"{pair:<10} {wlabel:<4}  no data")
                continue

            costs = _costs_for(pair, asset_type, exchange)
            strategy = TrIct(risk_pct=0.005, min_rr=1.5, sessions_only=True)

            try:
                result = run(strategy, data, entry_tf="5", costs=costs,
                             initial_equity=INITIAL_EQUITY, verbose=False)
            except Exception as e:
                print(f"{pair:<10} {wlabel:<4}  run error: {e}")
                continue

            trades = result.trades
            n = len(trades)
            if n == 0:
                print(f"{pair:<10} {wlabel:<4} {'0':>5}  no trades")
                continue

            wins  = sum(1 for t in trades if t.pnl > 0)
            wr    = wins / n * 100
            gw    = sum(t.pnl for t in trades if t.pnl > 0)
            gl    = abs(sum(t.pnl for t in trades if t.pnl < 0))
            pf    = gw / gl if gl > 0 else float("inf")
            avg_r = sum(t.r_multiple for t in trades) / n
            max_dd = getattr(result, "max_drawdown_pct", 0.0) * 100

            print(f"{pair:<10} {wlabel:<4} {n:>5} {wr:>5.1f}% {pf:>6.2f} {max_dd:>7.1f}% {avg_r:>7.2f}R")


def main() -> None:
    parser = argparse.ArgumentParser(description="TrIct ICT backtest")
    parser.add_argument("--crypto", action="store_true", help="crypto pairs only")
    parser.add_argument("--forex", action="store_true", help="forex pairs only")
    args = parser.parse_args()

    if args.crypto:
        run_backtest(CRYPTO_PAIRS, "CRYPTO")
    elif args.forex:
        run_backtest(FOREX_PAIRS, "FOREX")
    else:
        run_backtest(FOREX_PAIRS, "FOREX")
        run_backtest(CRYPTO_PAIRS, "CRYPTO")

    print()
    print("  OOS (May 24 – Jun 23 2026) untouched")


if __name__ == "__main__":
    main()
