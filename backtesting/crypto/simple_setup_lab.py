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
    walk_limit_outcome,
    walk_structural_outcome,
    walk_structural_outcome_ltf,
)
from backtesting.crypto.portfolio_validation import PortfolioRiskConfig, simulate_portfolio
from backtesting.crypto.structure_regime_journal import price_action_snapshot
from backtesting.features.core import atr
from backtesting.features.structure import StructureConfig, build_structure_index
from backtesting.features.vwap import build_vwap_index


@dataclass(frozen=True)
class SimpleSetupConfig:
    days: int = 400
    exchange: str = "binance"
    source: str = "merged"
    global_tf: str = "240"
    local_tf: str = "30"
    entry_tf: str = "15"
    stop_tf: str = ""
    context_mode: str = "strict"
    min_rr: float = 1.5
    horizon_bars: int = 96
    min_stop_pct: float = 0.1
    max_stop_pct: float | None = None
    base_round_trip_pct: float = 0.0006
    stress_round_trip_pct: float = 0.0020
    slippage_mode: str = "fixed"  # "fixed" or "atr_scaled"; when atr_scaled, base/stress are atr multipliers
    max_base_cost_r: float | None = None
    max_stress_cost_r: float | None = None
    sessions: tuple[str, ...] | None = None
    trend_strengths: tuple[str, ...] | None = None
    consolidation_states: tuple[str, ...] | None = None
    shock_alignments: tuple[str, ...] | None = None
    dmi_alignments: tuple[str, ...] | None = None
    vwap_alignments: tuple[str, ...] | None = None
    ema_alignments: tuple[str, ...] | None = None
    entry_delay_bars: int = 0
    partial_tp_pct: float = 0.0   # 0=no partial, 0.5=close 50% at 1R, let rest run
    ltf_monitor_tf: str = ""      # ""=no LTF monitoring, "5"=5m, "3"=3m
    fib_entry_pct: float = 0.0    # 0=market at close, 0.382/0.5/0.618=limit at Fib retrace of last swing
    structure_left: int = 2
    structure_right: int = 2
    context_structure_left: int = 2
    context_structure_right: int = 2
    run_label: str = ""


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


