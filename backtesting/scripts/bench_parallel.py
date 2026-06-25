"""Benchmark parallel vs sequential batch execution."""
import os, sys, time
sys.path.insert(0, ".")

from backtesting.batch import run_batch, make_configs
from backtesting.strategies.tr_accumulation import TrAccumulation

if __name__ == "__main__":
    configs = make_configs(
        pairs=["GBPCAD", "EURUSD", "AUDUSD"],
        entry_tfs=["15"],
        support_tfs_map={"15": ["240"]},
        param_grid={
            "compress_ratio": [0.60, 0.70, 0.80],
            "sl_buffer_pips": [5, 10, 20],
            "tp1_r": [1.0, 1.5, 2.0],
            "direction": ["bull"],
        },
        start="2022-07-01", end="2026-05-23",
    )
    n = min(18, len(configs))
    print(f"Testing {n} configs  |  cpu_count={os.cpu_count()}\n")

    t0 = time.time()
    df_seq = run_batch(TrAccumulation, configs[:n], workers=1)
    seq_t = time.time() - t0
    print(f"\nSequential {n} combos: {seq_t:.1f}s  ({seq_t/n:.2f}s each)")

    print()
    t0 = time.time()
    df_par = run_batch(TrAccumulation, configs[:n], workers=min(8, os.cpu_count()))
    par_t = time.time() - t0
    print(f"\nParallel   {n} combos: {par_t:.1f}s  ({par_t/n:.2f}s each)  speedup={seq_t/par_t:.1f}x")

    # Verify results match
    seq_pfs = df_seq.sort_values(["pair","compress_ratio","sl_buffer_pips","tp1_r"])["profit_factor"].tolist()
    par_pfs = df_par.sort_values(["pair","compress_ratio","sl_buffer_pips","tp1_r"])["profit_factor"].tolist()
    match = seq_pfs == par_pfs
    print(f"Results match: {match}")
