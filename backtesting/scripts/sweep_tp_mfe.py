"""
Find the optimal TP by sweeping tp1_r on acc_sweep + 4H filter.
Hypothesis: avg MFE=0.73R means TP ≥ 0.9R is too far. Test 0.5–2.0.
"""
import sys, os
sys.path.insert(0, ".")

from backtesting.batch import run_batch, make_configs
from backtesting.strategies.tr_accumulation import TrAccumulation
from backtesting.engine.metrics import table_header, table_row

if __name__ == "__main__":
    START = "2022-07-01"
    END   = "2026-05-23"

    configs = make_configs(
        pairs=["GBPCAD", "EURUSD", "AUDUSD", "GBPAUD"],
        entry_tfs=["15"],
        support_tfs_map={"15": ["240"]},
        param_grid={
            "compress_ratio": [0.70],
            "sl_buffer_pips": [20],
            "tp1_r": [0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2, 1.5, 2.0],
            "direction": ["bull"],
        },
        start=START, end=END,
    )

    df = run_batch(TrAccumulation, configs, workers=min(8, os.cpu_count()), min_trades=30)

    print("\n" + "=" * 90)
    print("  TP sweep  |  acc_sweep bull + 4H filter + compress=0.70 + sl=20pip  |  IS 2022-2026")
    print("=" * 90)
    print(table_header())
    print("-" * 90)
    for _, row in df.iterrows():
        if row.get("error"):
            continue
        label = f"{row['pair']} tp={row['tp1_r']}"
        report = {k: row[k] for k in row.index if k in [
            "trades","win_rate","profit_factor","payoff_ratio",
            "max_drawdown_pct","total_pnl","trade_pnls","trade_r_multiples"
        ]}
        print(table_row(report, label=label, tf="15m", start=START, end=END))
    print("-" * 90)

    # Per-pair summary: which TP gives best PF
    print("\n  Best TP per pair:")
    for pair in ["GBPCAD", "EURUSD", "AUDUSD", "GBPAUD"]:
        sub = df[df["pair"] == pair].dropna(subset=["profit_factor"])
        if sub.empty:
            continue
        best = sub.loc[sub["profit_factor"].idxmax()]
        print(f"  {pair}  tp={best['tp1_r']}  PF={best['profit_factor']:.3f}  WR={best['win_rate']:.1%}  T={best['trades']}")
