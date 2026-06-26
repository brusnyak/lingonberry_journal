"""
Analyze why short trades fail in TrFvg crypto backtest.

Runs best configs, splits trades by direction, computes per-direction
metrics, exit reason distributions, R-multiple profiles, and MFE/MAE.

Output: summary table + per-trade CSV for review page import.
"""
import sys, os, json, time
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from backtesting.engine.data import load_data
from backtesting.engine.costs import CryptoCosts
from backtesting.engine.runner import run
from backtesting.strategies.tr_fvg import TrFvg
from backtesting.engine.orders import Direction, ExitReason

# ── Config ────────────────────────────────────────────────────────────────
ACCOUNT = 70.0
LEVERAGE = 50
END = "2026-06-26"
WINDOWS = [
    ("2026-05-27", "2026-06-26"),  # IS window
    ("2026-05-20", "2026-06-19"),
    ("2026-05-13", "2026-06-12"),
]

# Test both on pairs with enough trades
CONFIGS = [
    {"pair": "XRPUSDT", "tf": "15",
     "params": {"sl_buffer_pips": 20, "tp1_r": 2.0, "direction": "both",
                "min_gap_atr_pct": 0.2, "sl_mode": "structure",
                "structure_sl_lookback": 20, "structure_sl_swing_n": 3}},
    {"pair": "AVAXUSDT", "tf": "15",
     "params": {"sl_buffer_pips": 20, "tp1_r": 2.0, "direction": "both",
                "min_gap_atr_pct": 0.2, "sl_mode": "structure",
                "structure_sl_lookback": 20, "structure_sl_swing_n": 3}},
    {"pair": "DOGEUSDT", "tf": "15",
     "params": {"sl_buffer_pips": 20, "tp1_r": 2.0, "direction": "both",
                "min_gap_atr_pct": 0.2, "sl_mode": "structure",
                "structure_sl_lookback": 20, "structure_sl_swing_n": 3}},
]

# ── Helpers ───────────────────────────────────────────────────────────────

def detect_pip_size(df: pd.DataFrame) -> float:
    c = df["close"].iloc[0]
    if c >= 1000: return 1.0
    if c >= 100:  return 0.1
    if c >= 10:   return 0.01
    if c >= 1:    return 0.001
    return 0.0001


