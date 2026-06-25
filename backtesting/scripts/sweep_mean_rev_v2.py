"""
Sweep MeanRevV2 on GBPAUD 5m IS data (2025-02-17 → 2026-05-23).

Usage:
    python -m backtesting.scripts.sweep_mean_rev_v2
"""

from __future__ import annotations

from collections import defaultdict

import pandas as pd

from backtesting.engine.costs import ForexCosts
from backtesting.engine.data import load_data
from backtesting.engine.runner import run
from backtesting.strategies.mean_rev_v2 import MeanRevV2

START = "2025-02-17"
END   = "2026-05-23"
SYM   = "GBPAUD"
TF    = "5"

SMA_PERIODS  = [10, 15, 20, 30, 50]
LONG_ONLY    = [True, False]

print(f"Loading {SYM} {TF}m  {START} → {END} …")
df = load_data(SYM, tf=TF, start=START, end=END)
print(f"  {len(df):,} bars loaded\n")

data = {TF: df}
costs = ForexCosts()
INITIAL_EQUITY = 10_000.0

rows = []

for lo in LONG_ONLY:
    for period in SMA_PERIODS:
        s = MeanRevV2(sma_period=period, long_only=lo)
        result = run(s, data, entry_tf=TF, costs=costs, initial_equity=INITIAL_EQUITY)
        r = result.report
        mode = "long_only" if lo else "bidir"

        n_trades = r.get("trades", 0)
        wr       = r.get("win_rate", 0.0) * 100
        pf       = r.get("profit_factor", 0.0)
        sharpe   = float(r.get("sharpe", 0.0))
        pnl_pct  = (float(r.get("total_pnl", 0.0)) / INITIAL_EQUITY) * 100
        max_dd   = float(r.get("max_drawdown_pct", 0.0)) * 100

        rows.append({
            "mode": mode,
            "sma": period,
            "trades": n_trades,
            "WR%": round(wr, 1),
            "PF": round(pf, 2),
            "Sharpe": round(sharpe, 2),
            "PnL%": round(pnl_pct, 2),
            "MaxDD%": round(max_dd, 1),
            "_result": result,
            "_mode": lo,
            "_period": period,
        })

# ── Print sweep table ──────────────────────────────────────────────────────────
display_cols = ["mode", "sma", "trades", "WR%", "PF", "Sharpe", "PnL%", "MaxDD%"]
tbl = pd.DataFrame(rows)[display_cols]
print("=" * 72)
print("SWEEP RESULTS — MeanRevV2 GBPAUD 5m IS")
print("=" * 72)
print(tbl.to_string(index=False))
print()

# ── Find best config (PF > 1.2 AND trades >= 50) ──────────────────────────────
valid = [r for r in rows if r["PF"] > 1.2 and r["trades"] >= 50]
if not valid:
    print("No config meets PF > 1.2 with >= 50 trades.\n")
else:
    best = max(valid, key=lambda r: r["PF"])
    print(f"Best edge: mode={best['mode']}  sma={best['sma']}")
    print(f"  trades={best['trades']}  WR={best['WR%']}%  PF={best['PF']}  "
          f"Sharpe={best['Sharpe']}  PnL={best['PnL%']}%  MaxDD={best['MaxDD%']}%\n")

    # Per-exit-reason breakdown for best config
    from collections import defaultdict
    result_obj = best["_result"]
    reason_data: dict[str, list[float]] = defaultdict(list)
    for t in result_obj.trades:
        reason = t.exit_reason.value if hasattr(t.exit_reason, "value") else str(t.exit_reason)
        reason_data[reason].append(t.r_multiple)

    print("Exit reason breakdown (best config):")
    print(f"  {'Reason':<10} {'Count':>6}  {'AvgR':>7}  {'TotalR':>8}")
    print("  " + "-" * 38)
    for reason, rs in sorted(reason_data.items()):
        avg_r = sum(rs) / len(rs)
        total_r = sum(rs)
        print(f"  {reason:<10} {len(rs):>6}  {avg_r:>7.3f}  {total_r:>8.3f}")
    print()
