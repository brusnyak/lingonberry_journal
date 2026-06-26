"""
Run TrFvg backtest across crypto pairs with $70 account, 10x leverage.
Analyze: best winners, why losers fail.
"""
import sys, os, json, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from backtesting.engine.base import Strategy
from backtesting.engine.orders import Direction
from backtesting.engine.data import load_data, load_funding_rate
from backtesting.engine.runner import run, BacktestResult
from backtesting.strategies.tr_fvg import TrFvg
from backtesting.engine.metrics import compute as compute_metrics
from backtesting.crypto.costs import build_crypto_costs

# ── Config ────────────────────────────────────────────────────────────────
ACCOUNT = 70.0
LEVERAGE = 10
EXCHANGE = "binance"
DAYS = 30
ENTRY_TFS = ["5", "15"]
SUPPORT_TFS = {"5": ["60", "240"], "15": ["60", "240"]}

# Pairs with good structure quality + high liquidity
PAIRS = [
    "ADAUSDT", "XRPUSDT", "SOLUSDT", "AVAXUSDT",
    "NEARUSDT", "DOGEUSDT", "LINKUSDT", "AAVEUSDT",
    "SUIUSDT",
]

# Param grid — focus on the fix: higher sl_buffer_pips + structure trailing
PARAM_GRID = {
    "sl_buffer_pips": [10, 20],
    "tp1_r": [1.5, 2.0],
    "direction": ["both", "bull", "bear"],
    "min_gap_atr_pct": [0.2],
    "sl_mode": ["structure"],  # use structural SL from swing point
    "structure_sl_lookback": [20],
    "structure_sl_swing_n": [3],
    "min_stop_pct": [0.001],
    "min_stop_atr_mult": [0.25],
    "max_stop_pct": [0.012],
    "max_stop_atr_mult": [2.5],
    "risk_pct": [0.02],
    "tp1_frac": [1.0],
}


def run_one(pair: str, entry_tf: str, params: dict) -> dict:
    try:
        tfs = list(dict.fromkeys([entry_tf] + SUPPORT_TFS.get(entry_tf, ["240"])))
        data = {}
        for tf in tfs:
            df = load_data(pair, tf=tf, days=DAYS, asset_type="crypto", exchange=EXCHANGE)
            if df.empty:
                df = load_data(pair, tf=tf, days=DAYS, asset_type="crypto", exchange="bybit")
            if df.empty:
                return {"pair": pair, "entry_tf": entry_tf, **params, "error": f"no data {tf}"}
            data[tf] = df

        pip_size = 0.0001
        first_close = data[entry_tf]["close"].iloc[0]
        if first_close >= 1000:
            pip_size = 1.0
        elif first_close >= 100:
            pip_size = 0.1
        elif first_close >= 10:
            pip_size = 0.01
        elif first_close >= 1:
            pip_size = 0.001

        strat = TrFvg(pip_size=pip_size, **params)
        costs = build_crypto_costs(pair, exchange=EXCHANGE, leverage=LEVERAGE, pip_size=pip_size)
        result = run(strat, data, entry_tf=entry_tf, costs=costs, initial_equity=ACCOUNT)
        rep = result.report
        return {
            "pair": pair, "exchange": EXCHANGE, "entry_tf": entry_tf, **params,
            "pip_size": pip_size,
            "trades": rep["trades"],
            "win_rate": rep["win_rate"],
            "profit_factor": rep["profit_factor"],
            "payoff_ratio": rep.get("payoff_ratio", 0),
            "avg_r": rep.get("avg_r", 0),
            "total_pnl": rep["total_pnl"],
            "return_pct": rep.get("return_pct", 0),
            "final_equity": rep.get("final_equity", 0),
            "max_drawdown_pct": rep["max_drawdown_pct"],
            "max_drawdown": rep["max_drawdown"],
            "sharpe": rep.get("sharpe", 0),
            "avg_duration_min": rep.get("avg_duration_min", 0),
            "error": None,
        }
    except Exception as e:
        return {"pair": pair, "entry_tf": entry_tf, **params, "error": f"{type(e).__name__}: {e}"}


