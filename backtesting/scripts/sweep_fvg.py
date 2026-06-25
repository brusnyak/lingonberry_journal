"""
Grid sweep TrFvg on 5m pairs. FVG bear_fill had t=3.43 avg across 7/7 pairs.
Best: EURGBP t=6.81, GBPJPY t=5.15, GBPCAD t=4.29.
Note: GBPJPY needs pip_size=0.01.
"""
import sys, os
sys.path.insert(0, ".")

from backtesting.batch import run_batch, make_configs, RunConfig
from backtesting.strategies.tr_fvg import TrFvg
from backtesting.engine.metrics import table_header, table_row

def make_configs_fvg(pairs, tfs, param_grid, start, end):
    """Build configs with correct pip_size per pair."""
    import itertools
    configs = []
    keys = list(param_grid.keys())
    combos = list(itertools.product(*param_grid.values()))
    for pair, tf, combo in itertools.product(pairs, tfs, combos):
        params = dict(zip(keys, combo))
        if "JPY" in pair:
            params["pip_size"] = 0.01
        else:
            params["pip_size"] = 0.0001
        configs.append(RunConfig(
            pair=pair,
            entry_tf=tf,
            support_tfs=["240"],
            params=params,
            start=start,
            end=end,
        ))
    return configs

if __name__ == "__main__":
    START = "2022-07-01"
    END   = "2026-05-23"

    configs = make_configs_fvg(
        pairs=["EURGBP", "GBPJPY", "GBPCAD", "EURUSD", "AUDUSD", "GBPAUD"],
        tfs=["5"],
        param_grid={
            "sl_buffer_pips": [5, 10],
            "tp1_r": [1.0, 1.5, 2.0],
            "min_gap_atr_pct": [0.2, 0.3],
            "direction": ["bear"],
        },
        start=START, end=END,
    )
    print(f"Total configs: {len(configs)}")

    df = run_batch(TrFvg, configs, workers=min(8, os.cpu_count()), min_trades=30)

    top = df[df["error"].isna() & (df["trades"] >= 30)].head(30)
    print("\n" + "=" * 95)
    print("  TrFvg bear_fill  |  5m  |  IS 2022-2026  |  sorted by PF")
    print("=" * 95)
    print(table_header())
    print("-" * 95)
    for _, row in top.iterrows():
        label = f"{row['pair']} sl={row['sl_buffer_pips']} tp={row['tp1_r']}"
        report = {k: row[k] for k in row.index if k in [
            "trades","win_rate","profit_factor","payoff_ratio",
            "max_drawdown_pct","total_pnl","trade_pnls"
        ]}
        print(table_row(report, label=label, tf="5m", start=START, end=END))
    print("-" * 95)

    print("\n  Best PF per pair:")
    for pair in ["EURGBP","GBPJPY","GBPCAD","EURUSD","AUDUSD","GBPAUD"]:
        sub = df[(df["pair"] == pair) & df["error"].isna() & (df["trades"] >= 30)]
        if sub.empty:
            continue
        best = sub.loc[sub["profit_factor"].idxmax()]
        print(f"  {pair}  sl={best['sl_buffer_pips']}  tp={best['tp1_r']}  "
              f"gap={best['min_gap_atr_pct']}  PF={best['profit_factor']:.3f}  "
              f"WR={best['win_rate']:.1%}  T={best['trades']}")
