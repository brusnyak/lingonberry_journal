"""Simple setup lab for causal path-context setups.

Current setups:
  expansion_exhaustion_fade
  sweep_reclaim_displacement
  sweep_reclaim_followthrough

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
    displacement_atr: float = 0.75
    displacement_close_location: float = 0.6
    followthrough_bars: int = 2
    followthrough_atr: float = 0.5
    followthrough_max_adverse_atr: float = 0.5
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


def run_frequency_audit(
    symbols: list[str],
    *,
    config: PathSetupConfig,
    accepted: pd.DataFrame | None = None,
) -> pd.DataFrame:
    rows = []
    for symbol in symbols:
        rows.extend(audit_symbol_frequency(symbol, config).to_dict("records"))
    daily = pd.DataFrame(rows)
    if daily.empty:
        return daily

    if accepted is not None and not accepted.empty:
        acc = accepted.copy()
        acc["entry_ts"] = pd.to_datetime(acc["entry_ts"], utc=True)
        acc["day"] = acc["entry_ts"].dt.floor("D")
        accepted_daily = acc.groupby(["symbol", "day"]).size().rename("portfolio_accepted").reset_index()
        daily = daily.merge(accepted_daily, on=["symbol", "day"], how="left")
    else:
        daily["portfolio_accepted"] = 0
    daily["portfolio_accepted"] = daily["portfolio_accepted"].fillna(0).astype(int)
    daily["primary_blocker"] = daily.apply(primary_frequency_blocker, axis=1)
    return daily.sort_values(["symbol", "day"]).reset_index(drop=True)


def build_signal_forensics(
    symbols: list[str],
    *,
    config: PathSetupConfig,
    accepted: pd.DataFrame | None = None,
) -> pd.DataFrame:
    accepted_keys = _accepted_trade_keys(accepted)
    rows = []
    for symbol in symbols:
        rows.extend(signal_forensics_symbol(symbol, config, accepted_keys).to_dict("records"))
    if not rows:
        return pd.DataFrame()
    data = pd.DataFrame(rows)
    data["portfolio_accepted"] = data.apply(
        lambda row: _trade_key(row.get("symbol"), row.get("signal_ts"), row.get("entry_ts"), row.get("direction")) in accepted_keys,
        axis=1,
    )
    data["review_stage"] = data["stage"]
    data.loc[data["portfolio_accepted"], "review_stage"] = "accepted"
    data.loc[(data["stage"] == "pre_portfolio_pass") & ~data["portfolio_accepted"], "review_stage"] = "portfolio_throttle"
    return data.sort_values(["signal_ts", "symbol"]).reset_index(drop=True)


def signal_forensics_symbol(
    symbol: str,
    cfg: PathSetupConfig,
    accepted_keys: set[tuple[str, str, str, str]] | None = None,
) -> pd.DataFrame:
    bars = load_crypto(symbol, tf=cfg.entry_tf, days=cfg.days, exchange=cfg.exchange, source=cfg.source).reset_index(drop=True)
    if bars.empty:
        return pd.DataFrame()
    bars["ts"] = pd.to_datetime(bars["ts"], utc=True)
    calls = selected_setup_calls_for_symbol(symbol, bars, cfg)
    if calls.empty:
        return pd.DataFrame()

    structure = build_structure_index(bars, StructureConfig(left=2, right=2))
    atr_values = _atr(bars, 14)
    rows = [
        signal_forensic_row(call, bars, structure, atr_values, cfg, accepted_keys or set())
        for _, call in calls.iterrows()
    ]
    return pd.DataFrame(rows)


def selected_setup_calls_for_symbol(symbol: str, bars: pd.DataFrame, cfg: PathSetupConfig) -> pd.DataFrame:
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
    return select_setup_calls(calls, cfg)


def signal_forensic_row(
    call: pd.Series,
    bars: pd.DataFrame,
    structure: pd.DataFrame,
    atr_values: pd.Series,
    cfg: PathSetupConfig,
    accepted_keys: set[tuple[str, str, str, str]],
) -> dict:
    symbol = str(call.get("symbol", ""))
    signal_i = int(call["entry_i"])
    signal_ts = pd.Timestamp(call["ts"])
    direction = str(call["trade_direction"])
    base = {
        "symbol": symbol,
        "setup": cfg.setup,
        "signal_ts": signal_ts,
        "signal_i": signal_i,
        "signal_session_utc": session_bucket(signal_ts),
        "direction": direction,
        "path_context": call.get("path_context", ""),
        "foundation_state": call.get("foundation_state", ""),
        "foundation_direction": call.get("foundation_direction", ""),
        "pre_8bar_move_atr": window_move_atr(bars, atr_values, signal_i, lookback=8),
        "pre_8bar_range_atr": window_range_atr(bars, atr_values, signal_i, lookback=8),
        "signal_body_atr": candle_body_atr(bars, atr_values, signal_i),
        "signal_close_location": candle_close_location(bars, signal_i),
        "post_4bar_direction_move_atr": post_direction_move_atr(bars, atr_values, signal_i, direction, bars_forward=4),
    }
    signal_probe = signal_entry_probe(call, bars, structure, atr_values, cfg)
    base.update(signal_probe)

    confirm_i = confirmed_entry_index(call, bars, atr_values, cfg)
    if confirm_i is None:
        return {
            **base,
            "stage": "no_confirmation",
            "confirmation_ts": pd.NaT,
            "entry_ts": pd.NaT,
            "entry_session_utc": "",
            "entry": np.nan,
            "sl": np.nan,
            "tp": np.nan,
            "stop_pct": np.nan,
            "stress_cost_r": np.nan,
            "gross_r": np.nan,
            "stress_net_r": np.nan,
            "mfe_r": np.nan,
            "mae_r": np.nan,
            "bars_to_exit": np.nan,
            "exit_kind": "",
            "portfolio_accepted": False,
            "missed_target_after_reject": bool(signal_probe.get("signal_entry_hit_target", False)),
        }

    entry_i = int(confirm_i)
    entry_ts = pd.Timestamp(bars["ts"].iat[entry_i])
    entry = float(bars["close"].iat[entry_i])
    sl, tp = path_stop_target(
        bars,
        signal_i if cfg.stop_model == "path_extreme" else entry_i,
        direction,
        entry,
        cfg.min_rr,
        atr_values,
        stop_model=cfg.stop_model,
        stop_buffer_atr=cfg.stop_buffer_atr,
        structure=structure,
        entry_ts=entry_ts,
    )
    common = {
        **base,
        "confirmation_ts": entry_ts,
        "entry_ts": entry_ts,
        "entry_session_utc": session_bucket(entry_ts),
        "entry": entry,
        "sl": sl,
        "tp": tp,
    }
    if entry_i >= len(bars) - 1 or not np.isfinite(sl):
        return {**common, **empty_outcome_fields("invalid_path", signal_probe)}
    risk = abs(entry - sl)
    if risk <= 0:
        return {**common, **empty_outcome_fields("invalid_path", signal_probe)}
    stop_pct = risk / entry * 100.0
    if stop_pct < cfg.min_stop_pct:
        return {**common, **empty_outcome_fields("invalid_path", signal_probe), "stop_pct": stop_pct}

    base_cost_r = cfg.base_round_trip_pct * entry / risk
    stress_cost_r = cfg.stress_round_trip_pct * entry / risk
    stage = "pre_portfolio_pass"
    if cfg.sessions and session_bucket(entry_ts) not in cfg.sessions:
        stage = "blocked_session"
    elif cfg.max_stress_cost_r is not None and stress_cost_r > cfg.max_stress_cost_r:
        stage = "blocked_cost"

    outcome = walk_structural_outcome(bars, entry_i, direction, sl, tp, horizon=cfg.horizon_bars, track_excursion=True)
    if outcome is None:
        return {**common, **empty_outcome_fields("invalid_path", signal_probe), "stop_pct": stop_pct, "stress_cost_r": stress_cost_r}
    gross_r = float(outcome["r_multiple"])
    accepted = _trade_key(symbol, signal_ts, entry_ts, direction) in accepted_keys
    return {
        **common,
        "stage": stage,
        "stop_pct": stop_pct,
        "target_pct": abs(tp - entry) / entry * 100.0,
        "planned_rr": abs(tp - entry) / risk,
        "base_cost_r": base_cost_r,
        "stress_cost_r": stress_cost_r,
        "gross_r": gross_r,
        "base_net_r": gross_r - base_cost_r,
        "stress_net_r": gross_r - stress_cost_r,
        "mfe_r": float(outcome.get("mfe_r", np.nan)),
        "mae_r": float(outcome.get("mae_r", np.nan)),
        "bars_to_exit": int(outcome.get("bars_to_exit", cfg.horizon_bars)),
        "exit_kind": str(outcome.get("exit_reason", "expiry")),
        "portfolio_accepted": accepted,
        "missed_target_after_reject": (not accepted and bool(signal_probe.get("signal_entry_hit_target", False))),
    }


def confirmed_entry_index(call: pd.Series, bars: pd.DataFrame, atr_values: pd.Series, cfg: PathSetupConfig) -> int | None:
    signal_i = int(call["entry_i"])
    direction = str(call["trade_direction"])
    if cfg.setup == "sweep_reclaim_displacement":
        return find_displacement_confirmation(
            bars,
            signal_i,
            direction,
            atr_values,
            max_bars=max(1, cfg.confirm_bars or 4),
            displacement_atr=cfg.displacement_atr,
            close_location=cfg.displacement_close_location,
        )
    if cfg.setup == "sweep_reclaim_followthrough":
        return find_followthrough_confirmation(
            bars,
            signal_i,
            direction,
            atr_values,
            max_bars=cfg.followthrough_bars,
            min_move_atr=cfg.followthrough_atr,
            max_adverse_atr=cfg.followthrough_max_adverse_atr,
        )
    entry_i = signal_i + cfg.confirm_bars
    if cfg.confirm_bars and cfg.require_reversal_close and not reversal_confirmed(bars, signal_i, entry_i, direction):
        return None
    return entry_i


def signal_entry_probe(
    call: pd.Series,
    bars: pd.DataFrame,
    structure: pd.DataFrame,
    atr_values: pd.Series,
    cfg: PathSetupConfig,
) -> dict:
    signal_i = int(call["entry_i"])
    direction = str(call["trade_direction"])
    if signal_i >= len(bars) - 1:
        return empty_signal_probe()
    signal_ts = pd.Timestamp(call["ts"])
    entry = float(bars["close"].iat[signal_i])
    sl, tp = path_stop_target(
        bars,
        signal_i,
        direction,
        entry,
        cfg.min_rr,
        atr_values,
        stop_model=cfg.stop_model,
        stop_buffer_atr=cfg.stop_buffer_atr,
        structure=structure,
        entry_ts=signal_ts,
    )
    if not np.isfinite(sl):
        return empty_signal_probe()
    risk = abs(entry - sl)
    if risk <= 0:
        return empty_signal_probe()
    outcome = walk_structural_outcome(bars, signal_i, direction, sl, tp, horizon=cfg.horizon_bars, track_excursion=True)
    if outcome is None:
        return empty_signal_probe()
    stress_cost_r = cfg.stress_round_trip_pct * entry / risk
    gross_r = float(outcome["r_multiple"])
    return {
        "signal_entry": entry,
        "signal_entry_sl": sl,
        "signal_entry_tp": tp,
        "signal_entry_stop_pct": risk / entry * 100.0,
        "signal_entry_stress_cost_r": stress_cost_r,
        "signal_entry_gross_r": gross_r,
        "signal_entry_stress_net_r": gross_r - stress_cost_r,
        "signal_entry_mfe_r": float(outcome.get("mfe_r", np.nan)),
        "signal_entry_mae_r": float(outcome.get("mae_r", np.nan)),
        "signal_entry_bars_to_exit": int(outcome.get("bars_to_exit", cfg.horizon_bars)),
        "signal_entry_exit_kind": str(outcome.get("exit_reason", "expiry")),
        "signal_entry_hit_target": str(outcome.get("exit_reason", "")) == "target",
    }


def empty_signal_probe() -> dict:
    return {
        "signal_entry": np.nan,
        "signal_entry_sl": np.nan,
        "signal_entry_tp": np.nan,
        "signal_entry_stop_pct": np.nan,
        "signal_entry_stress_cost_r": np.nan,
        "signal_entry_gross_r": np.nan,
        "signal_entry_stress_net_r": np.nan,
        "signal_entry_mfe_r": np.nan,
        "signal_entry_mae_r": np.nan,
        "signal_entry_bars_to_exit": np.nan,
        "signal_entry_exit_kind": "",
        "signal_entry_hit_target": False,
    }


def empty_outcome_fields(stage: str, signal_probe: dict | None = None) -> dict:
    return {
        "stage": stage,
        "stop_pct": np.nan,
        "target_pct": np.nan,
        "planned_rr": np.nan,
        "base_cost_r": np.nan,
        "stress_cost_r": np.nan,
        "gross_r": np.nan,
        "base_net_r": np.nan,
        "stress_net_r": np.nan,
        "mfe_r": np.nan,
        "mae_r": np.nan,
        "bars_to_exit": np.nan,
        "exit_kind": "",
        "portfolio_accepted": False,
        "missed_target_after_reject": bool((signal_probe or {}).get("signal_entry_hit_target", False)),
    }


def window_move_atr(bars: pd.DataFrame, atr_values: pd.Series, end_i: int, *, lookback: int) -> float:
    start = max(0, end_i - lookback)
    if end_i <= start:
        return np.nan
    atr_now = _atr_at(atr_values, end_i)
    if not np.isfinite(atr_now) or atr_now <= 0:
        return np.nan
    return float((float(bars["close"].iat[end_i]) - float(bars["close"].iat[start])) / atr_now)


def window_range_atr(bars: pd.DataFrame, atr_values: pd.Series, end_i: int, *, lookback: int) -> float:
    start = max(0, end_i - lookback)
    window = bars.iloc[start : end_i + 1]
    atr_now = _atr_at(atr_values, end_i)
    if window.empty or not np.isfinite(atr_now) or atr_now <= 0:
        return np.nan
    return float((float(window["high"].max()) - float(window["low"].min())) / atr_now)


def candle_body_atr(bars: pd.DataFrame, atr_values: pd.Series, i: int) -> float:
    atr_now = _atr_at(atr_values, i)
    if not np.isfinite(atr_now) or atr_now <= 0:
        return np.nan
    return float(abs(float(bars["close"].iat[i]) - float(bars["open"].iat[i])) / atr_now)


def candle_close_location(bars: pd.DataFrame, i: int) -> float:
    high = float(bars["high"].iat[i])
    low = float(bars["low"].iat[i])
    if high <= low:
        return np.nan
    return float((float(bars["close"].iat[i]) - low) / (high - low))


def post_direction_move_atr(
    bars: pd.DataFrame,
    atr_values: pd.Series,
    signal_i: int,
    direction: str,
    *,
    bars_forward: int,
) -> float:
    end_i = min(signal_i + bars_forward, len(bars) - 1)
    if end_i <= signal_i:
        return np.nan
    atr_now = _atr_at(atr_values, signal_i)
    if not np.isfinite(atr_now) or atr_now <= 0:
        return np.nan
    move = float(bars["close"].iat[end_i]) - float(bars["close"].iat[signal_i])
    if direction == "short":
        move = -move
    return float(move / atr_now)


def _atr_at(atr_values: pd.Series, i: int) -> float:
    if i >= len(atr_values):
        return np.nan
    value = float(atr_values.iat[i])
    return value if np.isfinite(value) else np.nan


def _accepted_trade_keys(accepted: pd.DataFrame | None) -> set[tuple[str, str, str, str]]:
    if accepted is None or accepted.empty:
        return set()
    return {
        _trade_key(row.symbol, row.signal_ts, row.entry_ts, row.direction)
        for row in accepted[["symbol", "signal_ts", "entry_ts", "direction"]].itertuples(index=False)
    }


def _trade_key(symbol: object, signal_ts: object, entry_ts: object, direction: object) -> tuple[str, str, str, str]:
    return str(symbol), _ts_key(signal_ts), _ts_key(entry_ts), str(direction)


def _ts_key(value: object) -> str:
    if pd.isna(value):
        return ""
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return ts.isoformat()


def audit_symbol_frequency(symbol: str, cfg: PathSetupConfig) -> pd.DataFrame:
    bars = load_crypto(symbol, tf=cfg.entry_tf, days=cfg.days, exchange=cfg.exchange, source=cfg.source).reset_index(drop=True)
    if bars.empty:
        return pd.DataFrame()
    bars["day"] = pd.to_datetime(bars["ts"], utc=True).dt.floor("D")
    days = bars[["day"]].drop_duplicates().copy()
    days["symbol"] = symbol

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
        return _empty_frequency_days(days)

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
    calls["day"] = pd.to_datetime(calls["ts"], utc=True).dt.floor("D")
    raw_daily = calls.groupby("day").size().rename("raw_events").reset_index()

    selected = select_setup_calls(calls, cfg)
    if selected.empty:
        out = days.merge(raw_daily, on="day", how="left")
        out["raw_events"] = out["raw_events"].fillna(0).astype(int)
        for col in [
            "setup_signals",
            "no_confirmation",
            "invalid_path",
            "blocked_session",
            "blocked_cost",
            "pre_portfolio_pass",
        ]:
            out[col] = 0
        return out

    selected["day"] = pd.to_datetime(selected["ts"], utc=True).dt.floor("D")
    setup_daily = selected.groupby("day").size().rename("setup_signals").reset_index()

    structure = build_structure_index(bars, StructureConfig(left=2, right=2))
    atr_values = _atr(bars, 14)
    stage_rows = []
    for _, call in selected.iterrows():
        stage = audit_call_stage(call, bars, structure, atr_values, cfg)
        stage_rows.append({
            "day": pd.Timestamp(call["day"]),
            "stage": stage,
        })
    stages = pd.DataFrame(stage_rows)
    stage_daily = pd.DataFrame()
    if not stages.empty:
        stage_daily = (
            stages.assign(value=1)
            .pivot_table(index="day", columns="stage", values="value", aggfunc="sum", fill_value=0)
            .reset_index()
        )

    out = days.copy()
    for frame in (raw_daily, setup_daily, stage_daily):
        if not frame.empty:
            out = out.merge(frame, on="day", how="left")
    for col in [
        "raw_events",
        "setup_signals",
        "no_confirmation",
        "invalid_path",
        "blocked_session",
        "blocked_cost",
        "pre_portfolio_pass",
    ]:
        if col not in out:
            out[col] = 0
        out[col] = out[col].fillna(0).astype(int)
    return out


def _empty_frequency_days(days: pd.DataFrame) -> pd.DataFrame:
    out = days.copy()
    for col in [
        "raw_events",
        "setup_signals",
        "no_confirmation",
        "invalid_path",
        "blocked_session",
        "blocked_cost",
        "pre_portfolio_pass",
    ]:
        out[col] = 0
    return out


def audit_call_stage(
    call: pd.Series,
    bars: pd.DataFrame,
    structure: pd.DataFrame,
    atr_values: pd.Series,
    cfg: PathSetupConfig,
) -> str:
    signal_i = int(call["entry_i"])
    confirm = confirmed_entry_index(call, bars, atr_values, cfg)
    if confirm is None:
        return "no_confirmation"
    entry_i = int(confirm)
    if entry_i >= len(bars) - 1:
        return "invalid_path"

    entry_ts = pd.Timestamp(bars["ts"].iat[entry_i]) if entry_i != signal_i else pd.Timestamp(call["ts"])
    direction = str(call["trade_direction"])
    entry = float(bars["close"].iat[entry_i])
    sl, tp = path_stop_target(
        bars,
        signal_i if cfg.stop_model == "path_extreme" else entry_i,
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
        return "invalid_path"
    risk = abs(entry - sl)
    if risk <= 0:
        return "invalid_path"
    stop_pct = risk / entry * 100.0
    if stop_pct < cfg.min_stop_pct:
        return "invalid_path"
    if cfg.sessions and session_bucket(entry_ts) not in cfg.sessions:
        return "blocked_session"
    stress_cost_r = cfg.stress_round_trip_pct * entry / risk
    if cfg.max_stress_cost_r is not None and stress_cost_r > cfg.max_stress_cost_r:
        return "blocked_cost"
    outcome = walk_structural_outcome(bars, entry_i, direction, sl, tp, horizon=cfg.horizon_bars, track_excursion=True)
    if outcome is None:
        return "invalid_path"
    return "pre_portfolio_pass"


def primary_frequency_blocker(row: pd.Series) -> str:
    if int(row.get("portfolio_accepted", 0)) > 0:
        return "accepted"
    if int(row.get("pre_portfolio_pass", 0)) > 0:
        return "portfolio_throttle"
    for col in ["blocked_cost", "blocked_session", "invalid_path", "no_confirmation"]:
        if int(row.get(col, 0)) > 0:
            return col
    if int(row.get("setup_signals", 0)) == 0 and int(row.get("raw_events", 0)) > 0:
        return "no_setup_signal"
    return "no_raw_event"


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
    calls = select_setup_calls(calls, cfg)
    if calls.empty:
        return pd.DataFrame()

    structure = build_structure_index(bars, StructureConfig(left=2, right=2))
    atr_values = _atr(bars, 14)
    rows = []
    for _, call in calls.iterrows():
        signal_i = int(call["entry_i"])
        confirm = confirmed_entry_index(call, bars, atr_values, cfg)
        if confirm is None:
            continue
        i = int(confirm)
        if i >= len(bars) - 1:
            continue
        direction = str(call["trade_direction"])
        entry_ts = pd.Timestamp(bars["ts"].iat[i]) if i != signal_i else pd.Timestamp(call["ts"])
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
            "displacement_atr": cfg.displacement_atr,
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


def select_setup_calls(calls: pd.DataFrame, cfg: PathSetupConfig) -> pd.DataFrame:
    if cfg.setup == "expansion_exhaustion_fade":
        return select_expansion_exhaustion_calls(
            calls,
            include_sweep_reclaim_long=cfg.include_sweep_reclaim_long,
        )
    if cfg.setup in {"sweep_reclaim_displacement", "sweep_reclaim_followthrough"}:
        return select_sweep_reclaim_calls(calls)
    raise ValueError(f"unknown path setup: {cfg.setup}")


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


def select_sweep_reclaim_calls(calls: pd.DataFrame) -> pd.DataFrame:
    if calls.empty:
        return calls
    selected = calls[calls["path_context"].isin(["sweep_reclaim_long", "sweep_reclaim_short"])].copy()
    if selected.empty:
        return selected
    selected["trade_direction"] = np.where(selected["path_context"].eq("sweep_reclaim_long"), "long", "short")
    return selected.reset_index(drop=True)


def find_displacement_confirmation(
    bars: pd.DataFrame,
    signal_i: int,
    direction: str,
    atr_values: pd.Series,
    *,
    max_bars: int = 4,
    displacement_atr: float = 0.75,
    close_location: float = 0.6,
) -> int | None:
    end_i = min(signal_i + max_bars, len(bars) - 1)
    for i in range(signal_i + 1, end_i + 1):
        atr_now = float(atr_values.iat[i]) if i < len(atr_values) else np.nan
        if not np.isfinite(atr_now) or atr_now <= 0:
            continue
        open_ = float(bars["open"].iat[i])
        high = float(bars["high"].iat[i])
        low = float(bars["low"].iat[i])
        close = float(bars["close"].iat[i])
        candle_range = high - low
        body = abs(close - open_)
        if candle_range <= 0 or body < displacement_atr * atr_now:
            continue
        close_pos = (close - low) / candle_range
        if direction == "long" and close > open_ and close_pos >= close_location:
            return i
        if direction == "short" and close < open_ and close_pos <= 1.0 - close_location:
            return i
    return None


def find_followthrough_confirmation(
    bars: pd.DataFrame,
    signal_i: int,
    direction: str,
    atr_values: pd.Series,
    *,
    max_bars: int = 2,
    min_move_atr: float = 0.5,
    max_adverse_atr: float = 0.5,
) -> int | None:
    signal_close = float(bars["close"].iat[signal_i])
    atr_now = _atr_at(atr_values, signal_i)
    if not np.isfinite(atr_now) or atr_now <= 0:
        return None
    end_i = min(signal_i + max(1, max_bars), len(bars) - 1)
    adverse = 0.0
    for i in range(signal_i + 1, end_i + 1):
        high = float(bars["high"].iat[i])
        low = float(bars["low"].iat[i])
        close = float(bars["close"].iat[i])
        if direction == "long":
            adverse = max(adverse, (signal_close - low) / atr_now)
            move = (close - signal_close) / atr_now
            if adverse <= max_adverse_atr and move >= min_move_atr:
                return i
        elif direction == "short":
            adverse = max(adverse, (high - signal_close) / atr_now)
            move = (signal_close - close) / atr_now
            if adverse <= max_adverse_atr and move >= min_move_atr:
                return i
    return None


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
    if cfg.entry_tf != "15":
        parts.append(f"tf{cfg.entry_tf}")
    if cfg.sessions:
        parts.append("sessions-" + "-".join(cfg.sessions))
    if cfg.base_round_trip_pct != 0.0006:
        parts.append(f"basefee{cfg.base_round_trip_pct:g}")
    if cfg.stress_round_trip_pct != 0.0020:
        parts.append(f"stressfee{cfg.stress_round_trip_pct:g}")
    if cfg.max_stress_cost_r is not None:
        parts.append(f"stresscost{cfg.max_stress_cost_r:g}r")
    if cfg.include_sweep_reclaim_long:
        parts.append("with-sweep-long")
    if cfg.confirm_bars:
        parts.append(f"confirm{cfg.confirm_bars}b")
    if cfg.require_reversal_close:
        parts.append("reversal-close")
    if cfg.setup in {"sweep_reclaim_displacement", "sweep_reclaim_followthrough"}:
        parts.append(f"disp{cfg.displacement_atr:g}")
        parts.append(f"close{cfg.displacement_close_location:g}")
    if cfg.setup == "sweep_reclaim_followthrough":
        parts.append(f"ft{cfg.followthrough_bars}b")
        parts.append(f"move{cfg.followthrough_atr:g}")
        parts.append(f"adv{cfg.followthrough_max_adverse_atr:g}")
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


def write_frequency_report(daily: pd.DataFrame, output: Path) -> None:
    lines = ["# Path Setup Frequency Audit", "", "## Summary", ""]
    if daily.empty:
        lines.append("_empty_")
    else:
        summary = daily.groupby("primary_blocker").agg(
            symbol_days=("day", "size"),
            raw_events=("raw_events", "sum"),
            setup_signals=("setup_signals", "sum"),
            no_confirmation=("no_confirmation", "sum"),
            invalid_path=("invalid_path", "sum"),
            blocked_session=("blocked_session", "sum"),
            blocked_cost=("blocked_cost", "sum"),
            pre_portfolio_pass=("pre_portfolio_pass", "sum"),
            portfolio_accepted=("portfolio_accepted", "sum"),
        ).reset_index().sort_values("symbol_days", ascending=False)
        lines.extend(_markdown_table(summary))
        lines.extend(["", "## Symbol Split", ""])
        by_symbol = daily.groupby(["symbol", "primary_blocker"]).agg(
            days=("day", "size"),
            raw_events=("raw_events", "sum"),
            setup_signals=("setup_signals", "sum"),
            pre_portfolio_pass=("pre_portfolio_pass", "sum"),
            portfolio_accepted=("portfolio_accepted", "sum"),
        ).reset_index().sort_values(["symbol", "days"], ascending=[True, False])
        lines.extend(_markdown_table(by_symbol))
        lines.extend(["", "## Read", ""])
        lines.extend([
            "- `no_raw_event`: path-context event layer found no expansion/sweep event that day.",
            "- `no_setup_signal`: events existed, but this setup did not select them.",
            "- `no_confirmation`: setup signal fired, but confirmation did not arrive in time.",
            "- `invalid_path`: confirmation existed, but stop/outcome geometry was not tradable.",
            "- `blocked_session`: tradable path existed outside the configured sessions.",
            "- `blocked_cost`: tradable path existed but stress cost in R was too high.",
            "- `portfolio_throttle`: trade passed setup gates but portfolio risk rules skipped it.",
        ])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n")


def write_signal_forensics_report(forensics: pd.DataFrame, output: Path) -> None:
    lines = ["# Path Setup Signal Forensics", "", "## Stage Summary", ""]
    if forensics.empty:
        lines.append("_empty_")
    else:
        summary = forensics.groupby("review_stage").agg(
            signals=("signal_ts", "count"),
            target_rate=("exit_kind", lambda s: float((s == "target").mean())),
            stop_rate=("exit_kind", lambda s: float((s == "stop").mean())),
            expiry_rate=("exit_kind", lambda s: float((s == "expiry").mean())),
            signal_entry_target_rate=("signal_entry_hit_target", "mean"),
            missed_target_rate=("missed_target_after_reject", "mean"),
            avg_stress_r=("stress_net_r", "mean"),
            avg_signal_entry_stress_r=("signal_entry_stress_net_r", "mean"),
            median_stop_pct=("stop_pct", "median"),
            median_stress_cost_r=("stress_cost_r", "median"),
            median_pre_move_atr=("pre_8bar_move_atr", "median"),
            median_post_4bar_move_atr=("post_4bar_direction_move_atr", "median"),
        ).reset_index().sort_values("signals", ascending=False)
        lines.extend(_markdown_table(summary))

        lines.extend(["", "## By Symbol And Stage", ""])
        by_symbol = forensics.groupby(["symbol", "review_stage"]).agg(
            signals=("signal_ts", "count"),
            avg_stress_r=("stress_net_r", "mean"),
            avg_signal_entry_stress_r=("signal_entry_stress_net_r", "mean"),
            missed_target_rate=("missed_target_after_reject", "mean"),
            target_rate=("exit_kind", lambda s: float((s == "target").mean())),
            stop_rate=("exit_kind", lambda s: float((s == "stop").mean())),
        ).reset_index().sort_values(["symbol", "signals"], ascending=[True, False])
        lines.extend(_markdown_table(by_symbol))

        lines.extend(["", "## Cost And Session Reads", ""])
        cost = forensics[forensics["review_stage"].eq("blocked_cost")]
        session = forensics[forensics["review_stage"].eq("blocked_session")]
        accepted = forensics[forensics["review_stage"].eq("accepted")]
        rows = []
        for name, frame in [("blocked_cost", cost), ("blocked_session", session), ("accepted", accepted)]:
            rows.append({
                "bucket": name,
                "signals": len(frame),
                "stress_pf": profit_factor(frame["stress_net_r"].dropna().to_numpy(dtype=float)) if len(frame) else np.nan,
                "avg_stress_r": float(frame["stress_net_r"].mean()) if len(frame) else np.nan,
                "median_stop_pct": float(frame["stop_pct"].median()) if len(frame) else np.nan,
                "median_stress_cost_r": float(frame["stress_cost_r"].median()) if len(frame) else np.nan,
            })
        lines.extend(_markdown_table(pd.DataFrame(rows)))

        lines.extend(["", "## Missed Signal-Entry Probe", ""])
        missed = forensics.groupby("review_stage").agg(
            signals=("signal_ts", "count"),
            signal_entry_pf=("signal_entry_stress_net_r", lambda s: profit_factor(s.dropna().to_numpy(dtype=float))),
            signal_entry_avg_r=("signal_entry_stress_net_r", "mean"),
            signal_entry_target_rate=("signal_entry_hit_target", "mean"),
            median_signal_entry_mfe_r=("signal_entry_mfe_r", "median"),
            median_signal_entry_mae_r=("signal_entry_mae_r", "median"),
        ).reset_index().sort_values("signals", ascending=False)
        lines.extend(_markdown_table(missed))

        lines.extend(["", "## Read", ""])
        lines.extend([
            "- Use the CSV to review individual rejected setup signals, not just accepted trades.",
            "- `blocked_session` rows show whether non-Asia signals had edge before promoting a wider session.",
            "- `no_confirmation` rows show whether displacement confirmation is too strict or correctly blocking chop.",
            "- `blocked_cost` rows show whether the stress-cost gate blocks winners or correctly blocks untradable tight stops.",
            "- `signal_entry_*` columns are diagnostics only: they show what happened if the engine entered at the signal close without confirmation.",
        ])
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
    parser.add_argument("--entry-tf", default="15")
    parser.add_argument(
        "--setup",
        default="expansion_exhaustion_fade",
        choices=["expansion_exhaustion_fade", "sweep_reclaim_displacement", "sweep_reclaim_followthrough"],
    )
    parser.add_argument("--min-rr", type=float, default=1.5)
    parser.add_argument("--horizon-bars", type=int, default=96)
    parser.add_argument("--sessions", default="")
    parser.add_argument("--max-stress-cost-r", type=float, default=None)
    parser.add_argument("--max-stop-pct", type=float, default=None)
    parser.add_argument("--base-round-trip-pct", type=float, default=0.0006)
    parser.add_argument("--stress-round-trip-pct", type=float, default=0.0020)
    parser.add_argument("--lookback-bars", type=int, default=32)
    parser.add_argument("--expansion-atr", type=float, default=1.5)
    parser.add_argument("--include-sweep-reclaim-long", action="store_true")
    parser.add_argument("--stop-model", default="path_extreme", choices=["path_extreme", "structural"])
    parser.add_argument("--stop-buffer-atr", type=float, default=0.1)
    parser.add_argument("--confirm-bars", type=int, default=0)
    parser.add_argument("--require-reversal-close", action="store_true")
    parser.add_argument("--displacement-atr", type=float, default=0.75)
    parser.add_argument("--displacement-close-location", type=float, default=0.6)
    parser.add_argument("--followthrough-bars", type=int, default=2)
    parser.add_argument("--followthrough-atr", type=float, default=0.5)
    parser.add_argument("--followthrough-max-adverse-atr", type=float, default=0.5)
    parser.add_argument("--portfolio", action="store_true")
    parser.add_argument("--frequency-audit", action="store_true")
    parser.add_argument("--signal-forensics", action="store_true")
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
        entry_tf=str(args.entry_tf),
        setup=args.setup,
        min_rr=args.min_rr,
        horizon_bars=args.horizon_bars,
        sessions=sessions,
        max_stress_cost_r=args.max_stress_cost_r,
        max_stop_pct=args.max_stop_pct,
        base_round_trip_pct=args.base_round_trip_pct,
        stress_round_trip_pct=args.stress_round_trip_pct,
        lookback_bars=args.lookback_bars,
        expansion_atr=args.expansion_atr,
        include_sweep_reclaim_long=args.include_sweep_reclaim_long,
        stop_model=args.stop_model,
        stop_buffer_atr=args.stop_buffer_atr,
        confirm_bars=args.confirm_bars,
        require_reversal_close=args.require_reversal_close,
        displacement_atr=args.displacement_atr,
        displacement_close_location=args.displacement_close_location,
        followthrough_bars=args.followthrough_bars,
        followthrough_atr=args.followthrough_atr,
        followthrough_max_adverse_atr=args.followthrough_max_adverse_atr,
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
    accepted = pd.DataFrame()
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
        daily = run_frequency_audit(symbols, config=cfg, accepted=accepted)
        daily.to_csv(out_dir / f"{suffix}_frequency_daily.csv", index=False)
        write_frequency_report(daily, out_dir / f"{suffix}_frequency_report.md")
    if args.signal_forensics:
        forensics = build_signal_forensics(symbols, config=cfg, accepted=accepted)
        forensics.to_csv(out_dir / f"{suffix}_signal_forensics.csv", index=False)
        write_signal_forensics_report(forensics, out_dir / f"{suffix}_signal_forensics_report.md")
    print(summary.to_string(index=False))
    if not windows.empty:
        print("\nRolling windows")
        print(summarize_windows(windows).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
