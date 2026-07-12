"""Rerunnable data freshness and source audit for research work.

Usage:
    python -m backtesting.data_audit
    python -m backtesting.data_audit --max-stale-days 7 --fail-on-stale
    python -m backtesting.data_audit --format csv --output backtesting/results/data_audit.csv
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd


STANDARD_TFS = ("1440", "240", "60", "30", "15", "5", "3", "1")


@dataclass(frozen=True)
class AuditTarget:
    category: str
    asset_type: str
    source: str
    path: Path


def parse_symbol_tf(path: Path) -> tuple[str, str | None]:
    """Parse {SYMBOL}{TF}.parquet without stripping digits from symbols."""
    stem = path.stem
    for tf in STANDARD_TFS:
        if stem.endswith(tf):
            return stem[: -len(tf)], tf
    return stem, None


def _read_parquet_timestamp_summary(path: Path, preferred_cols: Iterable[str]) -> dict:
    """Return row count and timestamp range using the first available ts column."""
    try:
        columns = pd.read_parquet(path).columns
    except Exception as exc:
        return {"rows": 0, "start": pd.NaT, "end": pd.NaT, "error": f"read_columns:{type(exc).__name__}"}

    ts_col = next((c for c in preferred_cols if c in columns), None)
    if ts_col is None:
        return {"rows": 0, "start": pd.NaT, "end": pd.NaT, "error": "missing_timestamp_column"}

    try:
        df = pd.read_parquet(path, columns=[ts_col])
    except Exception as exc:
        return {"rows": 0, "start": pd.NaT, "end": pd.NaT, "error": f"read_ts:{type(exc).__name__}"}

    ts = pd.to_datetime(df[ts_col], utc=True, errors="coerce")
    return {
        "rows": int(len(df)),
        "start": ts.min(),
        "end": ts.max(),
        "error": None,
    }


def iter_audit_targets(data_root: Path = Path("data")) -> Iterable[AuditTarget]:
    market = data_root / "market_data"

    for exchange in ("binance", "bybit"):
        path = market / "crypto" / exchange
        if path.exists():
            yield AuditTarget("ohlcv", "crypto", exchange, path)
            yield AuditTarget("funding", "crypto", exchange, path)
            yield AuditTarget("market_specs", "crypto", exchange, path)

    legacy = market / "crypto" / "legacy"
    if legacy.exists():
        yield AuditTarget("ohlcv", "crypto", "legacy", legacy)
        yield AuditTarget("funding", "crypto", "legacy", legacy)

    for asset_type, rel in (
        ("forex", "forex/parquet"),
        ("commodity", "commodity/parquet"),
        ("index", "index/parquet"),
    ):
        path = market / rel
        if path.exists():
            yield AuditTarget("ohlcv", asset_type, "primary", path)

    structure = data_root / "features" / "structure" / "L2_R2"
    if structure.exists():
        yield AuditTarget("structure", "crypto", "L2_R2", structure)


def audit_target(target: AuditTarget, as_of: pd.Timestamp) -> list[dict]:
    rows: list[dict] = []

    if target.category == "ohlcv":
        files = [
            p for p in sorted(target.path.glob("*.parquet"))
            if not p.name.endswith("_funding.parquet") and p.name != "market_specs.parquet"
        ]
        for path in files:
            symbol, tf = parse_symbol_tf(path)
            summary = _read_parquet_timestamp_summary(path, ("ts", "time", "timestamp", "datetime"))
            rows.append(_row(target, path, symbol, tf, summary, as_of))
        return rows

    if target.category == "funding":
        for path in sorted(target.path.glob("*_funding.parquet")):
            symbol = path.stem.replace("_funding", "")
            summary = _read_parquet_timestamp_summary(path, ("ts", "time", "timestamp", "datetime"))
            rows.append(_row(target, path, symbol, None, summary, as_of))
        return rows

    if target.category == "market_specs":
        path = target.path / "market_specs.parquet"
        if path.exists():
            summary = _read_parquet_timestamp_summary(path, ("ts", "time", "timestamp", "datetime"))
            rows.append(_row(target, path, "ALL", None, summary, as_of))
        return rows

    if target.category == "structure":
        for path in sorted(target.path.glob("*/*/*.parquet")):
            parts = path.parts
            source = parts[-3]
            symbol = parts[-2]
            tf = path.stem
            structure_target = AuditTarget(target.category, target.asset_type, source, target.path)
            summary = _read_parquet_timestamp_summary(path, ("known_after_ts", "ts"))
            rows.append(_row(structure_target, path, symbol, tf, summary, as_of))
        return rows

    return rows


def _row(
    target: AuditTarget,
    path: Path,
    symbol: str,
    tf: str | None,
    summary: dict,
    as_of: pd.Timestamp,
) -> dict:
    end = summary["end"]
    stale_days = None
    if pd.notna(end):
        stale_days = round((as_of - end).total_seconds() / 86400, 3)

    return {
        "category": target.category,
        "asset_type": target.asset_type,
        "source": target.source,
        "symbol": symbol,
        "tf": tf,
        "rows": summary["rows"],
        "start": summary["start"],
        "end": end,
        "stale_days": stale_days,
        "path": str(path),
        "error": summary["error"],
    }


def audit_all(data_root: Path = Path("data"), as_of: datetime | pd.Timestamp | None = None) -> pd.DataFrame:
    as_of_ts = pd.Timestamp(as_of or datetime.now(timezone.utc))
    if as_of_ts.tzinfo is None:
        as_of_ts = as_of_ts.tz_localize("UTC")
    rows: list[dict] = []
    for target in iter_audit_targets(data_root):
        rows.extend(audit_target(target, as_of_ts))
    if not rows:
        return pd.DataFrame(columns=[
            "category", "asset_type", "source", "symbol", "tf", "rows",
            "start", "end", "stale_days", "path", "error",
        ])
    return pd.DataFrame(rows).sort_values(
        ["category", "asset_type", "source", "symbol", "tf"],
        na_position="last",
    ).reset_index(drop=True)


def summarize(df: pd.DataFrame, max_stale_days: float) -> pd.DataFrame:
    if df.empty:
        return df
    grouped = df.groupby(["category", "asset_type", "source"], dropna=False)
    return grouped.agg(
        files=("path", "count"),
        symbols=("symbol", "nunique"),
        rows=("rows", "sum"),
        oldest_start=("start", "min"),
        newest_end=("end", "max"),
        median_stale_days=("stale_days", "median"),
        max_stale_days=("stale_days", "max"),
        stale_files=("stale_days", lambda s: int((s > max_stale_days).sum())),
        error_files=("error", lambda s: int(s.notna().sum())),
    ).reset_index()


def _print_text(df: pd.DataFrame, max_stale_days: float) -> None:
    summary = summarize(df, max_stale_days)
    if summary.empty:
        print("No data files found.")
        return
    print("\nDATA AUDIT SUMMARY")
    print(summary.to_string(index=False))

    stale = df[df["stale_days"].fillna(0) > max_stale_days]
    if not stale.empty:
        print(f"\nSTALE FILES > {max_stale_days:g} days (top 40)")
        cols = ["category", "asset_type", "source", "symbol", "tf", "rows", "end", "stale_days"]
        print(stale.sort_values("stale_days", ascending=False)[cols].head(40).to_string(index=False))

    errors = df[df["error"].notna()]
    if not errors.empty:
        print("\nERROR FILES")
        print(errors[["category", "asset_type", "source", "symbol", "tf", "error", "path"]].to_string(index=False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit research data freshness and source coverage.")
    parser.add_argument("--data-root", default="data", help="Data root directory.")
    parser.add_argument("--as-of", default=None, help="Audit timestamp, e.g. 2026-07-12T00:00:00Z.")
    parser.add_argument("--max-stale-days", type=float, default=7.0)
    parser.add_argument("--format", choices=("text", "csv"), default="text")
    parser.add_argument("--output", default=None, help="Optional CSV output path.")
    parser.add_argument("--fail-on-stale", action="store_true", help="Exit 1 when any file is stale.")
    parser.add_argument("--fail-on-error", action="store_true", help="Exit 1 when any file cannot be audited.")
    args = parser.parse_args(argv)

    as_of = pd.Timestamp(args.as_of) if args.as_of else None
    df = audit_all(Path(args.data_root), as_of=as_of)

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out, index=False)

    if args.format == "csv":
        print(df.to_csv(index=False), end="")
    else:
        _print_text(df, args.max_stale_days)

    has_stale = bool((df["stale_days"].fillna(0) > args.max_stale_days).any()) if not df.empty else False
    has_errors = bool(df["error"].notna().any()) if not df.empty else False
    if (args.fail_on_stale and has_stale) or (args.fail_on_error and has_errors):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
