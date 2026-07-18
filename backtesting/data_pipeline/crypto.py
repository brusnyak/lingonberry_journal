"""
Crypto data downloader — Binance + Bybit futures OHLCV + funding rates.

Usage:
    python -m backtesting.data_pipeline.crypto                          # core universe, last 365 days
    python -m backtesting.data_pipeline.crypto --symbols BTCUSDT,ETHUSDT,SOLUSDT
    python -m backtesting.data_pipeline.crypto --days 365 --fresh       # replace requested window
    python -m backtesting.data_pipeline.crypto --exchange binance       # binance only
    python -m backtesting.data_pipeline.crypto --tfs 1,5,15,60          # specific TFs

Output: data/market_data/crypto/{exchange}/{SYMBOL}{TF}.parquet
Funding rate: data/market_data/crypto/{exchange}/{SYMBOL}_funding.parquet
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

# Practical 50x research universe: liquid majors first, aggressive alts second.
DEFAULT_SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "DOGEUSDT",
    "BNBUSDT",
    "HYPEUSDT",
    "AAVEUSDT",
    "WLDUSDT",
    "1000PEPEUSDT",
]

ALL_TFS = {
    "1": "1m",
    "3": "3m",
    "5": "5m",
    "15": "15m",
    "30": "30m",
    "60": "1h",
    "240": "4h",
    "1440": "1d",
}


def _parse_symbol(symbol: str) -> str:
    """Convert BTCUSDT → BTC/USDT:USDT for linear swap ccxt markets."""
    s = symbol.upper().strip()
    if "/" in s:
        return s
    # BTCUSDT → BTC/USDT:USDT
    if s.endswith("USDT"):
        return s[: -4] + "/USDT:USDT"
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
    elif name == "bingx":
        return ccxt.bingx({"options": {"defaultType": "swap"}})
    else:
        raise ValueError(f"Unknown exchange: {name}")


def _exchange_dir(exchange_name: str) -> Path:
    path = DATA_DIR / exchange_name.lower()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _timeframe_ms(tf: str) -> int:
    minutes = {
        "1": 1,
        "3": 3,
        "5": 5,
        "15": 15,
        "30": 30,
        "60": 60,
        "240": 240,
        "1440": 1440,
    }.get(tf)
    if minutes is None:
        return 60_000
    return minutes * 60_000


def _market_id(symbol: str) -> str:
    return symbol.upper().replace("/", "").replace(":USDT", "")


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
    *,
    fresh: bool = False,
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
    exchange_dir = _exchange_dir(exchange_name)

    for tf in tfs:
        tf_ccxt = ALL_TFS.get(tf, tf)
        parquet_path = exchange_dir / f"{symbol}{tf}.parquet"

        # Load existing data to avoid re-downloading
        existing = pd.DataFrame()
        if parquet_path.exists() and not fresh:
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
        expected_batches = int((end_ms - current_since) / (_timeframe_ms(tf) * 1000)) + 2
        max_batches = max(500, min(expected_batches, 2500))

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
    exchange_name: str,
    symbol: str,
    start_date: datetime,
    end_date: datetime,
    *,
    fresh: bool = False,
) -> int:
    """
    Download funding rate history from a futures exchange.

    Funding rates are typically every 8 hours (00:00, 08:00, 16:00 UTC).
    """
    exchange = _get_exchange(exchange_name)
    symbol_ccxt = _parse_symbol(symbol)
    parquet_path = _exchange_dir(exchange_name) / f"{symbol}_funding.parquet"

    existing = pd.DataFrame()
    if parquet_path.exists() and not fresh:
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

    print(f"  {symbol} funding: fetching {exchange_name}...", end="", flush=True)

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


def download_market_specs(exchange_name: str, symbols: list[str]) -> int:
    """Snapshot exchange market metadata needed for realistic order simulation."""
    exchange = _get_exchange(exchange_name)
    markets = exchange.load_markets()
    rows = []
    wanted = {_market_id(symbol) for symbol in symbols}

    for market in markets.values():
        market_id = str(market.get("id", "")).upper()
        symbol = str(market.get("symbol", "")).upper()
        if market_id not in wanted and _market_id(symbol) not in wanted:
            continue
        if not (market.get("swap") or market.get("future")):
            continue
        if market.get("linear") is False:
            continue

        limits = market.get("limits") or {}
        amount_limits = limits.get("amount") or {}
        cost_limits = limits.get("cost") or {}
        precision = market.get("precision") or {}
        info = market.get("info") or {}

        rows.append({
            "ts": pd.Timestamp.now(tz="UTC"),
            "exchange": exchange_name,
            "id": market.get("id"),
            "symbol": market.get("symbol"),
            "base": market.get("base"),
            "quote": market.get("quote"),
            "settle": market.get("settle"),
            "type": market.get("type"),
            "linear": market.get("linear"),
            "contract": market.get("contract"),
            "active": market.get("active"),
            "amount_precision": precision.get("amount"),
            "price_precision": precision.get("price"),
            "min_qty": amount_limits.get("min"),
            "max_qty": amount_limits.get("max"),
            "min_notional": cost_limits.get("min"),
            "max_notional": cost_limits.get("max"),
            "raw_info": repr(info),
        })

    if not rows:
        print(f"  ⚠ No market specs matched for {exchange_name}")
        return 0

    out = _exchange_dir(exchange_name) / "market_specs.parquet"
    df = pd.DataFrame(rows)
    existing = pd.DataFrame()
    if out.exists():
        try:
            existing = pd.read_parquet(out)
        except Exception:
            pass
    if not existing.empty:
        df = pd.concat([existing, df], ignore_index=True)
        df = df.drop_duplicates(subset=["exchange", "id", "ts"], keep="last")
    df.to_parquet(out, index=False)
    print(f"  ✓ {exchange_name}/market_specs.parquet: {len(rows)} specs snapshotted")
    return len(rows)


def resample_to_tfs(df: pd.DataFrame, source_tf: str, target_tfs: list[str]) -> dict[str, pd.DataFrame]:
    """Resample 1m data to higher TFs."""
    result = {}
    df = df.set_index("ts").sort_index()

    tf_map = {"3": "3min", "5": "5min", "15": "15min", "30": "30min", "60": "1h", "240": "4h", "1440": "1D"}
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
                        help="Comma-separated symbols (default: liquid 50x research universe)")
    parser.add_argument("--days", type=int, default=365,
                        help="Days of history (default: 365)")
    parser.add_argument("--exchange", default="both", choices=["binance", "bybit", "bingx", "both"],
                        help="Exchange(s) to fetch from (default: both = binance+bybit; bingx is separate, "
                             "not included in 'both', per the 2026-07-12 data audit's exchange-namespace rule)")
    parser.add_argument("--tfs", default="1,3,5,15,60,240,1440",
                        help="Comma-separated timeframes (default: all)")
    parser.add_argument("--funding", action=argparse.BooleanOptionalAction, default=True,
                        help="Download funding rates (default: true)")
    parser.add_argument("--specs", action=argparse.BooleanOptionalAction, default=True,
                        help="Snapshot exchange instrument specs (default: true)")
    parser.add_argument("--fresh", action="store_true",
                        help="Ignore existing OHLCV/funding files and replace the requested date window")
    parser.add_argument("--resample-from-1m", action=argparse.BooleanOptionalAction, default=True,
                        help="When 1m is requested, download only 1m and derive higher TFs locally (default: true)")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",")]
    tfs = [s.strip() for s in args.tfs.split(",")]
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=args.days)

    exchanges = ["binance", "bybit"] if args.exchange == "both" else [args.exchange]
    download_tfs = ["1"] if args.resample_from_1m and "1" in tfs else tfs

    print(f"Downloading {symbols} from {exchanges}")
    print(f"  Period: {start_date.date()} → {end_date.date()}")
    print(f"  TFs: {tfs}")
    if download_tfs != tfs:
        print(f"  Download TFs: {download_tfs}; resampling the rest from 1m")
    if args.fresh:
        print("  Fresh mode: replacing requested OHLCV/funding windows")
    print()

    for symbol in symbols:
        for exchange_name in exchanges:
            print(f"\n{'='*60}")
            print(f"{exchange_name.upper()} / {symbol}")
            print(f"{'='*60}")
            try:
                bars = download_symbol(exchange_name, symbol, download_tfs, start_date, end_date, fresh=args.fresh)
                for tf, count in bars.items():
                    if count > 0:
                        print(f"  {tf}: {count} bars")
            except Exception as e:
                print(f"  ✗ Failed: {e}")

            # Resample from this exchange's 1m data if we got 1m data.
            one_min_path = _exchange_dir(exchange_name) / f"{symbol}1.parquet"
            if one_min_path.exists():
                try:
                    df = pd.read_parquet(one_min_path)
                    df["ts"] = pd.to_datetime(df["ts"], utc=True)
                    df = df[(df["ts"] >= start_date) & (df["ts"] <= end_date)].reset_index(drop=True)
                    higher_tfs = [tf for tf in tfs if tf != "1"]
                    resampled = resample_to_tfs(df, "1", higher_tfs)
                    for tf, rdf in resampled.items():
                        out_path = _exchange_dir(exchange_name) / f"{symbol}{tf}.parquet"

                        existing = pd.DataFrame()
                        if out_path.exists() and not args.fresh:
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
                        print(f"  ✓ Resampled {exchange_name}/{symbol}{tf}: {len(rdf)} bars")
                except Exception as e:
                    print(f"  ⚠ Resample error: {e}")

            # Funding rate
            if args.funding:
                try:
                    download_funding_rate(exchange_name, symbol, start_date, end_date, fresh=args.fresh)
                except Exception as e:
                    print(f"  ⚠ Funding rate error: {e}")

    if args.specs:
        for exchange_name in exchanges:
            try:
                download_market_specs(exchange_name, symbols)
            except Exception as e:
                print(f"  ⚠ Market specs error for {exchange_name}: {e}")

    print("\nDone.")


if __name__ == "__main__":
    main()
