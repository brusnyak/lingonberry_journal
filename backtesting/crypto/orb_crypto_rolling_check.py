"""
Rolling-window check on the 5 pairs that showed PF>1.1 in orb_crypto_scan.py
(DOGE/HYPE/AVAX/SOL/XRP). One full-history pass isn't validation -- this is
the same tool (rolling_validate) that proved ORB's forex edge was real
(482 windows, zero breaches) and that proved TrIct's crypto claim wasn't
(collapsed under a real sample). 30/60-day windows per the fast-iteration
request; step_days=5 to get real window counts out of ~380-600 days.

Usage: python -m backtesting.crypto.orb_crypto_rolling_check
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from backtesting.crypto.data import load_market_specs
from backtesting.crypto.validation import rolling_validate, print_validation_table
from backtesting.engine.costs import CryptoCosts
from backtesting.engine.data import load_data, load_funding_rate
from backtesting.engine.runner import run
from backtesting.lvl2_orb.orb_wide_stop import OrbNyWideStop

PAIRS = ["DOGEUSDT", "HYPEUSDT", "SOLUSDT", "XRPUSDT"]  # AVAXUSDT dropped: PF~1.0, only ~54% of windows profitable, not adopted
BINGX_TAKER_FEE = 0.0005
BINGX_MAKER_FEE = 0.0002
BINGX_MIN_NOTIONAL = 2.0


def backtest_trades(pair: str) -> pd.DataFrame:
    data = {}
    for tf in ("5", "30", "240"):
        data[tf] = load_data(pair, tf=tf, exchange="binance")
    funding_df = load_funding_rate(pair, exchange="binance")
    specs = load_market_specs(pair, "binance")  # only qty_step/tick_size borrowed from here -- min_notional forced to BingX's real number below
    costs = CryptoCosts(
        maker_fee=BINGX_MAKER_FEE, taker_fee=BINGX_TAKER_FEE, leverage=50.0,
        funding_df=funding_df if funding_df is not None and not funding_df.empty else None,
        min_notional=BINGX_MIN_NOTIONAL,  # forced, not a fallback -- confirmed live via ccxt.bingx(), don't let Binance's own (different) spec silently override it
        min_qty=specs.get("min_qty", 0.0), qty_step=specs.get("qty_step", 0.0),
        tick_size=specs.get("tick_size", 0.0),
        entry_slippage_pct=0.0005, sl_slippage_pct=0.0005,
    )
    strat = OrbNyWideStop(risk_pct=0.005, htf_key="240", ltf_key="30", multi_target=True)
    result = run(strat, data, entry_tf="5", costs=costs, initial_equity=20.0)
    return result.to_df()


def main():
    for pair in PAIRS:
        trades = backtest_trades(pair)
        results = []
        for wdays in (30, 60):
            vt = rolling_validate(trades, window_days=wdays, step_days=5, min_trades=3, initial_equity=20.0)
            results.append((f"{pair} {wdays}d window", vt))
        print_validation_table(results, title=pair)
        for label, vt in results:
            if vt.n_windows > 0:
                pass_rate = vt.n_profitable / vt.n_windows
                print(f"  {label}: {vt.n_windows} windows, {vt.n_with_trades} with trades, "
                      f"{vt.n_profitable} profitable ({pass_rate:.0%}), "
                      f"median PF {vt.median_pf:.2f}, worst window return {vt.worst_return_pct:.1%}")


if __name__ == "__main__":
    main()
