"""Grid sweep TrTrend on best pairs. Find if MA confluence beats acc_sweep ceiling."""
import sys, os
sys.path.insert(0, ".")

from backtesting.batch import run_batch, make_configs
from backtesting.strategies.tr_trend import TrTrend
from backtesting.engine.metrics import table_header, table_row

if __name__ == "__main__":
    START = "2022-07-01"
    END   = "2026-05-23"

    configs = make_configs(
        pairs=["GBPCAD", "EURUSD", "AUDUSD", "GBPAUD"],
        entry_tfs=["15"],
        support_tfs_map={"15": ["60", "240"]},
        param_grid={
            "htf_ma_period": [50, 100],
            "mtf_ma_period": [20, 50],
            "entry_ma_period": [8, 20],
            "ma_type": ["ema", "hma"],
            "sl_atr_mult": [1.5, 2.0],
            "tp_r": [1.5, 2.0],
        },
        start=START, end=END,
    )
    print(f"Total configs: {len(configs)}")

    df = run_batch(TrTrend, configs, workers=min(8, os.cpu_count()), min_trades=30)

    # Show top 20
    top = df[df["error"].isna() & (df["trades"] >= 30)].head(20)
    print("\n" + "=" * 95)
    print("  TrTrend top 20  |  IS 2022-2026  |  sorted by PF")
    print("=" * 95)
    print(table_header())
    print("-" * 95)
    for _, row in top.iterrows():
        label = f"{row['pair']} {row['ma_type']}"
        report = {k: row[k] for k in row.index if k in [
            "trades","win_rate","profit_factor","payoff_ratio",
            "max_drawdown_pct","total_pnl","trade_pnls"
        ]}
        print(table_row(report, label=label, tf="15m", start=START, end=END))
    print("-" * 95)

    print("\n  Best PF per pair:")
    for pair in df["pair"].unique():
        sub = df[(df["pair"] == pair) & df["error"].isna() & (df["trades"] >= 30)]
        if sub.empty:
            continue
        best = sub.loc[sub["profit_factor"].idxmax()]
        print(f"  {pair}  ma={best['ma_type']}  htf={best['htf_ma_period']}  "
              f"mtf={best['mtf_ma_period']}  entry={best['entry_ma_period']}  "
              f"PF={best['profit_factor']:.3f}  WR={best['win_rate']:.1%}  T={best['trades']}")
