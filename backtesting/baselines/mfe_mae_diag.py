#!/usr/bin/env python3
"""
MFE/MAE + rolling-30D diagnostic for the (rejected) KL sweep+reclaim entries.

NOT a new strategy. NOT parameter optimization. This only asks: do the entries
the strategy ACTUALLY took have any salvageable quality?

Method:
  - Take the real trade set from each cell (correct next-bar fills + 1-at-a-time
    gating).
  - For each trade, forward-walk the 15m bars from entry, IGNORING the 1R take-
    profit (which otherwise caps every winner at 1R), stopping only at the real
    SL or a 24h horizon. Record max favorable / adverse excursion in R.
    R = |entry - sl|.  "Reached XR" = MFE >= X before the stop ended it.
  - Rolling 30-calendar-day windows (step 7d) for realized performance, vs a
    random-direction null on the same entries.

IS-only (OOS wall). Cells under test (from the 40-cell scan, the two that
beat the null on direction):
  EURGBP  ema20 / 1.0R / regime
  GBPCAD  vwap  / 1.0R / regime
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backtesting.engine.costs import ForexCosts
from backtesting.engine.data import load_data
from backtesting.engine.runner import run
from backtesting.strategies.kl_sweep_reclaim_v0 import KlSweepReclaimV0
from backtesting.baselines.run_kl_sweep import RandomDirNull

CELLS = [
    dict(pair="EURGBP", reclaim="ema20", rr=1.0, use_regime=True),
    dict(pair="GBPCAD", reclaim="vwap", rr=1.0, use_regime=True),
]
# London-session UTC hours (matches session_of "London" bucket). Set to None for all.
import os
LONDON_HOURS = {7, 8, 9, 10, 11}
ALLOWED_HOURS = LONDON_HOURS if os.environ.get("LONDON_ONLY") == "1" else None
HORIZON_BARS = 96          # 24h on 15m — max hold for the excursion walk
THRESHOLDS = [0.5, 1.0, 1.5, 2.0, 3.0]
INIT_EQ = 10_000.0
NULL_SEEDS = 40


def session_of(ts: pd.Timestamp) -> str:
    h = ts.hour  # UTC
    if 0 <= h < 7:
        return "Asia"
    if 7 <= h < 12:
        return "London"
    if 12 <= h < 17:
        return "NY"
    return "Late"


def trade_excursions(trades: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    """Append mfe_r / mae_r to each trade via forward walk (SL-or-horizon)."""
    ts = df["ts"].astype("int64").to_numpy()  # UTC nanoseconds
    high = df["high"].to_numpy()
    low = df["low"].to_numpy()
    rows = []
    for _, t in trades.iterrows():
        entry, sl = t["entry_price"], t["sl"]
        R = abs(entry - sl)
        if R <= 0:
            continue
        idx = int(np.searchsorted(ts, pd.Timestamp(t["entry_time"]).value))
        if idx >= len(ts):
            continue
        is_long = t["direction"] == "long"
        mfe = mae = 0.0
        end = min(idx + HORIZON_BARS, len(ts) - 1)
        for k in range(idx, end + 1):
            if is_long:
                mfe = max(mfe, (high[k] - entry) / R)
                mae = max(mae, (entry - low[k]) / R)
                if low[k] <= sl:
                    break
            else:
                mfe = max(mfe, (entry - low[k]) / R)
                mae = max(mae, (high[k] - entry) / R)
                if high[k] >= sl:
                    break
        rows.append({**t.to_dict(), "mfe_r": mfe, "mae_r": mae,
                     "session": session_of(pd.Timestamp(t["entry_time"]))})
    return pd.DataFrame(rows)


def reach_table(ex: pd.DataFrame) -> str:
    n = len(ex)
    if n == 0:
        return "  (no trades)"
    lines = []
    for x in THRESHOLDS:
        c = int((ex["mfe_r"] >= x).sum())
        lines.append(f"    MFE>={x:>3}R : {c:>4} / {n}  ({c/n:5.1%})")
    lines.append(f"    median MFE {ex['mfe_r'].median():.2f}R | median MAE {ex['mae_r'].median():.2f}R")
    lines.append(f"    full stop-out (MAE>=1R): {(ex['mae_r']>=0.999).mean():.1%}")
    return "\n".join(lines)


def window_stats(tr: pd.DataFrame) -> dict:
    """Rolling 30d (step 7d) realized stats from a trade list (exit_time, pnl, r_multiple)."""
    if tr.empty:
        return {}
    tr = tr.sort_values("exit_time")
    t0 = pd.Timestamp(tr["exit_time"].min())
    t1 = pd.Timestamp(tr["exit_time"].max())
    rets, dds, counts, pfs, avgrs, streaks, profitable = [], [], [], [], [], [], 0
    start = t0
    step, win = pd.Timedelta(days=7), pd.Timedelta(days=30)
    n_win = 0
    worst = None
    while start <= t1:
        w = tr[(tr["exit_time"] >= start) & (tr["exit_time"] < start + win)]
        start += step
        if len(w) < 3:
            continue
        n_win += 1
        pnl = w["pnl"].to_numpy()
        ret = pnl.sum() / INIT_EQ
        curve = np.cumsum(pnl)
        peak = np.maximum.accumulate(np.concatenate([[0.0], curve]))
        dd = float((peak[1:] - curve).max()) / INIT_EQ
        pos, neg = pnl[pnl > 0].sum(), pnl[pnl <= 0].sum()
        pf = pos / abs(neg) if neg < 0 else float("inf")
        avgr = float(w["r_multiple"].mean())
        # losing streak
        s = mx = 0
        for r in w["r_multiple"]:
            s = s + 1 if r <= 0 else 0
            mx = max(mx, s)
        rets.append(ret); dds.append(dd); counts.append(len(w))
        pfs.append(pf if np.isfinite(pf) else np.nan); avgrs.append(avgr); streaks.append(mx)
        profitable += int(ret > 0)
        if worst is None or ret < worst[0]:
            worst = (ret, dd, len(w), str(start - step)[:10])
    if n_win == 0:
        return {}
    return dict(
        n_win=n_win,
        ret_mean=np.mean(rets), ret_med=np.median(rets),
        dd_med=np.median(dds), dd_max=np.max(dds),
        cnt_med=int(np.median(counts)),
        pf_med=np.nanmedian(pfs),
        avgr_med=np.median(avgrs),
        streak_max=int(np.max(streaks)),
        pct_profit=profitable / n_win,
        worst=worst,
    )


def main() -> None:
    all_ex = []
    per_cell_tr = {}
    dfs = {}
    for c in CELLS:
        pair = c["pair"]
        df = load_data(pair, tf="15", days=99999)
        dfs[pair] = df
        kw = dict(reclaim=c["reclaim"], rr=c["rr"], use_regime=c["use_regime"], allowed_hours=ALLOWED_HOURS, entry_tf="15")
        res = run(KlSweepReclaimV0(**kw), {"15": df}, entry_tf="15",
                  costs=ForexCosts(seed=0), initial_equity=INIT_EQ, next_bar_fill=True)
        tr = res.to_df()
        tr["pair"] = pair
        tr["cell"] = f"{pair}/{c['reclaim']}"
        per_cell_tr[pair] = (tr, res.report)
        ex = trade_excursions(tr, df)
        ex["cell"] = f"{pair}/{c['reclaim']}"
        all_ex.append(ex)

    ex = pd.concat(all_ex, ignore_index=True)

    print("=" * 64)
    print("1. MFE/MAE SUMMARY  (forward walk, SL-or-24h, exit-agnostic)")
    print("=" * 64)
    print(f"\nPOOLED  (n={len(ex)})")
    print(reach_table(ex))

    print("\n" + "=" * 64)
    print("3. BREAKDOWN")
    print("=" * 64)
    for key in ["cell", "direction", "session"]:
        print(f"\n-- by {key} --")
        for val, grp in ex.groupby(key):
            print(f"  [{val}]  n={len(grp)}")
            print(reach_table(grp))

    print("\n" + "=" * 64)
    print("2. ROLLING 30D  (step 7d, windows with >=3 trades)")
    print("=" * 64)
    pooled_tr = pd.concat([t for t, _ in per_cell_tr.values()], ignore_index=True)
    for label, tr in [("EURGBP", per_cell_tr["EURGBP"][0]),
                      ("GBPCAD", per_cell_tr["GBPCAD"][0]),
                      ("POOLED", pooled_tr)]:
        s = window_stats(tr)
        if not s:
            print(f"\n{label}: too few windows")
            continue
        print(f"\n{label}  ({s['n_win']} windows)")
        print(f"  30D return   mean {s['ret_mean']:+.2%}  median {s['ret_med']:+.2%}")
        print(f"  30D max DD   median {s['dd_med']:.2%}  worst {s['dd_max']:.2%}")
        print(f"  30D trades   median {s['cnt_med']}")
        print(f"  30D PF       median {s['pf_med']:.2f}")
        print(f"  30D avg R    median {s['avgr_med']:+.3f}")
        print(f"  30D streak   max losing {s['streak_max']}")
        print(f"  % profitable windows  {s['pct_profit']:.1%}")
        print(f"  worst window  {s['worst'][0]:+.2%} ret, {s['worst'][1]:.2%} DD, "
              f"{s['worst'][2]} trades, ~{s['worst'][3]}")

    print("\n" + "=" * 64)
    print("6. 30D vs RANDOM-DIRECTION NULL")
    print("=" * 64)
    strat_pct = window_stats(pooled_tr)["pct_profit"]
    null_pcts, null_means = [], []
    for seed in range(NULL_SEEDS):
        ntr = []
        for c in CELLS:
            kw = dict(reclaim=c["reclaim"], rr=c["rr"], use_regime=c["use_regime"], allowed_hours=ALLOWED_HOURS, entry_tf="15")
            nres = run(RandomDirNull(seed=seed, **kw), {"15": dfs[c["pair"]]}, entry_tf="15",
                       costs=ForexCosts(seed=0), initial_equity=INIT_EQ, next_bar_fill=True)
            ntr.append(nres.to_df())
        ns = window_stats(pd.concat(ntr, ignore_index=True))
        if ns:
            null_pcts.append(ns["pct_profit"])
            null_means.append(ns["ret_mean"])
    np_pcts = np.array(null_pcts)
    pctile = float((np_pcts < strat_pct).mean() * 100)
    print(f"  Strategy % profitable 30D windows : {strat_pct:.1%}")
    print(f"  Null     % profitable (mean)       : {np_pcts.mean():.1%}  "
          f"(range {np_pcts.min():.1%}..{np_pcts.max():.1%})")
    print(f"  Null     30D return mean           : {np.mean(null_means):+.2%}")
    print(f"  -> strategy sits at {pctile:.0f}th percentile of null on window-win-rate")


if __name__ == "__main__":
    main()
