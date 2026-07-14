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
from backtesting.crypto.portfolio_validation import PortfolioRiskConfig, simulate_portfolio
from backtesting.crypto.structure_regime_journal import price_action_snapshot
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
    max_base_cost_r: float | None = None
    max_stress_cost_r: float | None = None
    sessions: tuple[str, ...] | None = None
    trend_strengths: tuple[str, ...] | None = None
    consolidation_states: tuple[str, ...] | None = None
    shock_alignments: tuple[str, ...] | None = None


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
    trades = apply_trade_filters(trades, cfg)
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
        pa = price_action_snapshot(entry_bars, entry_ts=pd.to_datetime(entry_bars["ts"].iat[i], utc=True), direction=direction)
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
                "bars_to_exit": int(outcome.get("bars_to_exit", cfg.horizon_bars)),
                "exit_kind": str(outcome.get("exit_reason", exit_kind(gross_r))),
                "trend_strength": pa.get("trend_strength", "unknown"),
                "consolidation_state": pa.get("consolidation_state", "unknown"),
                "shock_alignment": pa.get("shock_alignment", "no_shock"),
                "compression_state": pa.get("compression_state", "unknown"),
                "pre_range_atr_16": pa.get("pre_range_atr_16", np.nan),
                "adx_14": pa.get("adx_14", np.nan),
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


def apply_trade_filters(trades: pd.DataFrame, cfg: SimpleSetupConfig) -> pd.DataFrame:
    if trades.empty:
        return trades
    out = trades.copy()
    if cfg.max_base_cost_r is not None:
        out = out[out["base_cost_r"] <= cfg.max_base_cost_r]
    if cfg.max_stress_cost_r is not None:
        out = out[out["stress_cost_r"] <= cfg.max_stress_cost_r]
    if cfg.sessions:
        out = out[out["session_utc"].isin(cfg.sessions)]
    if cfg.trend_strengths:
        out = out[out["trend_strength"].isin(cfg.trend_strengths)]
    if cfg.consolidation_states:
        out = out[out["consolidation_state"].isin(cfg.consolidation_states)]
    if cfg.shock_alignments:
        out = out[out["shock_alignment"].isin(cfg.shock_alignments)]
    return out.reset_index(drop=True)


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
        "top_trend_strength": mode_or_empty(group.get("trend_strength")),
        "top_consolidation_state": mode_or_empty(group.get("consolidation_state")),
        "top_shock_alignment": mode_or_empty(group.get("shock_alignment")),
    }


def mode_or_empty(values: pd.Series | None) -> str:
    if values is None or values.empty:
        return ""
    mode = values.astype(str).mode(dropna=True)
    return "" if mode.empty else str(mode.iat[0])


def profit_factor(r: np.ndarray) -> float:
    gains = r[r > 0].sum()
    losses = -r[r <= 0].sum()
    if losses > 0:
        return float(gains / losses)
    return float("inf") if gains > 0 else np.nan


def rolling_window_summary(
    trades: pd.DataFrame,
    *,
    window_days: int = 30,
    step_days: int = 7,
    min_trades: int = 5,
) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    data = trades.copy()
    data["entry_ts"] = pd.to_datetime(data["entry_ts"], utc=True)
    start = data["entry_ts"].min().floor("D")
    end_all = data["entry_ts"].max()
    rows = []
    while start + pd.Timedelta(days=window_days) <= end_all:
        end = start + pd.Timedelta(days=window_days)
        window = data[(data["entry_ts"] >= start) & (data["entry_ts"] < end)]
        if len(window) >= min_trades:
            rows.append(
                {
                    "window_start": start,
                    "window_end": end,
                    "trades": len(window),
                    "base_avg_r": float(window["base_net_r"].mean()),
                    "base_pf": profit_factor(window["base_net_r"].to_numpy(dtype=float)),
                    "stress_avg_r": float(window["stress_net_r"].mean()),
                    "stress_pf": profit_factor(window["stress_net_r"].to_numpy(dtype=float)),
                    "base_return_r": float(window["base_net_r"].sum()),
                    "stress_return_r": float(window["stress_net_r"].sum()),
                    "median_stop_pct": float(window["stop_pct"].median()),
                }
            )
        start += pd.Timedelta(days=step_days)
    return pd.DataFrame(rows)