def run_config(pair: str, tf: str, params: dict, start: str, end: str):
    """Run backtest, return BacktestResult."""
    tfs = list(dict.fromkeys([tf, "60", "240"]))
    data = {}
    for t in tfs:
        df = load_data(pair, tf=t, start=start, end=end, exchange="binance")
        if df.empty:
            df = load_data(pair, tf=t, start=start, end=end, exchange="bybit")
        data[t] = df

    pip_size = detect_pip_size(data[tf])
    strat = TrFvg(pip_size=pip_size, **params)
    costs = CryptoCosts(leverage=LEVERAGE)
    result = run(strat, data, entry_tf=tf, costs=costs, initial_equity=ACCOUNT)
    return result


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*110}")
    print(f"  SHORT TRADE AUTOPSY  —  TrFvg direction breakdown")
    print(f"{'='*110}\n")

    all_trades = []
    summary_rows = []

    for cfg in CONFIGS:
        pair = cfg["pair"]
        tf = cfg["tf"]
        params = cfg["params"]
        label = f"{pair} {tf}m {' '.join(f'{k}={v}' for k,v in params.items())}"

        for w_start, w_end in WINDOWS:
            wins = w_start[:10]
            print(f"  {label}  [{wins}] ...", end=" ", flush=True)
            result = run_config(pair, tf, params, w_start, w_end)
            df_trades = result.to_df()

            if df_trades.empty:
                print("0 trades")
                continue

            df_trades["pair"] = pair
            df_trades["tf"] = tf
            df_trades["window"] = w_start[:10]
            df_trades["direction_str"] = df_trades["direction"].apply(
                lambda d: "long" if d in (1, "LONG", Direction.LONG) else "short"
            )

            # Compute per-direction stats for this window
            for dir_name in ["long", "short"]:
                subset = df_trades[df_trades["direction_str"] == dir_name]
                if len(subset) < 2:
                    continue

                wins = subset[subset["pnl"] > 0]
                losses = subset[subset["pnl"] <= 0]
                exit_dist = subset["exit_reason"].value_counts()

                r_vals = subset["r_multiple"].dropna()
                entry_r = params.get("tp1_r", 2.0)

                summary_rows.append({
                    "pair": pair, "tf": tf, "window": w_start[:10],
                    "direction": dir_name,
                    "trades": len(subset),
                    "win_rate": len(wins) / len(subset),
                    "profit_factor": sum(wins["pnl"]) / abs(sum(losses["pnl"])) if len(losses) > 0 else float("inf"),
                    "avg_pnl": subset["pnl"].mean(),
                    "total_pnl": subset["pnl"].sum(),
                    "avg_r": r_vals.mean() if len(r_vals) > 0 else 0,
                    "median_r": r_vals.median() if len(r_vals) > 0 else 0,
                    "exit_tp": exit_dist.get("tp_hit", exit_dist.get("take_profit", exit_dist.get("TP", 0))),
                    "exit_sl": exit_dist.get("sl_hit", exit_dist.get("stop_loss", exit_dist.get("SL", 0))),
                    "exit_trail": exit_dist.get("trailing_stop", exit_dist.get("TRAILING_STOP", exit_dist.get("trailing", 0))),
                    "exit_timeout": exit_dist.get("timeout", exit_dist.get("TIMEOUT", 0)),
                })

            all_trades.append(df_trades)
            print(f"{len(df_trades)} trades")

    if not summary_rows:
        print("  No trades to analyze.")
        return

    df_summ = pd.DataFrame(summary_rows)

    # ── Print per-pair direction comparison ────────────────────────────
    print(f"\n{'='*110}")
    print(f"  DIRECTION BREAKDOWN  —  comparing longs vs shorts per pair")
    print(f"{'='*110}")

    header = f"{'Pair':<10} {'Dir':<6} {'Win':>3} {'T':>3} {'WR':>5} {'PF':>6} {'avgR':>5} {'medR':>5} {'avgPnL':>7} {'TP':>3} {'SL':>3} {'Trail':>5}"
    print(header)
    print("-" * len(header))

    for pair in sorted(df_summ["pair"].unique()):
        for dir_name in ["long", "short"]:
            subset = df_summ[(df_summ["pair"] == pair) & (df_summ["direction"] == dir_name)]
            if subset.empty:
                continue

            avg = subset.mean(numeric_only=True)
            total = subset.sum(numeric_only=True)

            line = (f"{pair:<10} {dir_name:<6} "
                    f"{avg['win_rate']*avg['trades']:>3.0f} "
                    f"{avg['trades']:>3.0f} "
                    f"{avg['win_rate']:>4.0%} "
                    f"{avg['profit_factor']:>5.2f} "
                    f"{avg['avg_r']:>4.2f} "
                    f"{avg['median_r']:>4.2f} "
                    f"{avg['avg_pnl']:>6.2f} "
                    f"{avg['exit_tp']:>3.0f} "
                    f"{avg['exit_sl']:>3.0f} "
                    f"{avg['exit_trail']:>3.0f}")
            print(line)

        print("-" * len(header))

    # ── Aggregate stats per direction ──────────────────────────────────
    print(f"\n{'='*110}")
    print(f"  AGGREGATE  —  all pairs, all windows")
    print(f"{'='*110}")

    for dir_name in ["long", "short"]:
        subset = df_summ[df_summ["direction"] == dir_name]
        if subset.empty:
            continue

        avg = subset.mean(numeric_only=True)
        total = subset.sum(numeric_only=True)
        total_trades = avg["trades"] * len(subset)
        total_wins = avg["win_rate"] * total_trades if total_trades > 0 else 0

        print(f"\n  {dir_name.upper()}:")
        print(f"    Total trades:  {total_trades:.0f}  ({len(subset)} window-configs)")
        print(f"    Win rate:      {avg['win_rate']:.1%}")
        print(f"    Profit factor: {avg['profit_factor']:.2f}")
        print(f"    Avg R:         {avg['avg_r']:.2f}")
        print(f"    Median R:      {avg['median_r']:.2f}")
        print(f"    Avg PnL:       ${avg['avg_pnl']:.2f}")
        print(f"    Total PnL:     ${total['total_pnl']:.2f}")
        print(f"    Exit TP:       {avg['exit_tp']:.0f} trades (TP hit)")
        print(f"    Exit SL:       {avg['exit_sl']:.0f} trades (SL hit)")
        print(f"    Exit trail:    {avg['exit_trail']:.0f} trades (trailed out)")

    # ── Aggregate by exit reason ──────────────────────────────────────
    print(f"\n{'='*110}")
    print(f"  EXIT REASON ANALYSIS  —  all trades pooled")
    print(f"{'='*110}")

    all_df = pd.concat(all_trades, ignore_index=True)
    for dir_name in ["long", "short"]:
        sub = all_df[all_df["direction_str"] == dir_name]
        print(f"\n  {dir_name.upper()}  ({len(sub)} trades):")
        exit_counts = sub["exit_reason"].value_counts()
        for reason, count in exit_counts.items():
            winrate = sub[(sub["exit_reason"] == reason) & (sub["pnl"] > 0)].shape[0] / count if count > 0 else 0
            avg_r = sub[sub["exit_reason"] == reason]["r_multiple"].mean()
            print(f"    {reason:<20}  {count:>3} trades  WR={winrate:.0%}  avgR={avg_r:.2f}")

    # ── R-multiple distribution ───────────────────────────────────────
    print(f"\n{'='*110}")
    print(f"  R-MULTIPLE DISTRIBUTION  —  how often does each R-level hit?")
    print(f"{'='*110}")

    for dir_name in ["long", "short"]:
        sub = all_df[all_df["direction_str"] == dir_name]
        r_vals = sub["r_multiple"].dropna()

        print(f"\n  {dir_name.upper()}:")
        for r_bin in [0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0]:
            pct = (r_vals >= r_bin).mean() * 100 if len(r_vals) > 0 else 0
            print(f"    R >= {r_bin:>3.1f}:  {pct:>4.0f}% of trades")

    # ── Save individual trade data ─────────────────────────────────────
    out_dir = ROOT / "results"
    out_dir.mkdir(exist_ok=True)

    # Per-trade CSV for review
    all_df.to_csv(out_dir / "short_analysis_trades.csv", index=False)
    print(f"\n  Per-trade data: {out_dir / 'short_analysis_trades.csv'}")

    # Summary JSON for review page
    summ_json = []
    for _, r in df_summ.iterrows():
        summ_json.append({
            "pair": r["pair"], "tf": r["tf"], "window": r["window"],
            "direction": r["direction"],
            "trades": int(r["trades"]),
            "win_rate": round(float(r["win_rate"]), 4),
            "profit_factor": round(float(r["profit_factor"]), 3),
            "avg_r": round(float(r["avg_r"]), 2),
            "median_r": round(float(r["median_r"]), 2),
            "avg_pnl": round(float(r["avg_pnl"]), 2),
            "total_pnl": round(float(r["total_pnl"]), 2),
        })
    with open(out_dir / "short_analysis_summary.json", "w") as f:
        json.dump(summ_json, f, indent=2)
    print(f"  Summary JSON:     {out_dir / 'short_analysis_summary.json'}")

    return df_summ, all_df


if __name__ == "__main__":
    df_summ, all_df = main()
