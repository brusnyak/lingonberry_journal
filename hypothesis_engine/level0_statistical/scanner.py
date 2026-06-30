"""
Statistical pocket scanner.

Loads OHLCV, computes forward returns per bar, groups by session+direction,
computes bootstrap confidence intervals. No trading logic, no lookahead.

Usage:
    from hypothesis_engine.level0_statistical.scanner import scan_pocket
    result = scan_pocket("EURUSD", "60", days=60)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from backtesting.engine.data import load_data


# Session definitions (UTC)
SESSIONS = {
    "asia":      (0, 7),
    "london":    (7, 16),
    "ny":        (12, 21),
    "london_ny": (12, 16),   # overlap
    "24h":       (0, 24),
}


def scan_pocket(
    symbol: str,
    tf: str,
    days: int = 60,
    horizons: tuple[int, ...] = (1, 5, 20, 50),
    allow_oos: bool = False,
) -> dict:
    """
    Scan a single (symbol, timeframe) pocket.

    Returns a dict of {session_name: {horizon: stats}}.
    """
    df = load_data(symbol, tf, days=days, allow_oos=allow_oos)
    if df.empty:
        return {"error": f"No data for {symbol} {tf}"}

    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    close = df["close"].to_numpy(dtype=float)
    ts = pd.to_datetime(df["ts"]).values
    n = len(close)
    if n < 50:
        return {"error": f"Too few bars ({n}) for {symbol} {tf}"}

    # Per-bar forward returns (log returns)
    returns = {}
    for h in horizons:
        if h >= n:
            continue
        ret = np.full(n, np.nan)
        ret[:n-h] = np.log(close[h:] / close[:n-h])
        returns[h] = ret

    # Direction: bar direction (bullish if close > open)
    open_p = df["open"].to_numpy(dtype=float)
    bar_bull = close > open_p

    # Hour of day
    hours = pd.Series(pd.to_datetime(ts)).dt.hour.values

    results = {}
    for session_name, (h_start, h_end) in SESSIONS.items():
        session_mask = (hours >= h_start) & (hours < h_end)
        n_session = int(session_mask.sum())
        if n_session < 20:
            continue

        # Split by bar direction
        bull_mask = session_mask & bar_bull
        bear_mask = session_mask & ~bar_bull

        session_results = {}
        for h in horizons:
            if h not in returns:
                continue
            r = returns[h]

            for dir_name, mask in [("bull", bull_mask), ("bear", bear_mask)]:
                vals = r[mask]
                vals = vals[~np.isnan(vals)]
                if len(vals) < 15:
                    continue

                stats = _compute_stats(vals)
                stats["n"] = len(vals)
                stats["horizon"] = h
                session_results[f"{dir_name}_{h}"] = stats

        if session_results:
            results[session_name] = session_results

    return {
        "symbol": symbol,
        "tf": tf,
        "bars": n,
        "start": str(pd.Timestamp(ts[0]))[:19],
        "end": str(pd.Timestamp(ts[-1]))[:19],
        "sessions": results,
    }


def _compute_stats(vals: np.ndarray, ci_method: str = "normal") -> dict:
    """
    Basic stats on a return series with CI.

    ci_method:
      "normal" — normal approximation (fast, valid for n>30)
      "bootstrap" — 1k vectorized bootstrap (slower but robust)
    """
    n = len(vals)
    mean_ret = float(np.mean(vals))
    std_ret = float(np.std(vals, ddof=1))
    se = std_ret / np.sqrt(n) if n > 0 else 0.0

    # CI
    if ci_method == "bootstrap":
        rng = np.random.default_rng(42)
        boot_idx = rng.integers(0, n, size=(1000, n))
        boot_means = np.mean(vals[boot_idx], axis=1)
        ci_low = float(np.percentile(boot_means, 2.5))
        ci_high = float(np.percentile(boot_means, 97.5))
    else:
        # Normal approximation: mean ± 1.96 * SE
        ci_low = mean_ret - 1.96 * se
        ci_high = mean_ret + 1.96 * se

    # T-test
    t_stat = mean_ret / se if se > 0 else 0.0

    # Effect size
    effect_size = mean_ret / std_ret if std_ret > 0 else 0.0

    # Win rate
    win_rate = float(np.mean(vals > 0))

    # Average win/loss
    wins = vals[vals > 0]
    losses = vals[vals <= 0]
    avg_win = float(np.mean(wins)) if len(wins) > 0 else 0.0
    avg_loss = float(np.mean(losses)) if len(losses) > 0 else 0.0
    pf = float(np.sum(wins) / abs(np.sum(losses))) if len(losses) > 0 and np.sum(losses) < 0 else float("inf")

    return {
        "mean_ret": round(mean_ret, 6),
        "std_ret": round(std_ret, 6),
        "win_rate": round(win_rate, 4),
        "avg_win": round(avg_win, 6),
        "avg_loss": round(avg_loss, 6),
        "profit_factor": round(pf, 3) if pf != float("inf") else float("inf"),
        "t_stat": round(t_stat, 3),
        "p_value_approx": round(_p_value_approx(t_stat, n), 4),
        "ci_low": round(ci_low, 6),
        "ci_high": round(ci_high, 6),
        "ci_contains_zero": ci_low < 0 < ci_high,
        "effect_size": round(effect_size, 4),
    }


def _p_value_approx(t_stat: float, df: int) -> float:
    """Approximate two-tailed p-value from t-distribution (normal approx for df>30)."""
    from scipy.stats import t as t_dist
    try:
        return float(2 * t_dist.sf(abs(t_stat), df=df))
    except ImportError:
        # Normal approximation
        from scipy.stats import norm as norm_dist
        try:
            return float(2 * norm_dist.sf(abs(t_stat)))
        except ImportError:
            return -1.0


def scan_all_pairs(
    symbols: list[str] | None = None,
    tfs: tuple[str, ...] = ("5", "15", "60", "240"),
    days: int = 60,
    allow_oos: bool = False,
) -> list[dict]:
    """Scan multiple pairs and return a list of results."""
    from backtesting.engine.data import list_pairs

    if symbols is None:
        symbols = list_pairs("forex")[:21]  # forex only

    results = []
    for sym in symbols:
        for tf in tfs:
            r = scan_pocket(sym, tf, days=days, allow_oos=allow_oos)
            results.append(r)
    return results


# ── Rolling window validation ────────────────────────────────────────

def rolling_window_scan(
    symbol: str,
    tf: str,
    *,
    window_days: int = 30,
    step_days: int = 15,
    horizons: tuple[int, ...] = (1, 5, 20, 50),
    max_windows: int = 40,
    allow_oos: bool = True,
) -> dict:
    """
    Scan a symbol/TF across multiple sliding time windows.

    Loads ALL available data, slides a (window_days)-day window with
    (step_days)-day stride, computes per-pocket stats in each window.
    Returns a dict with:
      - metadata: symbol, tf, data range, n_windows
      - results: flat list of per-window per-pocket stats

    Use aggregate_rolling() to compute stability metrics across windows.
    """
    df = load_data(symbol, tf, days=0, allow_oos=allow_oos)
    if df.empty:
        return {"error": f"No data for {symbol} {tf}"}

    close = df["close"].to_numpy(dtype=float)
    open_p = df["open"].to_numpy(dtype=float)
    ts = pd.to_datetime(df["ts"])
    hours = ts.dt.hour.values
    total_bars = len(close)

    if total_bars < 200:
        return {"error": f"Too few bars ({total_bars}) for {symbol} {tf}"}

    # Build windows
    t_min = ts.iloc[0]
    t_max = ts.iloc[-1]
    windows = []
    w_start = t_min
    while w_start + pd.Timedelta(days=window_days) <= t_max and len(windows) < max_windows:
        w_end = w_start + pd.Timedelta(days=window_days)
        mask = (ts >= w_start) & (ts < w_end)
        if mask.sum() >= 50:
            windows.append({
                "idx": len(windows),
                "start": str(w_start)[:10],
                "end": str(w_end)[:10],
                "mask": mask.values,
            })
        w_start += pd.Timedelta(days=step_days)

    if len(windows) < 2:
        return {"error": f"Only {len(windows)} window(s) for {symbol} {tf} (data spans {(t_max - t_min).days}d)"}

    # Precompute forward returns for the full series
    forward_rets = {}
    for h in horizons:
        if h >= total_bars:
            continue
        ret = np.full(total_bars, np.nan)
        ret[:total_bars - h] = np.log(close[h:] / close[:total_bars - h])
        forward_rets[h] = ret

    bar_bull = close > open_p

    # Per-window processing
    all_results: list[dict] = []
    for win in windows:
        m = win["mask"]
        for sname, (h_start, h_end) in SESSIONS.items():
            s_mask = m & (hours >= h_start) & (hours < h_end)
            n_session = int(s_mask.sum())
            if n_session < 15:
                continue

            for h in horizons:
                if h not in forward_rets:
                    continue
                r = forward_rets[h]

                for dname, dmask in [("bull", s_mask & bar_bull), ("bear", s_mask & ~bar_bull)]:
                    vals = r[dmask]
                    vals = vals[~np.isnan(vals)]
                    if len(vals) < 10:
                        continue

                    stats = _compute_stats(vals)
                    stats["n"] = len(vals)  # _compute_stats doesn't include n
                    all_results.append({
                        "symbol": symbol,
                        "tf": tf,
                        "session": sname,
                        "direction": dname,
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
        "total_bars": total_bars,
        "n_windows": len(windows),
        "data_start": str(ts.iloc[0])[:10],
        "data_end": str(ts.iloc[-1])[:10],
        "results": all_results,
    }


def aggregate_rolling(scan_result: dict) -> pd.DataFrame:
    """
    Take a rolling_window_scan result and compute stability metrics
    per pocket across all windows.

    Returns a DataFrame with columns:
      symbol, tf, session, direction, horizon,
      n_windows, n_significant, n_positive, n_negative,
      stability (fraction of windows with majority sign),
      mean_mean_ret, avg_t_stat, avg_pf, avg_wr
    """
    if "error" in scan_result:
        return pd.DataFrame()

    df = pd.DataFrame(scan_result["results"])
    if df.empty:
        return pd.DataFrame()

    def _stability(s: pd.Series) -> float:
        """Fraction of values with the majority sign."""
        pos = (s > 0).sum()
        neg = (s < 0).sum()
        return max(pos, neg) / len(s)

    agg = df.groupby(
        ["symbol", "tf", "session", "direction", "horizon"],
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

    # Sign: +1 if mean_mean_ret > 0, else -1
    agg["sign"] = agg["mean_mean_ret"].apply(lambda x: 1 if x > 0 else -1)

    # Consistency: all windows have same sign
    agg["consistent"] = agg["stability"] >= 1.0

    # Score: significance fraction × |avg_t_stat|
    agg["score"] = (
        (agg["n_significant"] / agg["n_windows"])
        * agg["avg_t_stat"].abs()
    )

    agg = agg.sort_values("score", ascending=False).reset_index(drop=True)
    return agg


def run_rolling_all(
    symbols: list[str] | None = None,
    tfs: tuple[str, ...] = ("5", "15", "60", "240"),
    window_days: int = 30,
    step_days: int = 15,
    max_windows: int = 40,
    allow_oos: bool = True,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Run rolling_window_scan on all symbols/TFs, aggregate, return a
    single DataFrame of stability metrics.
    """
    from backtesting.engine.data import list_pairs

    if symbols is None:
        symbols = list_pairs("forex")[:21]

    all_agg: list[pd.DataFrame] = []
    total = len(symbols) * len(tfs)
    done = 0

    for sym in symbols:
        for tf in tfs:
            done += 1
            if verbose:
                print(f"  [{done:>3}/{total}] {sym:<12} {tf:>3}m ...", end=" ", flush=True)

            result = rolling_window_scan(
                sym, tf,
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

            agg = aggregate_rolling(result)
            if not agg.empty:
                all_agg.append(agg)
            if verbose:
                print(f"{result['n_windows']} windows")

    if not all_agg:
        return pd.DataFrame()

    final = pd.concat(all_agg, ignore_index=True)
    final = final.sort_values("score", ascending=False).reset_index(drop=True)
    return final
