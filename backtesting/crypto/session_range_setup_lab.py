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
from backtesting.features.vwap import build_vwap_index
from backtesting.crypto.simple_setup_lab import (
    ema_slope_alignment,
    profit_factor,
    rolling_window_summary,
    run_portfolio_validation,
    session_bucket,
    summarize_trades,
    summarize_windows,
    vwap_alignment,
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
    reference_biases: tuple[str, ...] | None = None
    entry_vwap_alignments: tuple[str, ...] | None = None
    entry_ema_alignments: tuple[str, ...] | None = None
    entry_ema_stacks: tuple[str, ...] | None = None
    first_trade_hour_directions: tuple[str, ...] | None = None
    run_label: str = ""


SETUP_SESSIONS = {
    "london_asia_breakout": ("asia", "london", "breakout"),
    "london_asia_fakeout": ("asia", "london", "fakeout"),
    "london_asia_continuation": ("asia", "london", "continuation"),
    "london_asia_reversal": ("asia", "london", "reversal"),
    "ny_london_breakout": ("london", "ny", "breakout"),
    "ny_london_fakeout": ("london", "ny", "fakeout"),
    "ny_london_continuation": ("london", "ny", "continuation"),
    "ny_london_reversal": ("london", "ny", "reversal"),
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
    indicator_features = build_indicator_features(bars, atr_values)

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
        ref_features = reference_features(ref, ref_high, ref_low, atr_now, cfg)
        ref_bias = reference_direction(ref, ref_high, ref_low, atr_now, cfg)
        if mode in {"continuation", "reversal"} and ref_bias is None:
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
            features = trade_feature_context(
                bars,
                trade.index,
                int(i),
                signal,
                atr_i,
                indicator_features,
                ref_features,
                ref_high,
                ref_low,
                ref_mid,
            )
            row, _stage = trade_candidate(symbol, bars, atr_values, int(i), signal, cfg, ref_high, ref_low, ref_range_atr, features)
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
            "reference_close_location": np.nan,
            "reference_body_atr": np.nan,
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
        ref_features = reference_features(ref, ref_high, ref_low, atr_now, cfg)
        row["reference_close_location"] = ref_features["reference_close_location"]
        row["reference_body_atr"] = ref_features["reference_body_atr"]
        ref_bias = reference_direction(ref, ref_high, ref_low, atr_now, cfg)
        row["reference_bias"] = ref_bias or ""
        if mode in {"continuation", "reversal"} and ref_bias is None:
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
    if mode == "reversal":
        if reference_bias == "long" and swept_high and close < ref_high - reclaim_buffer_atr * atr and close <= ref_mid:
            return "short"
        if reference_bias == "short" and swept_low and close > ref_low + reclaim_buffer_atr * atr and close >= ref_mid:
            return "long"
        return None
    raise ValueError(f"unknown session range mode: {mode}")


def reference_direction(ref: pd.DataFrame, ref_high: float, ref_low: float, atr: float, cfg: SessionRangeConfig) -> str | None:
    features = reference_features(ref, ref_high, ref_low, atr, cfg)
    close_location = features["reference_close_location"]
    body_atr = features["reference_body_atr"]
    ref_open = features["reference_open"]
    ref_close = features["reference_close"]
    if not np.isfinite(close_location) or not np.isfinite(body_atr):
        return None
    if body_atr < cfg.min_reference_body_atr:
        return None
    threshold = cfg.reference_close_location_threshold
    if close_location >= threshold and ref_close > ref_open:
        return "long"
    if close_location <= 1.0 - threshold and ref_close < ref_open:
        return "short"
    return None


def reference_features(ref: pd.DataFrame, ref_high: float, ref_low: float, atr: float, cfg: SessionRangeConfig) -> dict:
    if ref.empty or not np.isfinite(atr) or atr <= 0:
        return {
            "reference_open": np.nan,
            "reference_close": np.nan,
            "reference_close_location": np.nan,
            "reference_body_atr": np.nan,
            "reference_return_atr": np.nan,
            "reference_bias": "",
        }
    ref_open = float(ref["open"].iloc[0])
    ref_close = float(ref["close"].iloc[-1])
    ref_range = ref_high - ref_low
    if ref_range <= 0:
        close_location = np.nan
    else:
        close_location = (ref_close - ref_low) / ref_range
    body_atr = abs(ref_close - ref_open) / atr
    return_atr = (ref_close - ref_open) / atr
    bias = ""
    if body_atr < cfg.min_reference_body_atr:
        pass
    elif close_location >= cfg.reference_close_location_threshold and ref_close > ref_open:
        bias = "long"
    elif close_location <= 1.0 - cfg.reference_close_location_threshold and ref_close < ref_open:
        bias = "short"
    return {
        "reference_open": ref_open,
        "reference_close": ref_close,
        "reference_close_location": float(close_location),
        "reference_body_atr": float(body_atr),
        "reference_return_atr": float(return_atr),
        "reference_bias": bias,
    }


def build_indicator_features(bars: pd.DataFrame, atr_values: pd.Series) -> pd.DataFrame:
    out = pd.DataFrame(index=bars.index)
    close = pd.to_numeric(bars["close"], errors="coerce")
    ema21 = close.ewm(span=21, adjust=False).mean()
    ema55 = close.ewm(span=55, adjust=False).mean()
    out["ema21"] = ema21
    out["ema55"] = ema55
    out["ema21_slope_5"] = ema21 - ema21.shift(5)
    out["atr"] = atr_values
    if "volume" in bars.columns:
        try:
            vwap_df = build_vwap_index(bars)
            out["vwap"] = pd.to_numeric(vwap_df["vwap"], errors="coerce")
            out["vwap_slope_12"] = pd.to_numeric(vwap_df["vwap_slope_12"], errors="coerce")
            out["vwap_z_score"] = pd.to_numeric(vwap_df["vwap_z_score"], errors="coerce")
        except (KeyError, ValueError):
            out["vwap"] = np.nan
            out["vwap_slope_12"] = np.nan
            out["vwap_z_score"] = np.nan
    else:
        out["vwap"] = np.nan
        out["vwap_slope_12"] = np.nan
        out["vwap_z_score"] = np.nan
    return out


def trade_feature_context(
    bars: pd.DataFrame,
    trade_index: pd.Index,
    i: int,
    direction: str,
    atr_i: float,
    indicator_features: pd.DataFrame,
    ref_features: dict,
    ref_high: float,
    ref_low: float,
    ref_mid: float,
) -> dict:
    entry = float(bars["close"].iat[i])
    features = dict(ref_features)
    features["reference_bias"] = ref_features.get("reference_bias", "")
    features["entry_vs_reference_mid_atr"] = (entry - ref_mid) / atr_i if atr_i > 0 else np.nan
    features["entry_vs_reference_high_atr"] = (entry - ref_high) / atr_i if atr_i > 0 else np.nan
    features["entry_vs_reference_low_atr"] = (entry - ref_low) / atr_i if atr_i > 0 else np.nan
    if i in indicator_features.index:
        ind = indicator_features.loc[i]
        vwap_val = float(ind.get("vwap", np.nan))
        ema_slope = float(ind.get("ema21_slope_5", np.nan))
        ema21 = float(ind.get("ema21", np.nan))
        ema55 = float(ind.get("ema55", np.nan))
        features["entry_vwap"] = vwap_val
        features["entry_vwap_distance_atr"] = (entry - vwap_val) / atr_i if np.isfinite(vwap_val) and atr_i > 0 else np.nan
        features["entry_vwap_alignment"] = vwap_alignment(direction, entry, vwap_val, atr_val=atr_i)
        features["entry_vwap_slope_12"] = float(ind.get("vwap_slope_12", np.nan))
        features["entry_vwap_z_score"] = float(ind.get("vwap_z_score", np.nan))
        features["entry_ema21"] = ema21
        features["entry_ema55"] = ema55
        features["entry_ema21_slope_5"] = ema_slope
        features["entry_ema_alignment"] = ema_slope_alignment(direction, ema_slope)
        features["entry_ema_stack"] = ema_stack_state(entry, ema21, ema55)
    else:
        features.update(empty_indicator_feature_values())
    features.update(first_trade_hour_features(bars, trade_index, i))
    return features


def empty_indicator_feature_values() -> dict:
    return {
        "entry_vwap": np.nan,
        "entry_vwap_distance_atr": np.nan,
        "entry_vwap_alignment": "unknown",
        "entry_vwap_slope_12": np.nan,
        "entry_vwap_z_score": np.nan,
        "entry_ema21": np.nan,
        "entry_ema55": np.nan,
        "entry_ema21_slope_5": np.nan,
        "entry_ema_alignment": "unknown",
        "entry_ema_stack": "unknown",
    }


def ema_stack_state(entry: float, ema21: float, ema55: float) -> str:
    if not all(np.isfinite(v) for v in [entry, ema21, ema55]):
        return "unknown"
    if entry > ema21 >= ema55:
        return "bullish"
    if entry < ema21 <= ema55:
        return "bearish"
    return "mixed"


def first_trade_hour_features(bars: pd.DataFrame, trade_index: pd.Index, i: int, bars_per_hour: int = 4) -> dict:
    positions = list(trade_index)
    if i not in positions:
        return {"trade_session_elapsed_bars": np.nan, "first_trade_hour_direction": "unknown", "first_trade_hour_return_atr": np.nan}
    elapsed = positions.index(i)
    if len(positions) < bars_per_hour or elapsed < bars_per_hour - 1:
        return {"trade_session_elapsed_bars": elapsed, "first_trade_hour_direction": "unknown", "first_trade_hour_return_atr": np.nan}
    first_i = int(positions[0])
    hour_i = int(positions[bars_per_hour - 1])
    open_ = float(bars["open"].iat[first_i])
    close = float(bars["close"].iat[hour_i])
    atr = float(_atr(bars, 14).iat[hour_i])
    ret_atr = (close - open_) / atr if np.isfinite(atr) and atr > 0 else np.nan
    if not np.isfinite(ret_atr) or abs(ret_atr) < 0.25:
        direction = "flat"
    else:
        direction = "up" if ret_atr > 0 else "down"
    return {"trade_session_elapsed_bars": elapsed, "first_trade_hour_direction": direction, "first_trade_hour_return_atr": ret_atr}


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
    feature_context: dict | None = None,
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
    row = {
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
    }
    if feature_context:
        row.update(feature_context)
    return row, "candidate"


def apply_filters(trades: pd.DataFrame, cfg: SessionRangeConfig) -> pd.DataFrame:
    if trades.empty:
        return trades
    out = trades.copy()
    if cfg.max_stress_cost_r is not None:
        out = out[out["stress_cost_r"] <= cfg.max_stress_cost_r]
    out = apply_feature_filter(out, "reference_bias", cfg.reference_biases)
    out = apply_feature_filter(out, "entry_vwap_alignment", cfg.entry_vwap_alignments)
    out = apply_feature_filter(out, "entry_ema_alignment", cfg.entry_ema_alignments)
    out = apply_feature_filter(out, "entry_ema_stack", cfg.entry_ema_stacks)
    out = apply_feature_filter(out, "first_trade_hour_direction", cfg.first_trade_hour_directions)
    return out.sort_values(["entry_ts", "symbol"]).reset_index(drop=True)


def apply_feature_filter(trades: pd.DataFrame, col: str, allowed: tuple[str, ...] | None) -> pd.DataFrame:
    if not allowed or col not in trades.columns:
        return trades
    values = trades[col].fillna("missing").replace("", "missing").astype(str)
    return trades[values.isin(allowed)]


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
    if cfg.setup.endswith(("_continuation", "_reversal")):
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
    if cfg.reference_biases:
        parts.append("refbias-" + "-".join(cfg.reference_biases))
    if cfg.entry_vwap_alignments:
        parts.append("vwap-" + "-".join(cfg.entry_vwap_alignments))
    if cfg.entry_ema_alignments:
        parts.append("ema-" + "-".join(cfg.entry_ema_alignments))
    if cfg.entry_ema_stacks:
        parts.append("emastack-" + "-".join(cfg.entry_ema_stacks))
    if cfg.first_trade_hour_directions:
        parts.append("firsthour-" + "-".join(cfg.first_trade_hour_directions))
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
        lines.extend(["", "## By Feature Buckets", ""])
        for col in [
            "reference_bias",
            "entry_vwap_alignment",
            "entry_ema_alignment",
            "entry_ema_stack",
            "first_trade_hour_direction",
        ]:
            if col not in trades.columns:
                continue
            bucket = summarize_feature_bucket(trades, col)
            lines.extend([f"### {col}", ""])
            lines.extend(_markdown_table(bucket))
            lines.append("")
    lines.extend(["", "## Rolling Windows", ""])
    lines.extend(_markdown_table(summarize_windows(windows)))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n")


def summarize_feature_bucket(trades: pd.DataFrame, col: str) -> pd.DataFrame:
    data = trades.copy()
    data[col] = data[col].fillna("missing").replace("", "missing")
    return (
        data.groupby(col, dropna=False)
        .agg(
            trades=("stress_net_r", "size"),
            win_rate=("stress_net_r", lambda s: float((s > 0).mean())),
            stress_pf=("stress_net_r", lambda s: profit_factor(s.to_numpy(dtype=float))),
            avg_stress_r=("stress_net_r", "mean"),
            median_stop_pct=("stop_pct", "median"),
        )
        .reset_index()
        .sort_values(["trades", "stress_pf"], ascending=[False, False])
    )


def _atr_at(atr_values: pd.Series, i: int) -> float:
    if i >= len(atr_values):
        return np.nan
    value = float(atr_values.iat[i])
    return value if np.isfinite(value) else np.nan


def parse_csv_tuple(value: str) -> tuple[str, ...] | None:
    parsed = tuple(part.strip() for part in str(value).split(",") if part.strip())
    return parsed or None


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
    parser.add_argument("--reference-biases", default="", help="Comma-separated feature filter: long,short,missing.")
    parser.add_argument("--entry-vwap-alignments", default="", help="Comma-separated feature filter: aligned,opposed,flat,unknown.")
    parser.add_argument("--entry-ema-alignments", default="", help="Comma-separated feature filter: aligned,opposed,flat,unknown.")
    parser.add_argument("--entry-ema-stacks", default="", help="Comma-separated feature filter: bullish,bearish,mixed,unknown.")
    parser.add_argument("--first-trade-hour-directions", default="", help="Comma-separated feature filter: up,down,flat,unknown.")
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
        reference_biases=parse_csv_tuple(args.reference_biases),
        entry_vwap_alignments=parse_csv_tuple(args.entry_vwap_alignments),
        entry_ema_alignments=parse_csv_tuple(args.entry_ema_alignments),
        entry_ema_stacks=parse_csv_tuple(args.entry_ema_stacks),
        first_trade_hour_directions=parse_csv_tuple(args.first_trade_hour_directions),
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
