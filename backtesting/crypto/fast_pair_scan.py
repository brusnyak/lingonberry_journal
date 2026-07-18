"""
Fast multi-pair TrIct scan on pure exchange-scoped data only (no legacy, no
BingX fetch dependency -- everything here is already on disk, zero wait).

30/60-day windows for iteration speed. SOLUSDT gets an extra full-history run
since its binance-scoped file happens to hold ~5.8 years of genuine pure data
(unlike the other pairs, refreshed to ~107 days on 2026-07-12) -- the one pair
here where a real sample size is available without touching legacy.

Usage: python -m backtesting.crypto.fast_pair_scan
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from backtesting.crypto.data import load_market_specs
from backtesting.engine.costs import CryptoCosts
from backtesting.engine.data import load_data, load_funding_rate
from backtesting.engine.runner import run
from backtesting.crypto.strategies.ict import TrIct

PAIRS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "BNBUSDT",
    "HYPEUSDT", "AAVEUSDT", "WLDUSDT", "1000PEPEUSDT", "LINKUSDT",
    "NEARUSDT", "AVAXUSDT", "SUIUSDT",
]
WINDOWS_DAYS = [30, 60]
RISK_PCT = 0.005  # not yet the tuned 0.002 -- fast scan, revisit once a pair shows signal
BINGX_TAKER_FEE = 0.0005
BINGX_MAKER_FEE = 0.0002
BINGX_MIN_NOTIONAL = 2.0


def run_one(pair: str, days: int) -> dict:
    data = {}
    for tf in ("30", "240"):
        df = load_data(pair, tf=tf, days=days, exchange="binance")
        if df.empty or len(df) < 20:
            return {"pair": pair, "days": days, "error": f"insufficient data tf={tf} ({len(df)} rows)"}
        data[tf] = df

    funding_df = load_funding_rate(pair, exchange="binance")
    specs = load_market_specs(pair, "binance")
    costs = CryptoCosts(
        maker_fee=BINGX_MAKER_FEE, taker_fee=BINGX_TAKER_FEE, leverage=50.0,
        funding_df=funding_df if funding_df is not None and not funding_df.empty else None,
        min_notional=specs.get("min_notional", 0.0) or BINGX_MIN_NOTIONAL,
        min_qty=specs.get("min_qty", 0.0), qty_step=specs.get("qty_step", 0.0),
        tick_size=specs.get("tick_size", 0.0),
        entry_slippage_pct=0.0005, sl_slippage_pct=0.0005,  # bake in a realistic 0.05% by default now
    )
    strat = TrIct(risk_pct=RISK_PCT, min_stop_pct=None)
    result = run(strat, data, entry_tf="30", costs=costs, initial_equity=20.0)
    rep = result.report
    return {
        "pair": pair, "days": days,
        "trades": rep.get("trades", 0), "win_rate": rep.get("win_rate", 0),
        "profit_factor": rep.get("profit_factor", 0), "return_pct": rep.get("return_pct", 0),
        "max_drawdown_pct": rep.get("max_drawdown_pct", 0), "error": None,
    }


def main():
    rows = []
    for pair in PAIRS:
        for days in WINDOWS_DAYS:
            try:
                rows.append(run_one(pair, days))
            except Exception as e:
                rows.append({"pair": pair, "days": days, "error": f"{type(e).__name__}: {e}"})

    # SOL bonus: full pure history, no days cap
    try:
        data = {}
        for tf in ("30", "240"):
            data[tf] = load_data("SOLUSDT", tf=tf, exchange="binance")
        funding_df = load_funding_rate("SOLUSDT", exchange="binance")
        specs = load_market_specs("SOLUSDT", "binance")
        costs = CryptoCosts(
            maker_fee=BINGX_MAKER_FEE, taker_fee=BINGX_TAKER_FEE, leverage=50.0,
            funding_df=funding_df if funding_df is not None and not funding_df.empty else None,
            min_notional=specs.get("min_notional", 0.0) or BINGX_MIN_NOTIONAL,
            min_qty=specs.get("min_qty", 0.0), qty_step=specs.get("qty_step", 0.0),
            tick_size=specs.get("tick_size", 0.0),
            entry_slippage_pct=0.0005, sl_slippage_pct=0.0005,
        )
        strat = TrIct(risk_pct=RISK_PCT, min_stop_pct=None)
        result = run(strat, data, entry_tf="30", costs=costs, initial_equity=20.0)
        rep = result.report
        rows.append({
            "pair": "SOLUSDT", "days": "FULL(~2115d)",
            "trades": rep.get("trades", 0), "win_rate": rep.get("win_rate", 0),
            "profit_factor": rep.get("profit_factor", 0), "return_pct": rep.get("return_pct", 0),
            "max_drawdown_pct": rep.get("max_drawdown_pct", 0), "error": None,
        })
    except Exception as e:
        rows.append({"pair": "SOLUSDT", "days": "FULL", "error": f"{type(e).__name__}: {e}"})

    df = pd.DataFrame(rows)
    pd.set_option("display.width", 160)
    print(df.to_string(index=False))
    out = ROOT / "backtesting" / "crypto" / "reports" / "fast_pair_scan.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
