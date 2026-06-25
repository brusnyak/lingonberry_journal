"""
OOS validation for the two best IS strategies.
IS: 2022-07-01 → 2026-05-23
OOS: 2026-05-24 → 2026-06-23 (30 days, never touched during development)

Strategies:
  1. GBPCAD acc_sweep bull + 4H  (IS PF=1.243)
  2. GBPJPY FVG bear_fill        (IS PF=1.373 at best params)
"""
import sys, os
sys.path.insert(0, ".")

from backtesting.engine.data import load_data
from backtesting.engine.runner import run
from backtesting.engine.costs import ForexCosts
from backtesting.engine.metrics import summary_str, table_header, table_row
from backtesting.strategies.tr_accumulation import TrAccumulation
from backtesting.strategies.tr_fvg import TrFvg

IS_START  = "2022-07-01"
IS_END    = "2026-05-23"
OOS_START = "2026-05-24"
OOS_END   = "2026-06-23"

if __name__ == "__main__":
    print("=" * 90)
    print("  OOS VALIDATION  |  NEVER-SEEN DATA  |  May 24 – Jun 23 2026")
    print("=" * 90)
    print(table_header())
    print("-" * 90)

    # ── 1. GBPCAD acc_sweep bull ──────────────────────────────────────────────
    for period, start, end in [("IS", IS_START, IS_END), ("OOS", OOS_START, OOS_END)]:
        df15 = load_data("GBPCAD", tf="15", start=start, end=end)
        df4h = load_data("GBPCAD", tf="240", start=start, end=end)
        r = run(
            TrAccumulation(compress_ratio=0.70, sl_buffer_pips=20, tp1_r=1.5, direction="bull"),
            {"15": df15, "240": df4h}, entry_tf="15",
            costs=ForexCosts(), initial_equity=10_000,
        )
        label = f"GBPCAD acc {period}"
        print(table_row(r.report, label=label, tf="15m", start=start, end=end))

    print("-" * 90)

    # ── 2. GBPJPY FVG bear_fill ───────────────────────────────────────────────
    for period, start, end in [("IS", IS_START, IS_END), ("OOS", OOS_START, OOS_END)]:
        df5  = load_data("GBPJPY", tf="5", start=start, end=end)
        df4h = load_data("GBPJPY", tf="240", start=start, end=end)
        r = run(
            TrFvg(sl_buffer_pips=10, tp1_r=2.0, min_gap_atr_pct=0.3,
                  direction="bear", pip_size=0.01),
            {"5": df5, "240": df4h}, entry_tf="5",
            costs=ForexCosts(), initial_equity=10_000,
        )
        label = f"GBPJPY fvg {period}"
        print(table_row(r.report, label=label, tf="5m", start=start, end=end))

    print("-" * 90)
    print()

    # Detailed OOS breakdown for both
    for name, strat, pair, tf, htf, pip in [
        ("GBPCAD acc_sweep",
         TrAccumulation(compress_ratio=0.70, sl_buffer_pips=20, tp1_r=1.5, direction="bull"),
         "GBPCAD", "15", "240", 0.0001),
        ("GBPJPY FVG bear",
         TrFvg(sl_buffer_pips=10, tp1_r=2.0, min_gap_atr_pct=0.3, direction="bear", pip_size=0.01),
         "GBPJPY", "5", "240", 0.01),
    ]:
        df_e = load_data(pair, tf=tf, start=OOS_START, end=OOS_END)
        df_h = load_data(pair, tf=htf, start=OOS_START, end=OOS_END)
        r = run(strat, {tf: df_e, htf: df_h}, entry_tf=tf,
                costs=ForexCosts(), initial_equity=10_000)
        print(f"  ── {name} OOS detail ──")
        print(summary_str(r.report))
        print()
