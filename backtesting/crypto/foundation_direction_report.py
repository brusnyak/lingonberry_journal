"""Causal MTF direction-state validation for crypto foundation research.

This is not a strategy. It scores the foundation states that a setup would
consume: confirmed trend, pullback in trend, local trend while HTF is neutral,
HTF/local disagreement, and unresolved/range.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.crypto.data import load_crypto
from backtesting.crypto.event_atlas import _atr
from backtesting.crypto.mtf_cascade_direction import (
    DEFAULT_SYMBOLS,
    asof_direction,
    ema_only_direction,
    structure_ema_direction,
    structure_trend_bias_direction,
)
from backtesting.crypto.structure_direction_accuracy import _walk_outcome


@dataclass(frozen=True)
class FoundationDirectionConfig:
    days: int = 360
    exchange: str = "binance"
    source: str = "merged"
    global_tf: str = "240"
    local_tf: str = "30"
    entry_tf: str = "15"
    horizons_bars: tuple[int, ...] = (24, 48, 96)
    atr_period: int = 14
    sample_mode: str = "daily_first"  # daily_first or transitions
    context_mode: str = "strict"  # strict or global_bias


def build_foundation_states(symbol: str, cfg: FoundationDirectionConfig | None = None) -> pd.DataFrame:
    config = cfg or FoundationDirectionConfig()
    bars = {
        "global": load_crypto(symbol, tf=config.global_tf, days=config.days, exchange=config.exchange, source=config.source).reset_index(drop=True),
        "local": load_crypto(symbol, tf=config.local_tf, days=config.days, exchange=config.exchange, source=config.source).reset_index(drop=True),
        "entry": load_crypto(symbol, tf=config.entry_tf, days=config.days, exchange=config.exchange, source=config.source).reset_index(drop=True),
    }
    if any(df.empty for df in bars.values()):
        return pd.DataFrame()
    return classify_foundation_states(symbol, bars["global"], bars["local"], bars["entry"], config)


def classify_foundation_states(
    symbol: str,
    global_bars: pd.DataFrame,
    local_bars: pd.DataFrame,
    entry_bars: pd.DataFrame,
    cfg: FoundationDirectionConfig | None = None,
) -> pd.DataFrame:
    config = cfg or FoundationDirectionConfig()
    global_builder = structure_trend_bias_direction if config.context_mode == "global_bias" else structure_ema_direction
    if config.context_mode not in {"strict", "global_bias"}:
        raise ValueError(f"unknown context_mode: {config.context_mode}")

    dir_global = global_builder(global_bars)
    dir_local = structure_ema_direction(local_bars)
    dir_entry = ema_only_direction(entry_bars)

    out = pd.DataFrame({
        "symbol": symbol,
        "ts": pd.to_datetime(entry_bars["ts"], utc=True),
        "close": pd.to_numeric(entry_bars["close"], errors="coerce"),
    })
    out["global_direction"] = asof_direction(out["ts"], dir_global)
    out["local_direction"] = asof_direction(out["ts"], dir_local)
    out["entry_direction"] = asof_direction(out["ts"], dir_entry)
    state, direction = classify_state_arrays(
        out["global_direction"].to_numpy(),
        out["local_direction"].to_numpy(),
        out["entry_direction"].to_numpy(),
    )
    out["foundation_state"] = state
    out["direction"] = direction
    out["day"] = out["ts"].dt.date
    return out


def classify_state_arrays(global_dir: np.ndarray, local_dir: np.ndarray, entry_dir: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    n = len(entry_dir)
    state = np.full(n, "range_or_unresolved", dtype=object)
    direction = np.full(n, "none", dtype=object)

    active_global = np.isin(global_dir, ["bull", "bear"])
    active_local = np.isin(local_dir, ["bull", "bear"])
    active_entry = np.isin(entry_dir, ["bull", "bear"])

    confirmed = active_global & (global_dir == local_dir) & (local_dir == entry_dir)
    state[confirmed] = "confirmed_trend"
    direction[confirmed] = global_dir[confirmed]

    pullback = active_global & (global_dir == local_dir) & ~confirmed
    state[pullback] = "pullback_in_trend"
    direction[pullback] = global_dir[pullback]

    local_only = ~active_global & active_local & active_entry & (local_dir == entry_dir)
    state[local_only] = "local_trend_htf_neutral"
    direction[local_only] = local_dir[local_only]

    disagree = active_global & active_local & (global_dir != local_dir)
    state[disagree] = "htf_local_disagree"
    direction[disagree] = "none"

    return state, direction


def sample_foundation_calls(states: pd.DataFrame, *, sample_mode: str = "daily_first") -> pd.DataFrame:
    if states.empty:
        return states
    data = states[states["direction"].isin(["bull", "bear"])].copy()
    if data.empty:
        return data
    if sample_mode == "transitions":
        changed = data["foundation_state"].ne(data["foundation_state"].shift(1)) | data["direction"].ne(data["direction"].shift(1))
        return data[changed].reset_index(drop=False).rename(columns={"index": "entry_i"})
    if sample_mode == "daily_first":
        first = data.groupby(["symbol", "day", "foundation_state", "direction"], sort=True).head(1)
        return first.reset_index(drop=False).rename(columns={"index": "entry_i"})
    raise ValueError(f"unknown sample_mode: {sample_mode}")


def score_foundation_calls(
    entry_bars: pd.DataFrame,
    calls: pd.DataFrame,
    cfg: FoundationDirectionConfig | None = None,
) -> pd.DataFrame:
    config = cfg or FoundationDirectionConfig()
    if calls.empty:
        return pd.DataFrame()
    bars = entry_bars.reset_index(drop=True)
    atr = _atr(bars, config.atr_period)
    rows = []
    for _, call in calls.iterrows():
        entry_i = int(call["entry_i"])
        if entry_i >= len(bars) - 1:
            continue
        atr_now = float(atr.iat[entry_i]) if entry_i < len(atr) else np.nan
        if not np.isfinite(atr_now) or atr_now <= 0:
            continue
        trade_direction = "long" if call["direction"] == "bull" else "short"
        for horizon in config.horizons_bars:
            outcome = _walk_outcome(
                bars,
                entry_i=entry_i,
                direction=trade_direction,
                stop_dist=atr_now,
                target_dist=atr_now,
                horizon=horizon,
            )
            rows.append({
                "symbol": call["symbol"],
                "ts": call["ts"],
                "day": call["day"],
                "foundation_state": call["foundation_state"],
                "direction": call["direction"],
                "horizon_bars": horizon,
                "outcome": outcome,
            })
    return pd.DataFrame(rows)


def run_foundation_direction_report(
    symbols: list[str] | None = None,
    *,
    cfg: FoundationDirectionConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    config = cfg or FoundationDirectionConfig()
    all_states = []
    all_scores = []
    for symbol in symbols or DEFAULT_SYMBOLS:
        entry_bars = load_crypto(symbol, tf=config.entry_tf, days=config.days, exchange=config.exchange, source=config.source).reset_index(drop=True)
        if entry_bars.empty:
            continue
        states = build_foundation_states(symbol, config)
        calls = sample_foundation_calls(states, sample_mode=config.sample_mode)
        scores = score_foundation_calls(entry_bars, calls, config)
        all_states.append(states)
        all_scores.append(scores)
    states_df = pd.concat(all_states, ignore_index=True) if all_states else pd.DataFrame()
    scores_df = pd.concat(all_scores, ignore_index=True) if all_scores else pd.DataFrame()
    return states_df, scores_df, summarize_foundation_scores(states_df, scores_df)


def summarize_foundation_scores(states: pd.DataFrame, scores: pd.DataFrame) -> pd.DataFrame:
    if scores.empty:
        return pd.DataFrame()
    rows = []
    for (state, horizon), group in scores.groupby(["foundation_state", "horizon_bars"], sort=True):
        wins = int((group["outcome"] == "win").sum())
        losses = int((group["outcome"] == "loss").sum())
        expiries = int((group["outcome"] == "expiry").sum())
        decided = wins + losses
        state_bars = states[states["foundation_state"] == state] if not states.empty else pd.DataFrame()
        rows.append({
            "foundation_state": state,
            "horizon_bars": horizon,
            "calls": int(len(group)),
            "symbols": int(group["symbol"].nunique()),
            "bar_share": float(len(state_bars) / len(states)) if len(states) else np.nan,
            "wins": wins,
            "losses": losses,
            "expiries": expiries,
            "direction_accuracy": wins / decided if decided else np.nan,
            "expiry_rate": expiries / len(group) if len(group) else np.nan,
        })
    return pd.DataFrame(rows).sort_values(["horizon_bars", "direction_accuracy"], ascending=[True, False]).reset_index(drop=True)


def summarize_foundation_scores_by_symbol(scores: pd.DataFrame) -> pd.DataFrame:
    if scores.empty:
        return pd.DataFrame()
    rows = []
    for (symbol, state, horizon), group in scores.groupby(["symbol", "foundation_state", "horizon_bars"], sort=True):
        wins = int((group["outcome"] == "win").sum())
        losses = int((group["outcome"] == "loss").sum())
        expiries = int((group["outcome"] == "expiry").sum())
        decided = wins + losses
        rows.append({
            "symbol": symbol,
            "foundation_state": state,
            "horizon_bars": horizon,
            "calls": int(len(group)),
            "wins": wins,
            "losses": losses,
            "expiries": expiries,
            "direction_accuracy": wins / decided if decided else np.nan,
            "expiry_rate": expiries / len(group) if len(group) else np.nan,
        })
    return pd.DataFrame(rows).sort_values(
        ["horizon_bars", "foundation_state", "direction_accuracy"],
        ascending=[True, True, False],
    ).reset_index(drop=True)


def write_foundation_report(summary: pd.DataFrame, by_symbol: pd.DataFrame, output: Path) -> None:
    lines = [
        "# Crypto Foundation Direction Report",
        "",
        "Purpose: validate causal MTF direction states before setup logic.",
        "",
    ]
    lines.extend(_markdown_table(summary))
    lines.extend(["", "## By Symbol", ""])
    lines.extend(_markdown_table(by_symbol))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n")


def _markdown_table(df: pd.DataFrame) -> list[str]:
    if df.empty:
        return ["_empty_"]
    show = df.copy()
    for col in show.select_dtypes(include=["float"]).columns:
        show[col] = show[col].map(lambda x: "" if pd.isna(x) else f"{x:.4f}")
    cols = list(show.columns)
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in show.iterrows():
        lines.append("| " + " | ".join(str(row[c]) for c in cols) + " |")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Causal foundation direction-state report.")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--days", type=int, default=360)
    parser.add_argument("--horizons", default="24,48,96")
    parser.add_argument("--sample-mode", default="daily_first", choices=["daily_first", "transitions"])
    parser.add_argument("--context-mode", default="strict", choices=["strict", "global_bias"])
    parser.add_argument("--output-dir", default="backtesting/results/crypto_foundation_direction_report")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    horizons = tuple(int(h.strip()) for h in args.horizons.split(",") if h.strip())
    cfg = FoundationDirectionConfig(
        days=args.days,
        horizons_bars=horizons,
        sample_mode=args.sample_mode,
        context_mode=args.context_mode,
    )
    states, scores, summary = run_foundation_direction_report(symbols, cfg=cfg)
    by_symbol = summarize_foundation_scores_by_symbol(scores)
    out_dir = Path(args.output_dir)
    suffix = f"{args.sample_mode}_{args.context_mode}_{args.days}d"
    out_dir.mkdir(parents=True, exist_ok=True)
    states.to_csv(out_dir / f"{suffix}_states.csv", index=False)
    scores.to_csv(out_dir / f"{suffix}_scores.csv", index=False)
    summary.to_csv(out_dir / f"{suffix}_summary.csv", index=False)
    by_symbol.to_csv(out_dir / f"{suffix}_by_symbol.csv", index=False)
    write_foundation_report(summary, by_symbol, out_dir / f"{suffix}_report.md")
    print(summary.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