def main():
    import itertools
    keys = list(PARAM_GRID.keys())
    combos = list(itertools.product(*PARAM_GRID.values()))
    total = len(PAIRS) * len(ENTRY_TFS) * len(combos)

    print(f"\n{'='*100}")
    print(f"  TrFvg Backtest | ${ACCOUNT} @ {LEVERAGE}x | {EXCHANGE} | {DAYS}d | {total} configs")
    print(f"{'='*100}\n")

    results = []
    t0 = time.time()
    i = 0
    for pair in PAIRS:
        for entry_tf in ENTRY_TFS:
            for combo in combos:
                params = dict(zip(keys, combo))
                i += 1
                print(f"  [{i}/{total}] {pair} {entry_tf}m {params}", end="  ", flush=True)
                row = run_one(pair, entry_tf, params)
                results.append(row)
                err = row.get("error")
                if err:
                    print(f"ERROR: {err[:80]}")
                else:
                    print(f"T={row['trades']}  PF={row['profit_factor']:.2f}  WR={row['win_rate']:.0%}")

    elapsed = time.time() - t0
    df = pd.DataFrame(results)

    # ── Print summary ────────────────────────────────────────────────────
    print(f"\n{'='*110}")
    print(f"  TRFVG BACKTEST RESULTS  |  ${ACCOUNT} @ {LEVERAGE}x  |  {EXCHANGE}  |  {DAYS}d  |  {elapsed:.0f}s")
    print(f"{'='*110}")

    # Filter: at least 3 trades, no errors
    valid = df[df["error"].isna() & (df["trades"] >= 3)].copy()
    errors = df[df["error"].notna()]

    if valid.empty:
        print("  No valid results (0 configs with >=3 trades)")
    else:
        # Sort by profit_factor descending
        valid = valid.sort_values("profit_factor", ascending=False)

        cols = ["pair", "entry_tf", "direction", "sl_buffer_pips", "tp1_r",
                "trades", "win_rate", "profit_factor", "payoff_ratio", "avg_r",
                "return_pct", "max_drawdown_pct", "total_pnl"]

        header = f"{'Pair':<10} {'TF':>2} {'Dir':<5} {'SLbuf':>5} {'TP1R':>4} "
        header += f"{'T':>4} {'WR':>5} {'PF':>6} {'RR':>5} {'avgR':>5} {'Ret%':>6} {'DD%':>6} {'PnL':>7}"
        print(header)
        print("-" * len(header))

        for _, r in valid.iterrows():
            line = (f"{r['pair']:<10} {r['entry_tf']:>2} {r['direction']:<5} {r['sl_buffer_pips']:>5} "
                    f"{r['tp1_r']:>4.1f} "
                    f"{r['trades']:>4} "
                    f"{r['win_rate']:>4.0%} "
                    f"{r['profit_factor']:>5.2f} "
                    f"{r['payoff_ratio']:>4.2f} "
                    f"{r['avg_r']:>4.2f} "
                    f"{r['return_pct']:>5.0%} "
                    f"{r['max_drawdown_pct']:>5.1%} "
                    f"{r['total_pnl']:>6.2f}")
            print(line)

        print("-" * len(header))

        # Top 10
        print(f"\n  TOP 10 (by PF >= 3 trades):")
        top10 = valid.head(10)
        for _, r in top10.iterrows():
            print(f"    {r['pair']:<10} {r['entry_tf']:>2}m {r['direction']:<5} "
                  f"SL={r['sl_buffer_pips']} TP={r['tp1_r']}  "
                  f"T={r['trades']} WR={r['win_rate']:.0%} PF={r['profit_factor']:.2f} "
                  f"RR={r['payoff_ratio']:.2f} Ret={r['return_pct']:.0%} DD={r['max_drawdown_pct']:.1%}")

    if not errors.empty:
        print(f"\n  ERRORS: {len(errors)}")
        for _, r in errors.iterrows():
            print(f"    {r['pair']} {r.get('entry_tf','?')}m: {str(r.get('error','?'))[:80]}")

    # ── Detailed analysis of best and worst configs ──────────────────────
    if not valid.empty:
        print(f"\n{'='*110}")
        print(f"  DETAILED ANALYSIS")
        print(f"{'='*110}")

        # Best config
        best = valid.iloc[0]
        worst = valid.iloc[-1]

        print(f"\n  BEST: {best['pair']} {best['entry_tf']}m dir={best['direction']} "
              f"SL={best['sl_buffer_pips']} TP={best['tp1_r']}")
        print(f"    {best['trades']}T  WR={best['win_rate']:.0%}  PF={best['profit_factor']:.2f}  "
              f"RR={best['payoff_ratio']:.2f}  avgR={best['avg_r']:.2f}")
        print(f"    Return: {best['return_pct']:.1%}  DD: {best['max_drawdown_pct']:.1%}  "
              f"PnL: ${best['total_pnl']:.2f}")

        # Aggregate best per pair
        print(f"\n  BEST PER PAIR (by PF):")
        for pair in PAIRS:
            pv = valid[valid["pair"] == pair]
            if pv.empty:
                continue
            best_p = pv.loc[pv["profit_factor"].idxmax()]
            print(f"    {pair:<10} {best_p['entry_tf']:>2}m {best_p['direction']:<5} "
                  f"SL={best_p['sl_buffer_pips']} TP={best_p['tp1_r']}  "
                  f"T={best_p['trades']} WR={best_p['win_rate']:.0%} PF={best_p['profit_factor']:.2f} "
                  f"Ret={best_p['return_pct']:.0%} DD={best_p['max_drawdown_pct']:.1%}")

        # Win rate vs direction
        print(f"\n  WIN RATE BY DIRECTION:")
        for d in ["both", "bull", "bear"]:
            dv = valid[valid["direction"] == d]
            if not dv.empty:
                print(f"    {d:<6}: {len(dv)} configs  avg WR={dv['win_rate'].mean():.0%}  "
                      f"avg PF={dv['profit_factor'].mean():.2f}  avg R={dv['avg_r'].mean():.2f}")

        # Win rate by entry_tf
        print(f"\n  WIN RATE BY ENTRY TF:")
        for tf in ENTRY_TFS:
            tv = valid[valid["entry_tf"] == tf]
            if not tv.empty:
                print(f"    {tf}m: {len(tv)} configs  avg WR={tv['win_rate'].mean():.0%}  "
                      f"avg PF={tv['profit_factor'].mean():.2f}")

        # Win rate by sl_buffer_pips
        print(f"\n  WIN RATE BY SL BUFFER:")
        for buf in [10, 20]:
            bv = valid[valid["sl_buffer_pips"] == buf]
            if not bv.empty:
                print(f"    SL={buf}: {len(bv)} configs  avg WR={bv['win_rate'].mean():.0%}  "
                      f"avg PF={bv['profit_factor'].mean():.2f}")

    # Save
    out_path = ROOT / "results" / "trfvg_backtest_70.csv"
    out_path.parent.mkdir(exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"\n  Full results: {out_path}")

    # Return for further analysis
    return df, valid


if __name__ == "__main__":
    df, valid = main()
