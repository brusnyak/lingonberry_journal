"""Canonical session setup harness for crypto intraday research.

Broad matrices are useful for discovery, but they are not a strategy. This
module collapses scored variants into one execution per setup signal and then
tests explicit session hypotheses.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.crypto.portfolio_validation import PortfolioRiskConfig, simulate_portfolio


DEFAULT_INPUT = Path("backtesting/results/crypto_fvg_execution_matrix_binance_15m/fvg_execution_trades.parquet")
DEFAULT_OUTPUT_DIR = Path("backtesting/results/crypto_canonical_session_harness")


@dataclass(frozen=True)
class SetupSpec:
    name: str
    filters: dict[str, str]
    entry_priority: tuple[str, ...]
    target_model: str = "fixed_2r"
    management_model: str = "be_after_half_target"


ENTRY_PRIORITY_CONFIRMED_RETEST = (
    "structure_confirmed_fvg_ce_retest",
    "structure_confirmed_fvg_edge_retest",
    "structure_confirmed_next_open",
    "fvg_ce_retest",
    "fvg_edge_retest",
    "next_open",
)

ENTRY_PRIORITY_CONFIRMED_NEXT_OPEN = (
    "structure_confirmed_next_open",
    "structure_confirmed_fvg_ce_retest",
    "structure_confirmed_fvg_edge_retest",
    "next_open",
    "fvg_ce_retest",
    "fvg_edge_retest",
)

ENTRY_PRIORITY_CE_RETEST = (
    "structure_confirmed_fvg_ce_retest",
    "fvg_ce_retest",
    "structure_confirmed_fvg_edge_retest",
    "fvg_edge_retest",
    "structure_confirmed_next_open",
    "next_open",
)

SETUPS = [
    SetupSpec(
        name="london_long_middle_local_next_open",
        filters={
            "session_utc": "london",
            "direction": "long",
            "ctx_240_regime": "bull",
            "trend_alignment": "middle_local_ema",
            "middle_ema_state": "bullish",
            "local_ema_state": "bullish",
        },
        entry_priority=ENTRY_PRIORITY_CONFIRMED_NEXT_OPEN,
    ),
    SetupSpec(
        name="london_long_middle_local_retest",
        filters={
            "session_utc": "london",
            "direction": "long",
            "ctx_240_regime": "bull",
            "trend_alignment": "middle_local_ema",
            "middle_ema_state": "bullish",
            "local_ema_state": "bullish",
        },
        entry_priority=ENTRY_PRIORITY_CONFIRMED_RETEST,
    ),
    SetupSpec(
        name="late_us_short_bearish_trend_ce",
        filters={
            "session_utc": "late_us",
            "direction": "short",
            "ctx_240_regime": "neutral",
            "trend_alignment": "global_middle_ema",
            "global_ema_state": "bearish",
            "middle_ema_state": "bearish",
            "local_ema_state": "bearish",
        },
        entry_priority=ENTRY_PRIORITY_CE_RETEST,
        management_model="hold_target_expiry",
    ),
    SetupSpec(
        name="late_us_short_bull_flush_ce",
        filters={
            "session_utc": "late_us",
            "direction": "short",
            "ctx_240_regime": "bull",
            "trend_alignment": "counter_global_or_structure",
            "global_ema_state": "bullish",
            "middle_ema_state": "bullish",
        },
        entry_priority=ENTRY_PRIORITY_CE_RETEST,
    ),
    SetupSpec(
        name="ny_long_neutral_reversal_ce",
        filters={
            "session_utc": "ny",
            "direction": "long",
            "ctx_240_regime": "neutral",
            "trend_alignment": "counter_global_or_structure",
        },
        entry_priority=ENTRY_PRIORITY_CE_RETEST,
    ),
]


def run_canonical_harness(
    trades: pd.DataFrame,
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    label: str = "run",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    accepted_rows = []
    cfg = PortfolioRiskConfig(
        risk_per_trade_pct=0.002,
        max_open_trades=6,
        max_open_per_symbol=1,
        daily_loss_limit_pct=0.005,
    )
    for spec in SETUPS:
        selected = select_setup(trades, spec)
        accepted, summary = simulate_portfolio(selected, cfg)
        rows.append(_summary_row(spec.name, selected, accepted, summary))
        if not accepted.empty:
            accepted = accepted.copy()
            accepted["setup_name"] = spec.name
            accepted_rows.append(accepted)
    summary_df = pd.DataFrame(rows).sort_values(["return_to_dd", "avg_r"], ascending=False).reset_index(drop=True)
    accepted_df = pd.concat(accepted_rows, ignore_index=True) if accepted_rows else pd.DataFrame()
    summary_df.to_csv(output_dir / f"{label}_canonical_summary.csv", index=False)
    accepted_df.to_csv(output_dir / f"{label}_canonical_trades.csv", index=False)
    write_report(summary_df, output_dir / f"{label}_canonical_report.md")
    return summary_df, accepted_df


def select_setup(trades: pd.DataFrame, spec: SetupSpec) -> pd.DataFrame:
    data = trades.copy()
    for col, val in spec.filters.items():
        if col not in data.columns:
            return data.head(0).copy()
        data = data[data[col].astype(str) == val].copy()
    data = data[
        (data["target_model"].astype(str) == spec.target_model)
        & (data["management_model"].astype(str) == spec.management_model)
    ].copy()
    if data.empty:
        return data
    rank = {name: i for i, name in enumerate(spec.entry_priority)}
    data["_entry_rank"] = data["entry_model"].map(rank).fillna(999).astype(int)
    data["_confirmed_rank"] = np.where(
        data["entry_model"].astype(str).str.startswith("structure_confirmed_")
        | ~data["confirmation_model"].astype(str).isin(["", "none", "nan"]),
        0,
        1,
    )
    signal_cols = [c for c in ["exchange", "symbol", "tf", "signal_i", "direction"] if c in data.columns]
    data = data.sort_values(["entry_ts", "_confirmed_rank", "_entry_rank", "bars_to_entry"]).reset_index(drop=True)
    if signal_cols:
        data = data.drop_duplicates(subset=signal_cols, keep="first")
    execution_cols = [c for c in ["exchange", "symbol", "entry_ts", "entry", "stop", "target", "direction", "target_model", "management_model"] if c in data.columns]
    if execution_cols:
        data = data.drop_duplicates(subset=execution_cols, keep="first")
    return data.drop(columns=["_entry_rank", "_confirmed_rank"], errors="ignore").reset_index(drop=True)


def _summary_row(name: str, selected: pd.DataFrame, accepted: pd.DataFrame, summary: dict) -> dict:
    span = _span_days(selected["entry_ts"]) if not selected.empty else 0.0
    symbols = int(selected["symbol"].nunique()) if not selected.empty else 0
    return {
        "setup_name": name,
        "candidates": int(len(selected)),
        "accepted": int(len(accepted)),
        "symbols": int(accepted["symbol"].nunique()) if not accepted.empty else 0,
        "candidate_per_symbol_day": float(len(selected) / (span * max(symbols, 1))) if span > 0 else np.nan,
        "accepted_per_symbol_day": float(len(accepted) / (span * max(symbols, 1))) if span > 0 else np.nan,
        "avg_r": float(summary.get("avg_r", 0.0)),
        "median_r": float(summary.get("median_r", 0.0)),
        "profit_factor": float(summary.get("profit_factor", 0.0)),
        "gross_return_pct": float(summary.get("gross_return_pct", 0.0)),
        "max_dd_pct": float(summary.get("max_dd_pct", 0.0)),
        "daily_max_dd_pct": float(summary.get("daily_max_dd_pct", 0.0)),
        "return_to_dd": float(summary.get("return_to_dd", 0.0)),
        "win_rate": float(summary.get("win_rate", 0.0)),
        "stop_rate": float(summary.get("stop_rate", 0.0)),
        "expiry_rate": float(summary.get("expiry_rate", 0.0)),
    }


def _span_days(ts: pd.Series) -> float:
    times = pd.to_datetime(ts, utc=True)
    if times.empty:
        return 0.0
    return max((times.max() - times.min()).total_seconds() / 86400.0, 1.0)


def write_report(summary: pd.DataFrame, output_path: Path) -> None:
    lines = [
        "# Crypto Canonical Session Harness",
        "",
        "Date: 2026-07-13.",
        "",
        "## Purpose",
        "",
        "- Collapse broad matrix variants into one selected execution per setup signal.",
        "- Compare session hypotheses by per-trade R, return/DD, stop rate, and accepted frequency.",
        "- Prevent raw/confirmed duplicates from being counted as separate trades.",
        "",
        "## Summary",
        "",
    ]
    lines.extend(_markdown_table(_format(summary)))
    lines.extend([
        "",
        "## Rule",
        "",
        "- Promote setups only after holdout/rolling validation.",
        "- Favor high return/DD and low stop rate over raw trade count.",
        "- If a setup needs duplicate variants to look good, reject it.",
    ])
    output_path.write_text("\n".join(lines) + "\n")


def _format(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if col.endswith("_pct") or col.endswith("_rate"):
            out[col] = out[col].map(lambda x: f"{float(x) * 100:.2f}%" if pd.notna(x) else "")
        elif col in {"avg_r", "median_r", "profit_factor", "return_to_dd", "candidate_per_symbol_day", "accepted_per_symbol_day"}:
            out[col] = out[col].map(lambda x: f"{float(x):+.3f}" if pd.notna(x) and np.isfinite(float(x)) else "inf")
    return out


def _markdown_table(df: pd.DataFrame) -> list[str]:
    if df.empty:
        return ["_empty_"]
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(str(row[c]) for c in cols) + " |")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Run canonical crypto session setup harness.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--label", default="run")
    args = parser.parse_args()

    path = Path(args.input)
    trades = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    summary, accepted = run_canonical_harness(trades, output_dir=Path(args.output_dir), label=args.label)
    print(summary.to_string(index=False))
    print(f"accepted_rows={len(accepted)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
