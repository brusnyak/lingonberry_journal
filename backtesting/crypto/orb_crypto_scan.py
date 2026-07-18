"""
Port the ONE forex strategy in this repo that actually survived rolling-
window validation (OrbNyWideStop -- opening-range breakout + HTF/LTF trend
filter, zero breaches across 482 rolling windows on NAS100/US30/DAX) onto
crypto pairs. Unmodified strategy code, unmodified default params (no
fitting to crypto data on this first pass) -- only the market/session
convention changes: NY session open (09:30 America/New_York), same
convention the existing crypto session-discovery work already targets.

Every reversal/sweep-family signal tested on this crypto data today (TrIct,
ny_reversal grid) looked good on <15 trades and died on a real sample. ORB
is mechanically different (breakout/continuation, ~1 trade/day max) so it's
a genuinely different bet, and its one-trade-per-day cadence means even the
~107-day pure-exchange window gives a real trade count instead of single
digits.

Usage: python -m backtesting.crypto.orb_crypto_scan
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
from backtesting.lvl2_orb.orb_wide_stop import OrbNyWideStop

PAIRS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "BNBUSDT",
    "HYPEUSDT", "AAVEUSDT", "WLDUSDT", "1000PEPEUSDT", "LINKUSDT",
    "NEARUSDT", "AVAXUSDT", "SUIUSDT",
]
BINGX_TAKER_FEE = 0.0005
BINGX_MAKER_FEE = 0.0002
BINGX_MIN_NOTIONAL = 2.0


def run_one(pair: str) -> dict:
    data = {}
    for tf in ("5", "30", "240"):
        df = load_data(pair, tf=tf, exchange="binance")  # pure exchange, no legacy, whatever's on disk (no wait)
        if df.empty or len(df) < 50:
            return {"pair": pair, "error": f"insufficient data tf={tf} ({len(df)} rows)"}
        data[tf] = df

    span_days = (data["5"]["ts"].max() - data["5"]["ts"].min()).days
    funding_df = load_funding_rate(pair, exchange="binance")
    specs = load_market_specs(pair, "binance")
    costs = CryptoCosts(
        maker_fee=BINGX_MAKER_FEE, taker_fee=BINGX_TAKER_FEE, leverage=50.0,
        funding_df=funding_df if funding_df is not None and not funding_df.empty else None,
        min_notional=specs.get("min_notional", 0.0) or BINGX_MIN_NOTIONAL,
        min_qty=specs.get("min_qty", 0.0), qty_step=specs.get("qty_step", 0.0),
        tick_size=specs.get("tick_size", 0.0),
        entry_slippage_pct=0.0005, sl_slippage_pct=0.0005,
    )
    strat = OrbNyWideStop(risk_pct=0.005, htf_key="240", ltf_key="30", multi_target=True)
    result = run(strat, data, entry_tf="5", costs=costs, initial_equity=20.0)
    rep = result.report
    return {
        "pair": pair, "span_days": span_days,
        "trades": rep.get("trades", 0), "win_rate": rep.get("win_rate", 0),
        "profit_factor": rep.get("profit_factor", 0), "return_pct": rep.get("return_pct", 0),
        "max_drawdown_pct": rep.get("max_drawdown_pct", 0), "error": None,
    }


def main():
    rows = [run_one(p) for p in PAIRS]
    df = pd.DataFrame(rows)
    pd.set_option("display.width", 160)
    print(df.to_string(index=False))
    out = ROOT / "backtesting" / "crypto" / "reports" / "orb_crypto_scan.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
