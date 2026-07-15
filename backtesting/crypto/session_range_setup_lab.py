"""Session range setup lab for crypto.

This is a separate setup family from sweep-reclaim path setups. It tests whether
London/NY behavior around the prior session range has standalone edge.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.crypto.data import load_crypto
from backtesting.crypto.event_atlas import _atr
from backtesting.crypto.mtf_cascade_direction import DEFAULT_SYMBOLS, walk_structural_outcome
from backtesting.crypto.path_setup_lab import _markdown_table
from backtesting.crypto.simple_setup_lab import (
    profit_factor,
    rolling_window_summary,
    run_portfolio_validation,
    session_bucket,
    summarize_trades,
    summarize_windows,
)


@dataclass(frozen=True)
class SessionRangeConfig:
    days: int = 360
    exchange: str = "binance"
    source: str = "merged"
    entry_tf: str = "15"
    setup: str = "london_asia_fakeout"
    min_rr: float = 1.5
    horizon_bars: int = 96
    min_stop_pct: float = 0.1
    max_stress_cost_r: float | None = 0.25
    base_round_trip_pct: float = 0.0006
    stress_round_trip_pct: float = 0.0020
    breakout_close_buffer_atr: float = 0.15
    reclaim_close_buffer_atr: float = 0.0
    reference_close_location_threshold: float = 0.7
    min_reference_body_atr: float = 0.5
    min_reference_range_atr: float = 0.75
    max_reference_range_atr: float = 6.0
    stop_buffer_atr: float = 0.1
    max_trades_per_symbol_day: int = 1
    filtered_candidate_uses_day_slot: bool = True
    run_label: str = ""


SETUP_SESSIONS = {
    "london_asia_breakout": ("asia", "london", "breakout"),
    "london_asia_fakeout": ("asia", "london", "fakeout"),
    "london_asia_continuation": ("asia", "london", "continuation"),
    "ny_london_breakout": ("london", "ny", "breakout"),
    "ny_london_fakeout": ("london", "ny", "fakeout"),
    "ny_london_continuation": ("london", "ny", "continuation"),
}


def run_session_range_lab(
    symbols: list[str] | None = None,
    *,
    config: SessionRangeConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    cfg = config or SessionRangeConfig()
    rows = []
    for symbol in symbols or DEFAULT_SYMBOLS:
        rows.extend(evaluate_symbol(symbol, cfg).to_dict("records"))
    trades = pd.DataFrame(rows)
    trades = apply_filters(trades, cfg)
    return trades, summarize_trades(trades)


def run_session_range_frequency_audit(symbols: list[str] | None = None, *, config: SessionRangeConfig | None = None) -> pd.DataFrame:
    cfg = config or SessionRangeConfig()
    rows = []
    for symbol in symbols or DEFAULT_SYMBOLS:
        rows.extend(audit_symbol_sessions(symbol, cfg).to_dict("records"))
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    out["primary_blocker"] = out.apply(lambda row: primary_session_blocker(row, cfg), axis=1)
    return out.sort_values(["symbol", "day"]).reset_index(drop=True)


def evaluate_symbol(symbol: str, cfg: SessionRangeConfig) -> pd.DataFrame:
    bars = load_crypto(symbol, tf=cfg.entry_tf, days=cfg.days, exchange=cfg.exchange, source=cfg.source).reset_index(drop=True)
    if bars.empty:
        return pd.DataFrame()
    bars["ts"] = pd.to_datetime(bars["ts"], utc=True)
    bars["day"] = bars["ts"].dt.floor("D")
    bars["session_utc"] = bars["ts"].map(session_bucket)
    atr_values = _atr(bars, 14)

    rows = []
    reference_session, trade_session, mode = SETUP_SESSIONS[cfg.setup]
    for day, day_bars in bars.groupby("day", sort=True):
        ref = day_bars[day_bars["session_utc"].eq(reference_session)]
        trade = day_bars[day_bars["session_utc"].eq(trade_session)]
        if ref.empty or trade.empty:
            continue
        ref_high = float(ref["high"].max())
        ref_low = float(ref["low"].min())
        ref_mid = (ref_high + ref_low) / 2.0
        ref_end_i = int(ref.index[-1])
        atr_now = _atr_at(atr_values, ref_end_i)
        if not np.isfinite(atr_now) or atr_now <= 0:
            continue
        ref_range_atr = (ref_high - ref_low) / atr_now
        if ref_range_atr < cfg.min_reference_range_atr or ref_range_atr > cfg.max_reference_range_atr:
            continue
        ref_bias = reference_direction(ref, ref_high, ref_low, atr_now, cfg)
        if mode == "continuation" and ref_bias is None:
            continue
        day_count = 0
        swept_high = False
        swept_low = False
        for i in trade.index:
            if day_count >= cfg.max_trades_per_symbol_day:
                break
            high = float(bars["high"].iat[i])
            low = float(bars["low"].iat[i])
            close = float(bars["close"].iat[i])
            atr_i = _atr_at(atr_values, int(i))
            if not np.isfinite(atr_i) or atr_i <= 0:
                continue
            swept_high = swept_high or high > ref_high
            swept_low = swept_low or low < ref_low
            signal = session_range_signal(
                mode=mode,
                close=close,
                ref_high=ref_high,
                ref_low=ref_low,
                ref_mid=ref_mid,
                atr=atr_i,
                swept_high=swept_high,
                swept_low=swept_low,
                reference_bias=ref_bias,
                breakout_buffer_atr=cfg.breakout_close_buffer_atr,
                reclaim_buffer_atr=cfg.reclaim_close_buffer_atr,
            )
            if signal is None:
                continue
            row, _stage = trade_candidate(symbol, bars, atr_values, int(i), signal, cfg, ref_high, ref_low, ref_range_atr)
            if row:
                passes_filters = candidate_passes_filters(row, cfg)
                if passes_filters:
                    rows.append(row)
                if passes_filters or cfg.filtered_candidate_uses_day_slot:
                    day_count += 1
    return pd.DataFrame(rows)


def audit_symbol_sessions(symbol: str, cfg: SessionRangeConfig) -> pd.DataFrame:
    bars = load_crypto(symbol, tf=cfg.entry_tf, days=cfg.days, exchange=cfg.exchange, source=cfg.source).reset_index(drop=True)
    if bars.empty:
        return pd.DataFrame()
    bars["ts"] = pd.to_datetime(bars["ts"], utc=True)
    bars["day"] = bars["ts"].dt.floor("D")
    bars["session_utc"] = bars["ts"].map(session_bucket)
    atr_values = _atr(bars, 14)

    rows = []
    reference_session, trade_session, mode = SETUP_SESSIONS[cfg.setup]
    for day, day_bars in bars.groupby("day", sort=True):
        row = {
            "symbol": symbol,
            "day": pd.Timestamp(day),
            "setup": cfg.setup,
            "reference_session": reference_session,
            "trade_session": trade_session,
            "reference_bars": 0,
            "trade_bars": 0,
            "reference_range_atr": np.nan,
            "reference_bias": "",
            "swept_high": 0,
            "swept_low": 0,
            "signal_attempts": 0,
            "blocked_cost": 0,
            "invalid_path": 0,
            "stop_too_tight": 0,
            "pre_portfolio_pass": 0,
            "target_at_signal": 0,
            "stop_at_signal": 0,
            "expiry_at_signal": 0,
            "median_stress_cost_r": np.nan,
            "median_stop_pct": np.nan,
        }
        ref = day_bars[day_bars["session_utc"].eq(reference_session)]
        trade = day_bars[day_bars["session_utc"].eq(trade_session)]
        row["reference_bars"] = int(len(ref))
        row["trade_bars"] = int(len(trade))
        if ref.empty or trade.empty:
            rows.append(row)
            continue
        ref_high = float(ref["high"].max())
        ref_low = float(ref["low"].min())
        ref_mid = (ref_high + ref_low) / 2.0
        ref_end_i = int(ref.index[-1])
        atr_now = _atr_at(atr_values, ref_end_i)
        if not np.isfinite(atr_now) or atr_now <= 0:
            rows.append(row)
            continue
        ref_range_atr = (ref_high - ref_low) / atr_now
        row["reference_range_atr"] = ref_range_atr
        if ref_range_atr < cfg.min_reference_range_atr or ref_range_atr > cfg.max_reference_range_atr:
            rows.append(row)
            continue
        ref_bias = reference_direction(ref, ref_high, ref_low, atr_now, cfg)
        row["reference_bias"] = ref_bias or ""
        if mode == "continuation" and ref_bias is None:
            rows.append(row)
            continue

        swept_high = False
        swept_low = False
        costs = []
        stops = []
        for i in trade.index:
            high = float(bars["high"].iat[i])
            low = float(bars["low"].iat[i])
            close = float(bars["close"].iat[i])
            atr_i = _atr_at(atr_values, int(i))
            if not np.isfinite(atr_i) or atr_i <= 0:
                continue
            swept_high = swept_high or high > ref_high
            swept_low = swept_low or low < ref_low
            row["swept_high"] = int(swept_high)
            row["swept_low"] = int(swept_low)
            signal = session_range_signal(
                mode=mode,
                close=close,
                ref_high=ref_high,
                ref_low=ref_low,
                ref_mid=ref_mid,
                atr=atr_i,
                swept_high=swept_high,
                swept_low=swept_low,
                reference_bias=ref_bias,
                breakout_buffer_atr=cfg.breakout_close_buffer_atr,
                reclaim_buffer_atr=cfg.reclaim_close_buffer_atr,
            )
            if signal is None:
                continue
            row["signal_attempts"] += 1
            candidate, stage = trade_candidate(symbol, bars, atr_values, int(i), signal, cfg, ref_high, ref_low, ref_range_atr)
            if candidate is None:
                if stage == "stop_too_tight":
                    row["stop_too_tight"] += 1
                else:
                    row["invalid_path"] += 1
                continue
            costs.append(float(candidate["stress_cost_r"]))
            stops.append(float(candidate["stop_pct"]))
            if cfg.max_stress_cost_r is not None and float(candidate["stress_cost_r"]) > cfg.max_stress_cost_r:
                row["blocked_cost"] += 1
                continue
            row["pre_portfolio_pass"] += 1
            if candidate["exit_kind"] == "target":
                row["target_at_signal"] += 1
            elif candidate["exit_kind"] == "stop":
                row["stop_at_signal"] += 1
            elif candidate["exit_kind"] == "expiry":
                row["expiry_at_signal"] += 1
        if costs:
            row["median_stress_cost_r"] = float(np.median(costs))
        if stops:
            row["median_stop_pct"] = float(np.median(stops))
        rows.append(row)
    return pd.DataFrame(rows)


def session_range_signal(
    *,
    mode: str,
    close: float,
    ref_high: float,
    ref_low: float,
    ref_mid: float,
    atr: float,
    swept_high: bool,
    swept_low: bool,
    breakout_buffer_atr: float,
    reclaim_buffer_atr: float,
    reference_bias: str | None = None,
) -> str | None:
    if mode == "breakout":
        if close > ref_high + breakout_buffer_atr * atr:
            return "long"
        if close < ref_low - breakout_buffer_atr * atr:
            return "short"
        return None
    if mode == "fakeout":
        if swept_high and close < ref_high - reclaim_buffer_atr * atr and close <= ref_mid:
            return "short"
        if swept_low and close > ref_low + reclaim_buffer_atr * atr and close >= ref_mid:
            return "long"
        return None
    if mode == "continuation":
        if reference_bias == "long" and close > ref_high + breakout_buffer_atr * atr:
            return "long"
        if reference_bias == "short" and close < ref_low - breakout_buffer_atr * atr:
            return "short"
        return None
    raise ValueError(f"unknown session range mode: {mode}")


def reference_direction(ref: pd.DataFrame, ref_high: float, ref_low: float, atr: float, cfg: SessionRangeConfig) -> str | None:
    if ref.empty or not np.isfinite(atr) or atr <= 0:
        return None
    ref_open = float(ref["open"].iloc[0])
    ref_close = float(ref["close"].iloc[-1])
    ref_range = ref_high - ref_low
    if ref_range <= 0:
        return None
    body_atr = abs(ref_close - ref_open) / atr
    if body_atr < cfg.min_reference_body_atr:
        return None
    close_location = (ref_close - ref_low) / ref_range
    threshold = cfg.reference_close_location_threshold
    if close_location >= threshold and ref_close > ref_open:
        return "long"
    if close_location <= 1.0 - threshold and ref_close < ref_open:
        return "short"
    return None


def trade_row(
    symbol: str,
    bars: pd.DataFrame,
    atr_values: pd.Series,
    i: int,
    direction: str,
    cfg: SessionRangeConfig,
    ref_high: float,
    ref_low: float,
    ref_range_atr: float,
) -> dict | None:
    row, _stage = trade_candidate(symbol, bars, atr_values, i, direction, cfg, ref_high, ref_low, ref_range_atr)
    return row


def trade_candidate(
    symbol: str,
    bars: pd.DataFrame,
    atr_values: pd.Series,
    i: int,
    direction: str,
    cfg: SessionRangeConfig,
    ref_high: float,
    ref_low: float,
    ref_range_atr: float,
) -> tuple[dict | None, str]:
    entry = float(bars["close"].iat[i])
    atr_i = _atr_at(atr_values, i)
    if not np.isfinite(atr_i) or atr_i <= 0:
        return None, "invalid_atr"
    buffer = cfg.stop_buffer_atr * atr_i
    if direction == "long":
        sl = min(float(bars["low"].iat[i]) - buffer, ref_low - buffer)
        risk = entry - sl
        tp = entry + cfg.min_rr * risk
    elif direction == "short":
        sl = max(float(bars["high"].iat[i]) + buffer, ref_high + buffer)
        risk = sl - entry
        tp = entry - cfg.min_rr * risk
    else:
        return None, "invalid_direction"
    if risk <= 0:
        return None, "invalid_risk"
    stop_pct = risk / entry * 100.0
    if stop_pct < cfg.min_stop_pct:
        return None, "stop_too_tight"
    outcome = walk_structural_outcome(bars, i, direction, sl, tp, horizon=cfg.horizon_bars, track_excursion=True)
    if outcome is None:
        return None, "invalid_outcome"
    base_cost_r = cfg.base_round_trip_pct * entry / risk
    stress_cost_r = cfg.stress_round_trip_pct * entry / risk
    gross_r = float(outcome["r_multiple"])
    entry_ts = pd.Timestamp(bars["ts"].iat[i])
    return {
        "symbol": symbol,
        "setup": cfg.setup,
        "entry_ts": entry_ts,
        "signal_ts": entry_ts,
        "direction": direction,
        "session_utc": session_bucket(entry_ts),
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "stop_pct": stop_pct,
        "target_pct": abs(tp - entry) / entry * 100.0,
        "planned_rr": abs(tp - entry) / risk,
        "reference_high": ref_high,
        "reference_low": ref_low,
        "reference_range_atr": ref_range_atr,
        "gross_r": gross_r,
        "base_cost_r": base_cost_r,
        "stress_cost_r": stress_cost_r,
        "base_net_r": gross_r - base_cost_r,
        "stress_net_r": gross_r - stress_cost_r,
        "mfe_r": float(outcome.get("mfe_r", np.nan)),
        "mae_r": float(outcome.get("mae_r", np.nan)),
        "bars_to_exit": int(outcome.get("bars_to_exit", cfg.horizon_bars)),
        "exit_kind": str(outcome.get("exit_reason", "expiry")),
    }, "candidate"


def apply_filters(trades: pd.DataFrame, cfg: SessionRangeConfig) -> pd.DataFrame:
    if trades.empty:
        return trades
    out = trades.copy()
    if cfg.max_stress_cost_r is not None:
        out = out[out["stress_cost_r"] <= cfg.max_stress_cost_r]
    return out.sort_values(["entry_ts", "symbol"]).reset_index(drop=True)


def candidate_passes_filters(row: dict, cfg: SessionRangeConfig) -> bool:
    if cfg.max_stress_cost_r is not None and float(row["stress_cost_r"]) > cfg.max_stress_cost_r:
        return False
    return True


def primary_session_blocker(row: pd.Series, cfg: SessionRangeConfig | None = None) -> str:
    cfg = cfg or SessionRangeConfig()
    if int(row.get("pre_portfolio_pass", 0)) > 0:
        return "pre_portfolio_pass"
    if int(row.get("blocked_cost", 0)) > 0:
        return "blocked_cost"
    if int(row.get("stop_too_tight", 0)) > 0:
        return "stop_too_tight"
    if int(row.get("invalid_path", 0)) > 0:
        return "invalid_path"
    if int(row.get("signal_attempts", 0)) > 0:
        return "signal_no_trade"
    if float(row.get("reference_bars", 0) or 0) == 0:
        return "missing_reference_session"
    if float(row.get("trade_bars", 0) or 0) == 0:
        return "missing_trade_session"
    ref_range = row.get("reference_range_atr", np.nan)
    if not np.isfinite(ref_range):
        return "invalid_reference_atr"
    if ref_range < cfg.min_reference_range_atr:
        return "reference_range_too_small"
    if ref_range > cfg.max_reference_range_atr:
        return "reference_range_too_large"
    if not int(row.get("swept_high", 0)) and not int(row.get("swept_low", 0)):
        return "no_sweep"
    return "sweep_without_reclaim"


def write_frequency_report(daily: pd.DataFrame, output: Path) -> None:
    lines = ["# Session Range Frequency Audit", ""]
    if daily.empty:
        lines.append("_empty_")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("\n".join(lines) + "\n")
        return
    blocker = daily.groupby("primary_blocker").size().rename("days").reset_index().sort_values("days", ascending=False)
    by_symbol = (
        daily.groupby(["symbol", "primary_blocker"])
        .size()
        .rename("days")
        .reset_index()
        .sort_values(["symbol", "days"], ascending=[True, False])
    )
    lines.extend(["## Primary Blockers", ""])
    lines.extend(_markdown_table(blocker))
    lines.extend(["", "## By Symbol", ""])
    lines.extend(_markdown_table(by_symbol))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n")


def output_suffix(cfg: SessionRangeConfig) -> str:
    parts = [
        cfg.setup,
        f"rr{cfg.min_rr:g}",
        f"tf{cfg.entry_tf}",
        f"ref{cfg.min_reference_range_atr:g}-{cfg.max_reference_range_atr:g}",
    ]
    if cfg.setup.endswith("_continuation"):
        parts.append(f"refloc{cfg.reference_close_location_threshold:g}")
        parts.append(f"refbody{cfg.min_reference_body_atr:g}")
    if cfg.max_stress_cost_r is not None:
        parts.append(f"stresscost{cfg.max_stress_cost_r:g}r")
    if cfg.base_round_trip_pct != 0.0006:
        parts.append(f"basefee{cfg.base_round_trip_pct:g}")
    if cfg.stress_round_trip_pct != 0.0020:
        parts.append(f"stressfee{cfg.stress_round_trip_pct:g}")
    if cfg.max_trades_per_symbol_day != 1:
        parts.append(f"maxday{cfg.max_trades_per_symbol_day}")
    if not cfg.filtered_candidate_uses_day_slot:
        parts.append("reuse-filtered-slot")
    if cfg.run_label:
        parts.append(cfg.run_label)
    return "_".join(parts).replace(".", "p")


def write_report(summary: pd.DataFrame, trades: pd.DataFrame, output: Path, windows: pd.DataFrame) -> None:
    lines = ["# Session Range Setup Lab", "", "## Summary", ""]
    lines.extend(_markdown_table(summary))
    lines.extend(["", "## By Setup/Session", ""])
    if trades.empty:
        lines.append("_empty_")
    else:
        grouped = trades.groupby(["setup", "session_utc"]).agg(
            trades=("entry_ts", "count"),
            win_rate=("stress_net_r", lambda s: float((s > 0).mean())),
            stress_pf=("stress_net_r", lambda s: profit_factor(s.to_numpy(dtype=float))),
            avg_stress_r=("stress_net_r", "mean"),
            median_ref_range_atr=("reference_range_atr", "median"),
            median_stop_pct=("stop_pct", "median"),
        ).reset_index()
        lines.extend(_markdown_table(grouped))
    lines.extend(["", "## Rolling Windows", ""])
    lines.extend(_markdown_table(summarize_windows(windows)))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n")


def _atr_at(atr_values: pd.Series, i: int) -> float:
    if i >= len(atr_values):
        return np.nan
    value = float(atr_values.iat[i])
    return value if np.isfinite(value) else np.nan


def main() -> int:
    parser = argparse.ArgumentParser(description="Session range setup lab.")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--days", type=int, default=360)
    parser.add_argument("--entry-tf", default="15")
    parser.add_argument("--setup", default="london_asia_fakeout", choices=list(SETUP_SESSIONS))
    parser.add_argument("--min-rr", type=float, default=1.5)
    parser.add_argument("--horizon-bars", type=int, default=96)
    parser.add_argument("--max-stress-cost-r", type=float, default=0.25)
    parser.add_argument("--base-round-trip-pct", type=float, default=0.0006)
    parser.add_argument("--stress-round-trip-pct", type=float, default=0.0020)
    parser.add_argument("--min-reference-range-atr", type=float, default=0.75)
    parser.add_argument("--max-reference-range-atr", type=float, default=6.0)
    parser.add_argument("--breakout-close-buffer-atr", type=float, default=0.15)
    parser.add_argument("--reclaim-close-buffer-atr", type=float, default=0.0)
    parser.add_argument("--reference-close-location-threshold", type=float, default=0.7)
    parser.add_argument("--min-reference-body-atr", type=float, default=0.5)
    parser.add_argument("--max-trades-per-symbol-day", type=int, default=1)
    parser.add_argument("--reuse-filtered-day-slot", action="store_true")
    parser.add_argument("--portfolio", action="store_true")
    parser.add_argument("--frequency-audit", action="store_true")
    parser.add_argument("--risk-pct", type=float, default=0.0025)
    parser.add_argument("--max-open", type=int, default=3)
    parser.add_argument("--max-open-per-symbol", type=int, default=1)
    parser.add_argument("--daily-loss-limit-pct", type=float, default=0.005)
    parser.add_argument("--cooldown-after-loss-bars", type=int, default=4)
    parser.add_argument("--run-label", default="")
    parser.add_argument("--output-dir", default="backtesting/results/crypto_session_range_setup_lab")
    args = parser.parse_args()

    cfg = SessionRangeConfig(
        days=args.days,
        entry_tf=str(args.entry_tf),
        setup=args.setup,
        min_rr=args.min_rr,
        horizon_bars=args.horizon_bars,
        max_stress_cost_r=args.max_stress_cost_r,
        base_round_trip_pct=args.base_round_trip_pct,
        stress_round_trip_pct=args.stress_round_trip_pct,
        min_reference_range_atr=args.min_reference_range_atr,
        max_reference_range_atr=args.max_reference_range_atr,
        breakout_close_buffer_atr=args.breakout_close_buffer_atr,
        reclaim_close_buffer_atr=args.reclaim_close_buffer_atr,
        reference_close_location_threshold=args.reference_close_location_threshold,
        min_reference_body_atr=args.min_reference_body_atr,
        max_trades_per_symbol_day=args.max_trades_per_symbol_day,
        filtered_candidate_uses_day_slot=not args.reuse_filtered_day_slot,
        run_label=args.run_label.strip(),
    )
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    trades, summary = run_session_range_lab(symbols, config=cfg)
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
    if args.frequency_audit:
        daily = run_session_range_frequency_audit(symbols, config=cfg)
        daily.to_csv(out_dir / f"{suffix}_frequency_daily.csv", index=False)
        write_frequency_report(daily, out_dir / f"{suffix}_frequency_report.md")
    print(summary.to_string(index=False))
    if not windows.empty:
        print("\nRolling windows")
        print(summarize_windows(windows).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
