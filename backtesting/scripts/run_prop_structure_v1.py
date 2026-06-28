#!/usr/bin/env python3
"""Run PropFirmStructureV1 and print GFT challenge reports."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from backtesting.engine.costs import ForexCosts
from backtesting.engine.data import load_data
from backtesting.engine.runner import run
from backtesting.prop_rules import evaluate_all_gft_rules
from backtesting.strategies.prop_firm_structure_v1 import PropFirmStructureV1

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


ASSET_DEFAULTS = {
    "XAUUSD": {"asset_type": "commodity", "pip_size": 0.1, "pip_value": 100.0},
    "NAS100": {"asset_type": "index", "pip_size": 1.0, "pip_value": 1.0},
    "GBPJPY": {"asset_type": "forex", "pip_size": 0.01, "pip_value": 9.0},
    "EURUSD": {"asset_type": "forex", "pip_size": 0.0001, "pip_value": 10.0},
    "GBPUSD": {"asset_type": "forex", "pip_size": 0.0001, "pip_value": 10.0},
    "GBPAUD": {"asset_type": "forex", "pip_size": 0.0001, "pip_value": 10.0},
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run PropFirmStructureV1")
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--start", default="2026-05-24")
    parser.add_argument("--end", default="2026-06-23")
    parser.add_argument("--risk-pct", type=float, default=0.25, help="Risk per trade in percent")
    parser.add_argument("--min-rr", type=float, default=1.5)
    parser.add_argument("--direction", choices=["both", "long", "short", "bull", "bear"], default="both")
    parser.add_argument("--sessions", default="", help="Comma-separated: asia,london_open,ny_open,other")
    parser.add_argument("--require-htf", action="store_true")
    parser.add_argument("--no-structure-cut", action="store_true")
    args = parser.parse_args()

    symbol = args.symbol.upper()
    meta = ASSET_DEFAULTS.get(symbol, {"asset_type": "forex", "pip_size": 0.0001, "pip_value": 10.0})
    data = {
        "5": load_data(symbol, "5", start=args.start, end=args.end, asset_type=meta["asset_type"]),
        "240": load_data(symbol, "240", start=args.start, end=args.end, asset_type=meta["asset_type"]),
    }
    if data["5"].empty:
        raise SystemExit(f"No 5m data for {symbol}")

    initial_equity = 25_000.0
    strategy = PropFirmStructureV1(
        risk_pct=args.risk_pct / 100.0,
        min_rr=args.min_rr,
        pip_size=meta["pip_size"],
        direction=args.direction,
        require_htf=args.require_htf,
        structure_cut=not args.no_structure_cut,
        sessions=tuple(s.strip() for s in args.sessions.split(",") if s.strip()),
    )
    result = run(
        strategy,
        data,
        entry_tf="5",
        costs=ForexCosts(pip_size=meta["pip_size"], pip_value_per_lot=meta["pip_value"]),
        initial_equity=initial_equity,
    )
    print(result.summary())
    trades = result.to_df()
    print()
    print(evaluate_all_gft_rules(trades, source_initial_balance=initial_equity).to_string(index=False))


if __name__ == "__main__":
    main()
