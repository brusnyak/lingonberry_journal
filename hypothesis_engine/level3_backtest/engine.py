"""
BOS backtest engine — returns in log-return units (matches scanner).

Edge measurement in % terms via log returns.
Spread applied as % cost (spread_price / entry_price).
All metrics comparable across assets.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from backtesting.engine.data import load_data
from hypothesis_engine.level1_conditions.conditions import CONDITIONS


# Spread in price units for entry+exit round-trip
SPREAD_COST: dict[str, float] = {
    # Forex majors
    "EURUSD": 0.00014, "GBPUSD": 0.00018, "USDJPY": 0.018, "AUDUSD": 0.00014,
    "USDCAD": 0.00016, "USDCHF": 0.00014, "NZDUSD": 0.00016,
    # Forex crosses
    "GBPJPY": 0.030, "EURJPY": 0.016, "EURGBP": 0.00012,
    "AUDJPY": 0.022, "CHFJPY": 0.030, "CADJPY": 0.022,
    "EURAUD": 0.00022, "AUDCAD": 0.00016, "AUDCHF": 0.00016,
    "AUDNZD": 0.00022, "CADCHF": 0.00016,
    "GBPAUD": 0.00030, "GBPCAD": 0.00030, "GBPCHF": 0.00022,
    "GBPNZD": 0.00036, "NZDCAD": 0.00022, "NZDCHF": 0.00022,
    "NZDJPY": 0.030,
    # Metals
    "XAUUSD": 0.50, "XAGUSD": 0.04,
    # Crypto (spread in USD price terms)
    "BTCUSDT": 1.0, "ETHUSDT": 0.30, "BNBUSDT": 0.05,
    "ADAUSDT": 0.0005, "DOGEUSDT": 0.0003, "SOLUSDT": 0.02,
    "AAVEUSDT": 0.05, "ALGOUSDT": 0.0005, "ARBUSDT": 0.005,
    "ATOMUSDT": 0.005, "AVAXUSDT": 0.01, "ENAUSDT": 0.0003,
    "1000PEPEUSDT": 0.001,
    # US indices
    "USA500IDXUSD": 0.5, "USATECHIDXUSD": 0.5, "USA30IDXUSD": 0.5,
}


def backtest_bos(
    symbol: str,
    tf: str = "5",
    horizon: int = 1,
    session: str | None = None,
    days: int = 365,
    allow_oos: bool = False,
) -> dict:
    """
    Backtest BOS with N-bar hold.
    All returns in log units (consistent with scanner).
    """
    df = load_data(symbol, tf, days=days, allow_oos=allow_oos)
    if df.empty:
        return {"error": f"Vazio: {symbol} {tf}"}

    arr = {
        "open": df["open"].to_numpy(float),
        "high": df["high"].to_numpy(float),
        "low": df["low"].to_numpy(float),
        "close": df["close"].to_numpy(float),
    }
    o, h, l, c = arr["open"], arr["high"], arr["low"], arr["close"]
    n = len(c)
    ts = pd.to_datetime(df["ts"])

    signal = CONDITIONS["bos"](**arr)

    # --- Forward log returns (matches scanner exactly) ---
    # entry at open[i+1], exit at close[i+1+h]
    if horizon + 1 >= n:
        return {"error": f"Horizonte {horizon} grande demais"}
    raw_log_ret = np.full(n, np.nan)
    raw_log_ret[:n - horizon - 1] = np.log(c[1 + horizon:] / o[1:n - horizon])

    # --- Session filter ---
    if session and session != "24h":
        from core.constants import SESSIONS
        if session not in SESSIONS:
            return {"error": f"Session desconhecida: {session}"}
        hs, he = SESSIONS[session]
        hours = ts.dt.hour.values
        session_mask = (hours >= hs) & (hours < he)
    else:
        session_mask = np.ones(n, dtype=bool)

    # --- Spread as % cost of entry ---
    spread_price = SPREAD_COST.get(symbol, 0)
    # Spread cost in log-return terms: ~spread / entry_price for small moves
    spread_cost = spread_price / o  # array, per-bar spread in log terms

    trades_list = []
    for i in range(n - horizon - 1):
        if signal[i] == 0 or not session_mask[i]:
            continue

        direction = 1 if signal[i] == 1 else -1
        raw_ret = raw_log_ret[i]  # log(close[i+1+h] / open[i+1])
        spread_i = spread_cost[i + 1] if i + 1 < len(spread_cost) else 0

        # Net return in log terms (positive = profit in direction):
        #   Long:  net = raw_ret - spread   (price rises minus cost)
        #   Short: net = -raw_ret - spread  (flip, price fall = profit, minus cost)
        if direction == 1:
            net_ret = raw_ret - spread_i
        else:
            net_ret = -raw_ret - spread_i

        trades_list.append({
            "entry_date": str(ts.iloc[i])[:19],
            "direction": "long" if direction == 1 else "short",
            "entry_price": float(o[i + 1]),
            "exit_price": float(c[i + 1 + horizon]),
            "log_return": round(float(raw_ret), 8),
            "spread_cost_pct": round(float(spread_i), 8),
            "net_return": round(float(net_ret), 8),
        })

    if len(trades_list) < 3:
        return {"error": f"Poucos trades ({len(trades_list)})"}

    trades_df = pd.DataFrame(trades_list)
    raw_vals = trades_df["log_return"].values
    net_vals = trades_df["net_return"].values

    def stats(vals):
        wr = float(np.mean(vals > 0))
        mu = float(np.mean(vals))
        sd = float(np.std(vals, ddof=1))
        t = mu / (sd / np.sqrt(len(vals))) if sd > 0 else 0
        wins = vals[vals > 0]
        losses = vals[vals <= 0]
        pf = float(np.sum(wins) / abs(np.sum(losses))) if len(losses) > 0 and np.sum(losses) != 0 else float("inf")
        avg_w = float(np.mean(wins)) if len(wins) > 0 else 0
        avg_l = float(np.mean(losses)) if len(losses) > 0 else 0
        rr = abs(avg_w / avg_l) if avg_l != 0 else 0
        return {"wr": wr, "mean": mu, "sd": sd, "t": t, "pf": pf, "rr": rr, "n": len(vals)}

    raw_stats = stats(raw_vals)
    net_stats = stats(net_vals)

    days_span = max((ts.iloc[-1] - ts.iloc[0]).days, 1)
    trades_per_day = len(trades_list) / days_span

    return {
        "symbol": symbol,
        "tf": tf,
        "horizon": horizon,
        "session": session or "24h",
        "n_trades": len(trades_list),
        "trades_per_day": round(trades_per_day, 1),
        "raw_wr": round(raw_stats["wr"] * 100, 2),
        "raw_mean": round(raw_stats["mean"], 8),
        "raw_t": round(raw_stats["t"], 2),
        "raw_pf": round(raw_stats["pf"], 2),
        "raw_rr": round(raw_stats["rr"], 2),
        "net_wr": round(net_stats["wr"] * 100, 2),
        "net_mean": round(net_stats["mean"], 8),
        "net_sd": round(net_stats["sd"], 8),
        "net_t": round(net_stats["t"], 2),
        "net_pf": round(net_stats["pf"], 2),
        "net_rr": round(net_stats["rr"], 2),
        "mean_spread_pct": round(float(np.mean(trades_df["spread_cost_pct"])), 8),
        "trades": trades_df,
    }


def run_all_assets(
    symbols: list[str] | None = None,
    tf: str = "5",
    horizon: int = 1,
    days: int = 365,
    verbose: bool = True,
) -> pd.DataFrame:
    """Run backtest on all assets. Returns summary DataFrame."""
    from backtesting.engine.data import list_pairs

    if symbols is None:
        forex = list_pairs("forex")[:21]
        crypto = list_pairs("crypto")[:15]
        indices = list_pairs("index")[:6]
        symbols = forex + crypto + indices

    rows = []
    for sym in symbols:
        if verbose:
            print(f"  {sym:<14}", end=" ", flush=True)
        result = backtest_bos(sym, tf, horizon, days=days)
        if "error" in result:
            if verbose:
                print(f"✗ ({result['error']})")
            continue

        rows.append({
            "symbol": sym,
            "n_trades": result["n_trades"],
            "trades_day": result["trades_per_day"],
            "raw_wr": result["raw_wr"],
            "raw_mean": result["raw_mean"],
            "raw_t": result["raw_t"],
            "raw_pf": result["raw_pf"],
            "net_wr": result["net_wr"],
            "net_mean": result["net_mean"],
            "net_t": result["net_t"],
            "net_pf": result["net_pf"],
            "net_rr": result["net_rr"],
            "spread_pct": result["mean_spread_pct"],
        })

        edge = "✓" if result["net_mean"] > 0 and result["net_t"] > 2 else "✗"
        if verbose:
            print(f"wr={result['net_wr']:.1f}% mean={result['net_mean']:.6f} "
                  f"pf={result['net_pf']:.2f} t={result['net_t']:.1f} {edge}")

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df = df.sort_values("net_t", ascending=False).reset_index(drop=True)
    return df
