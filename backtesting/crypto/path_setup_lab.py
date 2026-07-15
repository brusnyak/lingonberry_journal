"""Simple setup lab for causal path-context setups.

Current setup:
  expansion_exhaustion_fade

This converts the path-context research into actual trades with structural
stops, fixed-R targets, costs, rolling windows, and portfolio throttling.
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
from backtesting.crypto.mtf_cascade_direction import DEFAULT_SYMBOLS, walk_structural_outcome
from backtesting.crypto.path_context_report import PathContextConfig, build_path_context, sample_path_calls
from backtesting.crypto.simple_setup_lab import (
    asof_structure_row,
    profit_factor,
    rolling_window_summary,
    run_portfolio_validation,
    session_bucket,
    summarize_trades,
    summarize_windows,
)
from backtesting.features.structure import StructureConfig, build_structure_index


@dataclass(frozen=True)
class PathSetupConfig:
    days: int = 360
    exchange: str = "binance"
    source: str = "merged"
    entry_tf: str = "15"
    setup: str = "expansion_exhaustion_fade"
    min_rr: float = 1.5
    horizon_bars: int = 96
    min_stop_pct: float = 0.1
    max_stop_pct: float | None = None
    base_round_trip_pct: float = 0.0006
    stress_round_trip_pct: float = 0.0020
    max_stress_cost_r: float | None = None
    sessions: tuple[str, ...] | None = None
    lookback_bars: int = 32
    expansion_atr: float = 1.5
    include_sweep_reclaim_long: bool = False
    stop_model: str = "path_extreme"
    stop_buffer_atr: float = 0.1
    confirm_bars: int = 0
    require_reversal_close: bool = False
    run_label: str = ""


def run_path_setup_lab(
    symbols: list[str] | None = None,
    *,
    config: PathSetupConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    cfg = config or PathSetupConfig()
    rows = []
    for symbol in symbols or DEFAULT_SYMBOLS:
        rows.extend(evaluate_symbol(symbol, cfg).to_dict("records"))
    trades = pd.DataFrame(rows)
    trades = apply_filters(trades, cfg)
    return trades, summarize_trades(trades)


def evaluate_symbol(symbol: str, cfg: PathSetupConfig) -> pd.DataFrame:
    bars = load_crypto(symbol, tf=cfg.entry_tf, days=cfg.days, exchange=cfg.exchange, source=cfg.source).reset_index(drop=True)
    if bars.empty:
        return pd.DataFrame()
    path_cfg = PathContextConfig(
        days=cfg.days,
        exchange=cfg.exchange,
        source=cfg.source,
        entry_tf=cfg.entry_tf,
        lookback_bars=cfg.lookback_bars,
        expansion_atr=cfg.expansion_atr,
        direction_mode="fade",
    )
    context = build_path_context(symbol, bars, path_cfg)
    calls = sample_path_calls(context, sample_mode="events")
    if calls.empty:
        return pd.DataFrame()
    foundation = build_foundation_states(
        symbol,
        FoundationDirectionConfig(
            days=cfg.days,
            exchange=cfg.exchange,
            source=cfg.source,
            entry_tf=cfg.entry_tf,
        ),
    )
    if not foundation.empty:
        calls = calls.merge(
            foundation[["symbol", "ts", "foundation_state", "direction"]].rename(columns={"direction": "foundation_direction"}),
            on=["symbol", "ts"],
            how="left",
        )
    calls = select_expansion_exhaustion_calls(calls, include_sweep_reclaim_long=cfg.include_sweep_reclaim_long)
    if calls.empty:
        return pd.DataFrame()

    structure = build_structure_index(bars, StructureConfig(left=2, right=2))
    atr_values = _atr(bars, 14)
    rows = []
    for _, call in calls.iterrows():
        signal_i = int(call["entry_i"])
        i = signal_i + cfg.confirm_bars
        if i >= len(bars) - 1:
            continue
        entry_ts = pd.Timestamp(call["ts"])
        direction = str(call["trade_direction"])
        if cfg.confirm_bars:
            entry_ts = pd.Timestamp(bars["ts"].iat[i])
            if cfg.require_reversal_close and not reversal_confirmed(bars, signal_i, i, direction):
                continue
        entry = float(bars["close"].iat[i])
        sl, tp = path_stop_target(
            bars,
            signal_i if cfg.stop_model == "path_extreme" else i,
            direction,
            entry,
            cfg.min_rr,
            atr_values,
            stop_model=cfg.stop_model,
            stop_buffer_atr=cfg.stop_buffer_atr,
            structure=structure,
            entry_ts=entry_ts,
        )
        if not np.isfinite(sl):
            continue
        risk = abs(entry - sl)
        if risk <= 0:
            continue
        stop_pct = risk / entry * 100.0
        if stop_pct < cfg.min_stop_pct:
            continue
        outcome = walk_structural_outcome(bars, i, direction, sl, tp, horizon=cfg.horizon_bars, track_excursion=True)
        if outcome is None:
            continue
        base_cost_r = cfg.base_round_trip_pct * entry / risk
        stress_cost_r = cfg.stress_round_trip_pct * entry / risk
        gross_r = float(outcome["r_multiple"])
        rows.append({
            "symbol": symbol,
            "setup": cfg.setup,
            "entry_ts": entry_ts,
            "signal_ts": call["ts"],
            "direction": direction,
            "session_utc": session_bucket(entry_ts),
            "path_context": call["path_context"],
            "foundation_state": call.get("foundation_state", ""),
            "foundation_direction": call.get("foundation_direction", ""),
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "stop_pct": stop_pct,
            "target_pct": abs(tp - entry) / entry * 100.0,
            "planned_rr": abs(tp - entry) / risk,
            "stop_model": cfg.stop_model,
            "confirm_bars": cfg.confirm_bars,
            "require_reversal_close": cfg.require_reversal_close,
            "gross_r": gross_r,
            "base_cost_r": base_cost_r,
            "stress_cost_r": stress_cost_r,
            "base_net_r": gross_r - base_cost_r,
            "stress_net_r": gross_r - stress_cost_r,
            "mfe_r": float(outcome.get("mfe_r", np.nan)),
            "mae_r": float(outcome.get("mae_r", np.nan)),
            "bars_to_exit": int(outcome.get("bars_to_exit", cfg.horizon_bars)),
            "exit_kind": str(outcome.get("exit_reason", "expiry")),
        })
    return pd.DataFrame(rows)


def reversal_confirmed(bars: pd.DataFrame, signal_i: int, entry_i: int, direction: str) -> bool:
    signal_close = float(bars["close"].iat[signal_i])
    entry_close = float(bars["close"].iat[entry_i])
    if direction == "short":
        return entry_close < signal_close
    if direction == "long":
        return entry_close > signal_close
    return False


def select_expansion_exhaustion_calls(calls: pd.DataFrame, *, include_sweep_reclaim_long: bool = False) -> pd.DataFrame:
    if calls.empty:
        return calls
    data = calls.copy()
    state = data.get("foundation_state", pd.Series("", index=data.index)).astype(str)
    up = data["path_context"].eq("expansion_up") & state.eq("range_or_unresolved")
    down = data["path_context"].eq("expansion_down") & state.isin(["local_trend_htf_neutral", "confirmed_trend"])
    sweep = data["path_context"].eq("sweep_reclaim_long") & state.eq("range_or_unresolved") if include_sweep_reclaim_long else False
    selected = data[up | down | sweep].copy()
    if selected.empty:
        return selected
    selected["trade_direction"] = np.where(selected["path_context"].eq("expansion_up"), "short", "long")
    if include_sweep_reclaim_long:
        selected.loc[selected["path_context"].eq("sweep_reclaim_long"), "trade_direction"] = "short"
    return selected.reset_index(drop=True)


def path_stop_target(
    bars: pd.DataFrame,
    entry_i: int,
    direction: str,
    entry: float,
    min_rr: float,
    atr_values: pd.Series,
    *,
    stop_model: str = "path_extreme",
    stop_buffer_atr: float = 0.1,
    structure: pd.DataFrame | None = None,
    entry_ts: pd.Timestamp | None = None,
) -> tuple[float, float]:
    if stop_model == "path_extreme":
        atr_now = float(atr_values.iat[entry_i]) if entry_i < len(atr_values) else np.nan
        if not np.isfinite(atr_now) or atr_now <= 0:
            return np.nan, np.nan
        buffer = stop_buffer_atr * atr_now
        if direction == "short":
            sl = float(bars["high"].iat[entry_i]) + buffer
            risk = sl - entry
            tp = entry - min_rr * risk
        elif direction == "long":
            sl = float(bars["low"].iat[entry_i]) - buffer
            risk = entry - sl
            tp = entry + min_rr * risk
        else:
            return np.nan, np.nan
        if risk <= 0:
            return np.nan, np.nan
        return sl, tp
    if stop_model == "structural":
        if structure is None or entry_ts is None:
            return np.nan, np.nan
        from backtesting.crypto.mtf_cascade_direction import structural_stop_target

        stop_row = asof_structure_row(structure, entry_ts)
        if stop_row is None:
            return np.nan, np.nan
        return structural_stop_target(stop_row, direction, entry, min_rr)
    raise ValueError(f"unknown stop_model: {stop_model}")


def apply_filters(trades: pd.DataFrame, cfg: PathSetupConfig) -> pd.DataFrame:
    if trades.empty:
        return trades
    out = trades.copy()
    if cfg.sessions:
        out = out[out["session_utc"].isin(cfg.sessions)]
    if cfg.max_stop_pct is not None:
        out = out[out["stop_pct"] <= cfg.max_stop_pct]
    if cfg.max_stress_cost_r is not None:
        out = out[out["stress_cost_r"] <= cfg.max_stress_cost_r]
    return out.sort_values(["entry_ts", "symbol"]).reset_index(drop=True)


def output_suffix(cfg: PathSetupConfig) -> str:
    parts = [cfg.setup, f"rr{cfg.min_rr:g}", cfg.stop_model, f"lb{cfg.lookback_bars}", f"exp{cfg.expansion_atr:g}"]
    if cfg.sessions:
        parts.append("sessions-" + "-".join(cfg.sessions))
    if cfg.max_stress_cost_r is not None:
        parts.append(f"stresscost{cfg.max_stress_cost_r:g}r")
    if cfg.include_sweep_reclaim_long:
        parts.append("with-sweep-long")
    if cfg.confirm_bars:
        parts.append(f"confirm{cfg.confirm_bars}b")
    if cfg.require_reversal_close:
        parts.append("reversal-close")
    if cfg.run_label:
        parts.append(cfg.run_label)
    return "_".join(parts).replace(".", "p")


def write_report(summary: pd.DataFrame, trades: pd.DataFrame, output: Path, windows: pd.DataFrame) -> None:
    lines = ["# Path Setup Lab", "", "## Summary", ""]
    lines.extend(_markdown_table(summary))
    lines.extend(["", "## By Path/Foundation", ""])
    if trades.empty:
        lines.append("_empty_")
    else:
        grouped = trades.groupby(["path_context", "foundation_state"]).agg(
            trades=("entry_ts", "count"),
            win_rate=("base_net_r", lambda s: float((s > 0).mean())),
            base_pf=("base_net_r", lambda s: profit_factor(s.to_numpy(dtype=float))),
            stress_pf=("stress_net_r", lambda s: profit_factor(s.to_numpy(dtype=float))),
            avg_stress_r=("stress_net_r", "mean"),
        ).reset_index()
        lines.extend(_markdown_table(grouped))
    lines.extend(["", "## Rolling Windows", ""])
    lines.extend(_markdown_table(summarize_windows(windows)))
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
    parser = argparse.ArgumentParser(description="Path setup lab.")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--days", type=int, default=360)
    parser.add_argument("--min-rr", type=float, default=1.5)
    parser.add_argument("--horizon-bars", type=int, default=96)
    parser.add_argument("--sessions", default="")
    parser.add_argument("--max-stress-cost-r", type=float, default=None)
    parser.add_argument("--max-stop-pct", type=float, default=None)
    parser.add_argument("--lookback-bars", type=int, default=32)
    parser.add_argument("--expansion-atr", type=float, default=1.5)
    parser.add_argument("--include-sweep-reclaim-long", action="store_true")
    parser.add_argument("--stop-model", default="path_extreme", choices=["path_extreme", "structural"])
    parser.add_argument("--stop-buffer-atr", type=float, default=0.1)
    parser.add_argument("--confirm-bars", type=int, default=0)
    parser.add_argument("--require-reversal-close", action="store_true")
    parser.add_argument("--portfolio", action="store_true")
    parser.add_argument("--risk-pct", type=float, default=0.0025)
    parser.add_argument("--max-open", type=int, default=3)
    parser.add_argument("--max-open-per-symbol", type=int, default=1)
    parser.add_argument("--daily-loss-limit-pct", type=float, default=0.005)
    parser.add_argument("--cooldown-after-loss-bars", type=int, default=4)
    parser.add_argument("--run-label", default="")
    parser.add_argument("--output-dir", default="backtesting/results/crypto_path_setup_lab")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    sessions = tuple(s.strip() for s in args.sessions.split(",") if s.strip()) or None
    cfg = PathSetupConfig(
        days=args.days,
        min_rr=args.min_rr,
        horizon_bars=args.horizon_bars,
        sessions=sessions,
        max_stress_cost_r=args.max_stress_cost_r,
        max_stop_pct=args.max_stop_pct,
        lookback_bars=args.lookback_bars,
        expansion_atr=args.expansion_atr,
        include_sweep_reclaim_long=args.include_sweep_reclaim_long,
        stop_model=args.stop_model,
        stop_buffer_atr=args.stop_buffer_atr,
        confirm_bars=args.confirm_bars,
        require_reversal_close=args.require_reversal_close,
        run_label=args.run_label.strip(),
    )
    trades, summary = run_path_setup_lab(symbols, config=cfg)
    windows = rolling_window_summary(trades)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = output_suffix(cfg)
    trades.to_csv(out_dir / f"{suffix}_trades.csv", index=False)
    summary.to_csv(out_dir / f"{suffix}_summary.csv", index=False)
    windows.to_csv(out_dir / f"{suffix}_windows.csv", index=False)
    write_report(summary, trades, out_dir / f"{suffix}_report.md", windows)
    if args.portfolio:
        accepted, portfolio_summary = run_portfolio_validation(
            trades,
            risk_pct=args.risk_pct,
            max_open=args.max_open,
            max_open_per_symbol=args.max_open_per_symbol,
            daily_loss_limit_pct=args.daily_loss_limit_pct,
            cooldown_after_loss_bars=args.cooldown_after_loss_bars,
            tf_minutes=int(cfg.entry_tf),
        )
        portfolio_suffix = f"{suffix}_portfolio_stress_net_r_risk{args.risk_pct:g}".replace(".", "p")
        accepted.to_csv(out_dir / f"{portfolio_suffix}_accepted.csv", index=False)
        pd.DataFrame([portfolio_summary]).to_csv(out_dir / f"{portfolio_suffix}_summary.csv", index=False)
        print("\nPortfolio")
        print(pd.DataFrame([portfolio_summary]).to_string(index=False))
    print(summary.to_string(index=False))
    if not windows.empty:
        print("\nRolling windows")
        print(summarize_windows(windows).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
