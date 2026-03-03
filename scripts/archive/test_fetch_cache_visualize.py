#!/usr/bin/env python3
"""
End-to-end data pipeline check:
1) Fetch OHLCV data (cTrader first for forex)
2) Verify cache miss/hit behavior
3) Save raw candles to CSV
4) Render candlestick chart PNG
"""
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from infra.market_data import load_ohlcv_with_cache


def _plot_candles(df: pd.DataFrame, out_path: Path, symbol: str, timeframe: str) -> None:
    fig, ax = plt.subplots(figsize=(14, 7))
    frame = df.copy().sort_values("ts")
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True, errors="coerce")
    frame = frame.dropna(subset=["ts"])

    if len(frame) < 2:
        candle_width = 0.001
    else:
        seconds = frame["ts"].diff().dropna().dt.total_seconds().median()
        candle_width = max((float(seconds) * 0.7) / 86400.0, 0.0001)

    for _, row in frame.iterrows():
        t = row["ts"]
        o = float(row["open"])
        h = float(row["high"])
        l = float(row["low"])
        c = float(row["close"])
        color = "#16a34a" if c >= o else "#dc2626"
        ax.plot([t, t], [l, h], color=color, linewidth=0.8)
        body_low = min(o, c)
        body_h = max(abs(c - o), 1e-9)
        ax.add_patch(
            Rectangle(
                (mdates.date2num(t) - candle_width / 2.0, body_low),
                candle_width,
                body_h,
                facecolor=color,
                edgecolor=color,
                linewidth=0.6,
            )
        )

    ax.set_title(f"{symbol} {timeframe} Candles")
    ax.set_xlabel("Time (UTC)")
    ax.set_ylabel("Price")
    ax.grid(alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    plt.xticks(rotation=20)
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()


def main() -> int:
    symbol = os.getenv("TEST_SYMBOL", "EURUSD")
    asset_type = os.getenv("TEST_ASSET_TYPE", "forex")
    timeframe = os.getenv("TEST_TIMEFRAME", "M5")
    lookback_days = int(os.getenv("TEST_LOOKBACK_DAYS", "2"))
    ttl_seconds = int(os.getenv("TEST_CACHE_TTL", "86400"))

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=lookback_days)

    print(f"Fetching {symbol} {timeframe} ({asset_type}) from {start.isoformat()} to {end.isoformat()}")

    t0 = time.time()
    df1 = load_ohlcv_with_cache(
        symbol=symbol,
        asset_type=asset_type,
        timeframe=timeframe,
        start=start,
        end=end,
        ttl_seconds=ttl_seconds,
    )
    t1 = time.time()

    if df1.empty:
        print("❌ No market data fetched. Check cTrader SDK/network/credentials or fallback providers.")
        return 1

    t2 = time.time()
    df2 = load_ohlcv_with_cache(
        symbol=symbol,
        asset_type=asset_type,
        timeframe=timeframe,
        start=start,
        end=end,
        ttl_seconds=ttl_seconds,
    )
    t3 = time.time()

    cache_speedup = (t1 - t0) > (t3 - t2)
    same_rows = len(df1) == len(df2)

    out_dir = Path("data/market_data")
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    csv_path = out_dir / f"{symbol}_{timeframe}_raw_{ts}.csv"
    png_path = Path("data/reports") / f"{symbol}_{timeframe}_candles_{ts}.png"

    df1 = df1.sort_values("ts").reset_index(drop=True)
    df1.to_csv(csv_path, index=False)
    _plot_candles(df1, png_path, symbol=symbol, timeframe=timeframe)

    print(f"✅ Rows fetched: {len(df1)}")
    print(f"✅ Raw CSV: {csv_path}")
    print(f"✅ Candlestick chart: {png_path}")
    print(f"Cache check: first={t1 - t0:.3f}s second={t3 - t2:.3f}s same_rows={same_rows} faster_on_second={cache_speedup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