def summarize_windows(windows: pd.DataFrame) -> pd.DataFrame:
    if windows.empty:
        return pd.DataFrame()
    return pd.DataFrame(
        [
            {
                "windows": len(windows),
                "median_trades": float(windows["trades"].median()),
                "positive_base_windows": float((windows["base_return_r"] > 0).mean()),
                "positive_stress_windows": float((windows["stress_return_r"] > 0).mean()),
                "median_base_pf": float(windows["base_pf"].replace([np.inf, -np.inf], np.nan).median()),
                "worst_base_return_r": float(windows["base_return_r"].min()),
                "median_stress_pf": float(windows["stress_pf"].replace([np.inf, -np.inf], np.nan).median()),
                "worst_stress_return_r": float(windows["stress_return_r"].min()),
            }
        ]
    )


def run_portfolio_validation(
    trades: pd.DataFrame,
    *,
    net_column: str = "stress_net_r",
    risk_pct: float = 0.0025,
    max_open: int = 3,
    max_open_per_symbol: int = 1,
    daily_loss_limit_pct: float = 0.005,
    cooldown_after_loss_bars: int = 4,
    tf_minutes: int = 15,
) -> tuple[pd.DataFrame, dict]:
    if trades.empty:
        cfg = PortfolioRiskConfig(
            risk_per_trade_pct=risk_pct,
            max_open_trades=max_open,
            max_open_per_symbol=max_open_per_symbol,
            cooldown_after_loss_bars=cooldown_after_loss_bars,
            daily_loss_limit_pct=daily_loss_limit_pct,
            tf_minutes=tf_minutes,
        )
        return trades.copy(), {
            "candidates": 0,
            "accepted": 0,
            "acceptance_rate": 0.0,
            "gross_return_pct": 0.0,
            "max_dd_pct": 0.0,
            "daily_max_dd_pct": 0.0,
            "return_to_dd": np.nan,
        }
    if net_column not in trades.columns:
        raise ValueError(f"missing net column: {net_column}")
    data = trades.copy()
    data["exchange"] = "binance"
    data["net_r"] = data[net_column].astype(float)
    data["hit_stop"] = data["exit_kind"].eq("stop")
    data["exit_reason"] = data["exit_kind"]
    data["target_model"] = data["planned_rr"].map(lambda v: f"fixed_{float(v):g}r")
    data["management_model"] = "hold_to_target_stop_or_expiry"
    data["entry_model"] = data["setup"]
    data["stop"] = data["sl"]
    data["target"] = data["tp"]
    cfg = PortfolioRiskConfig(
        risk_per_trade_pct=risk_pct,
        max_open_trades=max_open,
        max_open_per_symbol=max_open_per_symbol,
        cooldown_after_loss_bars=cooldown_after_loss_bars,
        daily_loss_limit_pct=daily_loss_limit_pct,
        tf_minutes=tf_minutes,
    )
    return simulate_portfolio(data, cfg)


