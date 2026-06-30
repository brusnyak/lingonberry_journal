"""
Level 1 — Single-condition test harness.

For each (pair, timeframe, condition, session), measures the forward
return after a condition signal and computes bootstrap statistics.

Reuses the same methodology as Level 0: rolling windows, normal
approximation CI, sign-stability tracking.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from backtesting.engine.data import load_data

from core.constants import SESSIONS
from hypothesis_engine.level0_statistical.scanner import _compute_stats
from hypothesis_engine.level1_conditions.conditions import CONDITIONS


def scan_condition(
    symbol: str,
    tf: str,
    condition_name: str,
    days: int = 60,
    allow_oos: bool = False,
) -> dict:
    """
    Scan a single (symbol, tf, condition) combination over a fixed window.

    Returns per-session results with forward return statistics
    for both long (+1) and short (-1) signals from the condition.
    """
    if condition_name not in CONDITIONS:
        return {"error": f"Unknown condition: {condition_name}"}

    df = load_data(symbol, tf, days=days, allow_oos=allow_oos)
    if df.empty:
        return {"error": f"No data for {symbol} {tf}"}

    condition_fn = CONDITIONS[condition_name]
    n = len(df)

    arrays = {
        "open": df["open"].to_numpy(dtype=float),
        "high": df["high"].to_numpy(dtype=float),
        "low": df["low"].to_numpy(dtype=float),
        "close": df["close"].to_numpy(dtype=float),
    }

    # Compute condition signal
    signal = condition_fn(**arrays)
    if signal.sum() == 0:
        return {
            "symbol": symbol, "tf": tf,
            "condition": condition_name,
            "bars": n,
            "start": str(pd.to_datetime(df["ts"]).iloc[0])[:19],
            "end": str(pd.to_datetime(df["ts"]).iloc[-1])[:19],
            "signals": 0,
            "sessions": {},
        }

    # Precompute forward returns (entry at open[i+1] for signal at bar i)
    close = arrays["close"]
    open_p = arrays["open"]
    horizons = (1, 5, 20, 50)
    forward_rets = {}
    for h in horizons:
        if h >= n - 1:
            continue
        ret = np.full(n, np.nan)
        ret[:n - h - 1] = np.log(close[1 + h:] / open_p[1:n - h])
        forward_rets[h] = ret

    # Time of day
    ts = pd.to_datetime(df["ts"])
    hours = ts.dt.hour.values

    # Per-session stats
    results = {}
    for sname, (h_start, h_end) in SESSIONS.items():
        session_mask = (hours >= h_start) & (hours < h_end)
        n_session = int(session_mask.sum())
        if n_session < 20:
            continue

        # Split by signal direction
        long_mask = session_mask & (signal == 1)
        short_mask = session_mask & (signal == -1)

        session_results = {}
        for h in horizons:
            if h not in forward_rets:
                continue
            r = forward_rets[h]

            for sig_name, mask in [("long", long_mask), ("short", short_mask)]:
                vals = r[mask]
                vals = vals[~np.isnan(vals)]
                if len(vals) < 5:
                    continue

                stats = _compute_stats(vals)
                stats["n"] = len(vals)
                stats["horizon"] = h
                # For short signals, flip the forward return sign
                if sig_name == "short":
                    stats["mean_ret"] = -stats["mean_ret"]
                    stats["ci_low"], stats["ci_high"] = -stats["ci_high"], -stats["ci_low"]
                    stats["t_stat"] = -stats["t_stat"]
                    stats["win_rate"] = 1 - stats["win_rate"]
                    stats["profit_factor"] = 1 / stats["profit_factor"] if stats["profit_factor"] > 0 else float("inf")
                session_results[f"{sig_name}_{h}"] = stats

        if session_results:
            results[sname] = session_results

    return {
        "symbol": symbol,
        "tf": tf,
        "condition": condition_name,
        "bars": n,
        "start": str(ts.iloc[0])[:19],
        "end": str(ts.iloc[-1])[:19],
        "signals": int(signal.sum()),
        "sessions": results,
    }


def rolling_condition_scan(
    symbol: str,
    tf: str,
    condition_name: str,
    *,
    window_days: int = 30,
    step_days: int = 15,
    horizons: tuple[int, ...] = (1, 5, 20, 50),
    max_windows: int = 40,
    allow_oos: bool = True,
) -> dict:
    """
    Rolling window scan for a single condition.

    Loads all data once, slides a window, measures condition + forward
    returns per window, aggregates.
    """
    if condition_name not in CONDITIONS:
        return {"error": f"Unknown condition: {condition_name}"}

    df = load_data(symbol, tf, days=0, allow_oos=allow_oos)
    if df.empty:
        return {"error": f"No data for {symbol} {tf}"}

    condition_fn = CONDITIONS[condition_name]
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
    t_min = ts.iloc[0]
    t_max = ts.iloc[-1]
    windows = []
    w_start = t_min
    while w_start + pd.Timedelta(days=window_days) <= t_max and len(windows) < max_windows:
        w_end = w_start + pd.Timedelta(days=window_days)
        mask = (ts >= w_start) & (ts < w_end)
        if mask.sum() >= 100:
            windows.append({
                "idx": len(windows),
                "start": str(w_start)[:10],
                "end": str(w_end)[:10],
                "mask": mask.values,
            })
        w_start += pd.Timedelta(days=step_days)

    if len(windows) < 2:
        return {"error": f"Only {len(windows)} window(s) for {symbol} {tf}"}

    # Precompute forward returns (entry at open[i+1] for signal at bar i)
    open_p = arrays["open"]
    forward_rets = {}
    for h in horizons:
        if h >= n - 1:
            continue
        ret = np.full(n, np.nan)
        ret[:n - h - 1] = np.log(close[1 + h:] / open_p[1:n - h])
        forward_rets[h] = ret

    # Compute condition signal ONCE
    signal = condition_fn(**arrays)

    if signal.sum() == 0:
        return {"error": f"Condition {condition_name} produced no signals for {symbol} {tf}"}

    hours = ts.dt.hour.values

    # Per-window processing
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

                for sig_name, sig_mask in [("long", s_mask & (signal == 1)), ("short", s_mask & (signal == -1))]:
                    vals = r[sig_mask]
                    vals = vals[~np.isnan(vals)]
                    if len(vals) < 3:
                        continue

                    stats = _compute_stats(vals)
                    stats["n"] = len(vals)

                    # For short signals, flip returns
                    if sig_name == "short":
                        stats["mean_ret"] = -stats["mean_ret"]
                        stats["ci_low"], stats["ci_high"] = -stats["ci_high"], -stats["ci_low"]
                        stats["t_stat"] = -stats["t_stat"]
                        stats["win_rate"] = 1 - stats["win_rate"]
                        stats["profit_factor"] = 1 / stats["profit_factor"] if stats["profit_factor"] > 0 else float("inf")

                    all_results.append({
                        "symbol": symbol,
                        "tf": tf,
                        "condition": condition_name,
                        "signal_dir": sig_name,
                        "session": sname,
                        "horizon": h,
                        "window_idx": win["idx"],
                        "window_start": win["start"],
                        "window_end": win["end"],
                        "n": stats["n"],
                        "mean_ret": stats["mean_ret"],
                        "std_ret": stats["std_ret"],
                        "win_rate": stats["win_rate"],
                        "profit_factor": stats["profit_factor"],
                        "t_stat": stats["t_stat"],
                        "p_value_approx": stats["p_value_approx"],
                        "ci_low": stats["ci_low"],
                        "ci_high": stats["ci_high"],
                        "ci_contains_zero": stats["ci_contains_zero"],
                        "effect_size": stats["effect_size"],
                    })

    return {
        "symbol": symbol,
        "tf": tf,
        "condition": condition_name,
        "total_bars": n,
        "n_windows": len(windows),
        "total_signals": int(signal.sum()),
        "data_start": str(ts.iloc[0])[:10],
        "data_end": str(ts.iloc[-1])[:10],
        "results": all_results,
    }


def aggregate_condition_rolling(scan_result: dict) -> pd.DataFrame:
    """
    Aggregate rolling condition results into stability metrics per pocket.
    """
    if "error" in scan_result:
        return pd.DataFrame()

    df = pd.DataFrame(scan_result["results"])
    if df.empty:
        return pd.DataFrame()

    def _stability(s: pd.Series) -> float:
        pos = (s > 0).sum()
        neg = (s < 0).sum()
        return max(pos, neg) / len(s)

    agg = df.groupby(
        ["symbol", "tf", "condition", "signal_dir", "session", "horizon"],
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


def run_rolling_all(
    symbols: list[str] | None = None,
    tfs: tuple[str, ...] = ("5", "15", "60", "240"),
    conditions: list[str] | None = None,
    window_days: int = 30,
    step_days: int = 15,
    max_windows: int = 40,
    allow_oos: bool = True,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Run rolling condition scan on all symbols/TFs/conditions.
    """
    from backtesting.engine.data import list_pairs

    if symbols is None:
        symbols = list_pairs("forex")[:21]
    if conditions is None:
        conditions = list(CONDITIONS.keys())

    total = len(symbols) * len(tfs) * len(conditions)
    done = 0

    all_agg: list[pd.DataFrame] = []

    for sym in symbols:
        for tf in tfs:
            for cond in conditions:
                done += 1
                if verbose:
                    print(f"  [{done:>4}/{total}] {sym:<12} {tf:>3}m {cond:<12} ...", end=" ", flush=True)

                result = rolling_condition_scan(
                    sym, tf, cond,
                    window_days=window_days,
                    step_days=step_days,
                    horizons=(1, 5, 20, 50),
                    max_windows=max_windows,
                    allow_oos=allow_oos,
                )

                if "error" in result:
                    if verbose:
                        print(f"SKIP ({result['error']})")
                    continue

                agg = aggregate_condition_rolling(result)
                if not agg.empty:
                    all_agg.append(agg)
                if verbose:
                    print(f"{result['n_windows']} windows, {result['total_signals']} signals")

    if not all_agg:
        return pd.DataFrame()

    final = pd.concat(all_agg, ignore_index=True)
    final = final.sort_values("score", ascending=False).reset_index(drop=True)
    return final
