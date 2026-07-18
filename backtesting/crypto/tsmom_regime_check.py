"""
Re-test CryptoTsmomBreakout (Donchian/TSMOM) now that the regime layer
(MarketRegime + RegimeGate) exists -- per memory this was explicitly
"pending re-run after regime layer built" and its prior single-pass result
(SOL) collapsed under rolling-window scrutiny with no regime filter at all.
This is the direct "improve on direction" test: does gating entries to
trending regimes fix what killed it before?

Three configs per pair: no filter, own min_er gate, external RegimeGate
(240m HTF trend_up/trend_down only).

Usage: python -m backtesting.crypto.tsmom_regime_check
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from backtesting.engine.costs import CryptoCosts
from backtesting.engine.data import load_data, load_funding_rate
from backtesting.engine.regime_gate import RegimeGate
from backtesting.engine.runner import run
from backtesting.crypto.strategies.tsmom_breakout import CryptoTsmomBreakout
from backtesting.crypto.validation import rolling_validate

PAIRS = ["DOGEUSDT", "XRPUSDT", "SOLUSDT"]
EXCHANGE = "bingx"


def backtest(pair: str, gate: str) -> dict:
    data = {"60": load_data(pair, tf="60", exchange=EXCHANGE)}
    if gate == "regime_gate":
        data["240"] = load_data(pair, tf="240", exchange=EXCHANGE)
    funding_df = load_funding_rate(pair, exchange=EXCHANGE)
    costs = CryptoCosts(
        maker_fee=0.0002, taker_fee=0.0005, leverage=50.0,
        funding_df=funding_df if funding_df is not None and not funding_df.empty else None,
        min_notional=2.0, entry_slippage_pct=0.0005, sl_slippage_pct=0.0005,
    )
    if gate == "none":
        strat = CryptoTsmomBreakout(risk_pct=0.005, stop_mode="channel")
    elif gate == "min_er":
        strat = CryptoTsmomBreakout(risk_pct=0.005, stop_mode="channel", min_er=0.3)
    else:
        strat = RegimeGate(CryptoTsmomBreakout(risk_pct=0.005, stop_mode="channel"),
                            allowed_regimes={"trend_up", "trend_down"}, regime_tf="240", entry_tf="60")
    result = run(strat, data, entry_tf="60", costs=costs, initial_equity=20.0)
    rep = result.report
    trades = result.to_df()
    row = {
        "pair": pair, "gate": gate,
        "trades": rep.get("trades", 0), "win_rate": rep.get("win_rate", 0),
        "profit_factor": rep.get("profit_factor", 0), "return_pct": rep.get("return_pct", 0),
        "max_drawdown_pct": rep.get("max_drawdown_pct", 0),
    }
    if len(trades) >= 15:
        vt = rolling_validate(trades, window_days=60, step_days=10, min_trades=3, initial_equity=20.0)
        if vt.n_windows:
            row["windows_60d"] = vt.n_windows
            row["pct_profitable"] = vt.n_profitable / vt.n_windows
            row["median_pf"] = vt.median_pf
    return row


def main():
    rows = []
    for pair in PAIRS:
        for gate in ("none", "min_er", "regime_gate"):
            try:
                rows.append(backtest(pair, gate))
            except Exception as e:
                rows.append({"pair": pair, "gate": gate, "error": f"{type(e).__name__}: {e}"})
    df = pd.DataFrame(rows)
    pd.set_option("display.width", 180)
    print(df.to_string(index=False))
    out = ROOT / "backtesting" / "crypto" / "reports" / "tsmom_regime_check.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