def run_frequency_audit(
    symbols: list[str] | None = None,
    *,
    config: SimpleSetupConfig | None = None,
    setup: str = "context_change",
    accepted: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Explain daily trade frequency by pipeline stage, not just final trades."""
    cfg = config or SimpleSetupConfig()
    daily_rows: list[dict] = []
    signal_rows: list[dict] = []
    for symbol in symbols or DEFAULT_SYMBOLS:
        daily, signals = frequency_audit_symbol(symbol, cfg, setup=setup)
        daily_rows.extend(daily.to_dict("records"))
        signal_rows.extend(signals.to_dict("records"))
    daily_df = pd.DataFrame(daily_rows)
    signal_df = pd.DataFrame(signal_rows)
    if daily_df.empty:
        return daily_df, signal_df
    if accepted is not None and not accepted.empty:
        acc = accepted.copy()
        acc["entry_ts"] = pd.to_datetime(acc["entry_ts"], utc=True)
        acc["day"] = acc["entry_ts"].dt.date
        accepted_daily = acc.groupby(["symbol", "day"]).size().rename("portfolio_accepted").reset_index()
        daily_df = daily_df.merge(accepted_daily, on=["symbol", "day"], how="left")
    else:
        daily_df["portfolio_accepted"] = 0
    daily_df["portfolio_accepted"] = daily_df["portfolio_accepted"].fillna(0).astype(int)
    daily_df["portfolio_throttled"] = (daily_df["pre_portfolio_pass"] - daily_df["portfolio_accepted"]).clip(lower=0)
    daily_df["primary_blocker"] = daily_df.apply(primary_daily_blocker, axis=1)
    return daily_df.sort_values(["symbol", "day"]).reset_index(drop=True), signal_df.sort_values(["symbol", "entry_ts"]).reset_index(drop=True)


def frequency_audit_symbol(symbol: str, cfg: SimpleSetupConfig, *, setup: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    bars = {
        "global": load_crypto(symbol, tf=cfg.global_tf, days=cfg.days, exchange=cfg.exchange, source=cfg.source).reset_index(drop=True),
        "local": load_crypto(symbol, tf=cfg.local_tf, days=cfg.days, exchange=cfg.exchange, source=cfg.source).reset_index(drop=True),
        "entry": load_crypto(symbol, tf=cfg.entry_tf, days=cfg.days, exchange=cfg.exchange, source=cfg.source).reset_index(drop=True),
    }
    stop_tf = cfg.stop_tf or cfg.entry_tf
    bars["stop"] = bars["entry"] if stop_tf == cfg.entry_tf else load_crypto(
        symbol, tf=stop_tf, days=cfg.days, exchange=cfg.exchange, source=cfg.source
    ).reset_index(drop=True)
    if any(df.empty for df in bars.values()):
        return pd.DataFrame(), pd.DataFrame()

    entry_bars = bars["entry"]
    entry_ts = pd.to_datetime(entry_bars["ts"], utc=True)
    combo = direction_context(
        bars["global"],
        bars["local"],
        entry_bars,
        mode=cfg.context_mode,
        structure_left=cfg.context_structure_left,
        structure_right=cfg.context_structure_right,
    )
    structure_cfg = StructureConfig(left=cfg.structure_left, right=cfg.structure_right)
    structure = build_structure_index(entry_bars, structure_cfg)
    stop_structure = structure if stop_tf == cfg.entry_tf else build_structure_index(bars["stop"], structure_cfg)
    signal_mask = setup_signal(entry_bars, combo, setup, structure=structure, entry_delay_bars=cfg.entry_delay_bars)
    signal_idx = np.where(signal_mask)[0]

    signal_rows = []
    for i in signal_idx:
        row = signal_diagnostic_row(symbol, cfg, setup, entry_bars, stop_structure, combo, int(i))
        if row:
            signal_rows.append(row)
    signals = pd.DataFrame(signal_rows)

    daily = pd.DataFrame({"day": entry_ts.dt.date})
    daily["symbol"] = symbol
    daily["active_context_bar"] = pd.Series(combo).isin(["bull", "bear"]).to_numpy()
    daily = daily.groupby(["symbol", "day"]).agg(
        bars=("day", "size"),
        active_context_bars=("active_context_bar", "sum"),
    ).reset_index()
    if signals.empty:
        for col in FREQUENCY_COUNT_COLS:
            daily[col] = 0
        return daily, signals

    counts = signals.groupby(["symbol", "day"]).agg(
        raw_signals=("stage_status", "size"),
        valid_stop=("valid_stop", "sum"),
        min_stop_pass=("min_stop_pass", "sum"),
        session_pass=("session_pass", "sum"),
        context_filter_pass=("context_filter_pass", "sum"),
        cost_pass=("cost_pass", "sum"),
        pre_portfolio_pass=("pre_portfolio_pass", "sum"),
    ).reset_index()
    by_fail = signals[signals["stage_status"] != "pass"].groupby(["symbol", "day", "stage_status"]).size().unstack(fill_value=0).reset_index()
    daily = daily.merge(counts, on=["symbol", "day"], how="left").merge(by_fail, on=["symbol", "day"], how="left")
    for col in FREQUENCY_COUNT_COLS:
        if col not in daily.columns:
            daily[col] = 0
        daily[col] = daily[col].fillna(0).astype(int)
    return daily, signals


FREQUENCY_COUNT_COLS = [
    "raw_signals",
    "valid_stop",
    "min_stop_pass",
    "session_pass",
    "context_filter_pass",
    "cost_pass",
    "pre_portfolio_pass",
    "invalid_stop",
    "stop_too_tight",
    "stop_too_wide",
    "no_outcome",
    "blocked_session",
    "blocked_context",
    "blocked_cost",
]


def signal_diagnostic_row(
    symbol: str,
    cfg: SimpleSetupConfig,
    setup: str,
    entry_bars: pd.DataFrame,
    structure: pd.DataFrame,
    combo: np.ndarray,
    i: int,
) -> dict:
    if i >= len(entry_bars) - 1:
        return {}
    entry_ts = pd.to_datetime(entry_bars["ts"].iat[i], utc=True)
    direction = "long" if combo[i] == "bull" else "short"
    entry = float(entry_bars["close"].iat[i])
    row = {
        "symbol": symbol,
        "setup": setup,
        "entry_ts": entry_ts,
        "day": entry_ts.date(),
        "direction": direction,
        "session_utc": session_bucket(entry_ts),
        "valid_stop": False,
        "min_stop_pass": False,
        "max_stop_pass": False,
        "session_pass": False,
        "context_filter_pass": False,
        "cost_pass": False,
        "pre_portfolio_pass": False,
        "stage_status": "invalid_stop",
    }
    stop_row = asof_structure_row(structure, entry_ts)
    if stop_row is None:
        return row
    sl, tp = structural_stop_target(stop_row, direction, entry, cfg.min_rr)
    if not np.isfinite(sl):
        return row
    risk = abs(entry - sl)
    if risk <= 0:
        return row
    row["valid_stop"] = True
    stop_pct = risk / entry * 100.0
    if stop_pct < cfg.min_stop_pct:
        row["stage_status"] = "stop_too_tight"
        return row
    row["min_stop_pass"] = True
    if cfg.max_stop_pct is not None and stop_pct > cfg.max_stop_pct:
        row["stage_status"] = "stop_too_wide"
        return row
    row["max_stop_pass"] = True
    outcome = walk_structural_outcome(entry_bars, i, direction, sl, tp, horizon=cfg.horizon_bars)
    if outcome is None:
        row["stage_status"] = "no_outcome"
        return row
    row["session_pass"] = cfg.sessions is None or row["session_utc"] in cfg.sessions
    if not row["session_pass"]:
        row["stage_status"] = "blocked_session"
        return row
    pa = price_action_snapshot(entry_bars, entry_ts=entry_ts, direction=direction)
    dmi = dmi_alignment(direction, pa.get("plus_di_14", np.nan), pa.get("minus_di_14", np.nan))
    context_pass = (
        (cfg.trend_strengths is None or pa.get("trend_strength", "unknown") in cfg.trend_strengths)
        and (cfg.consolidation_states is None or pa.get("consolidation_state", "unknown") in cfg.consolidation_states)
        and (cfg.shock_alignments is None or pa.get("shock_alignment", "no_shock") in cfg.shock_alignments)
        and (cfg.dmi_alignments is None or dmi in cfg.dmi_alignments)
    )
    row["context_filter_pass"] = bool(context_pass)
    if not context_pass:
        row["stage_status"] = "blocked_context"
        return row
    base_cost_r = cfg.base_round_trip_pct * entry / risk
    stress_cost_r = cfg.stress_round_trip_pct * entry / risk
    cost_pass = (
        (cfg.max_base_cost_r is None or base_cost_r <= cfg.max_base_cost_r)
        and (cfg.max_stress_cost_r is None or stress_cost_r <= cfg.max_stress_cost_r)
    )
    row["cost_pass"] = bool(cost_pass)
    if not cost_pass:
        row["stage_status"] = "blocked_cost"
        return row
    row["pre_portfolio_pass"] = True
    row["stage_status"] = "pass"
    return row


def primary_daily_blocker(row: pd.Series) -> str:
    if int(row.get("portfolio_accepted", 0)) > 0:
        return "traded"
    if int(row.get("pre_portfolio_pass", 0)) > 0:
        return "portfolio_throttle"
    if int(row.get("raw_signals", 0)) == 0:
        return "no_setup_signal" if int(row.get("active_context_bars", 0)) else "no_active_context"
    blockers = {
        "blocked_cost": int(row.get("blocked_cost", 0)),
        "blocked_context": int(row.get("blocked_context", 0)),
        "blocked_session": int(row.get("blocked_session", 0)),
        "stop_too_tight": int(row.get("stop_too_tight", 0)),
        "stop_too_wide": int(row.get("stop_too_wide", 0)),
        "invalid_stop": int(row.get("invalid_stop", 0)),
        "no_outcome": int(row.get("no_outcome", 0)),
    }
    return max(blockers, key=blockers.get) if max(blockers.values()) > 0 else "unknown"


def evaluate_symbol(symbol: str, cfg: SimpleSetupConfig, *, setup: str) -> pd.DataFrame:
    bars = {
        "global": load_crypto(symbol, tf=cfg.global_tf, days=cfg.days, exchange=cfg.exchange, source=cfg.source).reset_index(drop=True),
        "local": load_crypto(symbol, tf=cfg.local_tf, days=cfg.days, exchange=cfg.exchange, source=cfg.source).reset_index(drop=True),
        "entry": load_crypto(symbol, tf=cfg.entry_tf, days=cfg.days, exchange=cfg.exchange, source=cfg.source).reset_index(drop=True),
    }
    stop_tf = cfg.stop_tf or cfg.entry_tf
    bars["stop"] = bars["entry"] if stop_tf == cfg.entry_tf else load_crypto(
        symbol, tf=stop_tf, days=cfg.days, exchange=cfg.exchange, source=cfg.source
    ).reset_index(drop=True)
    if any(df.empty for df in bars.values()):
        return pd.DataFrame()

    entry_bars = bars["entry"]
    combo = direction_context(
        bars["global"],
        bars["local"],
        entry_bars,
        mode=cfg.context_mode,
        structure_left=cfg.context_structure_left,
        structure_right=cfg.context_structure_right,
    )
    dir_global = structure_ema_direction(
        bars["global"],
        left=cfg.context_structure_left,
        right=cfg.context_structure_right,
    )  # HTF direction for LTF monitoring gate
    structure_cfg = StructureConfig(left=cfg.structure_left, right=cfg.structure_right)
    structure = build_structure_index(entry_bars, structure_cfg)
    stop_structure = structure if stop_tf == cfg.entry_tf else build_structure_index(bars["stop"], structure_cfg)
    signal_mask = setup_signal(entry_bars, combo, setup, structure=structure, entry_delay_bars=cfg.entry_delay_bars)
    signal_idx = np.where(signal_mask)[0]

    # Precompute VWAP index and EMA slope for the entry timeframe
    vwap_df = build_vwap_index(entry_bars) if "volume" in entry_bars.columns else None
    entry_close = pd.to_numeric(entry_bars["close"], errors="coerce").to_numpy(dtype=float)
    ema21 = pd.Series(entry_close).ewm(span=21, adjust=False).mean().to_numpy(dtype=float)
    ema21_slope = np.full(len(entry_close), np.nan, dtype=float)
    ema21_slope[5:] = ema21[5:] - ema21[:-5]  # 5-bar slope
    atr_arr = atr(
        pd.to_numeric(entry_bars["high"], errors="coerce").to_numpy(dtype=float),
        pd.to_numeric(entry_bars["low"], errors="coerce").to_numpy(dtype=float),
        entry_close,
        period=14,
    )

    # Trend-day override: detect if price has been above VWAP for 6+ bars with rising highs
    # (suppresses mean-reversion shorts in strong uptrend)
    vwap_trend_override = np.full(len(entry_close), False, dtype=bool)
    if vwap_df is not None:
        vwap_vals = vwap_df["vwap"].to_numpy(dtype=float)
        high_arr = pd.to_numeric(entry_bars["high"], errors="coerce").to_numpy(dtype=float)
        for i in range(6, len(entry_close)):
            above_vwap = entry_close[i - 6:i] > vwap_vals[i - 6:i]
            rising_highs = all(high_arr[i - 5:i + 1] > high_arr[i - 6:i])  # 6-bar trend of higher highs
            if above_vwap.all() and rising_highs:
                vwap_trend_override[i] = True
    else:
        vwap_vals = np.full(len(entry_close), np.nan)

    rows = []
    for i in signal_idx:
        if i >= len(entry_bars) - 1:
            continue
        direction = "long" if combo[i] == "bull" else "short"
        entry = float(entry_bars["close"].iat[i])
        stop_row = asof_structure_row(stop_structure, pd.to_datetime(entry_bars["ts"].iat[i], utc=True))
        if stop_row is None:
            continue

        # Fibonacci retracement entry: limit order at % of last swing range
        if cfg.fib_entry_pct > 0:
            last_lo = float(stop_row.get("last_swing_low", np.nan))
            last_hi = float(stop_row.get("last_swing_high", np.nan))
            if not (np.isfinite(last_lo) and np.isfinite(last_hi) and last_hi > last_lo):
                continue
            sw_range = last_hi - last_lo
            if direction == "long":
                entry = last_lo + sw_range * cfg.fib_entry_pct
            else:
                entry = last_hi - sw_range * cfg.fib_entry_pct

        sl, tp = structural_stop_target(stop_row, direction, entry, cfg.min_rr)
        if not np.isfinite(sl):
            continue
        risk = abs(entry - sl)
        if risk <= 0:
            continue
        stop_pct = risk / entry * 100.0
        if stop_pct < cfg.min_stop_pct:
            continue

        # Entry mode: limit order at fib level or market at close
        if cfg.fib_entry_pct > 0:
            outcome = walk_limit_outcome(
                entry_bars, i, direction, entry, sl, tp,
                horizon=cfg.horizon_bars,
                track_excursion=True,
            )
        elif cfg.ltf_monitor_tf:
            # Load LTF bars for monitoring
            ltf_data = load_crypto(symbol, tf=cfg.ltf_monitor_tf, days=cfg.days, exchange=cfg.exchange, source=cfg.source)
            outcome = walk_structural_outcome_ltf(
                entry_bars, i, ltf_data,
                direction, sl, tp,
                partial_pct=cfg.partial_tp_pct,
                horizon_bars=cfg.horizon_bars,
                dir_global=dir_global,
            )
        else:
            outcome = walk_structural_outcome(
                entry_bars, i, direction, sl, tp,
                horizon=cfg.horizon_bars,
                track_excursion=True,
            )
        if outcome is None:
            continue
        if cfg.slippage_mode == "atr_scaled" and i < len(atr_arr) and np.isfinite(atr_arr[i]) and atr_arr[i] > 0:
            atr_pct = atr_arr[i] / entry
            # base_round_trip_pct = ATR multiplier (e.g., 0.05 = 5% ATR)
            base_slip_pct = cfg.base_round_trip_pct * atr_pct
            stress_slip_pct = cfg.stress_round_trip_pct * atr_pct
            base_cost_r = base_slip_pct * entry / risk
            stress_cost_r = stress_slip_pct * entry / risk
        else:
            base_cost_r = cfg.base_round_trip_pct * entry / risk
            stress_cost_r = cfg.stress_round_trip_pct * entry / risk
        gross_r = float(outcome["r_multiple"])
        pa = price_action_snapshot(entry_bars, entry_ts=pd.to_datetime(entry_bars["ts"].iat[i], utc=True), direction=direction)

        # VWAP state
        vwap_val = vwap_vals[i] if vwap_df is not None else np.nan
        vwap_align = vwap_alignment(direction, entry, vwap_val, atr_val=atr_arr[i] if i < len(atr_arr) else None)
        trend_overridden = bool(vwap_trend_override[i]) and direction == "short"

        # EMA slope state
        ema_sl = ema21_slope[i] if i < len(ema21_slope) else np.nan
        ema_align = ema_slope_alignment(direction, ema_sl)

        rows.append(
            {
                "symbol": symbol,
                "setup": setup,
                "stop_tf": stop_tf,
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
                "plus_di_14": pa.get("plus_di_14", np.nan),
                "minus_di_14": pa.get("minus_di_14", np.nan),
                "dmi_alignment": dmi_alignment(direction, pa.get("plus_di_14", np.nan), pa.get("minus_di_14", np.nan)),
                "vwap_alignment": vwap_align,
                "ema_alignment": ema_align,
                "vwap_trend_overridden": trend_overridden,
                "vwap_price": vwap_val,
                "ema21_price": ema21[i] if i < len(ema21) else np.nan,
                "ema21_slope": ema_sl,
            }
        )
    return pd.DataFrame(rows)


def direction_context(
    global_bars: pd.DataFrame,
    local_bars: pd.DataFrame,
    entry_bars: pd.DataFrame,
    *,
    mode: str = "strict",
    structure_left: int = 2,
    structure_right: int = 2,
) -> np.ndarray:
    if mode not in {"strict", "htf_only"}:
        raise ValueError(f"unknown context mode: {mode}")
    dir_global = structure_ema_direction(global_bars, left=structure_left, right=structure_right)
    dir_local = structure_ema_direction(local_bars, left=structure_left, right=structure_right)
    g = asof_direction(entry_bars["ts"], dir_global)
    l = asof_direction(entry_bars["ts"], dir_local)
    if mode == "htf_only":
        return np.where((g == l) & (g != "neutral"), g, "neutral")
    entry_state = vec_ema_state(entry_bars).map({"bullish": "bull", "bearish": "bear"}).fillna("neutral").to_numpy()
    return np.where((g == l) & (l == entry_state) & (g != "neutral"), g, "neutral")


def setup_signal(
    entry_bars: pd.DataFrame,
    combo: np.ndarray,
    setup: str,
    *,
    structure: pd.DataFrame | None = None,
    entry_delay_bars: int = 0,
) -> np.ndarray:
    if setup not in {
        "pullback_reclaim",
        "context_change",
        "daily_first_context",
        "micro_reclaim_context",
        "continuation_reclaim",
        "structure_confirmed_context",
        "choch_bos_context",
    }:
        raise ValueError(f"unknown setup: {setup}")
    combo_s = pd.Series(combo)
    active = combo_s.isin(["bull", "bear"])
    if setup == "context_change":
        return delayed_context_signal(combo_s, delay_bars=entry_delay_bars).to_numpy()
    if setup == "daily_first_context":
        return daily_first_context_signal(entry_bars, combo_s).to_numpy()
    if setup == "micro_reclaim_context":
        if structure is None or structure.empty:
            return np.zeros(len(combo_s), dtype=bool)
        return micro_reclaim_context_signal(entry_bars, combo_s, structure).to_numpy()
    if setup == "continuation_reclaim":
        if structure is None or structure.empty:
            return np.zeros(len(combo_s), dtype=bool)
        return continuation_reclaim_signal(entry_bars, combo_s, structure).to_numpy()
    if setup == "structure_confirmed_context":
        if structure is None or structure.empty:
            return np.zeros(len(combo_s), dtype=bool)
        return structure_confirmed_context_signal(combo_s, structure)
    if setup == "choch_bos_context":
        if structure is None or structure.empty:
            return np.zeros(len(combo_s), dtype=bool)
        return choch_bos_context_signal(combo_s, structure, entry_bars=entry_bars)

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


def delayed_context_signal(combo_s: pd.Series, *, delay_bars: int = 0) -> pd.Series:
    """Signal after a fresh MTF context change has held for `delay_bars` bars."""
    if delay_bars < 0:
        raise ValueError("delay_bars must be >= 0")
    active = combo_s.isin(["bull", "bear"])
    context_change = combo_s.ne(combo_s.shift(1)) & active
    if delay_bars == 0:
        return context_change
    bars_since_context = _bars_since(context_change)
    return active & bars_since_context.eq(delay_bars) & combo_s.eq(combo_s.shift(delay_bars))


def daily_first_context_signal(entry_bars: pd.DataFrame, combo_s: pd.Series) -> pd.Series:
    """Signal on the first active context bar of each UTC day."""
    active = combo_s.isin(["bull", "bear"])
    days = pd.to_datetime(entry_bars["ts"], utc=True).dt.date
    active_seen = active.groupby(days).cummax()
    first_active = active & ~active_seen.shift(1, fill_value=False)
    previous_day = pd.Series(days).ne(pd.Series(days).shift(1))
    return first_active | (active & previous_day)


def micro_reclaim_context_signal(
    entry_bars: pd.DataFrame,
    combo_s: pd.Series,
    structure: pd.DataFrame,
    *,
    confirm_lookback: int = 20,
) -> pd.Series:
    """1m/5m reclaim confirmation inside an already-active higher-timeframe context."""
    close = pd.to_numeric(entry_bars["close"], errors="coerce")
    low = pd.to_numeric(entry_bars["low"], errors="coerce")
    high = pd.to_numeric(entry_bars["high"], errors="coerce")
    ema21 = close.ewm(span=21, adjust=False).mean()
    ema55 = close.ewm(span=55, adjust=False).mean()

    bull_reclaim = (combo_s == "bull") & (low.shift(1) <= ema21.shift(1)) & (close > ema21) & (ema21 >= ema55)
    bear_reclaim = (combo_s == "bear") & (high.shift(1) >= ema21.shift(1)) & (close < ema21) & (ema21 <= ema55)

    bull_structure = _rolling_recent_bool(structure["bos_up"].astype(bool) | structure["choch_up"].astype(bool), confirm_lookback)
    bear_structure = _rolling_recent_bool(structure["bos_down"].astype(bool) | structure["choch_down"].astype(bool), confirm_lookback)
    recent_bear_choch = _rolling_recent_bool(structure["choch_down"].astype(bool), confirm_lookback)
    recent_bull_choch = _rolling_recent_bool(structure["choch_up"].astype(bool), confirm_lookback)

    signal = (bull_reclaim & bull_structure & ~recent_bear_choch) | (bear_reclaim & bear_structure & ~recent_bull_choch)
    return signal & ~signal.shift(1, fill_value=False)


def continuation_reclaim_signal(
    entry_bars: pd.DataFrame,
    combo_s: pd.Series,
    structure: pd.DataFrame,
    *,
    confirm_lookback: int = 12,
    pullback_lookback: int = 6,
    min_context_bars: int = 2,
) -> pd.Series:
    """Continuation setup after context is already active, not on the first context-change bar."""
    close = pd.to_numeric(entry_bars["close"], errors="coerce")
    low = pd.to_numeric(entry_bars["low"], errors="coerce")
    high = pd.to_numeric(entry_bars["high"], errors="coerce")
    ema21 = close.ewm(span=21, adjust=False).mean()
    ema55 = close.ewm(span=55, adjust=False).mean()
    bars_since_context = _bars_since(combo_s.ne(combo_s.shift(1)) & combo_s.isin(["bull", "bear"]))
    mature_context = bars_since_context.ge(min_context_bars)

    bull_pullback = low.rolling(pullback_lookback, min_periods=1).min().shift(1) <= ema21.shift(1)
    bear_pullback = high.rolling(pullback_lookback, min_periods=1).max().shift(1) >= ema21.shift(1)
    bull_reclaim = (combo_s == "bull") & mature_context & bull_pullback & (close > ema21) & (ema21 >= ema55)
    bear_reclaim = (combo_s == "bear") & mature_context & bear_pullback & (close < ema21) & (ema21 <= ema55)

    regime = structure["regime"].astype(str).reset_index(drop=True)
    recent_bull_bos = _rolling_recent_bool(structure["bos_up"].astype(bool), confirm_lookback)
    recent_bear_bos = _rolling_recent_bool(structure["bos_down"].astype(bool), confirm_lookback)
    recent_bear_choch = _rolling_recent_bool(structure["choch_down"].astype(bool), confirm_lookback)
    recent_bull_choch = _rolling_recent_bool(structure["choch_up"].astype(bool), confirm_lookback)

    long_signal = bull_reclaim & regime.eq("bull") & recent_bull_bos & ~recent_bear_choch
    short_signal = bear_reclaim & regime.eq("bear") & recent_bear_bos & ~recent_bull_choch
    signal = long_signal | short_signal
    return signal & ~signal.shift(1, fill_value=False)


def structure_confirmed_context_signal(
    combo_s: pd.Series,
    structure: pd.DataFrame,
    *,
    context_lookback: int = 12,
    confirm_lookback: int = 8,
) -> np.ndarray:
    """Enter only after active MTF direction gets same-direction 15m structure confirmation."""
    active = combo_s.isin(["bull", "bear"])
    context_change = combo_s.ne(combo_s.shift(1)) & active
    bars_since_context = _bars_since(context_change)

    regime = structure["regime"].astype(str).reset_index(drop=True)
    bull_bos_recent = _rolling_recent_bool(structure["bos_up"].astype(bool), confirm_lookback)
    bear_bos_recent = _rolling_recent_bool(structure["bos_down"].astype(bool), confirm_lookback)
    bull_choch_recent = _rolling_recent_bool(structure["choch_up"].astype(bool), confirm_lookback)
    bear_choch_recent = _rolling_recent_bool(structure["choch_down"].astype(bool), confirm_lookback)

    valid_window = bars_since_context.between(1, context_lookback)
    long_confirm = (
        (combo_s == "bull")
        & valid_window
        & regime.eq("bull")
        & bull_bos_recent
        & ~bear_choch_recent
    )
    short_confirm = (
        (combo_s == "bear")
        & valid_window
        & regime.eq("bear")
        & bear_bos_recent
        & ~bull_choch_recent
    )
    signal = long_confirm | short_confirm
    return (signal & ~signal.shift(1, fill_value=False)).to_numpy()


def choch_bos_context_signal(
    combo_s: pd.Series,
    structure: pd.DataFrame,
    *,
    entry_bars: pd.DataFrame | None = None,
    choch_lookback: int = 12,
    bos_lookback: int = 8,
    min_context_bars: int = 1,
    max_context_bars: int = 48,
    gap_atr_mult: float = 0.0,
) -> np.ndarray:
    """Enter after a CHoCH AND a BOS in the new direction, in that order.

    Requirements:
      1. MTF direction context is active (bull/bear).
      2. A CHoCH in the new direction fired within `choch_lookback` bars.
      3. A BOS in the new direction fired within `bos_lookback` bars.
      4. The CHoCH bar index < BOS bar index (right order: reversal warning
         first, then trend continuation).
      5. No opposing CHoCH within the lookback.
      6. Context has been active for at least `min_context_bars` (optional).
      7. If gap_atr_mult > 0 and entry_bars provided: skip entry for
         `gap_cooldown_bars` after a candle > gap_atr_mult × ATR.

    This is a stronger confirmation than just BOS alone — it requires
    the market to first show a character change (CHoCH) and then confirm
    with a break of structure (BOS), which filters out many false starts.
    """
    active = combo_s.isin(["bull", "bear"])
    context_change = combo_s.ne(combo_s.shift(1)) & active
    bars_since_context = _bars_since(context_change)

    regime = structure["regime"].astype(str).reset_index(drop=True)

    # CHoCH and BOS detection in the lookback window
    bull_choch = _rolling_recent_bool(structure["choch_up"].astype(bool), choch_lookback)
    bear_choch = _rolling_recent_bool(structure["choch_down"].astype(bool), choch_lookback)
    bull_bos = _rolling_recent_bool(structure["bos_up"].astype(bool), bos_lookback)
    bear_bos = _rolling_recent_bool(structure["bos_down"].astype(bool), bos_lookback)

    # Opposing CHoCH would invalidate
    bear_choch_recent = _rolling_recent_bool(structure["choch_down"].astype(bool), choch_lookback)
    bull_choch_recent = _rolling_recent_bool(structure["choch_up"].astype(bool), choch_lookback)

    # Verify CHoCH happened before BOS (correct order).
    # Track the most recent CHoCH and BOS bar indices at each position.
    n = len(combo_s)
    st_n = len(structure)
    # Build arrays tracking "how many bars ago was the last event" at each bar
    bull_choch_ago = np.full(n, np.nan)
    bull_bos_ago = np.full(n, np.nan)
    bear_choch_ago = np.full(n, np.nan)
    bear_bos_ago = np.full(n, np.nan)

    last_bull_choch = -999
    last_bull_bos = -999
    last_bear_choch = -999
    last_bear_bos = -999

    for i in range(min(n, st_n)):
        if i < len(structure):
            if bool(structure["choch_up"].iat[i]):
                last_bull_choch = i
            if bool(structure["bos_up"].iat[i]):
                last_bull_bos = i
            if bool(structure["choch_down"].iat[i]):
                last_bear_choch = i
            if bool(structure["bos_down"].iat[i]):
                last_bear_bos = i
        bull_choch_ago[i] = i - last_bull_choch if last_bull_choch >= 0 else np.nan
        bull_bos_ago[i] = i - last_bull_bos if last_bull_bos >= 0 else np.nan
        bear_choch_ago[i] = i - last_bear_choch if last_bear_choch >= 0 else np.nan
        bear_bos_ago[i] = i - last_bear_bos if last_bear_bos >= 0 else np.nan

    # CHoCH before BOS check: choch_ago > bos_ago means the CHoCH happened
    # LONGER ago than the BOS, i.e., CHoCH came first (reversal warning),
    # then BOS followed (trend continuation). Correct order is CHoCH→BOS.
    bull_order_ok = (~np.isnan(bull_choch_ago)) & (~np.isnan(bull_bos_ago)) & (bull_choch_ago > bull_bos_ago)
    bear_order_ok = (~np.isnan(bear_choch_ago)) & (~np.isnan(bear_bos_ago)) & (bear_choch_ago > bear_bos_ago)

    # Gap protection: skip entry after abnormally large candles
    gap_filter = pd.Series(True, index=range(n))
    if gap_atr_mult > 0 and entry_bars is not None:
        high = pd.to_numeric(entry_bars["high"], errors="coerce")
        low = pd.to_numeric(entry_bars["low"], errors="coerce")
        candle_range = high - low
        atr = candle_range.rolling(14, min_periods=14).mean()
        large_candle = candle_range > gap_atr_mult * atr
        gap_cooldown = 0
        for i in range(n):
            if gap_cooldown > 0:
                gap_filter.iat[i] = False
                gap_cooldown -= 1
            if large_candle.iat[i] if i < len(large_candle) else False:
                # Large candle detected — cool down for 3 bars
                gap_cooldown = 3
                gap_filter.iat[i] = False if gap_cooldown > 0 else True

    # Combine all conditions
    valid_window = bars_since_context.between(min_context_bars, max_context_bars)
    long_signal = (
        (combo_s == "bull")
        & valid_window
        & bull_choch
        & bull_bos
        & bull_order_ok
        & ~bear_choch_recent
        & regime.eq("bull")
        & gap_filter
    )
    short_signal = (
        (combo_s == "bear")
        & valid_window
        & bear_choch
        & bear_bos
        & bear_order_ok
        & ~bull_choch_recent
        & regime.eq("bear")
        & gap_filter
    )
    signal = long_signal | short_signal
    return (signal & ~signal.shift(1, fill_value=False)).to_numpy()


def _bars_since(events: pd.Series) -> pd.Series:
    count = pd.Series(np.arange(len(events)), index=events.index)
    last = count.where(events).ffill()
    return count - last


def _rolling_recent_bool(values: pd.Series, lookback: int) -> pd.Series:
    return values.astype(int).rolling(lookback, min_periods=1).max().astype(bool)


def asof_structure_row(structure: pd.DataFrame, entry_ts: pd.Timestamp) -> pd.Series | None:
    if structure.empty:
        return None
    lookup_col = "known_after_ts" if "known_after_ts" in structure.columns else "ts"
    if lookup_col not in structure.columns:
        return None
    ts_ns = pd.to_datetime(structure[lookup_col], utc=True).to_numpy(dtype="datetime64[ns]").astype("int64")
    entry = pd.Timestamp(entry_ts)
    entry_ns = entry.tz_convert("UTC").value if entry.tzinfo else entry.tz_localize("UTC").value
    idx = ts_ns.searchsorted(entry_ns, side="right") - 1
    if idx < 0:
        return None
    return structure.iloc[int(idx)]


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
    if cfg.max_stop_pct is not None:
        out = out[out["stop_pct"] <= cfg.max_stop_pct]
    if cfg.sessions:
        out = out[out["session_utc"].isin(cfg.sessions)]
    if cfg.trend_strengths:
        out = out[out["trend_strength"].isin(cfg.trend_strengths)]
    if cfg.consolidation_states:
        out = out[out["consolidation_state"].isin(cfg.consolidation_states)]
    if cfg.shock_alignments:
        out = out[out["shock_alignment"].isin(cfg.shock_alignments)]
    if cfg.dmi_alignments:
        out = out[out["dmi_alignment"].isin(cfg.dmi_alignments)]
    if cfg.vwap_alignments:
        out = out[out["vwap_alignment"].isin(cfg.vwap_alignments)]
    if cfg.ema_alignments:
        out = out[out["ema_alignment"].isin(cfg.ema_alignments)]
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
        "top_dmi_alignment": mode_or_empty(group.get("dmi_alignment")),
        "top_vwap_alignment": mode_or_empty(group.get("vwap_alignment")),
        "top_ema_alignment": mode_or_empty(group.get("ema_alignment")),
    }


def mode_or_empty(values: pd.Series | None) -> str:
    if values is None or values.empty:
        return ""
    mode = values.astype(str).mode(dropna=True)
    return "" if mode.empty else str(mode.iat[0])


def dmi_alignment(direction: str, plus_di: float, minus_di: float) -> str:
    if not np.isfinite(plus_di) or not np.isfinite(minus_di):
        return "unknown"
    if plus_di == minus_di:
        return "flat"
    bullish = plus_di > minus_di
    if direction == "long":
        return "aligned" if bullish else "opposed"
    if direction == "short":
        return "aligned" if not bullish else "opposed"
    return "unknown"


def vwap_alignment(direction: str, entry: float, vwap_val: float, atr_val: float | None = None) -> str:
    """Classify VWAP alignment relative to trade direction.
    aligned  = long above VWAP or short below VWAP
    opposed  = long below VWAP or short above VWAP
    flat     = price within 0.5 ATR of VWAP (neutral zone)
    """
    if not np.isfinite(vwap_val) or not np.isfinite(entry):
        return "unknown"
    dist = entry - vwap_val
    if atr_val is not None and np.isfinite(atr_val) and atr_val > 0:
        dist_atr = abs(dist) / atr_val
        if dist_atr < 0.5:
            return "flat"
    if (direction == "long" and dist > 0) or (direction == "short" and dist < 0):
        return "aligned"
    return "opposed"


def ema_slope_alignment(direction: str, ema_slope: float) -> str:
    """Classify EMA21 slope alignment relative to trade direction.
    aligned  = long & rising EMA, or short & falling EMA
    opposed  = long & falling EMA, or short & rising EMA
    flat     = slope near zero
    """
    if not np.isfinite(ema_slope):
        return "unknown"
    if abs(ema_slope) < 0.001:  # near-zero slope
        return "flat"
    rising = ema_slope > 0
    if (direction == "long" and rising) or (direction == "short" and not rising):
        return "aligned"
    return "opposed"


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
    worst_base = float(windows["base_return_r"].min())
    worst_stress = float(windows["stress_return_r"].min())
    base_returns = windows["base_return_r"].to_numpy(dtype=float)
    stress_returns = windows["stress_return_r"].to_numpy(dtype=float)
    base_sharpe = _sharpe_ratio(base_returns) if len(base_returns) > 1 else np.nan
    stress_sharpe = _sharpe_ratio(stress_returns) if len(stress_returns) > 1 else np.nan
    return pd.DataFrame(
        [
            {
                "windows": len(windows),
                "median_trades": float(windows["trades"].median()),
                "positive_base_windows": float((windows["base_return_r"] > 0).mean()),
                "positive_stress_windows": float((windows["stress_return_r"] > 0).mean()),
                "median_base_pf": float(windows["base_pf"].replace([np.inf, -np.inf], np.nan).median()),
                "worst_base_return_r": worst_base,
                "worst_base_dd_pct": worst_base,  # R-based proxy for DD in window
                "median_stress_pf": float(windows["stress_pf"].replace([np.inf, -np.inf], np.nan).median()),
                "worst_stress_return_r": worst_stress,
                "worst_stress_dd_pct": worst_stress,
                "base_sharpe": base_sharpe,
                "stress_sharpe": stress_sharpe,
            }
        ]
    )


def _sharpe_ratio(returns: np.ndarray, risk_free: float = 0.0) -> float:
    """Annualized Sharpe from period returns (assumes ~96 15m bars per day)."""
    if len(returns) < 2 or np.std(returns) == 0:
        return np.nan
    periods_per_year = 365 * 24 * 60 / 15  # ~35040 for 15m bars
    mean_excess = np.mean(returns) - risk_free
    return float(mean_excess / np.std(returns) * np.sqrt(periods_per_year / len(returns)))


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
            "dmi_alignment": data.get("dmi_alignment", ""),
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


def build_candidate_feature_table(trades: pd.DataFrame, *, output_path: Path) -> pd.DataFrame:
    """Export setup candidates as supervised rows for later candle/price-action ranking."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if trades.empty:
        table = pd.DataFrame()
        table.to_csv(output_path, index=False)
        return table

    data = trades.copy()
    data["entry_ts"] = pd.to_datetime(data["entry_ts"], utc=True)
    stress = data["stress_net_r"].astype(float)
    table = pd.DataFrame(
        {
            "entry_ts": data["entry_ts"],
            "symbol": data["symbol"].astype(str),
            "setup": data["setup"].astype(str),
            "direction": data["direction"].astype(str),
            "session_utc": data["session_utc"].astype(str),
            "hour_utc": data["entry_ts"].dt.hour.astype(int),
            "day_of_week": data["entry_ts"].dt.dayofweek.astype(int),
            "stop_pct": data["stop_pct"].astype(float),
            "target_pct": data["target_pct"].astype(float),
            "planned_rr": data["planned_rr"].astype(float),
            "base_cost_r": data["base_cost_r"].astype(float),
            "stress_cost_r": data["stress_cost_r"].astype(float),
            "mfe_r": data["mfe_r"].astype(float),
            "mae_r": data["mae_r"].astype(float),
            "bars_to_exit": data["bars_to_exit"].astype(int),
            "trend_strength": data.get("trend_strength", "").astype(str),
            "consolidation_state": data.get("consolidation_state", "").astype(str),
            "shock_alignment": data.get("shock_alignment", "").astype(str),
            "compression_state": data.get("compression_state", "").astype(str),
            "dmi_alignment": data.get("dmi_alignment", "").astype(str),
            "adx_14": data.get("adx_14", np.nan).astype(float),
            "pre_range_atr_16": data.get("pre_range_atr_16", np.nan).astype(float),
            "plus_di_14": data.get("plus_di_14", np.nan).astype(float),
            "minus_di_14": data.get("minus_di_14", np.nan).astype(float),
            "label_target": data["exit_kind"].astype(str).eq("target"),
            "label_stop": data["exit_kind"].astype(str).eq("stop"),
            "label_expiry": data["exit_kind"].astype(str).eq("expiry"),
            "label_positive_stress_r": stress > 0,
            "label_mfe_ge_1r": data["mfe_r"].astype(float) >= 1.0,
            "label_mfe_ge_2r": data["mfe_r"].astype(float) >= 2.0,
            "outcome_stress_net_r": stress,
        }
    )
    table = table.sort_values(["symbol", "entry_ts"]).reset_index(drop=True)
    table.to_csv(output_path, index=False)
    return table


def build_candidate_filter_diagnostics(features: pd.DataFrame, *, min_count: int = 10) -> dict[str, pd.DataFrame]:
    """Rank candidate feature buckets before promoting any filter or ML model."""
    if features.empty:
        empty = pd.DataFrame()
        return {"overview": empty, "single_feature": empty, "pair_feature": empty, "good_buckets": empty, "bad_buckets": empty}

    data = features.copy()
    data["outcome_stress_net_r"] = pd.to_numeric(data["outcome_stress_net_r"], errors="coerce")
    data["stop_pct"] = pd.to_numeric(data.get("stop_pct"), errors="coerce")
    data["adx_14"] = pd.to_numeric(data.get("adx_14"), errors="coerce")
    data["pre_range_atr_16"] = pd.to_numeric(data.get("pre_range_atr_16"), errors="coerce")
    data["hour_bucket"] = pd.cut(
        pd.to_numeric(data.get("hour_utc"), errors="coerce"),
        bins=[-1, 6, 11, 16, 23],
        labels=["asia", "london", "ny", "late_us"],
    ).astype(str)
    data["stop_pct_bucket"] = pd.cut(
        data["stop_pct"],
        bins=[-np.inf, 0.75, 1.25, 2.0, 5.0, np.inf],
        labels=["<=0.75", "0.75-1.25", "1.25-2", "2-5", ">5"],
    ).astype(str)
    data["adx_bucket"] = pd.cut(
        data["adx_14"],
        bins=[-np.inf, 15, 25, 35, np.inf],
        labels=["<=15", "15-25", "25-35", ">35"],
    ).astype(str)
    data["pre_range_bucket"] = pd.cut(
        data["pre_range_atr_16"],
        bins=[-np.inf, 1.0, 2.0, 4.0, np.inf],
        labels=["<=1atr", "1-2atr", "2-4atr", ">4atr"],
    ).astype(str)
    if "day_of_week" in data.columns:
        data["day_of_week"] = data["day_of_week"].astype(str)

    overview = _feature_bucket_summary(data, ["setup"], min_count=1)
    single_cols = [
        "symbol",
        "direction",
        "session_utc",
        "hour_bucket",
        "day_of_week",
        "trend_strength",
        "consolidation_state",
        "compression_state",
        "dmi_alignment",
        "stop_pct_bucket",
        "adx_bucket",
        "pre_range_bucket",
    ]
    pair_cols = [
        ("symbol", "dmi_alignment"),
        ("symbol", "session_utc"),
        ("symbol", "trend_strength"),
        ("trend_strength", "dmi_alignment"),
        ("consolidation_state", "dmi_alignment"),
        ("stop_pct_bucket", "dmi_alignment"),
        ("adx_bucket", "dmi_alignment"),
    ]
    single = pd.concat(
        [_feature_bucket_summary(data, [col], min_count=min_count).assign(feature=col) for col in single_cols if col in data.columns],
        ignore_index=True,
    )
    pairs = pd.concat(
        [_feature_bucket_summary(data, list(cols), min_count=min_count).assign(feature="+".join(cols)) for cols in pair_cols],
        ignore_index=True,
    )
    baseline_avg = float(data["outcome_stress_net_r"].mean())
    good = pd.concat([single, pairs], ignore_index=True)
    if not good.empty:
        good = good[
            (good["trades"] >= min_count)
            & (good["stress_avg_r"] > baseline_avg)
            & (good["stress_pf"] >= 1.5)
            & (good["positive_rate"] >= 0.50)
        ].sort_values(["stress_pf", "stress_avg_r", "trades"], ascending=[False, False, False])
    bad = pd.concat([single, pairs], ignore_index=True)
    if not bad.empty:
        bad = bad[
            (bad["trades"] >= min_count)
            & ((bad["stress_pf"] < 1.0) | (bad["stop_rate"] >= 0.60))
        ].sort_values(["stress_pf", "stress_avg_r", "trades"], ascending=[True, True, False])
    return {
        "overview": overview,
        "single_feature": single.sort_values(["feature", "stress_pf", "trades"], ascending=[True, False, False]).reset_index(drop=True),
        "pair_feature": pairs.sort_values(["feature", "stress_pf", "trades"], ascending=[True, False, False]).reset_index(drop=True),
        "good_buckets": good.reset_index(drop=True),
        "bad_buckets": bad.reset_index(drop=True),
    }


def _feature_bucket_summary(data: pd.DataFrame, group_cols: list[str], *, min_count: int) -> pd.DataFrame:
    rows = []
    for keys, group in data.dropna(subset=group_cols).groupby(group_cols, dropna=False, sort=True):
        if len(group) < min_count:
            continue
        key_values = keys if isinstance(keys, tuple) else (keys,)
        r = group["outcome_stress_net_r"].to_numpy(dtype=float)
        rows.append(
            {
                "bucket": " | ".join(f"{col}={value}" for col, value in zip(group_cols, key_values)),
                "trades": len(group),
                "stress_avg_r": float(np.mean(r)),
                "stress_sum_r": float(np.sum(r)),
                "stress_pf": profit_factor(r),
                "positive_rate": float((r > 0).mean()),
                "target_rate": float(group["label_target"].astype(bool).mean()) if "label_target" in group else np.nan,
                "stop_rate": float(group["label_stop"].astype(bool).mean()) if "label_stop" in group else np.nan,
                "expiry_rate": float(group["label_expiry"].astype(bool).mean()) if "label_expiry" in group else np.nan,
                "mfe_2r_rate": float(group["label_mfe_ge_2r"].astype(bool).mean()) if "label_mfe_ge_2r" in group else np.nan,
                "median_stop_pct": float(group["stop_pct"].median()) if "stop_pct" in group else np.nan,
                "median_adx_14": float(group["adx_14"].median()) if "adx_14" in group else np.nan,
            }
        )
    return pd.DataFrame(rows)


def write_candidate_filter_report(features: pd.DataFrame, output: Path, *, min_count: int = 10) -> dict[str, pd.DataFrame]:
    diagnostics = build_candidate_filter_diagnostics(features, min_count=min_count)
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Candidate Filter Diagnostics",
        "",
        "Scope: rank candidate-event features before adding filters or ML. This is evidence gathering, not promotion.",
        "",
        f"Minimum bucket size: `{min_count}` trades.",
        "",
        "## Overview",
        "",
        dataframe_to_markdown(diagnostics["overview"]) if not diagnostics["overview"].empty else "No rows.",
        "",
        "## Strong Buckets",
        "",
        dataframe_to_markdown(diagnostics["good_buckets"].head(30)) if not diagnostics["good_buckets"].empty else "No rows.",
        "",
        "## Weak Buckets",
        "",
        dataframe_to_markdown(diagnostics["bad_buckets"].head(30)) if not diagnostics["bad_buckets"].empty else "No rows.",
        "",
        "## Best Single-Feature Buckets",
        "",
        dataframe_to_markdown(
            diagnostics["single_feature"].sort_values(["stress_pf", "stress_avg_r", "trades"], ascending=[False, False, False]).head(40)
        ) if not diagnostics["single_feature"].empty else "No rows.",
        "",
        "## Best Pair Buckets",
        "",
        dataframe_to_markdown(
            diagnostics["pair_feature"].sort_values(["stress_pf", "stress_avg_r", "trades"], ascending=[False, False, False]).head(40)
        ) if not diagnostics["pair_feature"].empty else "No rows.",
        "",
        "## Read",
        "",
        "- Promote nothing from this report directly.",
        "- A bucket is only useful if it has enough trades and remains stable across 30/60/90/180 day windows.",
        "- Use this to choose the next explicit filter test or to define supervised model features.",
    ]
    output.write_text("\n".join(lines) + "\n")
    return diagnostics


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


