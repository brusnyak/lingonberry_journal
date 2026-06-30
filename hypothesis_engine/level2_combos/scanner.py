"""
Level 2 — Pairwise condition combinations.

Tests stacked conditions: signal fires only when both conditions agree
on direction on the same bar.

Uses same rolling-window bootstrap methodology as Level 0/1.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from backtesting.engine.data import load_data
from hypothesis_engine.level0_statistical.scanner import _compute_stats, SESSIONS
from hypothesis_engine.level1_conditions.conditions import CONDITIONS


# Condition pairs to test (most promising from Level 1)
COMBO_PAIRS: list[tuple[str, str]] = [
    ("bos", "fvg"),
    ("bos", "sweep"),
    ("bos", "choch"),
    ("fvg", "sweep"),
    ("bos", "engulfing"),
    ("bos", "inside_bar"),
]


def combo_name(a: str, b: str) -> str:
    """Sorted combination name, e.g. 'bos+fvg'."""
    return "+".join(sorted([a, b]))


def combine_signals(sig_a: np.ndarray, sig_b: np.ndarray) -> np.ndarray:
    """
    AND combination: fires only when both signals agree.
    Returns: +1 when both +1, -1 when both -1, 0 otherwise.
    """
    out = np.zeros(len(sig_a), dtype=np.int64)
    out[(sig_a == 1) & (sig_b == 1)] = 1
    out[(sig_a == -1) & (sig_b == -1)] = -1
    return out


def rolling_combo_scan(
    symbol: str,
    tf: str,
    cond_a: str,
    cond_b: str,
    *,
    window_days: int = 30,
    step_days: int = 15,
    horizons: tuple[int, ...] = (1, 5, 20, 50),
    max_windows: int = 40,
    allow_oos: bool = True,
) -> dict:
    """Rolling window scan for a condition pair."""
    if cond_a not in CONDITIONS:
        return {"error": f"Unknown condition: {cond_a}"}
    if cond_b not in CONDITIONS:
        return {"error": f"Unknown condition: {cond_b}"}

    df = load_data(symbol, tf, days=0, allow_oos=allow_oos)
    if df.empty:
        return {"error": f"No data for {symbol} {tf}"}

    fn_a, fn_b = CONDITIONS[cond_a], CONDITIONS[cond_b]
    n = len(df)
    if n < 200:
        return {"error": f"Too few bars ({n}) for {symbol} {tf}"}

    arrays = {
        "open": df["open"].to_numpy(dtype=float),
        "high": df["high"].to_numpy(dtype=float),
        "low": df["low"].to_numpy(dtype=float),
        "close": df["close"].to_numpy(dtype=float),
    }
    close = arrays["close"]

    # Build windows
    ts = pd.to_datetime(df["ts"])
    t_min, t_max = ts.iloc[0], ts.iloc[-1]
    windows = []
    w_start = t_min
    while w_start + pd.Timedelta(days=window_days) <= t_max and len(windows) < max_windows:
        w_end = w_start + pd.Timedelta(days=window_days)
        mask = (ts >= w_start) & (ts < w_end)
        if mask.sum() >= 100:
            windows.append({"idx": len(windows), "start": str(w_start)[:10],
                            "end": str(w_end)[:10], "mask": mask.values})
        w_start += pd.Timedelta(days=step_days)

    if len(windows) < 2:
        return {"error": f"Only {len(windows)} window(s) for {symbol} {tf}"}

    # Precompute forward returns
    forward_rets = {}
    for h in horizons:
        if h >= n:
            continue
        ret = np.full(n, np.nan)
        ret[:n - h] = np.log(close[h:] / close[:n - h])
        forward_rets[h] = ret

    # Compute both condition signals ONCE
    sig_a = fn_a(**arrays)
    sig_b = fn_b(**arrays)
    signal = combine_signals(sig_a, sig_b)

    if signal.sum() == 0:
        return {"error": f"Combo {cond_a}+{cond_b} produced no signals for {symbol} {tf}"}

    hours = ts.dt.hour.values
    cname = combo_name(cond_a, cond_b)

    all_results: list[dict] = []
    for win in windows:
        m = win["mask"]
        for sname, (h_start, h_end) in SESSIONS.items():
            s_mask = m & (hours >= h_start) & (hours < h_end)
            if int(s_mask.sum()) < 10:
                continue

            for h in horizons:
                if h not in forward_rets:
                    continue
                r = forward_rets[h]

                for sig_name, sig_mask in [("long", s_mask & (signal == 1)),
                                           ("short", s_mask & (signal == -1))]:
                    vals = r[sig_mask]
                    vals = vals[~np.isnan(vals)]
                    if len(vals) < 3:
                        continue

                    stats = _compute_stats(vals)
                    stats["n"] = len(vals)

                    # For short signals, flip returns for consistent interpretation
                    if sig_name == "short":
                        stats["mean_ret"] = -stats["mean_ret"]
                        stats["ci_low"], stats["ci_high"] = -stats["ci_high"], -stats["ci_low"]
                        stats["t_stat"] = -stats["t_stat"]
                        stats["win_rate"] = 1 - stats["win_rate"]
                        stats["profit_factor"] = 1 / stats["profit_factor"] if stats["profit_factor"] > 0 else float("inf")

                    all_results.append({
                        "symbol": symbol, "tf": tf,
                        "combo": cname,
                        "signal_dir": sig_name,
                        "session": sname, "horizon": h,
                        "window_idx": win["idx"],
                        "window_start": win["start"], "window_end": win["end"],
                        "n": stats["n"],
                        "mean_ret": stats["mean_ret"],
                        "std_ret": stats["std_ret"],
                        "win_rate": stats["win_rate"],
                        "profit_factor": stats["profit_factor"],
                        "t_stat": stats["t_stat"],
                        "p_value_approx": stats["p_value_approx"],
                        "ci_low": stats["ci_low"], "ci_high": stats["ci_high"],
                        "ci_contains_zero": stats["ci_contains_zero"],
                        "effect_size": stats["effect_size"],
                    })

    return {
        "symbol": symbol, "tf": tf,
        "combo": cname,
        "total_bars": n, "n_windows": len(windows),
        "total_signals": int(signal.sum()),
        "data_start": str(ts.iloc[0])[:10], "data_end": str(ts.iloc[-1])[:10],
        "results": all_results,
    }


def aggregate_combo_rolling(scan_result: dict) -> pd.DataFrame:
    """Aggregate results — same as Level 1."""
    if "error" in scan_result:
        return pd.DataFrame()

    df = pd.DataFrame(scan_result["results"])
    if df.empty:
        return pd.DataFrame()

    def _stability(s):
        pos, neg = (s > 0).sum(), (s < 0).sum()
        return max(pos, neg) / len(s)

    agg = df.groupby(
        ["symbol", "tf", "combo", "signal_dir", "session", "horizon"],
        as_index=False,
    ).agg(
        n_windows=("mean_ret", "count"),
        n_significant=("ci_contains_zero", lambda x: (~x).sum()),
        n_positive=("mean_ret", lambda x: (x > 0).sum()),
        n_negative=("mean_ret", lambda x: (x < 0).sum()),
        stability=("mean_ret", _stability),
        mean_mean_ret=("mean_ret", "mean"),
        avg_t_stat=("t_stat", "mean"),
        avg_pf=("profit_factor", "mean"),
        avg_wr=("win_rate", "mean"),
    )

    agg["sign"] = agg["mean_mean_ret"].apply(lambda x: 1 if x > 0 else -1)
    agg["consistent"] = agg["stability"] >= 1.0
    agg["score"] = (agg["n_significant"] / agg["n_windows"]) * agg["avg_t_stat"].abs()
    agg = agg.sort_values("score", ascending=False).reset_index(drop=True)
    return agg


def run_all(
    symbols: list[str] | None = None,
    tfs: tuple[str, ...] = ("5", "15", "60", "240"),
    combos: list[tuple[str, str]] | None = None,
    window_days: int = 30,
    step_days: int = 15,
    max_windows: int = 40,
    allow_oos: bool = True,
    verbose: bool = True,
) -> pd.DataFrame:
    """Run all combo scans."""
    from backtesting.engine.data import list_pairs

    if symbols is None:
        symbols = list_pairs("forex")[:21]
    if combos is None:
        combos = COMBO_PAIRS

    total = len(symbols) * len(tfs) * len(combos)
    done = 0
    all_agg: list[pd.DataFrame] = []

    for sym in symbols:
        for tf in tfs:
            for ca, cb in combos:
                done += 1
                cname = combo_name(ca, cb)
                if verbose:
                    print(f"  [{done:>4}/{total}] {sym:<12} {tf:>3}m {cname:<15} ...", end=" ", flush=True)

                result = rolling_combo_scan(sym, tf, ca, cb,
                    window_days=window_days, step_days=step_days,
                    horizons=(1, 5, 20, 50),
                    max_windows=max_windows, allow_oos=allow_oos)

                if "error" in result:
                    if verbose:
                        print(f"SKIP ({result['error']})")
                    continue

                agg = aggregate_combo_rolling(result)
                if not agg.empty:
                    all_agg.append(agg)
                if verbose:
                    print(f"{result['n_windows']} windows, {result['total_signals']} signals")

    if not all_agg:
        return pd.DataFrame()

    final = pd.concat(all_agg, ignore_index=True)
    final = final.sort_values("score", ascending=False).reset_index(drop=True)
    return final
