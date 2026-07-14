"""Causal intraday path-context validation for crypto research.

This layer answers a narrower question than MTF trend direction: does the
recent tape look like expansion, sweep/reclaim, or compression, and does that
path class have forward directional value before setup-specific entries?
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.crypto.data import load_crypto
from backtesting.crypto.event_atlas import _atr
from backtesting.crypto.foundation_direction_report import FoundationDirectionConfig, build_foundation_states
from backtesting.crypto.mtf_cascade_direction import DEFAULT_SYMBOLS
from backtesting.crypto.structure_direction_accuracy import _walk_outcome


@dataclass(frozen=True)
class PathContextConfig:
    days: int = 360
    exchange: str = "binance"
    source: str = "merged"
    entry_tf: str = "15"
    lookback_bars: int = 32
    atr_period: int = 14
    horizons_bars: tuple[int, ...] = (24, 48, 96)
    expansion_atr: float = 1.5
    sweep_buffer_atr: float = 0.1
    compression_range_atr: float = 2.0
    close_location: float = 0.65
    sample_mode: str = "events"  # events or daily_first
    direction_mode: str = "continuation"  # continuation or fade
    attach_foundation: bool = True


def build_path_context(symbol: str, bars: pd.DataFrame, cfg: PathContextConfig | None = None) -> pd.DataFrame:
    config = cfg or PathContextConfig()
    data = bars.reset_index(drop=True).copy()
    data["ts"] = pd.to_datetime(data["ts"], utc=True)
    high = pd.to_numeric(data["high"], errors="coerce")
    low = pd.to_numeric(data["low"], errors="coerce")
    close = pd.to_numeric(data["close"], errors="coerce")
    open_ = pd.to_numeric(data["open"], errors="coerce")
    atr = _atr(data, config.atr_period)

    prior_high = high.shift(1).rolling(config.lookback_bars, min_periods=max(4, config.lookback_bars // 4)).max()
    prior_low = low.shift(1).rolling(config.lookback_bars, min_periods=max(4, config.lookback_bars // 4)).min()
    prior_close = close.shift(config.lookback_bars)
    prior_range = prior_high - prior_low
    move = close - prior_close
    candle_range = (high - low).replace(0, np.nan)
    close_pos = (close - low) / candle_range

    expansion_up = (
        (move > config.expansion_atr * atr)
        & (close_pos >= config.close_location)
        & (close > prior_high)
    )
    expansion_down = (
        (move < -config.expansion_atr * atr)
        & (close_pos <= 1.0 - config.close_location)
        & (close < prior_low)
    )
    sweep_reclaim_long = (
        (low < prior_low - config.sweep_buffer_atr * atr)
        & (close > prior_low)
        & (close > open_)
    )
    sweep_reclaim_short = (
        (high > prior_high + config.sweep_buffer_atr * atr)
        & (close < prior_high)
        & (close < open_)
    )
    compression = prior_range <= config.compression_range_atr * atr

    path = pd.Series("range_or_noise", index=data.index, dtype=object)
    direction = pd.Series("none", index=data.index, dtype=object)
    path[compression] = "compression"
    path[expansion_up] = "expansion_up"
    direction[expansion_up] = "bull"
    path[expansion_down] = "expansion_down"
    direction[expansion_down] = "bear"
    path[sweep_reclaim_long] = "sweep_reclaim_long"
    direction[sweep_reclaim_long] = "bull"
    path[sweep_reclaim_short] = "sweep_reclaim_short"
    direction[sweep_reclaim_short] = "bear"

    return pd.DataFrame({
        "symbol": symbol,
        "ts": data["ts"],
        "day": data["ts"].dt.date,
        "close": close,
        "path_context": path,
        "direction": direction,
        "prior_range_atr": prior_range / atr.replace(0, np.nan),
        "move_atr": move / atr.replace(0, np.nan),
        "close_pos": close_pos,
    })


def sample_path_calls(context: pd.DataFrame, *, sample_mode: str = "events") -> pd.DataFrame:
    if context.empty:
        return context
    data = context[context["direction"].isin(["bull", "bear"])].copy()
    if data.empty:
        return data
    if sample_mode == "events":
        event = data["path_context"].ne(data["path_context"].shift(1)) | data["direction"].ne(data["direction"].shift(1))
        return data[event].reset_index(drop=False).rename(columns={"index": "entry_i"})
    if sample_mode == "daily_first":
        first = data.groupby(["symbol", "day", "path_context", "direction"], sort=True).head(1)
        return first.reset_index(drop=False).rename(columns={"index": "entry_i"})
    raise ValueError(f"unknown sample_mode: {sample_mode}")


def score_path_calls(bars: pd.DataFrame, calls: pd.DataFrame, cfg: PathContextConfig | None = None) -> pd.DataFrame:
    config = cfg or PathContextConfig()
    if calls.empty:
        return pd.DataFrame()
    data = bars.reset_index(drop=True)
    atr = _atr(data, config.atr_period)
    rows = []
    for _, call in calls.iterrows():
        entry_i = int(call["entry_i"])
        if entry_i >= len(data) - 1:
            continue
        atr_now = float(atr.iat[entry_i]) if entry_i < len(atr) else np.nan
        if not np.isfinite(atr_now) or atr_now <= 0:
            continue
        if config.direction_mode == "continuation":
            score_direction = call["direction"]
        elif config.direction_mode == "fade":
            score_direction = "bear" if call["direction"] == "bull" else "bull"
        else:
            raise ValueError(f"unknown direction_mode: {config.direction_mode}")
        trade_direction = "long" if score_direction == "bull" else "short"
        for horizon in config.horizons_bars:
            outcome = _walk_outcome(data, entry_i, trade_direction, atr_now, atr_now, horizon)
            rows.append({
                "symbol": call["symbol"],
                "ts": call["ts"],
                "day": call["day"],
                "path_context": call["path_context"],
                "direction": call["direction"],
                "score_direction": score_direction,
                "direction_mode": config.direction_mode,
                "foundation_state": call.get("foundation_state", ""),
                "foundation_direction": call.get("foundation_direction", ""),
                "horizon_bars": horizon,
                "outcome": outcome,
            })
    return pd.DataFrame(rows)


def run_path_context_report(
    symbols: list[str] | None = None,
    *,
    cfg: PathContextConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    config = cfg or PathContextConfig()
    contexts = []
    scores = []
    for symbol in symbols or DEFAULT_SYMBOLS:
        bars = load_crypto(symbol, tf=config.entry_tf, days=config.days, exchange=config.exchange, source=config.source).reset_index(drop=True)
        if bars.empty:
            continue
        context = build_path_context(symbol, bars, config)
        calls = sample_path_calls(context, sample_mode=config.sample_mode)
        if config.attach_foundation and not calls.empty:
            foundation = build_foundation_states(
                symbol,
                FoundationDirectionConfig(
                    days=config.days,
                    exchange=config.exchange,
                    source=config.source,
                    entry_tf=config.entry_tf,
                ),
            )
            if not foundation.empty:
                calls = calls.merge(
                    foundation[["symbol", "ts", "foundation_state", "direction"]].rename(
                        columns={"direction": "foundation_direction"}
                    ),
                    on=["symbol", "ts"],
                    how="left",
                )
        score = score_path_calls(bars, calls, config)
        contexts.append(context)
        scores.append(score)
    context_df = pd.concat(contexts, ignore_index=True) if contexts else pd.DataFrame()
    score_df = pd.concat(scores, ignore_index=True) if scores else pd.DataFrame()
    return context_df, score_df, summarize_path_scores(context_df, score_df)


def summarize_path_scores(context: pd.DataFrame, scores: pd.DataFrame) -> pd.DataFrame:
    if scores.empty:
        return pd.DataFrame()
    rows = []
    group_cols = ["direction_mode", "path_context", "horizon_bars"] if "direction_mode" in scores.columns else ["path_context", "horizon_bars"]
    for key, group in scores.groupby(group_cols, sort=True):
        if len(group_cols) == 3:
            direction_mode, path, horizon = key
        else:
            direction_mode, path, horizon = "continuation", key[0], key[1]
        wins = int((group["outcome"] == "win").sum())
        losses = int((group["outcome"] == "loss").sum())
        expiries = int((group["outcome"] == "expiry").sum())
        decided = wins + losses
        path_bars = context[context["path_context"] == path] if not context.empty else pd.DataFrame()
        rows.append({
            "path_context": path,
            "direction_mode": direction_mode,
            "horizon_bars": horizon,
            "calls": int(len(group)),
            "symbols": int(group["symbol"].nunique()),
            "bar_share": float(len(path_bars) / len(context)) if len(context) else np.nan,
            "wins": wins,
            "losses": losses,
            "expiries": expiries,
            "direction_accuracy": wins / decided if decided else np.nan,
            "expiry_rate": expiries / len(group) if len(group) else np.nan,
        })
    return pd.DataFrame(rows).sort_values(["horizon_bars", "direction_accuracy"], ascending=[True, False]).reset_index(drop=True)


def summarize_path_scores_by_symbol(scores: pd.DataFrame) -> pd.DataFrame:
    if scores.empty:
        return pd.DataFrame()
    rows = []
    group_cols = ["symbol", "direction_mode", "path_context", "horizon_bars"] if "direction_mode" in scores.columns else ["symbol", "path_context", "horizon_bars"]
    for key, group in scores.groupby(group_cols, sort=True):
        if len(group_cols) == 4:
            symbol, direction_mode, path, horizon = key
        else:
            symbol, path, horizon = key
            direction_mode = "continuation"
        wins = int((group["outcome"] == "win").sum())
        losses = int((group["outcome"] == "loss").sum())
        expiries = int((group["outcome"] == "expiry").sum())
        decided = wins + losses
        rows.append({
            "symbol": symbol,
            "path_context": path,
            "direction_mode": direction_mode,
            "horizon_bars": horizon,
            "calls": int(len(group)),
            "wins": wins,
            "losses": losses,
            "expiries": expiries,
            "direction_accuracy": wins / decided if decided else np.nan,
            "expiry_rate": expiries / len(group) if len(group) else np.nan,
        })
    return pd.DataFrame(rows).sort_values(
        ["horizon_bars", "path_context", "direction_accuracy"],
        ascending=[True, True, False],
    ).reset_index(drop=True)


def summarize_path_scores_by_foundation(scores: pd.DataFrame, *, min_calls: int = 100) -> pd.DataFrame:
    if scores.empty or "foundation_state" not in scores.columns:
        return pd.DataFrame()
    data = scores[scores["foundation_state"].astype(str).ne("")].copy()
    if data.empty:
        return pd.DataFrame()
    rows = []
    for (mode, path, state, horizon), group in data.groupby(
        ["direction_mode", "path_context", "foundation_state", "horizon_bars"],
        sort=True,
    ):
        if len(group) < min_calls:
            continue
        wins = int((group["outcome"] == "win").sum())
        losses = int((group["outcome"] == "loss").sum())
        expiries = int((group["outcome"] == "expiry").sum())
        decided = wins + losses
        rows.append({
            "direction_mode": mode,
            "path_context": path,
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
        ["horizon_bars", "path_context", "direction_accuracy"],
        ascending=[True, True, False],
    ).reset_index(drop=True)


def write_path_report(summary: pd.DataFrame, by_symbol: pd.DataFrame, by_foundation: pd.DataFrame, output: Path) -> None:
    lines = [
        "# Crypto Path Context Report",
        "",
        "Purpose: validate causal expansion/sweep/compression path labels before setup logic.",
        "",
    ]
    lines.extend(_markdown_table(summary))
    lines.extend(["", "## By Foundation State", ""])
    lines.extend(_markdown_table(by_foundation))
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
    parser = argparse.ArgumentParser(description="Causal path-context report.")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--days", type=int, default=360)
    parser.add_argument("--horizons", default="24,48,96")
    parser.add_argument("--sample-mode", default="events", choices=["events", "daily_first"])
    parser.add_argument("--direction-mode", default="continuation", choices=["continuation", "fade"])
    parser.add_argument("--lookback-bars", type=int, default=32)
    parser.add_argument("--expansion-atr", type=float, default=1.5)
    parser.add_argument("--compression-range-atr", type=float, default=2.0)
    parser.add_argument("--output-dir", default="backtesting/results/crypto_path_context_report")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    horizons = tuple(int(h.strip()) for h in args.horizons.split(",") if h.strip())
    cfg = PathContextConfig(
        days=args.days,
        horizons_bars=horizons,
        sample_mode=args.sample_mode,
        lookback_bars=args.lookback_bars,
        expansion_atr=args.expansion_atr,
        compression_range_atr=args.compression_range_atr,
        direction_mode=args.direction_mode,
    )
    context, scores, summary = run_path_context_report(symbols, cfg=cfg)
    by_symbol = summarize_path_scores_by_symbol(scores)
    by_foundation = summarize_path_scores_by_foundation(scores)
    out_dir = Path(args.output_dir)
    suffix = f"{args.sample_mode}_{args.direction_mode}_lb{args.lookback_bars}_exp{args.expansion_atr:g}_{args.days}d".replace(".", "p")
    out_dir.mkdir(parents=True, exist_ok=True)
    context.to_csv(out_dir / f"{suffix}_context.csv", index=False)
    scores.to_csv(out_dir / f"{suffix}_scores.csv", index=False)
    summary.to_csv(out_dir / f"{suffix}_summary.csv", index=False)
    by_symbol.to_csv(out_dir / f"{suffix}_by_symbol.csv", index=False)
    by_foundation.to_csv(out_dir / f"{suffix}_by_foundation.csv", index=False)
    write_path_report(summary, by_symbol, by_foundation, out_dir / f"{suffix}_report.md")
    print(summary.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