def write_report(
    summary: pd.DataFrame,
    trades: pd.DataFrame,
    output: Path,
    windows: pd.DataFrame | None = None,
    windows_60d: pd.DataFrame | None = None,
    windows_90d: pd.DataFrame | None = None,
) -> None:
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
        context = trades.groupby(["trend_strength", "consolidation_state", "shock_alignment", "dmi_alignment", "vwap_alignment", "ema_alignment"]).agg(
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
                "### 30-day windows",
                "",
                dataframe_to_markdown(summarize_windows(windows)),
            ]
        )
        if not windows_60d.empty:
            lines.extend(
                [
                    "",
                    "### 60-day windows",
                    "",
                    dataframe_to_markdown(summarize_windows(windows_60d)),
                ]
            )
        if not windows_90d.empty:
            lines.extend(
                [
                    "",
                    "### 90-day windows",
                    "",
                    dataframe_to_markdown(summarize_windows(windows_90d)),
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


def write_frequency_report(daily: pd.DataFrame, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Simple Crypto Setup Frequency Audit",
        "",
        "Scope: day-level explanation of why the setup did or did not produce accepted trades.",
        "",
        "## Summary",
        "",
    ]
    if daily.empty:
        lines.append("No rows.")
    else:
        summary = daily.groupby("primary_blocker").agg(
            symbol_days=("day", "size"),
            active_context_bars=("active_context_bars", "sum"),
            raw_signals=("raw_signals", "sum"),
            pre_portfolio_pass=("pre_portfolio_pass", "sum"),
            portfolio_accepted=("portfolio_accepted", "sum"),
        ).reset_index().sort_values("symbol_days", ascending=False)
        lines.append(dataframe_to_markdown(summary))
        lines.extend(["", "## Symbol Split", ""])
        by_symbol = daily.groupby(["symbol", "primary_blocker"]).agg(
            days=("day", "size"),
            raw_signals=("raw_signals", "sum"),
            pre_portfolio_pass=("pre_portfolio_pass", "sum"),
            portfolio_accepted=("portfolio_accepted", "sum"),
        ).reset_index().sort_values(["symbol", "days"], ascending=[True, False])
        lines.append(dataframe_to_markdown(by_symbol))
        lines.extend(["", "## Read", ""])
        lines.extend(
            [
                "- `no_active_context`: 240m/30m/15m direction stack did not align that day.",
                "- `no_setup_signal`: direction context existed, but the setup trigger did not fire.",
                "- `blocked_context`: context filters such as no-shock/DMI/consolidation blocked signals.",
                "- `blocked_cost`: stop geometry was tradable but too expensive in R after cost gates.",
                "- `portfolio_throttle`: signal passed setup gates but was skipped by portfolio risk rules.",
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
    rows = [[str(v).replace("|", "\\|") for v in row] for row in formatted.to_numpy()]
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
    parser.add_argument(
        "--setup",
        default="pullback_reclaim",
        choices=[
            "pullback_reclaim",
            "context_change",
            "daily_first_context",
            "micro_reclaim_context",
            "continuation_reclaim",
            "structure_confirmed_context",
            "choch_bos_context",
        ],
    )
    parser.add_argument("--days", type=int, default=400)
    parser.add_argument("--entry-tf", default="15", help="Entry/confirmation timeframe.")
    parser.add_argument("--stop-tf", default="", help="Optional structure timeframe for SL/TP. Defaults to entry tf.")
    parser.add_argument("--min-rr", type=float, default=1.5)
    parser.add_argument("--horizon-bars", type=int, default=96)
    parser.add_argument("--context-mode", default="strict", choices=["strict", "htf_only"], help="strict=240/30/15 agree; htf_only=240/30 agree.")
    parser.add_argument("--max-base-cost-r", type=float, default=None)
    parser.add_argument("--max-stress-cost-r", type=float, default=None)
    parser.add_argument("--max-stop-pct", type=float, default=None)
    parser.add_argument("--sessions", default="", help="Comma-separated UTC session buckets: asia,london,ny,late_us")
    parser.add_argument("--trend-strengths", default="", help="Comma-separated trend buckets: weak_or_range,transition,trend,strong_trend")
    parser.add_argument("--consolidation-states", default="", help="Comma-separated consolidation states.")
    parser.add_argument("--shock-alignments", default="", help="Comma-separated shock states: no_shock,aligned_shock,opposing_shock")
    parser.add_argument("--dmi-alignments", default="", help="Comma-separated DMI direction states: aligned,opposed,flat,unknown")
    parser.add_argument("--vwap-alignments", default="", help="Comma-separated VWAP alignment states: aligned,opposed,flat,unknown")
    parser.add_argument("--ema-alignments", default="", help="Comma-separated EMA slope alignment states: aligned,opposed,flat,unknown")
    parser.add_argument("--entry-delay-bars", type=int, default=0, help="For context_change: wait N entry bars after a fresh context change.")
    parser.add_argument("--run-label", default="", help="Optional suffix label for output files, e.g. no-btc.")
    parser.add_argument("--partial-tp", type=float, default=0.0, help="Close this fraction at 1R, let rest run to 2R. 0.5 = close half.")
    parser.add_argument("--ltf-monitor", default="", choices=["", "1", "3", "5"], help="Lower timeframe for position monitoring (1/3/5m). Empty = no LTF monitoring.")
    parser.add_argument("--fib-entry", type=float, default=0.0, help="Fibonacci retracement entry: 0=market at close, 0.382/0.5/0.618=limit at Fib pct of last swing.")
    parser.add_argument("--structure-left", type=int, default=2, help="Left pivot bars for entry/stop structure detection.")
    parser.add_argument("--structure-right", type=int, default=2, help="Right pivot bars for entry/stop structure detection.")
    parser.add_argument("--context-structure-left", type=int, default=2, help="Left pivot bars for global/local direction-context structure.")
    parser.add_argument("--context-structure-right", type=int, default=2, help="Right pivot bars for global/local direction-context structure.")
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
    parser.add_argument("--feature-table", action="store_true", help="Export filtered setup candidates with labels for later ranking/ML research.")
    parser.add_argument("--feature-report", action="store_true", help="Write feature bucket diagnostics from the exported candidate table.")
    parser.add_argument("--slippage-mode", default="fixed", choices=["fixed", "atr_scaled"], help="fixed=flat bps cost; atr_scaled=base/stress are ATR multipliers")
    parser.add_argument("--base-cost-pct", type=float, default=0.0006, help="Base round-trip cost pct (fixed mode) or ATR multiplier (atr_scaled mode).")
    parser.add_argument("--stress-cost-pct", type=float, default=0.0020, help="Stress round-trip cost pct (fixed mode) or ATR multiplier (atr_scaled mode).")
    parser.add_argument("--feature-min-count", type=int, default=10, help="Minimum trades per feature bucket in the feature report.")
    parser.add_argument("--frequency-audit", action="store_true", help="Write a day-level audit explaining untraded days and blocked signals.")
    parser.add_argument("--output-dir", default="backtesting/results/crypto_simple_setup_lab")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    sessions = tuple(s.strip() for s in args.sessions.split(",") if s.strip()) or None
    trend_strengths = tuple(s.strip() for s in args.trend_strengths.split(",") if s.strip()) or None
    consolidation_states = tuple(s.strip() for s in args.consolidation_states.split(",") if s.strip()) or None
    shock_alignments = tuple(s.strip() for s in args.shock_alignments.split(",") if s.strip()) or None
    dmi_alignments = tuple(s.strip() for s in args.dmi_alignments.split(",") if s.strip()) or None
    vwap_alignments = tuple(s.strip() for s in args.vwap_alignments.split(",") if s.strip()) or None
    ema_alignments = tuple(s.strip() for s in args.ema_alignments.split(",") if s.strip()) or None
    cfg = SimpleSetupConfig(
        days=args.days,
        entry_tf=args.entry_tf,
        stop_tf=args.stop_tf,
        context_mode=args.context_mode,
        min_rr=args.min_rr,
        horizon_bars=args.horizon_bars,
        max_base_cost_r=args.max_base_cost_r,
        max_stress_cost_r=args.max_stress_cost_r,
        max_stop_pct=args.max_stop_pct,
        sessions=sessions,
        trend_strengths=trend_strengths,
        consolidation_states=consolidation_states,
        shock_alignments=shock_alignments,
        dmi_alignments=dmi_alignments,
        vwap_alignments=vwap_alignments,
        ema_alignments=ema_alignments,
        entry_delay_bars=args.entry_delay_bars,
        partial_tp_pct=args.partial_tp,
        ltf_monitor_tf=args.ltf_monitor,
        fib_entry_pct=args.fib_entry,
        structure_left=args.structure_left,
        structure_right=args.structure_right,
        context_structure_left=args.context_structure_left,
        context_structure_right=args.context_structure_right,
        slippage_mode=args.slippage_mode,
        base_round_trip_pct=args.base_cost_pct,
        stress_round_trip_pct=args.stress_cost_pct,
        run_label=args.run_label.strip(),
    )
    trades, summary = run_simple_setup_lab(symbols, config=cfg, setup=args.setup)
    windows = rolling_window_summary(trades, window_days=args.window_days, step_days=args.step_days)
    windows_60d = rolling_window_summary(trades, window_days=60, step_days=14, min_trades=3)
    windows_90d = rolling_window_summary(trades, window_days=90, step_days=21, min_trades=3)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = output_suffix(args.setup, cfg)
    trades.to_csv(out_dir / f"{suffix}_trades.csv", index=False)
    summary.to_csv(out_dir / f"{suffix}_summary.csv", index=False)
    windows.to_csv(out_dir / f"{suffix}_windows.csv", index=False)
    write_report(summary, trades, out_dir / f"{suffix}_report.md", windows, windows_60d, windows_90d)
    if args.feature_table:
        feature_path = out_dir / f"{suffix}_features.csv"
        features = build_candidate_feature_table(trades, output_path=feature_path)
        print(f"Saved feature table: {feature_path} rows={len(features)}")
        if args.feature_report:
            feature_report_path = out_dir / f"{suffix}_feature_report.md"
            write_candidate_filter_report(features, feature_report_path, min_count=args.feature_min_count)
            print(f"Saved feature report: {feature_report_path}")
    accepted = pd.DataFrame()
    if args.portfolio:
        accepted, portfolio_summary = run_portfolio_validation(
            trades,
            net_column=args.portfolio_net,
            risk_pct=args.risk_pct,
            max_open=args.max_open,
            max_open_per_symbol=args.max_open_per_symbol,
            daily_loss_limit_pct=args.daily_loss_limit_pct,
            cooldown_after_loss_bars=args.cooldown_after_loss_bars,
            tf_minutes=int(cfg.entry_tf),
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
    if args.frequency_audit:
        daily, signal_audit = run_frequency_audit(symbols, config=cfg, setup=args.setup, accepted=accepted)
        daily.to_csv(out_dir / f"{suffix}_frequency_daily.csv", index=False)
        signal_audit.to_csv(out_dir / f"{suffix}_frequency_signals.csv", index=False)
        write_frequency_report(daily, out_dir / f"{suffix}_frequency_report.md")
        if not daily.empty:
            print("\nFrequency")
            print(daily["primary_blocker"].value_counts().to_string())
    print(summary.to_string(index=False))
    if not windows.empty:
        print("\nRolling windows (30d)")
        print(summarize_windows(windows).to_string(index=False))
        if not windows_60d.empty:
            print("\nRolling windows (60d)")
            print(summarize_windows(windows_60d).to_string(index=False))
        if not windows_90d.empty:
            print("\nRolling windows (90d)")
            print(summarize_windows(windows_90d).to_string(index=False))
    return 0


def output_suffix(setup: str, cfg: SimpleSetupConfig) -> str:
    parts = [setup, f"rr{cfg.min_rr:g}"]
    if cfg.entry_tf != "15":
        parts.append(f"entry{cfg.entry_tf}m")
    if cfg.stop_tf and cfg.stop_tf != cfg.entry_tf:
        parts.append(f"stop{cfg.stop_tf}m")
    if cfg.max_base_cost_r is not None:
        parts.append(f"basecost{cfg.max_base_cost_r:g}r")
    if cfg.max_stress_cost_r is not None:
        parts.append(f"stresscost{cfg.max_stress_cost_r:g}r")
    if cfg.max_stop_pct is not None:
        parts.append(f"maxstop{cfg.max_stop_pct:g}pct")
    if cfg.sessions:
        parts.append("sessions-" + "-".join(cfg.sessions))
    if cfg.trend_strengths:
        parts.append("trend-" + "-".join(cfg.trend_strengths))
    if cfg.consolidation_states:
        parts.append("state-" + "-".join(cfg.consolidation_states))
    if cfg.shock_alignments:
        parts.append("shock-" + "-".join(cfg.shock_alignments))
    if cfg.dmi_alignments:
        parts.append("dmi-" + "-".join(cfg.dmi_alignments))
    if cfg.vwap_alignments:
        parts.append("vwap-" + "-".join(cfg.vwap_alignments))
    if cfg.ema_alignments:
        parts.append("ema-" + "-".join(cfg.ema_alignments))
    if cfg.entry_delay_bars:
        parts.append(f"delay{cfg.entry_delay_bars}b")
    if cfg.partial_tp_pct > 0:
        parts.append(f"part{cfg.partial_tp_pct:g}")
    if cfg.fib_entry_pct > 0:
        parts.append(f"fib{cfg.fib_entry_pct:g}")
    if cfg.ltf_monitor_tf:
        parts.append(f"ltf{cfg.ltf_monitor_tf}m")
    if cfg.structure_left != 2 or cfg.structure_right != 2:
        parts.append(f"structL{cfg.structure_left}R{cfg.structure_right}")
    if cfg.context_structure_left != 2 or cfg.context_structure_right != 2:
        parts.append(f"ctxL{cfg.context_structure_left}R{cfg.context_structure_right}")
    if cfg.run_label:
        parts.append(cfg.run_label)
    if cfg.context_mode != "strict":
        parts.append(cfg.context_mode)
    if cfg.slippage_mode != "fixed":
        parts.append(f"slip-{cfg.slippage_mode}")
    if cfg.base_round_trip_pct != 0.0006:
        parts.append(f"basecostpct{cfg.base_round_trip_pct:g}")
    if cfg.stress_round_trip_pct != 0.0020:
        parts.append(f"stresscostpct{cfg.stress_round_trip_pct:g}")
    return "_".join(parts).replace(".", "p")


if __name__ == "__main__":
    raise SystemExit(main())
