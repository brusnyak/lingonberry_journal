"""
TrAsiaSweep on NAS100: 15m Asia range + 1m FVG entry.
IS: 2025-08-13 → 2025-11-28 (all available 1m NAS100 data).
"""
import sys, os, itertools
sys.path.insert(0, ".")

from backtesting.engine.data import load_data
from backtesting.engine.runner import run
from backtesting.engine.costs import ForexCosts
from backtesting.engine.metrics import summary_str, table_header, table_row
from backtesting.batch import run_batch, RunConfig
from backtesting.strategies.tr_asia_sweep import TrAsiaSweep

IS_START = "2025-08-13"
IS_END   = "2025-11-28"

if __name__ == "__main__":
    df1  = load_data("USATECHIDXUSD", tf="1",  asset_type="index", start=IS_START, end=IS_END)
    df15 = load_data("USATECHIDXUSD", tf="15", asset_type="index", start=IS_START, end=IS_END)
    print(f"1m bars: {len(df1)} | 15m bars: {len(df15)} | {IS_START} to {IS_END}")

    # Default run
    r = run(
        TrAsiaSweep(sl_buffer_pts=5, tp1_r=2.0, direction="both"),
        {"1": df1, "15": df15}, entry_tf="1",
        costs=ForexCosts(), initial_equity=10_000,
    )
    print("\n── Default (sl=5 tp=2.0 both) ──")
    print(summary_str(r.report))

    # Grid
    configs = []
    for sl, tp, lookback, fvg_bars, min_fvg, dirn in itertools.product(
        [3, 5, 10, 20],
        [1.5, 2.0, 3.0],
        [5, 10, 20],
        [20, 40, 80],
        [3, 5, 10],
        ["bull", "bear", "both"],
    ):
        configs.append(RunConfig(
            pair="USATECHIDXUSD",
            entry_tf="1",
            support_tfs=["15"],
            params=dict(sl_buffer_pts=sl, tp1_r=tp, sweep_lookback=lookback,
                        fvg_entry_bars=fvg_bars, min_fvg_pts=min_fvg, direction=dirn),
            start=IS_START, end=IS_END,
        ))

    print(f"\nGrid: {len(configs)} configs")
    df_res = run_batch(TrAsiaSweep, configs, workers=min(8, os.cpu_count()), min_trades=20)

    top = df_res[df_res["error"].isna() & (df_res["trades"] >= 20)].head(20)
    print("\n" + "=" * 100)
    print("  TrAsiaSweep NAS100  15m Asia + 1m entry  |  top 20 by PF")
    print("=" * 100)
    print(table_header())
    print("-" * 100)
    for _, row in top.iterrows():
        label = f"sl={row['sl_buffer_pts']} tp={row['tp1_r']} dir={row['direction']}"
        report = {k: row[k] for k in row.index if k in [
            "trades","win_rate","profit_factor","payoff_ratio",
            "max_drawdown_pct","total_pnl","trade_pnls"
        ]}
        print(table_row(report, label=label, tf="1m", start=IS_START, end=IS_END))
    print("-" * 100)
    if not df_res.empty and "profit_factor" in df_res.columns:
        valid = df_res[df_res["error"].isna() & (df_res["trades"] >= 20)]
        if not valid.empty:
            best = valid.loc[valid["profit_factor"].idxmax()]
            print(f"\n  Best: sl={best['sl_buffer_pts']} tp={best['tp1_r']} "
                  f"lookback={best['sweep_lookback']} fvg_bars={best['fvg_entry_bars']} "
                  f"min_fvg={best['min_fvg_pts']} dir={best['direction']}")
            print(f"  PF={best['profit_factor']:.3f}  WR={best['win_rate']:.1%}  T={best['trades']}")
