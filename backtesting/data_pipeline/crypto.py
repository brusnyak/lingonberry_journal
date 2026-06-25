"""
Crypto data downloader — Binance + Bybit futures OHLCV + funding rates.

Usage:
    python -m backtesting.data_pipeline.crypto                          # BTCUSDT + ETHUSDT, last 90 days
    python -m backtesting.data_pipeline.crypto --symbols BTCUSDT,ETHUSDT,SOLUSDT
    python -m backtesting.data_pipeline.crypto --days 365               # 1 year of 1m data
    python -m backtesting.data_pipeline.crypto --exchange binance       # binance only
    python -m backtesting.data_pipeline.crypto --tfs 1,5,15,60          # specific TFs

Output: data/market_data/crypto/{SYMBOL}{TF}.parquet
Funding rate: data/market_data/crypto/{SYMBOL}_funding.parquet
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "market_data" / "crypto"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Top pairs by volume that matter for trading
DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT"]

ALL_TFS = {
    "1": "1m",
    "5": "5m",
    "15": "15m",
    "30": "30m",
    "60": "1h",
    "240": "4h",
    "1440": "1d",
}


def _parse_symbol(symbol: str) -> str:
    """Convert BTCUSDT → BTC/USDT for ccxt."""
    s = symbol.upper().strip()
    if "/" in s:
        return s
    # BTCUSDT → BTC/USDT
    if s.endswith("USDT"):
        return s[: -4] + "/USDT"
    if s.endswith("USD"):
        return s[: -3] + "/USD"
    return s


def _get_exchange(name: str):
    """Get a ccxt exchange instance with rate limiting."""
    import ccxt

    if name == "binance":
        return ccxt.binance({"options": {"defaultType": "future"}})
    elif name == "bybit":
        return ccxt.bybit({"options": {"defaultType": "linear"}})
    else:
        raise ValueError(f"Unknown exchange: {name}")


def fetch_ohlcv_batch(
    exchange,
    symbol_ccxt: str,
    tf_ccxt: str,
    since_ms: int,
    limit: int = 1000,
    max_retries: int = 3,
) -> list:
    """Fetch one batch of OHLCV with retry."""
    for attempt in range(max_retries):
        try:
            return exchange.fetch_ohlcv(symbol_ccxt, tf_ccxt, since=since_ms, limit=limit)
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                print(f"  ⚠ Retry {attempt + 1}/{max_retries} after {wait}s: {e}")
                time.sleep(wait)
            else:
                print(f"  ✗ Failed after {max_retries} attempts: {e}")
                return []


def download_symbol(
    exchange_name: str,
    symbol: str,
    tfs: list[str],
    start_date: datetime,
    end_date: datetime,
) -> dict[str, int]:
    """
    Download OHLCV for one symbol from one exchange.

    Returns {tf: num_bars_downloaded}.
    """
    exchange = _get_exchange(exchange_name)
    symbol_ccxt = _parse_symbol(symbol)
    result = {}

    start_ms = int(start_date.timestamp() * 1000)
    end_ms = int(end_date.timestamp() * 1000)

    for tf in tfs:
        tf_ccxt = ALL_TFS.get(tf, tf)
        parquet_path = DATA_DIR / f"{symbol}{tf}.parquet"

        # Load existing data to avoid re-downloading
        existing = pd.DataFrame()
        if parquet_path.exists():
            try:
                existing = pd.read_parquet(parquet_path)
                if not existing.empty:
                    existing["ts"] = pd.to_datetime(existing["ts"], utc=True)
                    print(f"  {symbol} {tf}: loaded {len(existing)} existing bars")
            except Exception as e:
                print(f"  ⚠ Could not read existing {parquet_path.name}: {e}")

        # Determine where to start
        if not existing.empty:
            last_ts = existing["ts"].max()
            since_ms = int(last_ts.timestamp() * 1000) + 1
            if since_ms >= end_ms:
                result[tf] = 0
                continue
        else:
            since_ms = start_ms

        # Fetch in batches
        all_bars: list[list] = []
        current_since = since_ms
        batch_count = 0
        max_batches = 500  # safety limit

        print(f"  {symbol} {tf}: fetching {exchange_name}...", end="", flush=True)

        while current_since < end_ms and batch_count < max_batches:
            bars = fetch_ohlcv_batch(exchange, symbol_ccxt, tf_ccxt, since_ms=current_since)
            if not bars:
                break

            all_bars.extend(bars)
            batch_count += 1

            # Move to next batch (last timestamp + 1ms)
            last_ts = bars[-1][0]
            current_since = last_ts + 1

            if len(bars) < 10:  # end of available data
                break

            # Rate limit: be nice to the API
            if batch_count % 10 == 0:
                time.sleep(0.5)
            if batch_count % 50 == 0:
                print(f" [{batch_count * 1000} bars]", end="", flush=True)

        if not all_bars:
            if existing.empty:
                print(" no data")
            else:
                print(" up to date")
            result[tf] = 0
            continue

        print(f" {len(all_bars)} bars", flush=True)

        # Convert to DataFrame
        df = pd.DataFrame(
            all_bars, columns=["ts", "open", "high", "low", "close", "volume"]
        )
        df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
        df["open"] = df["open"].astype(float)
        df["high"] = df["high"].astype(float)
        df["low"] = df["low"].astype(float)
        df["close"] = df["close"].astype(float)
        df["volume"] = df["volume"].astype(float)

        # Merge with existing data
        if not existing.empty:
            df = pd.concat([existing, df], ignore_index=True)
            df = df.drop_duplicates(subset=["ts"], keep="last")
            df = df.sort_values("ts").reset_index(drop=True)

        # Filter to requested range
        df = df[(df["ts"] >= start_date) & (df["ts"] <= end_date)].reset_index(drop=True)

        # Save
        df.to_parquet(parquet_path, index=False)
        result[tf] = len(df)
        print(f"  ✓ {parquet_path.name}: {len(df)} bars saved")

    return result


def download_funding_rate(
    symbol: str,
    start_date: datetime,
    end_date: datetime,
) -> int:
    """
    Download funding rate history from Binance futures.

    Funding rates are typically every 8 hours (00:00, 08:00, 16:00 UTC).
    """
    import ccxt

    exchange = ccxt.binance({"options": {"defaultType": "future"}})
    symbol_ccxt = _parse_symbol(symbol)
    parquet_path = DATA_DIR / f"{symbol}_funding.parquet"

    existing = pd.DataFrame()
    if parquet_path.exists():
        try:
            existing = pd.read_parquet(parquet_path)
            existing["ts"] = pd.to_datetime(existing["ts"], utc=True)
        except Exception:
            pass

    start_ms = int(start_date.timestamp() * 1000)
    end_ms = int(end_date.timestamp() * 1000)

    if not existing.empty:
        last_ts = existing["ts"].max()
        since_ms = int(last_ts.timestamp() * 1000) + 1
        if since_ms >= end_ms:
            print(f"  {symbol} funding: already up to date")
            return 0
    else:
        since_ms = start_ms

    all_rates: list[dict] = []
    current_since = since_ms

    print(f"  {symbol} funding: fetching...", end="", flush=True)

    while current_since < end_ms:
        try:
            rates = exchange.fetch_funding_rate_history(
                symbol_ccxt, since=current_since, limit=100
            )
        except Exception as e:
            print(f"\n  ⚠ Funding rate error: {e}")
            break

        if not rates:
            break

        all_rates.extend(rates)
        last_ts = rates[-1]["timestamp"]
        current_since = last_ts + 1

        if len(rates) < 10:
            break

        time.sleep(0.3)

    if not all_rates:
        print(" no data")
        return 0

    print(f" {len(all_rates)} rates")

    df = pd.DataFrame(all_rates)
    df["ts"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df["fundingRate"] = df["fundingRate"].astype(float)
    df = df[["ts", "fundingRate"]].sort_values("ts").drop_duplicates(subset=["ts"])

    # Merge with existing
    if not existing.empty:
        df = pd.concat([existing, df], ignore_index=True)
        df = df.drop_duplicates(subset=["ts"], keep="last")
        df = df.sort_values("ts").reset_index(drop=True)

    df = df[(df["ts"] >= start_date) & (df["ts"] <= end_date)].reset_index(drop=True)
    df.to_parquet(parquet_path, index=False)
    print(f"  ✓ {parquet_path.name}: {len(df)} rates saved")
    return len(df)


def resample_to_tfs(df: pd.DataFrame, source_tf: str, target_tfs: list[str]) -> dict[str, pd.DataFrame]:
    """Resample 1m data to higher TFs."""
    result = {}
    df = df.set_index("ts").sort_index()

    tf_map = {"5": "5min", "15": "15min", "30": "30min", "60": "1h", "240": "4h", "1440": "1D"}
    needed = [tf for tf in target_tfs if tf != source_tf and tf in tf_map]

    for tf in needed:
        rule = tf_map[tf]
        resampled = df.resample(rule).agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }).dropna()
        resampled = resampled.reset_index()
        result[tf] = resampled[["ts", "open", "high", "low", "close", "volume"]]

    return result


def main():
    parser = argparse.ArgumentParser(description="Crypto data downloader")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS),
                        help="Comma-separated symbols (default: BTCUSDT,ETHUSDT)")
    parser.add_argument("--days", type=int, default=90,
                        help="Days of history (default: 90)")
    parser.add_argument("--exchange", default="both", choices=["binance", "bybit", "both"],
                        help="Exchange(s) to fetch from (default: both)")
    parser.add_argument("--tfs", default="1,5,15,60,240,1440",
                        help="Comma-separated timeframes (default: all)")
    parser.add_argument("--funding", action="store_true", default=True,
                        help="Download funding rates (default: True)")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",")]
    tfs = [s.strip() for s in args.tfs.split(",")]
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=args.days)

    exchanges = ["binance", "bybit"] if args.exchange == "both" else [args.exchange]

    print(f"Downloading {symbols} from {exchanges}")
    print(f"  Period: {start_date.date()} → {end_date.date()}")
    print(f"  TFs: {tfs}")
    print()

    for symbol in symbols:
        for exchange_name in exchanges:
            print(f"\n{'='*60}")
            print(f"{exchange_name.upper()} / {symbol}")
            print(f"{'='*60}")
            try:
                bars = download_symbol(exchange_name, symbol, tfs, start_date, end_date)
                for tf, count in bars.items():
                    if count > 0:
                        print(f"  {tf}: {count} bars")
            except Exception as e:
                print(f"  ✗ Failed: {e}")

        # Resample from 1m to other TFs if we got 1m data
        one_min_path = DATA_DIR / f"{symbol}1.parquet"
        if one_min_path.exists():
            try:
                df = pd.read_parquet(one_min_path)
                higher_tfs = [tf for tf in tfs if tf != "1"]
                resampled = resample_to_tfs(df, "1", higher_tfs)
                for tf, rdf in resampled.items():
                    out_path = DATA_DIR / f"{symbol}{tf}.parquet"

                    # Merge with existing
                    existing = pd.DataFrame()
                    if out_path.exists():
                        try:
                            existing = pd.read_parquet(out_path)
                            existing["ts"] = pd.to_datetime(existing["ts"], utc=True)
                        except Exception:
                            pass

                    if not existing.empty:
                        rdf = pd.concat([existing, rdf], ignore_index=True)
                        rdf = rdf.drop_duplicates(subset=["ts"], keep="last")
                        rdf = rdf.sort_values("ts").reset_index(drop=True)

                    rdf.to_parquet(out_path, index=False)
                    print(f"  ✓ Resampled {symbol}{tf}: {len(rdf)} bars")
            except Exception as e:
                print(f"  ⚠ Resample error: {e}")

        # Funding rate
        if args.funding:
            try:
                download_funding_rate(symbol, start_date, end_date)
            except Exception as e:
                print(f"  ⚠ Funding rate error: {e}")

    print("\nDone.")


if __name__ == "__main__":
    main()
