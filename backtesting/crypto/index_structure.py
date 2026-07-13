"""Build no-lookahead crypto structure feature cache.

Usage:
    python -m backtesting.crypto.index_structure
    python -m backtesting.crypto.index_structure --days 120 --exchange both
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from backtesting.engine.data import load_data
from backtesting.features.structure import StructureConfig, build_structure_index


DEFAULT_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "BNBUSDT",
    "HYPEUSDT", "AAVEUSDT", "WLDUSDT", "1000PEPEUSDT",
    "AVAXUSDT", "LINKUSDT", "NEARUSDT", "SUIUSDT",
]

DEFAULT_TFS = ["1", "3", "5", "15", "30", "60", "240", "1440"]


@dataclass(frozen=True)
class StructureIndexResult:
    exchange: str
    symbol: str
    tf: str
    rows: int
    start: pd.Timestamp | None
    end: pd.Timestamp | None
    path: Path
    error: str | None = None


def build_one(
    symbol: str,
    tf: str,
    exchange: str,
    *,
    days: int = 120,
    output_root: Path = Path("data/features/structure/L2_R2"),
    config: StructureConfig | None = None,
    crypto_source: str = "exchange",
) -> StructureIndexResult:
    out_path = output_root / exchange / symbol / f"{tf}.parquet"
    try:
        df = load_data(
            symbol,
            tf=tf,
            days=days,
            asset_type="crypto",
            exchange=exchange,
            crypto_source=crypto_source,
        )
        if df.empty:
            return StructureIndexResult(exchange, symbol, tf, 0, None, None, out_path, "empty_ohlcv")

        features = build_structure_index(df, config or StructureConfig(left=2, right=2))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        features.to_parquet(out_path, index=False)
        ts = pd.to_datetime(features["known_after_ts"], utc=True, errors="coerce")
        return StructureIndexResult(
            exchange=exchange,
            symbol=symbol,
            tf=tf,
            rows=len(features),
            start=ts.min(),
            end=ts.max(),
            path=out_path,
        )
    except Exception as exc:
        return StructureIndexResult(
            exchange=exchange,
            symbol=symbol,
            tf=tf,
            rows=0,
            start=None,
            end=None,
            path=out_path,
            error=f"{type(exc).__name__}: {exc}",
        )


def build_crypto_structure_cache(
    *,
    symbols: list[str],
    exchanges: list[str],
    tfs: list[str],
    days: int,
    output_root: Path = Path("data/features/structure/L2_R2"),
    config: StructureConfig | None = None,
    crypto_source: str = "exchange",
) -> pd.DataFrame:
    rows: list[dict] = []
    for exchange in exchanges:
        for symbol in symbols:
            for tf in tfs:
                result = build_one(
                    symbol,
                    tf,
                    exchange,
                    days=days,
                    output_root=output_root,
                    config=config,
                    crypto_source=crypto_source,
                )
                rows.append({
                    "exchange": result.exchange,
                    "symbol": result.symbol,
                    "tf": result.tf,
                    "rows": result.rows,
                    "start": result.start,
                    "end": result.end,
                    "path": str(result.path),
                    "error": result.error,
                })
                if result.error:
                    print(f"  {exchange}/{symbol} {tf}: ERROR {result.error}", flush=True)
                else:
                    print(f"  {exchange}/{symbol} {tf}: {result.rows} rows -> {result.path}", flush=True)
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build crypto structure feature cache.")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--exchange", default="both", choices=["binance", "bybit", "both"])
    parser.add_argument("--tfs", default=",".join(DEFAULT_TFS))
    parser.add_argument("--days", type=int, default=120)
    parser.add_argument("--left", type=int, default=2)
    parser.add_argument("--right", type=int, default=2)
    parser.add_argument("--output-root", default="data/features/structure/L2_R2")
    parser.add_argument("--summary-output", default="backtesting/results/crypto_structure_index_summary.csv")
    parser.add_argument("--source", default="exchange", choices=["exchange", "legacy", "merged"],
                         help="'exchange' caps history to exchange-scoped files (~90-120d); "
                              "'merged' pulls in deep legacy history (multi-year) too.")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    exchanges = ["binance", "bybit"] if args.exchange == "both" else [args.exchange]
    tfs = [tf.strip() for tf in args.tfs.split(",") if tf.strip()]

    print("Building crypto structure cache")
    print(f"  Symbols: {len(symbols)}")
    print(f"  Exchanges: {', '.join(exchanges)}")
    print(f"  TFs: {', '.join(tfs)}")
    print(f"  Days: {args.days}")

    summary = build_crypto_structure_cache(
        symbols=symbols,
        exchanges=exchanges,
        tfs=tfs,
        days=args.days,
        output_root=Path(args.output_root),
        config=StructureConfig(left=args.left, right=args.right),
        crypto_source=args.source,
    )

    out = Path(args.summary_output)
    out.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(out, index=False)
    print(f"Summary saved to {out}")

    errors = summary["error"].notna().sum() if not summary.empty else 0
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
