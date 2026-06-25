#!/usr/bin/env python3
"""
Analyze Daily Open (DO) behavior with focus on Friday/Monday.

Outputs:
- Console summary (global + per-symbol)
- CSV report for all weekdays and Friday/Monday slices

Usage:
  python backend/scripts/analyze_daily_open_patterns.py
  python backend/scripts/analyze_daily_open_patterns.py --asset forex --hours 1 3 6
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


WEEKDAY_NAMES = {
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: "Friday",
    5: "Saturday",
    6: "Sunday",
}


@dataclass
class DayRecord:
    symbol: str
    asset: str
    date: pd.Timestamp
    weekday: int
    do_price: float
    close_h1: float | None
    close_h3: float | None
    close_h6: float | None
    ret_h1: float | None
    ret_h3: float | None
    ret_h6: float | None
    max_up_3h: float | None
    max_down_3h: float | None
    continuation_1h_to_3h: int | None


def _load_df(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    if "datetime" in df.columns:
        df["datetime"] = pd.to_datetime(df["datetime"], utc=False)
        df = df.set_index("datetime")
    elif not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index, utc=False)
    df = df.sort_index()
    need = ["open", "high", "low", "close"]
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise ValueError(f"{path.name}: missing columns {missing}")
    return df


def _safe_ret(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or a == 0:
        return None
    return (b - a) / a


def _pick_close(group: pd.DataFrame, n_minutes: int) -> float | None:
    if group.empty:
        return None
    # First bar is minute 0 from daily open anchor.
    if len(group) <= n_minutes:
        return None
    return float(group["close"].iloc[n_minutes])


def _sign(x: float | None, eps: float = 1e-7) -> int:
    if x is None or np.isnan(x):
        return 0
    if x > eps:
        return 1
    if x < -eps:
        return -1
    return 0


def _extract_symbol(path: Path) -> str:
    # e.g. EURUSD1.parquet -> EURUSD
    stem = path.stem
    while stem and stem[-1].isdigit():
        stem = stem[:-1]
    return stem


def iter_files(root: Path, assets: Iterable[str], timeframe: str) -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = []
    for asset in assets:
        base = root / asset
        if not base.exists():
            continue
        out.extend((asset, p) for p in sorted(base.glob(f"*{timeframe}.parquet")))
    return out


def analyze_file(asset: str, path: Path, hours: list[int]) -> list[DayRecord]:
    df = _load_df(path)
    symbol = _extract_symbol(path)
    if df.empty:
        return []

    day_key = df.index.floor("D")
    records: list[DayRecord] = []

    for day, g in df.groupby(day_key):
        g = g.sort_index()
        if g.empty:
            continue

        do_price = float(g["open"].iloc[0])
        h_closes: dict[int, float | None] = {}
        for h in hours:
            h_closes[h] = _pick_close(g, h * 60)

        first_3h = g.iloc[: 3 * 60 + 1] if len(g) > 0 else g
        max_up_3h = None
        max_down_3h = None
        if not first_3h.empty and do_price != 0:
            max_up_3h = float((first_3h["high"].max() - do_price) / do_price)
            max_down_3h = float((first_3h["low"].min() - do_price) / do_price)

        ret_h1 = _safe_ret(do_price, h_closes.get(1))
        ret_h3 = _safe_ret(do_price, h_closes.get(3))
        ret_h6 = _safe_ret(do_price, h_closes.get(6))

        continuation = None
        s1 = _sign(ret_h1)
        s3 = _sign(ret_h3)
        if s1 != 0 and s3 != 0:
            continuation = int(s1 == s3)

        records.append(
            DayRecord(
                symbol=symbol,
                asset=asset,
                date=pd.Timestamp(day),
                weekday=int(pd.Timestamp(day).dayofweek),
                do_price=do_price,
                close_h1=h_closes.get(1),
                close_h3=h_closes.get(3),
                close_h6=h_closes.get(6),
                ret_h1=ret_h1,
                ret_h3=ret_h3,
                ret_h6=ret_h6,
                max_up_3h=max_up_3h,
                max_down_3h=max_down_3h,
                continuation_1h_to_3h=continuation,
            )
        )

    return records


def summarize(df: pd.DataFrame, name: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    grp = df.groupby(["weekday"]).agg(
        days=("date", "count"),
        up_h1=("ret_h1", lambda s: float((s > 0).mean())),
        up_h3=("ret_h3", lambda s: float((s > 0).mean())),
        up_h6=("ret_h6", lambda s: float((s > 0).mean())),
        abs_ret_h1=("ret_h1", lambda s: float(s.abs().mean())),
        abs_ret_h3=("ret_h3", lambda s: float(s.abs().mean())),
        abs_ret_h6=("ret_h6", lambda s: float(s.abs().mean())),
        mean_ret_h1=("ret_h1", "mean"),
        mean_ret_h3=("ret_h3", "mean"),
        mean_ret_h6=("ret_h6", "mean"),
        max_up_3h=("max_up_3h", "mean"),
        max_down_3h=("max_down_3h", "mean"),
        continuation_1h_to_3h=("continuation_1h_to_3h", "mean"),
    )

    grp = grp.reset_index()
    grp["weekday_name"] = grp["weekday"].map(WEEKDAY_NAMES)
    grp.insert(0, "scope", name)
    return grp


def apply_quality_filters(df: pd.DataFrame, max_abs_ret: float = 0.2) -> pd.DataFrame:
    """Drop obvious bad ticks/days that can poison weekday aggregates."""
    if df.empty:
        return df

    out = df.copy()
    out = out[out["do_price"] > 0]

    # Keep days where all observed horizon returns stay inside a broad, realistic band.
    for col in ["ret_h1", "ret_h3", "ret_h6"]:
        mask = out[col].isna() | (out[col].abs() <= max_abs_ret)
        out = out[mask]

    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Friday/Monday DO behavior")
    parser.add_argument("--data-root", default="data/parquet", help="Parquet root")
    parser.add_argument(
        "--asset",
        action="append",
        dest="assets",
        default=None,
        help="Asset folder (forex/crypto/metals/indeces). Repeatable.",
    )
    parser.add_argument("--timeframe", default="1", help="Timeframe suffix, default 1")
    parser.add_argument(
        "--hours",
        nargs="+",
        type=int,
        default=[1, 3, 6],
        help="Horizons in hours from DO",
    )
    parser.add_argument(
        "--out",
        default="data/daily_open_friday_monday_report.csv",
        help="Output CSV path",
    )
    args = parser.parse_args()

    assets = args.assets or ["forex", "crypto", "metals", "indeces"]
    root = Path(args.data_root)
    files = iter_files(root, assets, args.timeframe)
    if not files:
        raise SystemExit("No parquet files found for requested scope")

    all_records: list[DayRecord] = []
    for asset, path in files:
        try:
            all_records.extend(analyze_file(asset, path, args.hours))
        except Exception as exc:
            print(f"[WARN] Skipped {path}: {exc}")

    if not all_records:
        raise SystemExit("No day records produced")

    df = pd.DataFrame([r.__dict__ for r in all_records])
    df["weekday_name"] = df["weekday"].map(WEEKDAY_NAMES)

    raw_count = len(df)
    df = apply_quality_filters(df, max_abs_ret=0.2)

    global_summary = summarize(df, "all_symbols")
    fm_summary = summarize(df[df["weekday"].isin([0, 4])], "friday_monday_only")

    per_symbol = (
        df[df["weekday"].isin([0, 4])]
        .groupby(["symbol", "weekday", "weekday_name"], as_index=False)
        .agg(
            days=("date", "count"),
            up_h3=("ret_h3", lambda s: float((s > 0).mean())),
            abs_ret_h3=("ret_h3", lambda s: float(s.abs().mean())),
            mean_ret_h3=("ret_h3", "mean"),
            continuation_1h_to_3h=("continuation_1h_to_3h", "mean"),
        )
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    merged = pd.concat([global_summary, fm_summary], ignore_index=True)
    merged.to_csv(out, index=False)

    per_symbol_out = out.with_name(out.stem + "_per_symbol.csv")
    per_symbol.to_csv(per_symbol_out, index=False)

    print("\n=== Daily Open Friday/Monday Analysis ===")
    print(f"Records: {len(df):,} day-samples from {df['symbol'].nunique()} symbols")
    print(f"Filtered outliers: {raw_count - len(df):,} days removed")
    print(f"Output: {out}")
    print(f"Per-symbol: {per_symbol_out}")

    print("\n--- Friday vs Monday (aggregate) ---")
    show = fm_summary[[
        "weekday_name",
        "days",
        "up_h1",
        "up_h3",
        "up_h6",
        "abs_ret_h1",
        "abs_ret_h3",
        "abs_ret_h6",
        "continuation_1h_to_3h",
    ]].sort_values("weekday_name")
    with pd.option_context("display.max_columns", None, "display.width", 160):
        print(show.to_string(index=False))

    print("\n--- Biggest Friday/Monday asymmetry by symbol (|Monday up_h3 - Friday up_h3|) ---")
    pivot = per_symbol.pivot_table(index="symbol", columns="weekday_name", values="up_h3")
    if {"Monday", "Friday"}.issubset(set(pivot.columns)):
        pivot = pivot.dropna(subset=["Monday", "Friday"]).copy()
        pivot["delta_up_h3"] = (pivot["Monday"] - pivot["Friday"]).abs()
        top = pivot.sort_values("delta_up_h3", ascending=False).head(12)
        print(top.to_string())
    else:
        print("Insufficient Monday/Friday overlap in per-symbol data")


if __name__ == "__main__":
    main()
