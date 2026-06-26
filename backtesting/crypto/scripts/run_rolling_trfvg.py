"""
Rolling 30d backtest — multi-window validation for TrFvg on crypto.

Tests each config across multiple 30-day sliding windows.
Configs with PF > 1.2 across 3+ windows = real edge.
Configs that spike once = overfitted noise.

Primary question: does HTF structure filter fix the bear direction bleed?
    "both" + htf_structure=False  vs  "both" + htf_structure=True
"""
import sys, os, time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from backtesting.engine.data import load_data
from backtesting.engine.runner import run
from backtesting.strategies.tr_fvg import TrFvg
from backtesting.crypto.costs import build_crypto_costs

# ── Config ────────────────────────────────────────────────────────────────
ACCOUNT = 70.0
LEVERAGE = 10
EXCHANGE = "binance"

WINDOW_DAYS = 30   # size of each window
STEP_DAYS = 7      # slide forward this many days between windows
MAX_WINDOWS = 8    # max windows (covers 8×7=56 days with 30d windows)

# Test core pairs + HTF filter toggle
PAIRS = ["XRPUSDT", "DOGEUSDT", "AVAXUSDT", "ADAUSDT", "SUIUSDT"]
ENTRY_TF = "15"

# Focused grid: test HTF filter impact on "both" direction
PARAM_GRID = {
    "sl_buffer_pips": [20],
    "tp1_r": [2.0],
    "direction": ["both", "bull"],
    "min_gap_atr_pct": [0.2],
    "sl_mode": ["structure"],
    "structure_sl_lookback": [20],
    "structure_sl_swing_n": [3],
    "htf_structure": [False, True],
    "min_stop_pct": [0.001],
    "min_stop_atr_mult": [0.25],
    "max_stop_pct": [0.012],
    "max_stop_atr_mult": [2.5],
    "risk_pct": [0.02],
    "tp1_frac": [1.0],
}

# ── Data ──────────────────────────────────────────────────────────────────

def build_windows(end_date: str = "2026-06-26") -> list[tuple[str, str]]:
    """Generate (start, end) date pairs for sliding 30-day windows."""
    end = datetime.strptime(end_date, "%Y-%m-%d")
    windows = []
    for i in range(MAX_WINDOWS):
        w_end = end - timedelta(days=i * STEP_DAYS)
        w_start = w_end - timedelta(days=WINDOW_DAYS)
        windows.append((w_start.strftime("%Y-%m-%d"), w_end.strftime("%Y-%m-%d")))
    return windows


def detect_pip_size(entry_df: pd.DataFrame) -> float:
    fc = entry_df["close"].iloc[0]
    if fc >= 1000: return 1.0
    if fc >= 100:  return 0.1
    if fc >= 10:   return 0.01
    if fc >= 1:    return 0.001
    return 0.0001


def load_pair_data(pair: str, start: str, end: str, tfs: list[str]) -> Optional[dict]:
    """Load all TFs for one pair+window. Returns None if any TF missing."""
    data = {}
    for tf in tfs:
        df = load_data(pair, tf=tf, start=start, end=end, asset_type="crypto", exchange=EXCHANGE)
        if df.empty:
            df = load_data(pair, tf=tf, start=start, end=end, asset_type="crypto", exchange="bybit")
        if df.empty:
            return None
        data[tf] = df
    return data


