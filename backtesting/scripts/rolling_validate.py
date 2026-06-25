"""
Rolling window validation for GBPJPY FVG bear_fill.
5 non-overlapping 9-month windows across IS data.
A strategy is real if it's profitable in ≥4/5 windows.
"""
import sys
sys.path.insert(0, ".")

from backtesting.engine.data import load_data
from backtesting.engine.runner import run
from backtesting.engine.costs import ForexCosts
from backtesting.engine.metrics import table_header, table_row
from backtesting.strategies.tr_fvg import TrFvg

WINDOWS = [
    ("W1 Jul22–Mar23", "2022-07-01", "2023-03-31"),
    ("W2 Apr23–Dec23", "2023-04-01", "2023-12-31"),
    ("W3 Jan24–Sep24", "2024-01-01", "2024-09-30"),
    ("W4 Oct24–Jun25", "2024-10-01", "2025-06-30"),
    ("W5 Jul25–May26", "2025-07-01", "2026-05-23"),
]

def make_strat():
    return TrFvg(sl_buffer_pips=10, tp1_r=2.0, min_gap_atr_pct=0.3,
                 direction="bear", pip_size=0.01)

if __name__ == "__main__":
    # check data availability
    test = load_data("GBPJPY", tf="5", start="2022-07-01", end="2022-07-31")
    print(f"  Data check GBPJPY 5m Jul2022: {len(test)} bars")

    print("=" * 90)
    print("  ROLLING VALIDATION  |  GBPJPY FVG bear_fill  |  sl=10 tp=2.0 gap=0.3")
    print("=" * 90)
    print(table_header())
    print("-" * 90)

    wins = 0
    for label, start, end in WINDOWS:
        df5  = load_data("GBPJPY", tf="5", start=start, end=end)
        df4h = load_data("GBPJPY", tf="240", start=start, end=end)
        if df5.empty:
            print(f"  {label}: NO DATA")
            continue
        r = run(make_strat(), {"5": df5, "240": df4h}, entry_tf="5",
                costs=ForexCosts(), initial_equity=10_000)
        pf = r.report["profit_factor"]
        wins += int(pf > 1.0)
        print(table_row(r.report, label=label, tf="5m", start=start, end=end))

    print("-" * 90)
    print(f"\n  Profitable windows: {wins}/5")
    print(f"  {'PASS — robust' if wins >= 4 else 'FAIL — regime-specific'}")
    print()
    print("  OOS (never-seen):")
    df5  = load_data("GBPJPY", tf="5", start="2026-05-24", end="2026-06-23")
    df4h = load_data("GBPJPY", tf="240", start="2026-05-24", end="2026-06-23")
    r = run(make_strat(), {"5": df5, "240": df4h}, entry_tf="5",
            costs=ForexCosts(), initial_equity=10_000)
    print(table_row(r.report, label="OOS Jun26", tf="5m",
                    start="2026-05-24", end="2026-06-23"))
