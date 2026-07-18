"""
A/B test the two concrete fixes identified from the user's structural
critique: (1) body-based swing pivots instead of wick-noisy ones, (2) an
HTF structural-trend filter so TrIct stops taking counter-trend fades.

4 configs per pair: baseline (wick swings, no trend filter) vs each fix
alone vs both together. Real BingX data, real costs, rolling-window check
-- same rigor as every other result this session.

Usage: python -m backtesting.crypto.trict_structure_fix_check
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from backtesting.crypto.data import load_market_specs
from backtesting.crypto.strategies.ict import TrIct
from backtesting.crypto.validation import rolling_validate
from backtesting.engine.costs import CryptoCosts
from backtesting.engine.data import load_data, load_funding_rate
from backtesting.engine.runner import run
from backtesting.engine.structure_trend_gate import StructureTrendGate

PAIRS = ["DOGEUSDT", "XRPUSDT", "SOLUSDT"]
EXCHANGE = "bingx"


def backtest(pair: str, use_body: bool, trend_filter: bool) -> dict:
    data = {"30": load_data(pair, tf="30", exchange=EXCHANGE)}
    if trend_filter:
        data["240"] = load_data(pair, tf="240", exchange=EXCHANGE)
    funding_df = load_funding_rate(pair, exchange=EXCHANGE)
    specs = load_market_specs(pair, "binance")
    costs = CryptoCosts(
        maker_fee=0.0002, taker_fee=0.0005, leverage=50.0,
        funding_df=funding_df if funding_df is not None and not funding_df.empty else None,
        min_notional=2.0, qty_step=specs.get("qty_step", 0.0), tick_size=specs.get("tick_size", 0.0),
        entry_slippage_pct=0.0005, sl_slippage_pct=0.0005,
    )
    # min_stop_pct/sessions_only relaxed deliberately for THIS test -- isolating
    # the trend-filter effect needs raw signal volume; stacking every filter at
    # once starves the sample to single digits and makes the comparison noise.
    strat = TrIct(risk_pct=0.005, min_stop_pct=None, sessions_only=False, use_body_swings=use_body)
    if trend_filter:
        strat = StructureTrendGate(strat, htf_key="240", entry_tf="30", use_body=True)
    result = run(strat, data, entry_tf="30", costs=costs, initial_equity=20.0)
    rep = result.report
    trades = result.to_df()
    row = {
        "pair": pair, "use_body": use_body, "trend_filter": trend_filter,
        "trades": rep.get("trades", 0), "win_rate": rep.get("win_rate", 0),
        "profit_factor": rep.get("profit_factor", 0), "return_pct": rep.get("return_pct", 0),
        "max_drawdown_pct": rep.get("max_drawdown_pct", 0),
    }
    if len(trades) >= 15:
        vt = rolling_validate(trades, window_days=60, step_days=10, min_trades=3, initial_equity=20.0)
        if vt.n_windows:
            row["windows"] = vt.n_windows
            row["pct_profitable"] = vt.n_profitable / vt.n_windows
    return row


def main():
    rows = []
    for pair in PAIRS:
        for use_body in (False, True):
            for trend_filter in (False, True):
                try:
                    rows.append(backtest(pair, use_body, trend_filter))
                except Exception as e:
                    rows.append({"pair": pair, "use_body": use_body, "trend_filter": trend_filter,
                                  "error": f"{type(e).__name__}: {e}"})
    df = pd.DataFrame(rows)
    pd.set_option("display.width", 180)
    print(df.to_string(index=False))
    out = ROOT / "backtesting" / "crypto" / "reports" / "trict_structure_fix_check.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