def run_one(pair: str, params: dict, start: str, end: str) -> Optional[dict]:
    """Single backtest, return metric dict or None."""
    try:
        entry_tf = params.get("_entry_tf", ENTRY_TF)
        tfs = list(dict.fromkeys([entry_tf, "60", "240"]))
        data = load_pair_data(pair, start, end, tfs)
        if data is None:
            return None

        pip_size = detect_pip_size(data[entry_tf])
        strat_params = {k: v for k, v in params.items() if not k.startswith("_")}
        strat = TrFvg(pip_size=pip_size, **strat_params)
        costs = build_crypto_costs(pair, exchange=EXCHANGE, leverage=LEVERAGE, pip_size=pip_size)
        result = run(strat, data, entry_tf=entry_tf, costs=costs, initial_equity=ACCOUNT)
        rep = result.report

        if rep["trades"] < 3:
            return None  # too few trades for meaningful metrics

        return {
            "trades": rep["trades"],
            "win_rate": rep["win_rate"],
            "profit_factor": rep["profit_factor"],
            "payoff_ratio": rep.get("payoff_ratio", 0),
            "avg_r": rep.get("avg_r", 0),
            "total_pnl": rep["total_pnl"],
            "return_pct": rep.get("return_pct", 0),
            "max_drawdown_pct": rep["max_drawdown_pct"],
        }
    except Exception as e:
        return None


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    import itertools
    from collections import defaultdict

    windows = build_windows()
    print(f"\n{'='*100}")
    print(f"  ROLLING 30D TRFVG  |  ${ACCOUNT} @ {LEVERAGE}x  |  "
          f"{EXCHANGE}  |  {len(windows)} windows  |  step={STEP_DAYS}d")
    print(f"  Windows: {windows[-1][0]} → {windows[0][1]}")
    print(f"{'='*100}\n")

    keys = list(PARAM_GRID.keys())
    combos = list(itertools.product(*PARAM_GRID.values()))
    total = len(PAIRS) * len(combos) * len(windows)

    # results[config_key] = list of per-window metric dicts
    results: dict[str, list] = defaultdict(list)

    t0 = time.time()
    run_i = 0
    for pair in PAIRS:
        for combo in combos:
            params = dict(zip(keys, combo))
            config_key = f"{pair} | {' '.join(f'{k}={v}' for k, v in zip(keys, combo))}"

            wins_ok = 0
            wins_total = 0
            for w_start, w_end in windows:
                run_i += 1
                wins_total += 1
                row = run_one(pair, params, w_start, w_end)
                if row is not None:
                    results[config_key].append({"window": f"{w_start}→{w_end}", **row})
                    wins_ok += 1

            # One-line per config
            label = f"[{run_i}/{total}] {config_key}"
            if wins_ok == 0:
                print(f"  {label}  NO VALID WINDOWS")
            else:
                pfs = [r["profit_factor"] for r in results[config_key]]
                print(f"  {label}  OK={wins_ok}/{wins_total}  "
                      f"PF={np.mean(pfs):.2f}±{np.std(pfs):.2f}  "
                      f"T={np.mean([r['trades'] for r in results[config_key]]):.0f}")

    elapsed = time.time() - t0
    print(f"\n  Completed {run_i} runs in {elapsed:.0f}s ({elapsed/max(run_i,1):.1f}s/run)")

    # ── Aggregate ──────────────────────────────────────────────────────────
    print(f"\n{'='*110}")
    print(f"  AGGREGATED RESULTS  —  configs with >=2 valid windows shown")
    print(f"{'='*110}")

    rows = []
    for config_key, window_results in results.items():
        if len(window_results) < 2:
            continue

        pfs = [r["profit_factor"] for r in window_results]
        wrs = [r["win_rate"] for r in window_results]
        dds = [r["max_drawdown_pct"] for r in window_results]
        trades = [r["trades"] for r in window_results]
        rets = [r["return_pct"] for r in window_results]

        rows.append({
            "config": config_key,
            "windows": len(window_results),
            "mean_PF": np.mean(pfs),
            "std_PF": np.std(pfs),
            "min_PF": min(pfs),
            "mean_WR": np.mean(wrs),
            "mean_DD": np.mean(dds),
            "max_DD": max(dds),
            "mean_trades": np.mean(trades),
            "mean_ret": np.mean(rets),
            "stability": np.mean(pfs) / max(np.std(pfs), 0.01),
        })

    if not rows:
        print("  No configs with >=2 valid windows.")
        return

    df = pd.DataFrame(rows)
    df = df.sort_values("mean_PF", ascending=False)

    # Header
    header = (f"{'Config':<60} {'Win':>3} {'PF':>6} {'PFstd':>5} {'minPF':>5} "
              f"{'WR':>4} {'DD':>5} {'T':>4} {'Ret%':>5} {'Stab':>5}")
    print(header)
    print("-" * len(header))

    for _, r in df.iterrows():
        config_short = r["config"][:58]
        print(f"{config_short:<60} "
              f"{r['windows']:>3.0f} "
              f"{r['mean_PF']:>5.2f} "
              f"{r['std_PF']:>4.2f} "
              f"{r['min_PF']:>4.2f} "
              f"{r['mean_WR']:>3.0%} "
              f"{r['mean_DD']:>4.1%} "
              f"{r['mean_trades']:>3.0f} "
              f"{r['mean_ret']:>4.1%} "
              f"{r['stability']:>4.0f}")

    # ── Best configs ──────────────────────────────────────────────────────
    print(f"\n  TOP 5 (by mean PF, min 2 windows):")
    top5 = df.head(5)
    for _, r in top5.iterrows():
        print(f"    {r['config']:<60}  PF={r['mean_PF']:.2f}±{r['std_PF']:.2f}  "
              f"WR={r['mean_WR']:.0%}  DD={r['mean_DD']:.1%}  T={r['mean_trades']:.0f}")

    # ── HTF structure filter analysis ─────────────────────────────────────
    print(f"\n{'='*110}")
    print(f"  HTF STRUCTURE FILTER ANALYSIS  —  both direction only")
    print(f"{'='*110}")

    both_no_htf = [r for r in rows if "direction=both" in r["config"] and "htf_structure=False" in r["config"]]
    both_htf = [r for r in rows if "direction=both" in r["config"] and "htf_structure=True" in r["config"]]

    if both_no_htf:
        print(f"  'both' WITHOUT HTF filter:  {len(both_no_htf)} configs")
        avg_pf = np.mean([r["mean_PF"] for r in both_no_htf])
        avg_wr = np.mean([r["mean_WR"] for r in both_no_htf])
        print(f"    avg PF={avg_pf:.2f}  avg WR={avg_wr:.0%}")

        # show best
        best = max(both_no_htf, key=lambda r: r["mean_PF"])
        print(f"    best: {best['config']:<60}  PF={best['mean_PF']:.2f}±{best['std_PF']:.2f}")

    if both_htf:
        print(f"  'both' WITH HTF structure filter:  {len(both_htf)} configs")
        avg_pf = np.mean([r["mean_PF"] for r in both_htf])
        avg_wr = np.mean([r["mean_WR"] for r in both_htf])
        print(f"    avg PF={avg_pf:.2f}  avg WR={avg_wr:.0%}")

        best = max(both_htf, key=lambda r: r["mean_PF"])
        print(f"    best: {best['config']:<60}  PF={best['mean_PF']:.2f}±{best['std_PF']:.2f}")

    # Bull-only filter analysis
    bull_no_htf = [r for r in rows if "direction=bull" in r["config"] and "htf_structure=False" in r["config"]]
    bull_htf = [r for r in rows if "direction=bull" in r["config"] and "htf_structure=True" in r["config"]]

    if bull_no_htf:
        print(f"\n  'bull' WITHOUT HTF filter:  {len(bull_no_htf)} configs")
        print(f"    avg PF={np.mean([r['mean_PF'] for r in bull_no_htf]):.2f}  "
              f"avg WR={np.mean([r['mean_WR'] for r in bull_no_htf]):.0%}")

    if bull_htf:
        print(f"  'bull' WITH HTF structure filter:  {len(bull_htf)} configs")
        print(f"    avg PF={np.mean([r['mean_PF'] for r in bull_htf]):.2f}  "
              f"avg WR={np.mean([r['mean_WR'] for r in bull_htf]):.0%}")

    # ── Save ──────────────────────────────────────────────────────────────
    out_path = ROOT / "backtesting" / "results" / "rolling_trfvg_results.csv"
    out_path.parent.mkdir(exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"\n  Full results: {out_path}")

    return df


if __name__ == "__main__":
    df = main()