def build_full_review_packet(
    accepted: pd.DataFrame,
    *,
    output_path: Path,
    predictor: str = "crypto_simple_context_change_strict_no_shock",
    target_r: float = 2.0,
    tf: str = "15",
) -> pd.DataFrame:
    """Export every accepted simple-lab portfolio trade for the review UI."""
    if accepted.empty:
        packet = pd.DataFrame()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        packet.to_csv(output_path, index=False)
        return packet

    data = accepted.copy()
    data["entry_ts"] = pd.to_datetime(data["entry_ts"], utc=True)
    if "exit_ts" in data.columns:
        data["exit_ts"] = pd.to_datetime(data["exit_ts"], utc=True)
    else:
        data["exit_ts"] = data["entry_ts"] + pd.to_timedelta(pd.to_numeric(data["bars_to_exit"], errors="coerce") * int(tf), unit="m")

    risk = (data["entry"].astype(float) - data["stop"].astype(float)).abs()
    packet = pd.DataFrame(
        {
            "ts": data["entry_ts"],
            "exit_ts": data["exit_ts"],
            "symbol": data["symbol"].astype(str),
            "exchange": data.get("exchange", "binance"),
            "tf": tf,
            "predictor": predictor,
            "session": data["session_utc"].astype(str),
            "direction": data["direction"].astype(str),
            "entry_price": data["entry"].astype(float),
            "sl": data["stop"].astype(float),
            "tp1": data["target"].astype(float),
            "risk_price": risk.astype(float),
            f"outcome_{target_r:g}r": data["net_r"].astype(float),
            f"hit_{target_r:g}r": data["exit_reason"].astype(str).eq("target"),
            "planned_rr": data["planned_rr"].astype(float),
            "duration_min": pd.to_numeric(data["bars_to_exit"], errors="coerce").astype(float) * int(tf),
            "return_pct": data.get("pnl_pct", data["net_r"].astype(float) * data.get("risk_per_trade_pct", 0.0)).astype(float) * 100.0,
            "mfe_r": data["mfe_r"].astype(float),
            "mae_r": data["mae_r"].astype(float),
            "exit_reason": data["exit_reason"].astype(str),
            "review_bucket": "accepted_trade",
            "setup": data["setup"].astype(str),
            "trend_strength": data.get("trend_strength", ""),
            "consolidation_state": data.get("consolidation_state", ""),
            "shock_alignment": data.get("shock_alignment", ""),
            "compression_state": data.get("compression_state", ""),
            "base_net_r": data.get("base_net_r", np.nan),
            "stress_net_r": data.get("stress_net_r", np.nan),
            "notes_hint": data.apply(_review_notes_hint, axis=1),
        }
    )
    packet = packet.sort_values(["symbol", "ts"]).reset_index(drop=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    packet.to_csv(output_path, index=False)
    for symbol, group in packet.groupby("symbol"):
        group.to_csv(output_path.with_name(f"{output_path.stem}_{symbol}.csv"), index=False)
    return packet


def _review_notes_hint(row: pd.Series) -> str:
    return (
        f"Full accepted trade. setup={row.get('setup')}; "
        f"session={row.get('session_utc')}; context={row.get('trend_strength')}/"
        f"{row.get('consolidation_state')}/{row.get('shock_alignment')}; "
        f"stressR={float(row.get('net_r', 0.0)):.2f}."
    )


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


def write_report(summary: pd.DataFrame, trades: pd.DataFrame, output: Path, windows: pd.DataFrame | None = None) -> None:
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
        context = trades.groupby(["trend_strength", "consolidation_state", "shock_alignment"]).agg(
            trades=("base_net_r", "size"),
            stress_avg_r=("stress_net_r", "mean"),
            stress_pf=("stress_net_r", profit_factor),
        ).reset_index().sort_values(["stress_avg_r", "trades"], ascending=[False, False])
        lines.extend(["", "## Context Split", "", dataframe_to_markdown(context.head(20))])
    else:
        lines.append("No trades.")
    if windows is not None and not windows.empty:
        lines.extend(
            [
                "",
                "## Rolling Windows",
                "",
                dataframe_to_markdown(summarize_windows(windows)),
            ]
        )
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


def write_portfolio_report(summary: dict, accepted: pd.DataFrame, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    summary_df = pd.DataFrame([summary])
    lines = [
        "# Simple Crypto Setup Portfolio Validation",
        "",
        "Scope: portfolio/risk throttle applied to one already-filtered simple setup candidate set.",
        "",
        "## Summary",
        "",
        dataframe_to_markdown(summary_df),
        "",
        "## Symbol Split",
        "",
    ]
    if not accepted.empty:
        by_symbol = accepted.groupby("symbol").agg(
            trades=("net_r", "size"),
            avg_r=("net_r", "mean"),
            pf=("net_r", profit_factor),
            pnl_pct=("pnl_pct", "sum"),
        ).reset_index()
        lines.append(dataframe_to_markdown(by_symbol))
    else:
        lines.append("No accepted trades.")
    lines.extend(
        [
            "",
            "## Read",
            "",
            "- This is still research validation, not live approval.",
            "- Stress-mode validation should be treated as the primary deployment-risk read.",
        ]
    )
    output.write_text("\n".join(lines) + "\n")


def dataframe_to_markdown(df: pd.DataFrame) -> str:
    if df.empty:
        return "No rows."
    formatted = df.copy()
    for col in formatted.columns:
        if pd.api.types.is_float_dtype(formatted[col]):
            formatted[col] = formatted[col].map(lambda v: "" if pd.isna(v) else f"{v:.4f}")
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
    parser.add_argument("--min-rr", type=float, default=1.5)
    parser.add_argument("--max-base-cost-r", type=float, default=None)
    parser.add_argument("--max-stress-cost-r", type=float, default=None)
    parser.add_argument("--sessions", default="", help="Comma-separated UTC session buckets: asia,london,ny,late_us")
    parser.add_argument("--trend-strengths", default="", help="Comma-separated trend buckets: weak_or_range,transition,trend,strong_trend")
    parser.add_argument("--consolidation-states", default="", help="Comma-separated consolidation states.")
    parser.add_argument("--shock-alignments", default="", help="Comma-separated shock states: no_shock,aligned_shock,opposing_shock")
    parser.add_argument("--window-days", type=int, default=30)
    parser.add_argument("--step-days", type=int, default=7)
    parser.add_argument("--portfolio", action="store_true")
    parser.add_argument("--portfolio-net", default="stress_net_r", choices=["base_net_r", "stress_net_r"])
    parser.add_argument("--risk-pct", type=float, default=0.0025)
    parser.add_argument("--max-open", type=int, default=3)
    parser.add_argument("--max-open-per-symbol", type=int, default=1)
    parser.add_argument("--daily-loss-limit-pct", type=float, default=0.005)
    parser.add_argument("--cooldown-after-loss-bars", type=int, default=4)
    parser.add_argument("--review-packet", action="store_true", help="When portfolio is enabled, export every accepted trade for the review UI.")
    parser.add_argument("--output-dir", default="backtesting/results/crypto_simple_setup_lab")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    sessions = tuple(s.strip() for s in args.sessions.split(",") if s.strip()) or None
    trend_strengths = tuple(s.strip() for s in args.trend_strengths.split(",") if s.strip()) or None
    consolidation_states = tuple(s.strip() for s in args.consolidation_states.split(",") if s.strip()) or None
    shock_alignments = tuple(s.strip() for s in args.shock_alignments.split(",") if s.strip()) or None
    cfg = SimpleSetupConfig(
        days=args.days,
        min_rr=args.min_rr,
        max_base_cost_r=args.max_base_cost_r,
        max_stress_cost_r=args.max_stress_cost_r,
        sessions=sessions,
        trend_strengths=trend_strengths,
        consolidation_states=consolidation_states,
        shock_alignments=shock_alignments,
    )
    trades, summary = run_simple_setup_lab(symbols, config=cfg, setup=args.setup)
    windows = rolling_window_summary(trades, window_days=args.window_days, step_days=args.step_days)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = output_suffix(args.setup, cfg)
    trades.to_csv(out_dir / f"{suffix}_trades.csv", index=False)
    summary.to_csv(out_dir / f"{suffix}_summary.csv", index=False)
    windows.to_csv(out_dir / f"{suffix}_windows.csv", index=False)
    write_report(summary, trades, out_dir / f"{suffix}_report.md", windows)
    if args.portfolio:
        accepted, portfolio_summary = run_portfolio_validation(
            trades,
            net_column=args.portfolio_net,
            risk_pct=args.risk_pct,
            max_open=args.max_open,
            max_open_per_symbol=args.max_open_per_symbol,
            daily_loss_limit_pct=args.daily_loss_limit_pct,
            cooldown_after_loss_bars=args.cooldown_after_loss_bars,
        )
        portfolio_suffix = f"{suffix}_portfolio_{args.portfolio_net}_risk{args.risk_pct:g}".replace(".", "p")
        accepted.to_csv(out_dir / f"{portfolio_suffix}_accepted.csv", index=False)
        pd.DataFrame([portfolio_summary]).to_csv(out_dir / f"{portfolio_suffix}_summary.csv", index=False)
        write_portfolio_report(portfolio_summary, accepted, out_dir / f"{portfolio_suffix}_report.md")
        if args.review_packet:
            review_path = Path("backtesting/results/review_samples") / f"{portfolio_suffix}_full_review.csv"
            packet = build_full_review_packet(accepted, output_path=review_path, target_r=args.min_rr, tf=cfg.entry_tf)
            print(f"Saved review packet: {review_path} rows={len(packet)}")
        print("\nPortfolio")
        print(pd.DataFrame([portfolio_summary]).to_string(index=False))
    print(summary.to_string(index=False))
    if not windows.empty:
        print("\nRolling windows")
        print(summarize_windows(windows).to_string(index=False))
    return 0


def output_suffix(setup: str, cfg: SimpleSetupConfig) -> str:
    parts = [setup, f"rr{cfg.min_rr:g}"]
    if cfg.max_base_cost_r is not None:
        parts.append(f"basecost{cfg.max_base_cost_r:g}r")
    if cfg.max_stress_cost_r is not None:
        parts.append(f"stresscost{cfg.max_stress_cost_r:g}r")
    if cfg.sessions:
        parts.append("sessions-" + "-".join(cfg.sessions))
    if cfg.trend_strengths:
        parts.append("trend-" + "-".join(cfg.trend_strengths))
    if cfg.consolidation_states:
        parts.append("state-" + "-".join(cfg.consolidation_states))
    if cfg.shock_alignments:
        parts.append("shock-" + "-".join(cfg.shock_alignments))
    return "_".join(parts).replace(".", "p")


if __name__ == "__main__":
    raise SystemExit(main())
