#!/usr/bin/env python3
"""Normalize NAS100 broker CSVs into standard parquet files."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


TF_FILES = {
    "1": "USATECHIDXUSD1.csv",
    "5": "USATECHIDXUSD5.csv",
    "15": "USATECHIDXUSD15.csv",
    "30": "USATECHIDXUSD30.csv",
    "60": "USATECHIDXUSD60.csv",
    "240": "USATECHIDXUSD240.csv",
    "1440": "USATECHIDXUSD1440.csv",
}


def normalize_file(src: Path, dst: Path) -> dict:
    df = pd.read_csv(
        src,
        sep="\t",
        header=None,
        names=["ts", "open", "high", "low", "close", "volume"],
    )
    df["ts"] = pd.to_datetime(df["ts"], utc=True, errors="coerce")
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["ts", "open", "high", "low", "close"])
    df = df.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    dst.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(dst, index=False)
    return {
        "source": str(src),
        "output": str(dst),
        "rows": len(df),
        "start": df["ts"].min(),
        "end": df["ts"].max(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize NAS100 CSV data")
    parser.add_argument("--input-dir", default="data/market_data/index/NAS100")
    parser.add_argument("--symbol", default="NAS100")
    args = parser.parse_args()

    in_dir = Path(args.input_dir)
    rows = []
    for tf, name in TF_FILES.items():
        src = in_dir / name
        if not src.exists():
            continue
        dst = in_dir / f"{args.symbol}{tf}.parquet"
        rows.append(normalize_file(src, dst))

    out = pd.DataFrame(rows)
    if out.empty:
        raise SystemExit(f"No NAS100 CSV files found under {in_dir}")
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
