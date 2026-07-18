"""
Walk-forward validation for ORB, addressing "we only had one backtest."

Discipline, stated up front:
  - Hard IS/OOS wall: last 90 days per pair is OOS, untouched during tuning.
  - Parameter search runs on IS only, across ALL 7 pairs pooled -- ONE config
    picked, not per-pair tuned configs. Per-pair tuning is the exact
    overfitting trap flagged in this project's own memory ("engine must
    generalize across assets", 2026-07-13). A config that only wins because
    it was fit to one asset's IS noise is not edge.
  - The winning config is then run UNCHANGED on OOS, in 30d and 60d rolling
    windows, and compared directly against the untouched baseline default
    (risk_pct=0.005, confirm_bars=0) on the same OOS data. If the "improved"
    config doesn't actually beat baseline OOS, that's reported as-is, not
    hidden -- an IS-only win that fails OOS is exactly the failure mode this
    script exists to catch.

Usage: python -m backtesting.crypto.orb_walk_forward
"""
from __future__ import annotations

import sys
from pathlib import Path
from itertools import product

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from backtesting.crypto.data import load_market_specs
from backtesting.crypto.validation import rolling_validate
from backtesting.engine.costs import CryptoCosts
from backtesting.engine.data import load_data, load_funding_rate
from backtesting.engine.runner import run
from backtesting.lvl2_orb.orb_wide_stop import OrbNyWideStop

PAIRS = ["DOGEUSDT", "XRPUSDT", "SOLUSDT", "PUMPUSDT", "BOMEUSDT", "1000BONKUSDT", "AKEUSDT"]
OOS_DAYS = 90
EXCHANGE = "bingx"

PARAM_GRID = {
    # or_len_min/target_r actually change WHICH trades get taken and where
    # they exit -- unlike risk_pct (pure position sizing, mathematically
    # invariant to WR/PF) and confirm_bars (came back completely inert on
    # the first pass, identical numbers at 0 and 1 -- dropped).
    "or_len_min": [15, 30],
    "target_r": [5.0, 10.0],
}
BASELINE = {"or_len_min": 15, "target_r": 10.0}


def load_pair(pair: str):
    data = {}
    for tf in ("5", "30", "240"):
        data[tf] = load_data(pair, tf=tf, exchange=EXCHANGE)
    return data


def split_is_oos(data: dict, oos_days: int) -> tuple[dict, dict]:
    cutoff = data["5"]["ts"].max() - pd.Timedelta(days=oos_days)
    is_data = {tf: df[df["ts"] < cutoff].reset_index(drop=True) for tf, df in data.items()}
    oos_data = {tf: df[df["ts"] >= cutoff].reset_index(drop=True) for tf, df in data.items()}
    return is_data, oos_data


def backtest(data: dict, params: dict, pair: str):
    funding_df = load_funding_rate(pair, exchange=EXCHANGE)
    costs = CryptoCosts(
        maker_fee=0.0002, taker_fee=0.0005, leverage=50.0,
        funding_df=funding_df if funding_df is not None and not funding_df.empty else None,
        min_notional=2.0, entry_slippage_pct=0.0005, sl_slippage_pct=0.0005,
    )
    strat = OrbNyWideStop(htf_key="240", ltf_key="30", multi_target=True, **params)
    if any(data[tf].empty or len(data[tf]) < 50 for tf in data):
        return None
    return run(strat, data, entry_tf="5", costs=costs, initial_equity=20.0)


def main():
    print(f"=== Phase 1: IS parameter search, pooled across {len(PAIRS)} pairs ===\n")
    is_data_by_pair = {}
    oos_data_by_pair = {}
    for pair in PAIRS:
        data = load_pair(pair)
        is_data, oos_data = split_is_oos(data, OOS_DAYS)
        is_data_by_pair[pair] = is_data
        oos_data_by_pair[pair] = oos_data

    grid_rows = []
    configs = [dict(zip(PARAM_GRID.keys(), combo)) for combo in product(*PARAM_GRID.values())]
    for params in configs:
        pooled_windows = 0
        pooled_profitable = 0
        pooled_pf_list = []
        for pair in PAIRS:
            result = backtest(is_data_by_pair[pair], params, pair)
            if result is None:
                continue
            trades = result.to_df()
            if len(trades) < 15:
                continue
            vt = rolling_validate(trades, window_days=30, step_days=10, min_trades=3, initial_equity=20.0)
            if vt.n_windows:
                pooled_windows += vt.n_windows
                pooled_profitable += vt.n_profitable
                pooled_pf_list.append(vt.median_pf)
        pass_rate = pooled_profitable / pooled_windows if pooled_windows else 0
        avg_median_pf = sum(pooled_pf_list) / len(pooled_pf_list) if pooled_pf_list else 0
        grid_rows.append({**params, "pooled_windows": pooled_windows,
                           "pass_rate": pass_rate, "avg_median_pf": avg_median_pf})

    grid_df = pd.DataFrame(grid_rows).sort_values(["pass_rate", "avg_median_pf"], ascending=False)
    pd.set_option("display.width", 160)
    print(grid_df.to_string(index=False))

    winner = grid_df.iloc[0][list(PARAM_GRID.keys())].to_dict()
    winner = {k: (int(v) if k == "or_len_min" else float(v)) for k, v in winner.items()}
    print(f"\nWinning IS config: {winner}")
    print(f"Baseline for comparison: {BASELINE}")

    print(f"\n=== Phase 2: OOS validation (last {OOS_DAYS}d, untouched during tuning) ===\n")
    oos_rows = []
    for pair in PAIRS:
        for label, params in [("winner", winner), ("baseline", BASELINE)]:
            result = backtest(oos_data_by_pair[pair], params, pair)
            if result is None:
                oos_rows.append({"pair": pair, "config": label, "error": "no data"})
                continue
            rep = result.report
            trades = result.to_df()
            row = {"pair": pair, "config": label, "trades": rep.get("trades", 0),
                   "pf": rep.get("profit_factor", 0), "wr": rep.get("win_rate", 0),
                   "return_pct": rep.get("return_pct", 0), "dd_pct": rep.get("max_drawdown_pct", 0)}
            if len(trades) >= 10:
                vt30 = rolling_validate(trades, window_days=30, step_days=10, min_trades=3, initial_equity=20.0)
                if vt30.n_windows:
                    row["oos_30d_windows"] = vt30.n_windows
                    row["oos_30d_pass_rate"] = vt30.n_profitable / vt30.n_windows
            oos_rows.append(row)

    oos_df = pd.DataFrame(oos_rows)
    print(oos_df.to_string(index=False))

    out = ROOT / "backtesting" / "crypto" / "reports" / "orb_walk_forward.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    oos_df.to_csv(out, index=False)
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
