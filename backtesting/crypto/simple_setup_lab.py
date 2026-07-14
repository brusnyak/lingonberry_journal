"""Narrow crypto setup lab.

Purpose: test one simple setup at a time against the existing structure/EMA
direction context, with explicit cost-per-R diagnostics. This is deliberately
smaller than the old canonical/session harnesses: no broad matrix, no duplicate
variants, no promotion logic.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.crypto.data import load_crypto
from backtesting.crypto.mtf_cascade_direction import (
    DEFAULT_SYMBOLS,
    asof_direction,
    structural_stop_target,
    structure_ema_direction,
    vec_ema_state,
    walk_structural_outcome,
)
from backtesting.features.structure import StructureConfig, build_structure_index


@dataclass(frozen=True)
class SimpleSetupConfig:
    days: int = 400
    exchange: str = "binance"
    source: str = "merged"
    global_tf: str = "240"
    local_tf: str = "30"
    entry_tf: str = "15"
    min_rr: float = 1.5
    horizon_bars: int = 96
    min_stop_pct: float = 0.1
    base_round_trip_pct: float = 0.0006
    stress_round_trip_pct: float = 0.0020


def run_simple_setup_lab(
    symbols: list[str] | None = None,
    *,
    config: SimpleSetupConfig | None = None,
    setup: str = "pullback_reclaim",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    cfg = config or SimpleSetupConfig()
    rows: list[dict] = []
    for symbol in symbols or DEFAULT_SYMBOLS:
        rows.extend(evaluate_symbol(symbol, cfg, setup=setup).to_dict("records"))
    trades = pd.DataFrame(rows)
    return trades, summarize_trades(trades)


def evaluate_symbol(symbol: str, cfg: SimpleSetupConfig, *, setup: str) -> pd.DataFrame:
    bars = {
        "global": load_crypto(symbol, tf=cfg.global_tf, days=cfg.days, exchange=cfg.exchange, source=cfg.source).reset_index(drop=True),
        "local": load_crypto(symbol, tf=cfg.local_tf, days=cfg.days, exchange=cfg.exchange, source=cfg.source).reset_index(drop=True),
        "entry": load_crypto(symbol, tf=cfg.entry_tf, days=cfg.days, exchange=cfg.exchange, source=cfg.source).reset_index(drop=True),
    }
    if any(df.empty for df in bars.values()):
        return pd.DataFrame()

    entry_bars = bars["entry"]
    combo = direction_context(bars["global"], bars["local"], entry_bars)
    structure = build_structure_index(entry_bars, StructureConfig(left=2, right=2))
    signal_mask = setup_signal(entry_bars, combo, setup)
    signal_idx = np.where(signal_mask)[0]

    rows = []
    for i in signal_idx:
        if i >= len(entry_bars) - 1:
            continue
        direction = "long" if combo[i] == "bull" else "short"
        entry = float(entry_bars["close"].iat[i])
        sl, tp = structural_stop_target(structure.iloc[i], direction, entry, cfg.min_rr)
        if not np.isfinite(sl):
            continue
        risk = abs(entry - sl)
        if risk <= 0:
            continue
        stop_pct = risk / entry * 100.0
        if stop_pct < cfg.min_stop_pct:
            continue
        outcome = walk_structural_outcome(
            entry_bars,
            i,
            direction,
            sl,
            tp,
            horizon=cfg.horizon_bars,
            track_excursion=True,
        )
        if outcome is None:
            continue
        base_cost_r = cfg.base_round_trip_pct * entry / risk
        stress_cost_r = cfg.stress_round_trip_pct * entry / risk
        gross_r = float(outcome["r_multiple"])
        rows.append(
            {
                "symbol": symbol,
                "setup": setup,
                "entry_ts": pd.to_datetime(entry_bars["ts"].iat[i], utc=True),
                "direction": direction,
                "session_utc": session_bucket(pd.to_datetime(entry_bars["ts"].iat[i], utc=True)),
                "entry": entry,
                "sl": sl,
                "tp": tp,
                "stop_pct": stop_pct,
                "target_pct": abs(tp - entry) / entry * 100.0,
                "planned_rr": abs(tp - entry) / risk,
                "gross_r": gross_r,
                "base_cost_r": base_cost_r,
                "stress_cost_r": stress_cost_r,
                "base_net_r": gross_r - base_cost_r,
                "stress_net_r": gross_r - stress_cost_r,
                "mfe_r": float(outcome.get("mfe_r", np.nan)),
                "mae_r": float(outcome.get("mae_r", np.nan)),
                "exit_kind": exit_kind(gross_r),
            }
        )
    return pd.DataFrame(rows)


def direction_context(global_bars: pd.DataFrame, local_bars: pd.DataFrame, entry_bars: pd.DataFrame) -> np.ndarray:
    dir_global = structure_ema_direction(global_bars)
    dir_local = structure_ema_direction(local_bars)
    entry_state = vec_ema_state(entry_bars).map({"bullish": "bull", "bearish": "bear"}).fillna("neutral").to_numpy()
    g = asof_direction(entry_bars["ts"], dir_global)
    l = asof_direction(entry_bars["ts"], dir_local)
    return np.where((g == l) & (l == entry_state) & (g != "neutral"), g, "neutral")


def setup_signal(entry_bars: pd.DataFrame, combo: np.ndarray, setup: str) -> np.ndarray:
    if setup not in {"pullback_reclaim", "context_change"}:
        raise ValueError(f"unknown setup: {setup}")
    combo_s = pd.Series(combo)
    active = combo_s.isin(["bull", "bear"])
    if setup == "context_change":
        return (combo_s.ne(combo_s.shift(1)) & active).to_numpy()

    close = pd.to_numeric(entry_bars["close"], errors="coerce")
    low = pd.to_numeric(entry_bars["low"], errors="coerce")
    high = pd.to_numeric(entry_bars["high"], errors="coerce")
    ema21 = close.ewm(span=21, adjust=False).mean()
    recently_touched_from_above = low.rolling(6, min_periods=1).min().shift(1) <= ema21.shift(1)
    recently_touched_from_below = high.rolling(6, min_periods=1).max().shift(1) >= ema21.shift(1)
    prior_bull_context = (combo_s.shift(1) == "bull").astype(float).rolling(6, min_periods=1).min() == 1.0
    prior_bear_context = (combo_s.shift(1) == "bear").astype(float).rolling(6, min_periods=1).min() == 1.0
    bull_reclaim = (combo_s == "bull") & prior_bull_context & recently_touched_from_above & (close > ema21)
    bear_reclaim = (combo_s == "bear") & prior_bear_context & recently_touched_from_below & (close < ema21)
    return (bull_reclaim | bear_reclaim).to_numpy()


def summarize_trades(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    rows = []
    for (setup, symbol), group in trades.groupby(["setup", "symbol"], sort=True):
        rows.append(summary_row(group, setup=setup, symbol=symbol))
    rows.append(summary_row(trades, setup="ALL", symbol="ALL"))
    return pd.DataFrame(rows)


def summary_row(group: pd.DataFrame, *, setup: str, symbol: str) -> dict:
    base = group["base_net_r"].to_numpy(dtype=float)
    stress = group["stress_net_r"].to_numpy(dtype=float)
    gross = group["gross_r"].to_numpy(dtype=float)
    return {
        "setup": setup,
        "symbol": symbol,
        "trades": len(group),
        "win_rate": float((base > 0).mean()) if len(group) else np.nan,
        "gross_avg_r": float(np.mean(gross)) if len(group) else np.nan,
        "base_avg_r": float(np.mean(base)) if len(group) else np.nan,
        "base_pf": profit_factor(base),
        "stress_avg_r": float(np.mean(stress)) if len(group) else np.nan,
        "stress_pf": profit_factor(stress),
        "median_stop_pct": float(group["stop_pct"].median()),
        "median_planned_rr": float(group["planned_rr"].median()),
        "median_base_cost_r": float(group["base_cost_r"].median()),
        "median_stress_cost_r": float(group["stress_cost_r"].median()),
        "target_rate": float((group["exit_kind"] == "target").mean()),
        "stop_rate": float((group["exit_kind"] == "stop").mean()),
        "expiry_rate": float((group["exit_kind"] == "expiry").mean()),
        "median_mfe_r": float(group["mfe_r"].median()),
        "median_mae_r": float(group["mae_r"].median()),
    }


def profit_factor(r: np.ndarray) -> float:
    gains = r[r > 0].sum()
    losses = -r[r <= 0].sum()
    if losses > 0:
        return float(gains / losses)
    return float("inf") if gains > 0 else np.nan


def exit_kind(gross_r: float) -> str:
    if gross_r > 0:
        return "target"
    if gross_r < 0:
        return "stop"
    return "expiry"


def session_bucket(ts: pd.Timestamp) -> str:
    hour = int(ts.hour)
    if 0 <= hour < 7:
        return "asia"
    if 7 <= hour < 12:
        return "london"
    if 12 <= hour < 17:
        return "ny"
    return "late_us"


def write_report(summary: pd.DataFrame, trades: pd.DataFrame, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Simple Crypto Setup Lab",
        "",
        "Scope: one setup family at a time, existing 240m/30m structure+EMA direction context, 15m entry, structural SL/TP, explicit cost-per-R.",
        "",
        "## Summary",
        "",
        dataframe_to_markdown(summary) if not summary.empty else "No trades.",
        "",
        "## Session Split",
        "",
    ]
    if not trades.empty:
        session = trades.groupby(["setup", "session_utc"]).agg(
            trades=("base_net_r", "size"),
            base_avg_r=("base_net_r", "mean"),
            base_pf=("base_net_r", profit_factor),
            median_stop_pct=("stop_pct", "median"),
        ).reset_index()
        lines.append(dataframe_to_markdown(session))
    else:
        lines.append("No trades.")
    lines.extend(
        [
            "",
            "## Read",
            "",
            "- Base cost uses 6bps round-trip, roughly taker entry plus maker target exit.",
            "- Stress cost uses 20bps round-trip. If a setup dies there, it has weak execution margin.",
            "- This lab is not a promotion tool. It exists to falsify simple setup ideas before they reach the engine.",
        ]
    )
    output.write_text("\n".join(lines) + "\n")


def dataframe_to_markdown(df: pd.DataFrame) -> str:
    if df.empty:
        return "No rows."
    formatted = df.copy()
    for col in formatted.columns:
        if pd.api.types.is_float_dtype(formatted[col]):
            formatted[col] = formatted[col].map(lambda v: "" if pd.isna(v) else f"{v:.3f}")
    headers = [str(c) for c in formatted.columns]
    rows = [[str(v) for v in row] for row in formatted.to_numpy()]
    widths = [len(h) for h in headers]
    for row in rows:
        widths = [max(w, len(cell)) for w, cell in zip(widths, row)]
    header_line = "| " + " | ".join(h.ljust(w) for h, w in zip(headers, widths)) + " |"
    sep_line = "| " + " | ".join("-" * w for w in widths) + " |"
    body = ["| " + " | ".join(cell.ljust(w) for cell, w in zip(row, widths)) + " |" for row in rows]
    return "\n".join([header_line, sep_line, *body])


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a narrow crypto setup lab.")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--setup", default="pullback_reclaim", choices=["pullback_reclaim", "context_change"])
    parser.add_argument("--days", type=int, default=400)
    parser.add_argument("--output-dir", default="backtesting/results/crypto_simple_setup_lab")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    cfg = SimpleSetupConfig(days=args.days)
    trades, summary = run_simple_setup_lab(symbols, config=cfg, setup=args.setup)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    trades.to_csv(out_dir / f"{args.setup}_trades.csv", index=False)
    summary.to_csv(out_dir / f"{args.setup}_summary.csv", index=False)
    write_report(summary, trades, out_dir / f"{args.setup}_report.md")
    print(summary.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
