"""Foundation trade forensics and indicator chemistry for crypto MTF journal.

This module starts from the structure-regime journal and collapses duplicated
target/management variants into concrete execution rows before reporting
frequency, duration, return/DD, post-exit continuation, and simple indicator
filters.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.crypto.data import load_crypto
from backtesting.crypto.portfolio_validation import PortfolioRiskConfig, simulate_portfolio
from backtesting.crypto.structure_regime_journal import average_true_range


DEFAULT_INPUT = Path("backtesting/results/crypto_structure_regime_journal_reindexed/structure_regime_trade_journal.csv")
DEFAULT_OUTPUT_DIR = Path("backtesting/results/crypto_foundation_trade_forensics")
DEFAULT_REVIEW_LABELS = Path("webapp/review_labels.json")

BASE_VALIDATION_RULES = [
    "strict_candidates",
    "ny_13_range_reversal",
    "late_us_fade",
    "london_trend_aligned",
]

DIRECTION_VALIDATION_RULES = [
    "strict_vwap_agrees",
    "strict_ema_stack_confirmed",
    "strict_late_us_vwap_agrees",
    "strict_late_us_no_weak_ema",
    "late_us_fade_vwap_agrees",
    "strict_direction_quality",
]

VALIDATION_RULES = BASE_VALIDATION_RULES + DIRECTION_VALIDATION_RULES

REPORT_RULES = [
    "strict_candidates",
    "strict_late_us_no_weak_ema",
    "strict_late_us_vwap_agrees",
    "strict_ema_stack_confirmed",
    "strict_vwap_agrees",
    "strict_direction_quality",
    "late_us_fade",
]


@dataclass(frozen=True)
class ForensicsRunConfig:
    target_model: str = "fixed_2r"
    management_model: str = "hold_target_expiry"
    risk_per_trade_pct: float = 0.002
    max_open_trades: int = 6
    max_open_per_symbol: int = 1
    daily_loss_limit_pct: float = 0.005
    days: int = 90
    post_bars: tuple[int, ...] = (4, 8, 16, 24)


def run_foundation_trade_forensics(
    input_path: Path = DEFAULT_INPUT,
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    config: ForensicsRunConfig | None = None,
) -> dict[str, pd.DataFrame]:
    cfg = config or ForensicsRunConfig()
    journal = _load_table(input_path)
    if journal.empty:
        raise ValueError(f"No journal rows found at {input_path}")

    concrete = select_concrete_execution(journal, cfg.target_model, cfg.management_model)
    events = enrich_events(concrete, cfg)
    rules = evaluate_windowed_rules(events, cfg)
    stress = evaluate_stress_matrix(events, cfg)
    extreme = evaluate_extreme_config_matrix(events, cfg)
    rolling = evaluate_rolling_validation(events, cfg)
    rolling_summary = summarize_rolling_validation(rolling)
    rolling_trades = collect_rolling_window_trades(events, rolling, cfg)
    failure_diagnostics = diagnose_rolling_failures(rolling_trades)
    review_packet = build_foundation_review_packet(rolling_trades)
    review_audit = analyze_foundation_review_labels(review_packet, DEFAULT_REVIEW_LABELS)
    frequency_expansion = evaluate_frequency_expansion(events, cfg)
    direction_audit = evaluate_direction_audit(events)
    contribution = evaluate_contribution_concentration(events)
    by_symbol = summarize_by_symbol(events)
    by_setup = summarize(events, ["setup_name", "mtf_mode"])
    management = compare_management_variants(journal)

    output_dir.mkdir(parents=True, exist_ok=True)
    events.to_csv(output_dir / "foundation_physical_trade_journal.csv", index=False)
    rules.to_csv(output_dir / "foundation_rule_matrix.csv", index=False)
    stress.to_csv(output_dir / "foundation_stress_matrix.csv", index=False)
    extreme.to_csv(output_dir / "foundation_extreme_config_matrix.csv", index=False)
    rolling.to_csv(output_dir / "foundation_rolling_validation.csv", index=False)
    rolling_summary.to_csv(output_dir / "foundation_rolling_validation_summary.csv", index=False)
    rolling_trades.to_csv(output_dir / "foundation_rolling_window_trades.csv", index=False)
    failure_diagnostics.to_csv(output_dir / "foundation_failure_diagnostics.csv", index=False)
    review_packet.to_csv(output_dir / "foundation_review_packet.csv", index=False)
    review_audit.to_csv(output_dir / "foundation_manual_review_audit.csv", index=False)
    frequency_expansion.to_csv(output_dir / "foundation_frequency_expansion_matrix.csv", index=False)
    direction_audit.to_csv(output_dir / "foundation_direction_audit.csv", index=False)
    contribution.to_csv(output_dir / "foundation_contribution_concentration.csv", index=False)
    by_symbol.to_csv(output_dir / "foundation_frequency_by_symbol.csv", index=False)
    by_setup.to_csv(output_dir / "foundation_summary_by_setup.csv", index=False)
    management.to_csv(output_dir / "foundation_management_comparison.csv", index=False)
    _write_report(events, rules, stress, extreme, rolling_summary, failure_diagnostics, review_packet, review_audit, frequency_expansion, direction_audit, contribution, by_symbol, by_setup, management, output_dir / "foundation_trade_forensics_report.md", cfg)
    return {
        "events": events,
        "rules": rules,
        "stress": stress,
        "extreme": extreme,
        "rolling": rolling,
        "rolling_summary": rolling_summary,
        "rolling_trades": rolling_trades,
        "failure_diagnostics": failure_diagnostics,
        "review_packet": review_packet,
        "review_audit": review_audit,
        "frequency_expansion": frequency_expansion,
        "direction_audit": direction_audit,
        "contribution": contribution,
        "by_symbol": by_symbol,
        "by_setup": by_setup,
        "management": management,
    }


def select_concrete_execution(journal: pd.DataFrame, target_model: str, management_model: str) -> pd.DataFrame:
    required = {"target_model", "management_model", "entry_ts", "symbol", "direction", "entry", "stop"}
    missing = required - set(journal.columns)
    if missing:
        raise ValueError(f"Missing journal columns: {sorted(missing)}")
    data = journal[
        (journal["target_model"].astype(str) == target_model)
        & (journal["management_model"].astype(str) == management_model)
    ].copy()
    if data.empty:
        return data
    data["entry_ts"] = pd.to_datetime(data["entry_ts"], utc=True, errors="coerce")
    data["exit_ts"] = pd.to_datetime(data["exit_ts"], utc=True, errors="coerce")
    data["_setup_priority"] = data["setup_name"].astype(str).map(_setup_priority).fillna(99)
    identity = ["exchange", "symbol", "direction", "entry_ts", "entry", "stop"]
    identity = [c for c in identity if c in data.columns]
    return (
        data.sort_values(["entry_ts", "symbol", "_setup_priority"])
        .drop_duplicates(identity, keep="first")
        .drop(columns=["_setup_priority"], errors="ignore")
        .reset_index(drop=True)
    )


def enrich_events(events: pd.DataFrame, cfg: ForensicsRunConfig) -> pd.DataFrame:
    if events.empty:
        return events.copy()
    cache: dict[tuple[str, str, str], pd.DataFrame] = {}
    rows: list[dict] = []
    for _, event in events.iterrows():
        row = event.to_dict()
        exchange = str(row.get("exchange", "binance")).lower()
        symbol = str(row.get("symbol", "")).upper()
        tf = str(row.get("tf", "15"))
        key = (exchange, symbol, tf)
        if key not in cache:
            cache[key] = load_crypto(symbol, tf=tf, days=cfg.days, exchange=exchange, source="exchange")
        ohlcv = _prepare_ohlcv(cache[key])
        row.update(indicator_snapshot(ohlcv, pd.Timestamp(row["entry_ts"])))
        row.update(post_exit_continuation(ohlcv, row, cfg.post_bars))
        row["duration_hours"] = _duration_hours(row)
        row["is_strict_candidate"] = is_strict_candidate(row)
        row["vwap_direction_agreement"] = _vwap_direction_agreement(pd.Series(row))
        rows.append(row)
    out = pd.DataFrame(rows)
    return out.sort_values(["entry_ts", "symbol", "setup_name"]).reset_index(drop=True)


def indicator_snapshot(data: pd.DataFrame, entry_ts: pd.Timestamp) -> dict:
    base = {
        "rsi_14": np.nan,
        "rsi_bucket": "unknown",
        "ema_21": np.nan,
        "ema_55": np.nan,
        "ema_21_55_state": "unknown",
        "ema_21_slope_atr": np.nan,
        "atr_pct": np.nan,
        "atr_pct_bucket": "unknown",
        "volume_z_48": np.nan,
        "volume_bucket": "unknown",
        "session_vwap": np.nan,
        "session_vwap_dist_atr": np.nan,
        "session_vwap_state": "unknown",
        "session_vwap_extension": "unknown",
    }
    if data.empty:
        return base
    idx = _entry_index(data, entry_ts)
    if idx is None or idx < 2:
        return base
    close = pd.to_numeric(data["close"], errors="coerce")
    ema21 = close.ewm(span=21, adjust=False).mean()
    ema55 = close.ewm(span=55, adjust=False).mean()
    atr = average_true_range(data, 14)
    rsi = rsi_14(close)
    out = dict(base)
    out["rsi_14"] = float(rsi.iat[idx]) if np.isfinite(rsi.iat[idx]) else np.nan
    out["rsi_bucket"] = rsi_bucket(out["rsi_14"])
    out["ema_21"] = float(ema21.iat[idx])
    out["ema_55"] = float(ema55.iat[idx])
    atr_now = float(atr.iat[idx]) if np.isfinite(atr.iat[idx]) else np.nan
    close_now = float(close.iat[idx])
    slope = float(ema21.iat[idx] - ema21.iat[idx - 1])
    if np.isfinite(out["ema_21"]) and np.isfinite(out["ema_55"]):
        if close_now > out["ema_21"] > out["ema_55"] and slope > 0:
            out["ema_21_55_state"] = "bullish"
        elif close_now < out["ema_21"] < out["ema_55"] and slope < 0:
            out["ema_21_55_state"] = "bearish"
        else:
            out["ema_21_55_state"] = "mixed"
    out["ema_21_slope_atr"] = slope / atr_now if np.isfinite(atr_now) and atr_now > 0 else np.nan
    out["atr_pct"] = atr_now / close_now if np.isfinite(atr_now) and close_now > 0 else np.nan
    out["atr_pct_bucket"] = atr_pct_bucket(out["atr_pct"])
    if "volume" in data.columns:
        volume = pd.to_numeric(data["volume"], errors="coerce")
        roll = volume.rolling(48, min_periods=12)
        mean = roll.mean()
        std = roll.std(ddof=0)
        z = (volume - mean) / std.replace(0, np.nan)
        out["volume_z_48"] = float(z.iat[idx]) if np.isfinite(z.iat[idx]) else np.nan
        out["volume_bucket"] = volume_bucket(out["volume_z_48"])
        out.update(session_vwap_snapshot(data, entry_ts, atr))
    return out


def session_vwap_snapshot(data: pd.DataFrame, entry_ts: pd.Timestamp, atr: pd.Series) -> dict:
    """Causal UTC-day VWAP snapshot from completed candles before entry."""
    base = {
        "session_vwap": np.nan,
        "session_vwap_dist_atr": np.nan,
        "session_vwap_state": "unknown",
        "session_vwap_extension": "unknown",
    }
    idx = _completed_entry_index(data, entry_ts)
    if idx is None or idx < 1 or "volume" not in data.columns:
        return base
    volume = pd.to_numeric(data["volume"], errors="coerce")
    if not np.isfinite(volume.iat[idx]) or volume.iat[idx] <= 0:
        return base
    day = pd.Timestamp(data["ts"].iat[idx]).date()
    same_day = data.index[pd.to_datetime(data["ts"], utc=True).dt.date == day]
    same_day = same_day[same_day <= idx]
    if len(same_day) < 2:
        return base
    scoped = data.loc[same_day]
    vol = pd.to_numeric(scoped["volume"], errors="coerce").fillna(0.0)
    vol_sum = float(vol.sum())
    if vol_sum <= 0:
        return base
    typical = (pd.to_numeric(scoped["high"], errors="coerce") + pd.to_numeric(scoped["low"], errors="coerce") + pd.to_numeric(scoped["close"], errors="coerce")) / 3.0
    vwap = float((typical * vol).sum() / vol_sum)
    close_now = float(pd.to_numeric(data["close"], errors="coerce").iat[idx])
    atr_now = float(atr.iat[idx]) if idx < len(atr) and np.isfinite(atr.iat[idx]) else np.nan
    dist_atr = (close_now - vwap) / atr_now if np.isfinite(atr_now) and atr_now > 0 else np.nan
    out = dict(base)
    out["session_vwap"] = vwap
    out["session_vwap_dist_atr"] = float(dist_atr) if np.isfinite(dist_atr) else np.nan
    out["session_vwap_state"] = vwap_state(dist_atr)
    out["session_vwap_extension"] = vwap_extension(dist_atr)
    return out


def post_exit_continuation(data: pd.DataFrame, row: dict, post_bars: tuple[int, ...]) -> dict:
    out = {}
    for bars in post_bars:
        out[f"post_{bars}_fav_r"] = np.nan
        out[f"post_{bars}_adv_r"] = np.nan
    if data.empty or pd.isna(row.get("exit_ts")):
        return out
    idx = _entry_index(data, pd.Timestamp(row["exit_ts"]))
    if idx is None:
        return out
    target = float(row.get("target", np.nan))
    risk = float(row.get("risk_price", np.nan))
    if not np.isfinite(target) or not np.isfinite(risk) or risk <= 0:
        return out
    is_long = str(row.get("direction", "")).lower() == "long"
    for bars in post_bars:
        window = data.iloc[idx : min(len(data), idx + bars + 1)]
        if window.empty:
            continue
        if is_long:
            out[f"post_{bars}_fav_r"] = float((window["high"].max() - target) / risk)
            out[f"post_{bars}_adv_r"] = float((window["low"].min() - target) / risk)
        else:
            out[f"post_{bars}_fav_r"] = float((target - window["low"].min()) / risk)
            out[f"post_{bars}_adv_r"] = float((target - window["high"].max()) / risk)
    return out


def evaluate_rules(events: pd.DataFrame, cfg: ForensicsRunConfig) -> pd.DataFrame:
    specs = rule_masks(events)
    rows: list[dict] = []
    risk_cfg = PortfolioRiskConfig(
        risk_per_trade_pct=cfg.risk_per_trade_pct,
        max_open_trades=cfg.max_open_trades,
        max_open_per_symbol=cfg.max_open_per_symbol,
        daily_loss_limit_pct=cfg.daily_loss_limit_pct,
        tf_minutes=15,
    )
    for name, mask in specs.items():
        selected = events[mask.fillna(False)].copy()
        accepted, portfolio = simulate_portfolio(selected, risk_cfg)
        row = {
            "rule": name,
            "candidates": int(len(selected)),
            "accepted": int(len(accepted)),
            "symbols": int(selected["symbol"].nunique()) if not selected.empty else 0,
            "events_in_window": float(len(selected)),
            "events_per_day": float(len(selected) / _span_days(events["entry_ts"])),
            "events_per_symbol_week": float(len(selected) / max(selected["symbol"].nunique(), 1) / (_span_days(events["entry_ts"]) / 7.0)) if len(selected) else 0.0,
            "avg_duration_h": float(pd.to_numeric(selected.get("duration_hours"), errors="coerce").mean()) if len(selected) else 0.0,
            "median_duration_h": float(pd.to_numeric(selected.get("duration_hours"), errors="coerce").median()) if len(selected) else 0.0,
            **portfolio,
            "median_mfe_r": _median(selected, "mfe_r"),
            "p75_mfe_r": _quantile(selected, "mfe_r", 0.75),
            "target_exits": int((selected.get("exit_reason", pd.Series(dtype=str)) == "target").sum()) if len(selected) else 0,
            "post8_more_1r_after_target": _target_continuation_rate(selected, "post_8_fav_r", 1.0),
            "post16_more_1r_after_target": _target_continuation_rate(selected, "post_16_fav_r", 1.0),
        }
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["gross_return_pct", "max_dd_pct"], ascending=[False, True]).reset_index(drop=True)


def rule_masks(events: pd.DataFrame) -> dict[str, pd.Series]:
    if events.empty:
        return {"all_physical_fixed2_hold": pd.Series(dtype=bool)}
    ema_state = events["ema_21_55_state"] if "ema_21_55_state" in events else pd.Series("", index=events.index)
    ema_stack = _ema_stack_series(events)
    confirmed_ema_stack = ema_stack.isin([
        "bearish/bearish/mixed",
        "mixed/bullish/bullish",
        "bullish/bullish/bullish",
    ])
    weak_ema_stack = ema_stack == "bullish/bullish/mixed"
    rsi = pd.to_numeric(events["rsi_14"], errors="coerce") if "rsi_14" in events else pd.Series(np.nan, index=events.index)
    compression = events["compression_state"] if "compression_state" in events else pd.Series("", index=events.index)
    shock_alignment = events["shock_alignment"] if "shock_alignment" in events else pd.Series("", index=events.index)
    vwap_agreement = (
        events["vwap_direction_agreement"]
        if "vwap_direction_agreement" in events
        else events.apply(_vwap_direction_agreement, axis=1)
    )
    strict = events.apply(is_strict_candidate, axis=1)
    late_us = events["setup_name"].astype(str) == "late_us_short_bull_flush_ce"
    late_us_fade = late_us & events["mtf_mode"].isin(["countertrend", "range_or_transition"])
    return {
        "all_physical_fixed2_hold": pd.Series(True, index=events.index),
        "strict_candidates": strict,
        "strict_vwap_agrees": strict & (vwap_agreement == "agrees"),
        "strict_ema_stack_confirmed": strict & confirmed_ema_stack,
        "strict_late_us_vwap_agrees": strict & (~late_us | (vwap_agreement == "agrees")),
        "strict_late_us_no_weak_ema": strict & (~late_us | ~weak_ema_stack),
        "late_us_fade_vwap_agrees": late_us_fade & (vwap_agreement == "agrees"),
        "strict_direction_quality": strict & (vwap_agreement == "agrees") & confirmed_ema_stack,
        "london_trend_aligned": events["setup_name"].astype(str).str.contains("london_long_middle_local", na=False)
        & (events["mtf_mode"] == "trend_aligned"),
        "london_trend_ema_bullish": events["setup_name"].astype(str).str.contains("london_long_middle_local", na=False)
        & (events["mtf_mode"] == "trend_aligned")
        & (ema_state == "bullish"),
        "london_trend_rsi_not_overbought": events["setup_name"].astype(str).str.contains("london_long_middle_local", na=False)
        & (events["mtf_mode"] == "trend_aligned")
        & (rsi <= 70),
        "ny_13_range_reversal": (events["setup_name"] == "ny_long_neutral_reversal_ce")
        & (events["entry_hour_utc"].astype(int) == 13)
        & (events["mtf_mode"] == "range_or_transition"),
        "ny_13_expanded_or_opposing": (events["setup_name"] == "ny_long_neutral_reversal_ce")
        & (events["entry_hour_utc"].astype(int) == 13)
        & (events["mtf_mode"] == "range_or_transition")
        & ((compression == "expanded") | (shock_alignment == "opposing_shock")),
        "late_us_fade": late_us_fade,
        "late_us_fade_no_aligned_shock": late_us_fade & (shock_alignment != "aligned_shock"),
    }


def evaluate_stress_matrix(events: pd.DataFrame, cfg: ForensicsRunConfig) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    data = events.copy()
    data["entry_ts"] = pd.to_datetime(data["entry_ts"], utc=True, errors="coerce")
    min_ts = data["entry_ts"].min()
    max_ts = data["entry_ts"].max()
    windows = [
        ("60d", data),
        ("first30d", data[data["entry_ts"] < min_ts + pd.Timedelta(days=30)].copy()),
        ("30d", data[data["entry_ts"] >= max_ts - pd.Timedelta(days=30)].copy()),
    ]
    scenarios = [
        ("baseline", 0.0, 0.0),
        ("realistic_10bps", 6.0, 2.0),
        ("high_22bps", 12.0, 5.0),
        ("punitive_40bps", 20.0, 10.0),
        ("nightmare_60bps", 30.0, 15.0),
    ]
    keep_rules = {"all_physical_fixed2_hold", *VALIDATION_RULES}
    risk_cfg = PortfolioRiskConfig(
        risk_per_trade_pct=cfg.risk_per_trade_pct,
        max_open_trades=cfg.max_open_trades,
        max_open_per_symbol=cfg.max_open_per_symbol,
        daily_loss_limit_pct=cfg.daily_loss_limit_pct,
        tf_minutes=15,
    )
    rows: list[dict] = []
    for window, subset in windows:
        specs = rule_masks(subset)
        for rule, mask in specs.items():
            if rule not in keep_rules:
                continue
            selected = subset[mask.fillna(False)].copy()
            for scenario, fee_round_trip_bps, slippage_side_bps in scenarios:
                stressed = apply_cost_stress(
                    selected,
                    fee_round_trip_bps=fee_round_trip_bps,
                    slippage_side_bps=slippage_side_bps,
                )
                accepted, portfolio = simulate_portfolio(stressed, risk_cfg)
                avg_extra = _median(stressed, "extra_cost_r")
                rows.append({
                    "window": window,
                    "rule": rule,
                    "scenario": scenario,
                    "fee_round_trip_bps": fee_round_trip_bps,
                    "slippage_side_bps": slippage_side_bps,
                    "candidates": int(len(stressed)),
                    "accepted": int(len(accepted)),
                    "median_extra_cost_r": avg_extra,
                    "events_per_day": float(len(stressed) / _span_days(subset["entry_ts"])) if len(subset) else 0.0,
                    **portfolio,
                })
    return pd.DataFrame(rows).sort_values(["window", "rule", "fee_round_trip_bps", "slippage_side_bps"]).reset_index(drop=True)


def evaluate_extreme_config_matrix(events: pd.DataFrame, cfg: ForensicsRunConfig) -> pd.DataFrame:
    """Stress portfolio mechanics while keeping signal rules fixed."""
    if events.empty:
        return pd.DataFrame()
    data = events.copy()
    data["entry_ts"] = pd.to_datetime(data["entry_ts"], utc=True, errors="coerce")
    min_ts = data["entry_ts"].min()
    max_ts = data["entry_ts"].max()
    windows = [
        ("60d", data),
        ("first30d", data[data["entry_ts"] < min_ts + pd.Timedelta(days=30)].copy()),
        ("30d", data[data["entry_ts"] >= max_ts - pd.Timedelta(days=30)].copy()),
    ]
    config_specs = [
        ("micro_risk_tight", 0.001, 3, 1, 0.0025),
        ("base", cfg.risk_per_trade_pct, cfg.max_open_trades, cfg.max_open_per_symbol, cfg.daily_loss_limit_pct),
        ("conservative", 0.0015, 4, 1, 0.0035),
        ("loose_concurrency", 0.002, 10, 2, 0.0075),
        ("aggressive", 0.003, 8, 2, 0.0100),
        ("prop_strict", 0.0025, 4, 1, 0.0040),
    ]
    scenario_specs = [
        ("baseline", 0.0, 0.0),
        ("high_22bps", 12.0, 5.0),
        ("punitive_40bps", 20.0, 10.0),
        ("nightmare_60bps", 30.0, 15.0),
    ]
    keep_rules = VALIDATION_RULES
    rows: list[dict] = []
    for window, subset in windows:
        specs = rule_masks(subset)
        for rule in keep_rules:
            mask = specs.get(rule, pd.Series(False, index=subset.index))
            selected = subset[mask.fillna(False)].copy()
            for scenario, fee_round_trip_bps, slippage_side_bps in scenario_specs:
                stressed = apply_cost_stress(
                    selected,
                    fee_round_trip_bps=fee_round_trip_bps,
                    slippage_side_bps=slippage_side_bps,
                )
                for config_name, risk_pct, max_open, max_per_symbol, daily_limit in config_specs:
                    risk_cfg = PortfolioRiskConfig(
                        risk_per_trade_pct=risk_pct,
                        max_open_trades=max_open,
                        max_open_per_symbol=max_per_symbol,
                        daily_loss_limit_pct=daily_limit,
                        tf_minutes=15,
                    )
                    accepted, portfolio = simulate_portfolio(stressed, risk_cfg)
                    rows.append({
                        "window": window,
                        "rule": rule,
                        "scenario": scenario,
                        "config": config_name,
                        "risk_per_trade_pct": risk_pct,
                        "max_open_trades": max_open,
                        "max_open_per_symbol": max_per_symbol,
                        "daily_loss_limit_pct": daily_limit,
                        "candidates": int(len(stressed)),
                        "accepted": int(len(accepted)),
                        "median_extra_cost_r": _median(stressed, "extra_cost_r"),
                        "events_per_day": float(len(stressed) / _span_days(subset["entry_ts"])) if len(subset) else 0.0,
                        **portfolio,
                    })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["window", "rule", "scenario", "config"]).reset_index(drop=True)


def evaluate_rolling_validation(events: pd.DataFrame, cfg: ForensicsRunConfig) -> pd.DataFrame:
    """Validate selected rules across rolling calendar windows."""
    if events.empty:
        return pd.DataFrame()
    data = events.copy()
    data["entry_ts"] = pd.to_datetime(data["entry_ts"], utc=True, errors="coerce")
    data = data.dropna(subset=["entry_ts"]).sort_values("entry_ts").reset_index(drop=True)
    if data.empty:
        return pd.DataFrame()

    rules = VALIDATION_RULES
    scenarios = [
        ("baseline", 0.0, 0.0),
        ("high_22bps", 12.0, 5.0),
        ("punitive_40bps", 20.0, 10.0),
        ("nightmare_60bps", 30.0, 15.0),
    ]
    configs = [
        ("micro_risk_tight", 0.001, 3, 1, 0.0025),
        ("conservative", 0.0015, 4, 1, 0.0035),
        ("base", cfg.risk_per_trade_pct, cfg.max_open_trades, cfg.max_open_per_symbol, cfg.daily_loss_limit_pct),
        ("prop_strict", 0.0025, 4, 1, 0.0040),
    ]
    rows: list[dict] = []
    first = data["entry_ts"].min().normalize()
    last = data["entry_ts"].max().normalize() + pd.Timedelta(days=1)
    for window_days, step_days in [(14, 7), (30, 7), (45, 7)]:
        start = first
        window_id = 0
        while start + pd.Timedelta(days=window_days) <= last:
            end = start + pd.Timedelta(days=window_days)
            subset = data[(data["entry_ts"] >= start) & (data["entry_ts"] < end)].copy()
            masks = rule_masks(subset) if not subset.empty else {}
            for rule in rules:
                mask = masks.get(rule, pd.Series(False, index=subset.index))
                selected = subset[mask.fillna(False)].copy() if not subset.empty else subset.copy()
                for scenario, fee_round_trip_bps, slippage_side_bps in scenarios:
                    stressed = apply_cost_stress(
                        selected,
                        fee_round_trip_bps=fee_round_trip_bps,
                        slippage_side_bps=slippage_side_bps,
                    )
                    for config_name, risk_pct, max_open, max_per_symbol, daily_limit in configs:
                        risk_cfg = PortfolioRiskConfig(
                            risk_per_trade_pct=risk_pct,
                            max_open_trades=max_open,
                            max_open_per_symbol=max_per_symbol,
                            daily_loss_limit_pct=daily_limit,
                            tf_minutes=15,
                        )
                        accepted, portfolio = simulate_portfolio(stressed, risk_cfg)
                        passed, reason = _rolling_gate(portfolio, scenario, window_days)
                        rows.append({
                            "window_days": window_days,
                            "step_days": step_days,
                            "window_id": window_id,
                            "window_start": start,
                            "window_end": end,
                            "rule": rule,
                            "scenario": scenario,
                            "config": config_name,
                            "candidates": int(len(stressed)),
                            "accepted": int(len(accepted)),
                            "events_per_day": float(len(stressed) / window_days),
                            "median_extra_cost_r": _median(stressed, "extra_cost_r"),
                            "passed_gate": bool(passed),
                            "fail_reason": reason,
                            **portfolio,
                        })
            start += pd.Timedelta(days=step_days)
            window_id += 1
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["window_days", "window_start", "rule", "scenario", "config"]
    ).reset_index(drop=True)


def summarize_rolling_validation(rolling: pd.DataFrame) -> pd.DataFrame:
    if rolling.empty:
        return pd.DataFrame()
    rows: list[dict] = []
    groups = rolling.groupby(["window_days", "rule", "scenario", "config"], dropna=False)
    for keys, group in groups:
        rows.append({
            "window_days": int(keys[0]),
            "rule": keys[1],
            "scenario": keys[2],
            "config": keys[3],
            "windows": int(len(group)),
            "pass_rate": float(group["passed_gate"].mean()),
            "passed_windows": int(group["passed_gate"].sum()),
            "negative_windows": int((pd.to_numeric(group["gross_return_pct"], errors="coerce") <= 0).sum()),
            "median_return_pct": _median(group, "gross_return_pct"),
            "worst_return_pct": float(pd.to_numeric(group["gross_return_pct"], errors="coerce").min()),
            "worst_dd_pct": float(pd.to_numeric(group["max_dd_pct"], errors="coerce").max()),
            "median_pf": _median(group, "profit_factor"),
            "median_win_rate": _median(group, "win_rate"),
            "min_accepted": int(pd.to_numeric(group["accepted"], errors="coerce").min()),
            "median_events_per_day": _median(group, "events_per_day"),
        })
    return pd.DataFrame(rows).sort_values(
        ["pass_rate", "median_return_pct", "worst_return_pct"],
        ascending=[False, False, False],
    ).reset_index(drop=True)


def collect_rolling_window_trades(events: pd.DataFrame, rolling: pd.DataFrame, cfg: ForensicsRunConfig) -> pd.DataFrame:
    """Materialize accepted trades for the rolling validation rows worth diagnosing."""
    if events.empty or rolling.empty:
        return pd.DataFrame()
    data = events.copy()
    data["entry_ts"] = pd.to_datetime(data["entry_ts"], utc=True, errors="coerce")
    data = data.dropna(subset=["entry_ts"]).sort_values("entry_ts").reset_index(drop=True)
    focus = rolling[
        (rolling["rule"] == "strict_candidates")
        & (rolling["config"] == "base")
        & (rolling["window_days"].isin([14, 30, 45]))
        & (rolling["scenario"].isin(["baseline", "high_22bps", "punitive_40bps", "nightmare_60bps"]))
    ].copy()
    if focus.empty:
        return pd.DataFrame()
    scenario_costs = {
        "baseline": (0.0, 0.0),
        "high_22bps": (12.0, 5.0),
        "punitive_40bps": (20.0, 10.0),
        "nightmare_60bps": (30.0, 15.0),
    }
    risk_cfg = PortfolioRiskConfig(
        risk_per_trade_pct=cfg.risk_per_trade_pct,
        max_open_trades=cfg.max_open_trades,
        max_open_per_symbol=cfg.max_open_per_symbol,
        daily_loss_limit_pct=cfg.daily_loss_limit_pct,
        tf_minutes=15,
    )
    rows: list[pd.DataFrame] = []
    for row in focus.itertuples(index=False):
        start = pd.Timestamp(row.window_start)
        end = pd.Timestamp(row.window_end)
        subset = data[(data["entry_ts"] >= start) & (data["entry_ts"] < end)].copy()
        if subset.empty:
            continue
        mask = rule_masks(subset).get("strict_candidates", pd.Series(False, index=subset.index))
        selected = subset[mask.fillna(False)].copy()
        fee, slip = scenario_costs.get(str(row.scenario), (0.0, 0.0))
        stressed = apply_cost_stress(selected, fee_round_trip_bps=fee, slippage_side_bps=slip)
        accepted, _portfolio = simulate_portfolio(stressed, risk_cfg)
        if accepted.empty:
            continue
        accepted = accepted.copy()
        accepted["window_days"] = int(row.window_days)
        accepted["window_id"] = int(row.window_id)
        accepted["window_start"] = start
        accepted["window_end"] = end
        accepted["scenario"] = str(row.scenario)
        accepted["rolling_passed_gate"] = bool(row.passed_gate)
        accepted["rolling_fail_reason"] = str(row.fail_reason)
        accepted["rolling_window_return_pct"] = float(row.gross_return_pct)
        accepted["rolling_window_pf"] = float(row.profit_factor)
        rows.append(accepted)
    if not rows:
        return pd.DataFrame()
    out = pd.concat(rows, ignore_index=True)
    return out.sort_values(["window_days", "scenario", "window_start", "entry_ts", "symbol"]).reset_index(drop=True)


def diagnose_rolling_failures(rolling_trades: pd.DataFrame) -> pd.DataFrame:
    if rolling_trades.empty:
        return pd.DataFrame()
    dims = [
        "symbol",
        "setup_name",
        "mtf_mode",
        "foundation_state",
        "consolidation_state",
        "trend_strength",
        "entry_hour_utc",
        "ctx_240_regime",
        "global_ema_state",
        "middle_ema_state",
        "local_ema_state",
        "compression_state",
        "shock_alignment",
        "rsi_bucket",
        "atr_pct_bucket",
        "volume_bucket",
        "session_vwap_state",
        "session_vwap_extension",
        "vwap_direction_agreement",
        "exit_reason",
    ]
    rows: list[dict] = []
    for scenario in ["high_22bps", "punitive_40bps", "nightmare_60bps"]:
        data = rolling_trades[rolling_trades["scenario"] == scenario].copy()
        if data.empty:
            continue
        for window_days in [14, 30, 45]:
            scoped = data[data["window_days"] == window_days].copy()
            if scoped.empty:
                continue
            for dim in dims:
                if dim not in scoped.columns:
                    continue
                values = scoped[dim].fillna("unknown").astype(str)
                scoped = scoped.assign(_dim_value=values)
                for value, group in scoped.groupby("_dim_value", dropna=False):
                    failed = group[~group["rolling_passed_gate"].astype(bool)]
                    passed = group[group["rolling_passed_gate"].astype(bool)]
                    if len(group) < 3:
                        continue
                    failed_net = pd.to_numeric(failed["net_r"], errors="coerce")
                    passed_net = pd.to_numeric(passed["net_r"], errors="coerce")
                    all_net = pd.to_numeric(group["net_r"], errors="coerce")
                    rows.append({
                        "scenario": scenario,
                        "window_days": window_days,
                        "feature": dim,
                        "value": value,
                        "events": int(len(group)),
                        "failed_events": int(len(failed)),
                        "passed_events": int(len(passed)),
                        "failed_window_share": float(len(failed) / len(group)),
                        "avg_r": float(all_net.mean()) if len(all_net) else 0.0,
                        "failed_avg_r": float(failed_net.mean()) if len(failed_net) else 0.0,
                        "passed_avg_r": float(passed_net.mean()) if len(passed_net) else 0.0,
                        "failed_pf": profit_factor(failed_net),
                        "passed_pf": profit_factor(passed_net),
                        "win_rate": float((all_net > 0).mean()) if len(all_net) else 0.0,
                        "failed_win_rate": float((failed_net > 0).mean()) if len(failed_net) else 0.0,
                        "passed_win_rate": float((passed_net > 0).mean()) if len(passed_net) else 0.0,
                    })
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    return out.sort_values(
        ["scenario", "window_days", "failed_window_share", "failed_events", "failed_avg_r"],
        ascending=[True, True, False, False, True],
    ).reset_index(drop=True)


def build_foundation_review_packet(rolling_trades: pd.DataFrame, per_bucket: int = 12) -> pd.DataFrame:
    """Export targeted rolling-failure cases in the existing review UI schema."""
    if rolling_trades.empty:
        return pd.DataFrame()
    data = rolling_trades.copy()
    data["entry_ts"] = pd.to_datetime(data["entry_ts"], utc=True, errors="coerce")
    data["net_r"] = pd.to_numeric(data["net_r"], errors="coerce")
    data["mfe_r"] = pd.to_numeric(data.get("mfe_r"), errors="coerce")
    data["mae_r"] = pd.to_numeric(data.get("mae_r"), errors="coerce")
    post16 = pd.to_numeric(data["post_16_fav_r"], errors="coerce") if "post_16_fav_r" in data else pd.Series(np.nan, index=data.index)
    samples: list[pd.DataFrame] = []
    specs = [
        ("punitive_failed_loser", data[(data["scenario"] == "punitive_40bps") & (~data["rolling_passed_gate"].astype(bool)) & (data["net_r"] <= 0)].sort_values("net_r")),
        ("nightmare_failed_loser", data[(data["scenario"] == "nightmare_60bps") & (~data["rolling_passed_gate"].astype(bool)) & (data["net_r"] <= 0)].sort_values("net_r")),
        ("low_return_baseline", data[(data["scenario"] == "baseline") & (data["rolling_window_return_pct"] < 0.015)].sort_values(["rolling_window_return_pct", "net_r"])),
        ("high_mae_winner", data[(data["net_r"] > 0) & (data["mae_r"] <= -0.75)].sort_values("mae_r")),
        ("target_too_short_winner", data[(data["net_r"] > 0) & (post16 >= 1.0)].assign(post_16_fav_r=post16).sort_values("post_16_fav_r", ascending=False)),
        ("clean_winner", data[(data["scenario"] == "baseline") & (data["rolling_passed_gate"].astype(bool)) & (data["net_r"] > 0)].sort_values("net_r", ascending=False)),
    ]
    seen: set[str] = set()
    for bucket, group in specs:
        if group.empty:
            continue
        take = group.copy()
        take["_review_key"] = _review_key_series(take)
        take = take.drop_duplicates("_review_key", keep="first")
        take = take[~take["_review_key"].isin(seen)].head(per_bucket).copy()
        seen.update(take["_review_key"].astype(str))
        if take.empty:
            continue
        take["review_bucket"] = bucket
        samples.append(take.drop(columns=["_review_key"], errors="ignore"))
    if not samples:
        return pd.DataFrame()
    return _foundation_to_review_schema(pd.concat(samples, ignore_index=True))


def _foundation_to_review_schema(trades: pd.DataFrame) -> pd.DataFrame:
    out = trades.copy()
    out["ts"] = pd.to_datetime(out["entry_ts"], utc=True)
    out["predictor"] = "crypto_foundation_rolling"
    out["session"] = out.get("session_utc", "")
    out["direction"] = out.get("direction", "short")
    out["entry_price"] = out["entry"].astype(float)
    out["sl"] = out["stop"].astype(float)
    out["tp1"] = out["target"].astype(float)
    out["risk_price"] = out["risk_price"].astype(float)
    out["outcome_1.5r"] = out["net_r"].astype(float)
    out["hit_1.5r"] = out["hit_target"].astype(bool)
    out["notes_hint"] = out.apply(_foundation_notes_hint, axis=1)
    cols = [
        "ts",
        "symbol",
        "exchange",
        "tf",
        "predictor",
        "session",
        "direction",
        "entry_price",
        "sl",
        "tp1",
        "risk_price",
        "outcome_1.5r",
        "hit_1.5r",
        "mfe_r",
        "mae_r",
        "exit_reason",
        "review_bucket",
        "setup_name",
        "mtf_mode",
        "entry_model",
        "target_model",
        "management_model",
        "scenario",
        "window_days",
        "rolling_fail_reason",
        "rolling_window_return_pct",
        "rsi_bucket",
        "atr_pct_bucket",
        "volume_bucket",
        "ema_21_55_state",
        "session_vwap_state",
        "session_vwap_extension",
        "vwap_direction_agreement",
        "foundation_state",
        "consolidation_state",
        "trend_strength",
        "compression_state",
        "shock_alignment",
        "notes_hint",
    ]
    for col in cols:
        if col not in out.columns:
            out[col] = np.nan
    order = {
        "punitive_failed_loser": 0,
        "nightmare_failed_loser": 1,
        "low_return_baseline": 2,
        "high_mae_winner": 3,
        "target_too_short_winner": 4,
        "clean_winner": 5,
    }
    out["_bucket_order"] = out["review_bucket"].map(order).fillna(99)
    return out.sort_values(["_bucket_order", "symbol", "ts"])[cols].reset_index(drop=True)


def _foundation_notes_hint(row: pd.Series) -> str:
    bucket = str(row.get("review_bucket", ""))
    if bucket == "punitive_failed_loser":
        return "Punitive-cost failed-window loser: decide if direction was wrong, entry was late, or stop/target too tight for fees."
    if bucket == "nightmare_failed_loser":
        return "Nightmare-cost failed-window loser: likely execution-fragile. Check if this trade should be gated out entirely."
    if bucket == "low_return_baseline":
        return "Low-return baseline window: find what made normal-cost edge weak here."
    if bucket == "high_mae_winner":
        return "High-MAE winner: direction eventually worked, but entry/stop may be weak."
    if bucket == "target_too_short_winner":
        return "Target-too-short winner: fixed 2R may leave continuation; check next liquidity target."
    if bucket == "clean_winner":
        return "Clean winner: extract what losing windows lacked."
    return "Judge direction, entry confirmation, stop, target, management, and cost fragility."


def _review_key_series(trades: pd.DataFrame) -> pd.Series:
    entry_ts = pd.to_datetime(trades["entry_ts"], utc=True, errors="coerce").astype(str)
    return trades["exchange"].astype(str) + "|" + trades["symbol"].astype(str) + "|" + entry_ts + "|" + trades["entry"].astype(str)


def _label_ts(value: object) -> str:
    ts = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(ts):
        return ""
    return pd.Timestamp(ts).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def analyze_foundation_review_labels(review_packet: pd.DataFrame, labels_path: Path = DEFAULT_REVIEW_LABELS) -> pd.DataFrame:
    """Join saved UI labels to the current foundation review packet."""
    if review_packet.empty or not labels_path.exists():
        return pd.DataFrame()
    import json

    try:
        labels = json.loads(labels_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return pd.DataFrame()
    rows: list[dict] = []
    for key, value in labels.items():
        if not isinstance(value, dict) or not value.get("entry_time"):
            continue
        rows.append({
            "label_key": key,
            "symbol": value.get("symbol"),
            "tf": str(value.get("tf")),
            "ts_norm": _label_ts(value.get("entry_time")),
            "user_label": value.get("label") if value.get("label") else "unlabeled",
            "user_notes": value.get("notes", ""),
        })
    if not rows:
        return pd.DataFrame()
    label_df = pd.DataFrame(rows)
    packet = review_packet.copy()
    packet["tf"] = packet["tf"].astype(str)
    packet["ts_norm"] = pd.to_datetime(packet["ts"], utc=True, errors="coerce").dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    joined = packet.merge(label_df, on=["symbol", "tf", "ts_norm"], how="inner")
    if joined.empty:
        return pd.DataFrame()
    return joined.sort_values(["symbol", "ts_norm", "label_key"]).reset_index(drop=True)


def evaluate_frequency_expansion(events: pd.DataFrame, cfg: ForensicsRunConfig) -> pd.DataFrame:
    """Compare frequency-improving variants against the current strict rule."""
    if events.empty:
        return pd.DataFrame()
    data = events.copy()
    data["entry_ts"] = pd.to_datetime(data["entry_ts"], utc=True, errors="coerce")
    data = data.dropna(subset=["entry_ts"]).sort_values("entry_ts").reset_index(drop=True)
    if data.empty:
        return pd.DataFrame()
    max_ts = data["entry_ts"].max()
    windows = [
        ("60d", data),
        ("30d", data[data["entry_ts"] >= max_ts - pd.Timedelta(days=30)].copy()),
    ]
    scenarios = [
        ("baseline", 0.0, 0.0),
        ("punitive_40bps", 20.0, 10.0),
    ]
    risk_cfg = PortfolioRiskConfig(
        risk_per_trade_pct=0.0015,
        max_open_trades=4,
        max_open_per_symbol=1,
        daily_loss_limit_pct=0.0035,
        tf_minutes=15,
    )
    rows: list[dict] = []
    for window, subset in windows:
        variants = frequency_variant_masks(subset)
        span = _span_days(subset["entry_ts"]) if not subset.empty else 1.0
        for variant, mask in variants.items():
            selected = subset[mask.fillna(False)].copy() if not subset.empty else subset.copy()
            symbols = int(selected["symbol"].nunique()) if not selected.empty else 0
            for scenario, fee_round_trip_bps, slippage_side_bps in scenarios:
                stressed = apply_cost_stress(
                    selected,
                    fee_round_trip_bps=fee_round_trip_bps,
                    slippage_side_bps=slippage_side_bps,
                )
                accepted, portfolio = simulate_portfolio(stressed, risk_cfg)
                rows.append({
                    "window": window,
                    "variant": variant,
                    "scenario": scenario,
                    "candidates": int(len(selected)),
                    "accepted": int(len(accepted)),
                    "symbols": symbols,
                    "events_per_day": float(len(selected) / span) if span else 0.0,
                    "events_per_symbol_week": float(len(selected) / max(symbols, 1) / (span / 7.0)) if span else 0.0,
                    "median_extra_cost_r": _median(stressed, "extra_cost_r"),
                    **portfolio,
                    "frequency_verdict": _frequency_verdict(selected, portfolio, scenario),
                })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["window", "scenario", "gross_return_pct", "events_per_symbol_week"],
        ascending=[True, True, False, False],
    ).reset_index(drop=True)


def frequency_variant_masks(events: pd.DataFrame) -> dict[str, pd.Series]:
    if events.empty:
        return {}
    strict = rule_masks(events).get("strict_candidates", pd.Series(False, index=events.index)).fillna(False)
    setup = events["setup_name"].astype(str)
    structure_confirmation = events.get("structure_confirmation", pd.Series("", index=events.index)).astype(str)
    ema = events.get("ema_21_55_state", pd.Series("", index=events.index)).astype(str)
    local_ema = events.get("local_ema_state", pd.Series("", index=events.index)).astype(str)
    mtf_mode = events.get("mtf_mode", pd.Series("", index=events.index)).astype(str)
    ny_or_london = setup.isin(["ny_long_neutral_reversal_ce", "london_long_middle_local_retest"])
    confirmed_enough = structure_confirmation.isin(["mtf_and_local", "mtf_only", "local_only", "range_unconfirmed"])
    late_us = setup == "late_us_short_bull_flush_ce"
    return {
        "strict_current": strict,
        "strict_no_late_us": strict & ~late_us,
        "strict_ema_not_mixed": strict & (ema != "mixed"),
        "strict_late_us_no_mixed_ema": strict & (~late_us | (ema != "mixed")),
        "strict_late_us_bearish_ema": strict & (~late_us | (ema == "bearish") | (local_ema == "bearish")),
        "strict_no_countertrend": strict & (mtf_mode != "countertrend"),
        "ny_london_plus_non_strict_confirmed": ny_or_london & confirmed_enough,
        "all_foundation_physical": pd.Series(True, index=events.index),
    }


def _frequency_verdict(selected: pd.DataFrame, portfolio: dict, scenario: str) -> str:
    if selected.empty:
        return "reject_empty"
    pf = float(portfolio.get("profit_factor", 0.0))
    gross = float(portfolio.get("gross_return_pct", 0.0))
    max_dd = float(portfolio.get("max_dd_pct", 0.0))
    epsw = float(len(selected) / max(selected["symbol"].nunique(), 1) / (_span_days(selected["entry_ts"]) / 7.0))
    if gross <= 0 or pf < 1.2:
        return "reject_more_trades_break_edge"
    if scenario == "punitive_40bps" and (max_dd > 0.02 or pf < 1.5):
        return "research_only_fragile_costs"
    if epsw < 1.0:
        return "quality_ok_frequency_sparse"
    return "candidate_frequency_improves"


def evaluate_direction_audit(events: pd.DataFrame, *, min_events: int = 5) -> pd.DataFrame:
    """Summarize direction quality by structure, trend, VWAP, and tape context."""
    if events.empty:
        return pd.DataFrame()
    data = events.copy()
    strict_mask = rule_masks(data).get("strict_candidates", pd.Series(False, index=data.index)).fillna(False)
    data["direction_stack"] = _direction_stack_series(data)
    data["ema_stack"] = _ema_stack_series(data)
    data["vwap_direction_agreement"] = data.apply(_vwap_direction_agreement, axis=1)
    dimensions = [
        "direction_stack",
        "mtf_mode",
        "structure_confirmation",
        "foundation_state",
        "consolidation_state",
        "trend_strength",
        "context_regime",
        "middle_regime",
        "local_regime",
        "ema_stack",
        "global_ema_state",
        "middle_ema_state",
        "local_ema_state",
        "ema_21_55_state",
        "session_vwap_state",
        "session_vwap_extension",
        "vwap_direction_agreement",
        "compression_state",
        "shock_alignment",
        "setup_name",
        "session_utc",
    ]
    rows: list[dict] = []
    for scope, subset in [("all_physical", data), ("strict", data[strict_mask].copy())]:
        if subset.empty:
            continue
        for feature in dimensions:
            if feature not in subset.columns:
                continue
            values = subset[feature].fillna("unknown").astype(str)
            for value, group in subset.assign(_feature_value=values).groupby("_feature_value", dropna=False):
                if len(group) < min_events:
                    continue
                net = pd.to_numeric(group["net_r"], errors="coerce")
                rows.append({
                    "scope": scope,
                    "feature": feature,
                    "value": value,
                    "events": int(len(group)),
                    "events_per_symbol_week": _events_per_symbol_week(group),
                    "avg_r": float(net.mean()) if len(net) else 0.0,
                    "profit_factor": profit_factor(net),
                    "win_rate": float((net > 0).mean()) if len(net) else 0.0,
                    "direction_accuracy": _bool_rate(group, "direction_correct"),
                    "bad_direction_rate": _bool_rate(group, "bad_direction"),
                    "bad_entry_rate": _bool_rate(group, "bad_entry"),
                    "stop_rate": _bool_rate(group, "hit_stop"),
                    "expiry_rate": float((group["exit_reason"].astype(str) == "expiry").mean()) if "exit_reason" in group else np.nan,
                    "median_mfe_r": _median(group, "mfe_r"),
                    "median_mae_r": _median(group, "mae_r"),
                })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["scope", "feature", "avg_r", "events"],
        ascending=[True, True, False, False],
    ).reset_index(drop=True)


def _direction_stack_series(data: pd.DataFrame) -> pd.Series:
    cols = ["context_regime", "middle_regime", "local_regime"]
    values = []
    for _, row in data.iterrows():
        parts = [str(row.get(col, "missing")) for col in cols]
        values.append("/".join(parts))
    return pd.Series(values, index=data.index)


def _ema_stack_series(data: pd.DataFrame) -> pd.Series:
    cols = ["global_ema_state", "middle_ema_state", "local_ema_state"]
    values = []
    for _, row in data.iterrows():
        parts = [str(row.get(col, "unknown")) for col in cols]
        values.append("/".join(parts))
    return pd.Series(values, index=data.index)


def _vwap_direction_agreement(row: pd.Series) -> str:
    direction = str(row.get("direction", "")).lower()
    state = str(row.get("session_vwap_state", "unknown"))
    if state == "unknown" or direction not in {"long", "short"}:
        return "unknown"
    if state == "near":
        return "near_vwap"
    if direction == "long" and state == "above":
        return "agrees"
    if direction == "short" and state == "below":
        return "agrees"
    return "opposes"


def evaluate_contribution_concentration(events: pd.DataFrame) -> pd.DataFrame:
    """Measure whether strict candidate returns depend on one symbol/setup/session."""
    if events.empty:
        return pd.DataFrame()
    masks = rule_masks(events)
    strict = events[masks.get("strict_candidates", pd.Series(False, index=events.index)).fillna(False)].copy()
    if strict.empty:
        return pd.DataFrame()
    stressed = apply_cost_stress(strict, fee_round_trip_bps=20.0, slippage_side_bps=10.0)
    accepted, _portfolio = simulate_portfolio(
        stressed,
        PortfolioRiskConfig(
            risk_per_trade_pct=0.0015,
            max_open_trades=4,
            max_open_per_symbol=1,
            daily_loss_limit_pct=0.0035,
            tf_minutes=15,
        ),
    )
    if accepted.empty:
        return pd.DataFrame()
    total_r = float(pd.to_numeric(accepted["net_r"], errors="coerce").sum())
    rows: list[dict] = []
    for dim in ["symbol", "setup_name", "session_utc", "mtf_mode", "entry_hour_utc"]:
        if dim not in accepted.columns:
            continue
        for value, group in accepted.groupby(dim, dropna=False):
            net = pd.to_numeric(group["net_r"], errors="coerce")
            contribution_r = float(net.sum())
            rows.append({
                "dimension": dim,
                "value": value,
                "events": int(len(group)),
                "total_r": contribution_r,
                "share_of_total_r": float(contribution_r / total_r) if total_r else 0.0,
                "avg_r": float(net.mean()) if len(net) else 0.0,
                "profit_factor": profit_factor(net),
                "win_rate": float((net > 0).mean()) if len(net) else 0.0,
            })
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["dimension", "total_r"], ascending=[True, False]).reset_index(drop=True)


def _rolling_gate(portfolio: dict, scenario: str, window_days: int) -> tuple[bool, str]:
    accepted = int(portfolio.get("accepted", 0))
    min_trades = 8 if window_days == 14 else 15 if window_days == 30 else 20
    gross = float(portfolio.get("gross_return_pct", 0.0))
    max_dd = float(portfolio.get("max_dd_pct", 0.0))
    daily_dd = float(portfolio.get("daily_max_dd_pct", 0.0))
    pf = float(portfolio.get("profit_factor", 0.0))
    required_pf = {
        "baseline": 1.2,
        "high_22bps": 1.5,
        "punitive_40bps": 1.2,
        "nightmare_60bps": 1.0,
    }.get(scenario, 1.2)
    failures: list[str] = []
    if accepted < min_trades:
        failures.append("low_trades")
    if gross <= 0:
        failures.append("negative_return")
    if max_dd > 0.02:
        failures.append("dd_gt_2pct")
    if daily_dd > 0.0075:
        failures.append("daily_dd_gt_0_75pct")
    if pf < required_pf:
        failures.append("pf_low")
    return (not failures, "pass" if not failures else ",".join(failures))


def apply_cost_stress(
    trades: pd.DataFrame,
    *,
    fee_round_trip_bps: float,
    slippage_side_bps: float,
) -> pd.DataFrame:
    if trades.empty:
        out = trades.copy()
        out["extra_cost_r"] = pd.Series(dtype=float)
        return out
    out = trades.copy()
    total_bps = float(fee_round_trip_bps) + 2.0 * float(slippage_side_bps)
    entry = pd.to_numeric(out["entry"], errors="coerce").abs()
    risk = pd.to_numeric(out["risk_price"], errors="coerce").abs().replace(0, np.nan)
    extra_r = (total_bps / 10_000.0) * (entry / risk)
    out["extra_cost_r"] = extra_r.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    out["net_r"] = pd.to_numeric(out["net_r"], errors="coerce").fillna(0.0) - out["extra_cost_r"]
    return out


def evaluate_windowed_rules(events: pd.DataFrame, cfg: ForensicsRunConfig) -> pd.DataFrame:
    if events.empty:
        return evaluate_rules(events, cfg)
    data = events.copy()
    data["entry_ts"] = pd.to_datetime(data["entry_ts"], utc=True, errors="coerce")
    min_ts = data["entry_ts"].min()
    max_ts = data["entry_ts"].max()
    windows = [
        ("60d", data),
        ("first30d", data[data["entry_ts"] < min_ts + pd.Timedelta(days=30)].copy()),
        ("30d", data[data["entry_ts"] >= max_ts - pd.Timedelta(days=30)].copy()),
    ]
    frames: list[pd.DataFrame] = []
    for label, subset in windows:
        matrix = evaluate_rules(subset, cfg)
        matrix.insert(0, "window", label)
        frames.append(matrix)
    return pd.concat(frames, ignore_index=True)


def compare_management_variants(journal: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    for (target_model, management_model), group in journal.groupby(["target_model", "management_model"], dropna=False):
        concrete = select_concrete_execution(group, str(target_model), str(management_model))
        if concrete.empty:
            continue
        strict = concrete[concrete.apply(is_strict_candidate, axis=1)].copy()
        for scope, data in [("all", concrete), ("strict", strict)]:
            if data.empty:
                continue
            rows.append({
                "scope": scope,
                "target_model": target_model,
                "management_model": management_model,
                "events": int(len(data)),
                "avg_r": float(pd.to_numeric(data["net_r"], errors="coerce").mean()),
                "profit_factor": profit_factor(pd.to_numeric(data["net_r"], errors="coerce")),
                "win_rate": float((pd.to_numeric(data["net_r"], errors="coerce") > 0).mean()),
                "target_rate": float((data["exit_reason"] == "target").mean()),
                "stop_rate": float((data["exit_reason"] == "stop").mean()),
                "expiry_rate": float((data["exit_reason"] == "expiry").mean()),
                "breakeven_rate": float((data["exit_reason"] == "breakeven").mean()),
            })
    return pd.DataFrame(rows).sort_values(["scope", "avg_r"], ascending=[True, False]).reset_index(drop=True)


def summarize_by_symbol(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    return summarize(events, ["symbol"]).sort_values(["events", "avg_r"], ascending=[False, False]).reset_index(drop=True)


def summarize(events: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    rows: list[dict] = []
    span = _span_days(events["entry_ts"]) if "entry_ts" in events else 60.0
    for keys, group in events.groupby(group_cols, dropna=False):
        net = pd.to_numeric(group["net_r"], errors="coerce")
        rows.append({
            **dict(zip(group_cols, keys if isinstance(keys, tuple) else (keys,))),
            "events": int(len(group)),
            "events_per_day": float(len(group) / span),
            "events_per_week": float(len(group) / (span / 7.0)),
            "avg_r": float(net.mean()),
            "profit_factor": profit_factor(net),
            "win_rate": float((net > 0).mean()),
            "median_duration_h": _median(group, "duration_hours"),
            "median_mfe_r": _median(group, "mfe_r"),
            "p75_mfe_r": _quantile(group, "mfe_r", 0.75),
            "median_mae_r": _median(group, "mae_r"),
            "strict_events": int(group.apply(is_strict_candidate, axis=1).sum()),
        })
    return pd.DataFrame(rows).sort_values(["avg_r", "events"], ascending=[False, False]).reset_index(drop=True)


def is_strict_candidate(row: pd.Series | dict) -> bool:
    setup = str(row.get("setup_name", ""))
    mtf = str(row.get("mtf_mode", ""))
    hour = int(float(row.get("entry_hour_utc", -1))) if pd.notna(row.get("entry_hour_utc", np.nan)) else -1
    if "london_long_middle_local" in setup:
        return mtf == "trend_aligned"
    if setup == "ny_long_neutral_reversal_ce":
        return hour == 13 and mtf == "range_or_transition"
    if setup == "late_us_short_bull_flush_ce":
        return mtf in {"countertrend", "range_or_transition"}
    return False


def rsi_14(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def rsi_bucket(value: float) -> str:
    if not np.isfinite(value):
        return "unknown"
    if value < 30:
        return "oversold"
    if value > 70:
        return "overbought"
    if value >= 55:
        return "bullish_mid"
    if value <= 45:
        return "bearish_mid"
    return "neutral_mid"


def atr_pct_bucket(value: float) -> str:
    if not np.isfinite(value):
        return "unknown"
    if value < 0.004:
        return "low"
    if value > 0.018:
        return "high"
    return "normal"


def volume_bucket(value: float) -> str:
    if not np.isfinite(value):
        return "unknown"
    if value >= 1.5:
        return "high"
    if value <= -1.0:
        return "low"
    return "normal"


def vwap_state(dist_atr: float) -> str:
    if not np.isfinite(dist_atr):
        return "unknown"
    if dist_atr >= 0.25:
        return "above"
    if dist_atr <= -0.25:
        return "below"
    return "near"


def vwap_extension(dist_atr: float) -> str:
    if not np.isfinite(dist_atr):
        return "unknown"
    distance = abs(dist_atr)
    if distance >= 2.0:
        return "extended"
    if distance >= 1.0:
        return "stretched"
    return "normal"


def profit_factor(net: pd.Series) -> float:
    clean = pd.to_numeric(net, errors="coerce").dropna()
    wins = clean[clean > 0].sum()
    losses = -clean[clean < 0].sum()
    if losses > 0:
        return float(wins / losses)
    return float("inf") if wins > 0 else 0.0


def _prepare_ohlcv(data: pd.DataFrame) -> pd.DataFrame:
    if data is None or data.empty:
        return pd.DataFrame()
    out = data.copy()
    out["ts"] = pd.to_datetime(out["ts"], utc=True, errors="coerce")
    for col in ["open", "high", "low", "close", "volume"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out.dropna(subset=["ts", "open", "high", "low", "close"]).sort_values("ts").reset_index(drop=True)


def _entry_index(data: pd.DataFrame, ts: pd.Timestamp) -> int | None:
    if data.empty:
        return None
    entry = pd.Timestamp(ts)
    if entry.tzinfo is None:
        entry = entry.tz_localize("UTC")
    else:
        entry = entry.tz_convert("UTC")
    matches = data.index[data["ts"] <= entry].to_list()
    return int(matches[-1]) if matches else None


def _completed_entry_index(data: pd.DataFrame, ts: pd.Timestamp) -> int | None:
    if data.empty:
        return None
    entry = pd.Timestamp(ts)
    if entry.tzinfo is None:
        entry = entry.tz_localize("UTC")
    else:
        entry = entry.tz_convert("UTC")
    matches = data.index[data["ts"] < entry].to_list()
    return int(matches[-1]) if matches else None


def _duration_hours(row: dict) -> float:
    start = pd.Timestamp(row.get("entry_ts"))
    end = pd.Timestamp(row.get("exit_ts"))
    if pd.isna(start) or pd.isna(end):
        return np.nan
    return float((end - start).total_seconds() / 3600.0)


def _setup_priority(setup_name: str) -> int:
    if setup_name == "ny_long_neutral_reversal_ce":
        return 0
    if "london_long_middle_local_retest" in setup_name:
        return 1
    if "london_long_middle_local_next_open" in setup_name:
        return 2
    if setup_name == "late_us_short_bull_flush_ce":
        return 3
    if setup_name == "late_us_short_bearish_trend_ce":
        return 4
    return 9


def _span_days(ts: pd.Series) -> float:
    values = pd.to_datetime(ts, utc=True, errors="coerce").dropna()
    if values.empty:
        return 1.0
    return max(float((values.max() - values.min()).total_seconds() / 86400.0), 1.0)


def _events_per_symbol_week(df: pd.DataFrame) -> float:
    if df.empty or "entry_ts" not in df:
        return 0.0
    symbols = int(df["symbol"].nunique()) if "symbol" in df else 1
    return float(len(df) / max(symbols, 1) / (_span_days(df["entry_ts"]) / 7.0))


def _bool_rate(df: pd.DataFrame, col: str) -> float:
    if df.empty or col not in df:
        return np.nan
    values = df[col]
    if values.dtype == bool:
        return float(values.mean())
    normalized = values.astype(str).str.lower()
    return float(normalized.isin(["true", "1", "yes"]).mean())


def _median(df: pd.DataFrame, col: str) -> float:
    if col not in df or df.empty:
        return 0.0
    return float(pd.to_numeric(df[col], errors="coerce").median())


def _quantile(df: pd.DataFrame, col: str, q: float) -> float:
    if col not in df or df.empty:
        return 0.0
    return float(pd.to_numeric(df[col], errors="coerce").quantile(q))


def _target_continuation_rate(df: pd.DataFrame, col: str, threshold: float) -> float:
    if df.empty or col not in df or "exit_reason" not in df:
        return 0.0
    target = df[df["exit_reason"] == "target"]
    if target.empty:
        return 0.0
    return float((pd.to_numeric(target[col], errors="coerce") >= threshold).mean())


def _load_table(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)


def _write_report(
    events: pd.DataFrame,
    rules: pd.DataFrame,
    stress: pd.DataFrame,
    extreme: pd.DataFrame,
    rolling_summary: pd.DataFrame,
    failure_diagnostics: pd.DataFrame,
    review_packet: pd.DataFrame,
    review_audit: pd.DataFrame,
    frequency_expansion: pd.DataFrame,
    direction_audit: pd.DataFrame,
    contribution: pd.DataFrame,
    by_symbol: pd.DataFrame,
    by_setup: pd.DataFrame,
    management: pd.DataFrame,
    path: Path,
    cfg: ForensicsRunConfig,
) -> None:
    lines = [
        "# Crypto Foundation Trade Forensics",
        "",
        "Purpose: de-duplicate the MTF structure journal into physical trades and test simple indicator chemistry.",
        "",
        "## Test Scope",
        f"- Interval: `15m`.",
        f"- Concrete execution: `{cfg.target_model}` + `{cfg.management_model}`.",
        f"- Risk model: `{cfg.risk_per_trade_pct * 100:.2f}%` risk/trade, max `{cfg.max_open_trades}` open, max `{cfg.max_open_per_symbol}` per symbol, daily loss cap `{cfg.daily_loss_limit_pct * 100:.2f}%`.",
        f"- Entry span: `{events['entry_ts'].min()}` to `{events['entry_ts'].max()}`." if not events.empty else "- Entry span: empty.",
        f"- Physical events: `{len(events)}`.",
        f"- Strict candidate events: `{int(events['is_strict_candidate'].sum()) if 'is_strict_candidate' in events else 0}`.",
        "",
        "## Rule Matrix",
        *_markdown_table(_format_report_table(rules.head(20))),
        "",
        "## Cost And Slippage Stress",
        *_markdown_table(_format_report_table(_stress_report_slice(stress))),
        "",
        "## Extreme Configuration Matrix",
        *_markdown_table(_format_report_table(_extreme_report_slice(extreme))),
        "",
        "## Rolling Validation Summary",
        *_markdown_table(_format_report_table(_rolling_report_slice(rolling_summary))),
        "",
        "## Rolling Failure Diagnostics",
        *_markdown_table(_format_report_table(_failure_report_slice(failure_diagnostics))),
        "",
        "## Review Packet",
        *_markdown_table(_format_report_table(_review_packet_summary(review_packet))),
        "",
        "## Saved Manual Review Audit",
        *_markdown_table(_format_report_table(_manual_review_summary(review_audit))),
        "",
        "## Frequency Expansion Matrix",
        *_markdown_table(_format_report_table(_frequency_expansion_report_slice(frequency_expansion))),
        "",
        "## Direction Audit",
        *_markdown_table(_format_report_table(_direction_audit_report_slice(direction_audit))),
        "",
        "## Concentration",
        *_markdown_table(_format_report_table(_contribution_report_slice(contribution))),
        "",
        "## Frequency By Symbol",
        *_markdown_table(_format_report_table(by_symbol.head(20))),
        "",
        "## Setup Summary",
        *_markdown_table(_format_report_table(by_setup.head(20))),
        "",
        "## Management Comparison",
        *_markdown_table(_format_report_table(management.head(20))),
        "",
        "## Verdict",
        "- Structure improves quality, but strict filtering lowers per-symbol frequency below a few trades per week.",
        "- Frequency has to come from more independent setup families or lower-timeframe entry expansion, not from weakening the MTF filter.",
        "- EMA helps only if the rule matrix improves return/DD without starving trades; otherwise it is descriptive, not a gate.",
        "- Post-target continuation is measured because fixed 2R may be too short for clean London/NY winners.",
        "- Stress scenarios convert extra bps into R, so tight-stop trades are penalized harder.",
        "- Extreme configs vary risk, concurrency, daily lockout, and friction with fixed signal rules.",
        "- Rolling validation is the promotion gate; aggregate 60d performance is not enough.",
        "- Review packet targets failed rolling windows and clean winners; it is not a random sample.",
        "- Saved manual labels mostly flag direction/confirmation defects, especially late-US countertrend shorts.",
        "- Frequency expansion rejects broad non-strict additions when they improve count but break punitive-cost expectancy.",
        "- Direction audit keeps legacy stops fixed and tests whether structure, EMA, VWAP, shock, and compression explain direction quality.",
        "- Legacy stop construction is intentionally unchanged; direction research treats stop quality as a dependent metric, not a tuning knob.",
        "- Current direction-gate candidate: `strict_late_us_no_weak_ema`; it improves weak-window behavior without starving frequency as badly as pure VWAP agreement.",
        "- Pure VWAP agreement is cleaner but too sparse for the main engine; keep it as a review/research slice until more setup families exist.",
        "- Concentration is measured on strict candidates with conservative risk under punitive costs.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _stress_report_slice(stress: pd.DataFrame) -> pd.DataFrame:
    if stress.empty:
        return stress
    keep = stress[
        (stress["window"].isin(["60d", "30d"]))
        & (stress["rule"].isin(REPORT_RULES))
        & (stress["scenario"].isin(["baseline", "punitive_40bps", "nightmare_60bps"]))
    ].copy()
    cols = [
        "window",
        "rule",
        "scenario",
        "candidates",
        "accepted",
        "median_extra_cost_r",
        "gross_return_pct",
        "max_dd_pct",
        "profit_factor",
        "win_rate",
        "return_to_dd",
    ]
    return keep[cols]


def _extreme_report_slice(extreme: pd.DataFrame) -> pd.DataFrame:
    if extreme.empty:
        return extreme
    keep = extreme[
        (extreme["window"].isin(["60d", "30d"]))
        & (extreme["rule"].isin(REPORT_RULES))
        & (extreme["scenario"].isin(["baseline", "punitive_40bps", "nightmare_60bps"]))
        & (extreme["config"].isin(["conservative", "base", "prop_strict"]))
    ].copy()
    cols = [
        "window",
        "rule",
        "scenario",
        "config",
        "risk_per_trade_pct",
        "max_open_trades",
        "daily_loss_limit_pct",
        "accepted",
        "gross_return_pct",
        "max_dd_pct",
        "daily_max_dd_pct",
        "profit_factor",
        "win_rate",
        "return_to_dd",
    ]
    return keep[cols]


def _rolling_report_slice(rolling_summary: pd.DataFrame) -> pd.DataFrame:
    if rolling_summary.empty:
        return rolling_summary
    keep = rolling_summary[
        (rolling_summary["window_days"].isin([30, 45]))
        & (rolling_summary["rule"].isin(REPORT_RULES))
        & (rolling_summary["scenario"].isin(["baseline", "punitive_40bps", "nightmare_60bps"]))
        & (rolling_summary["config"].isin(["conservative", "base"]))
    ].copy()
    cols = [
        "window_days",
        "rule",
        "scenario",
        "config",
        "windows",
        "pass_rate",
        "negative_windows",
        "median_return_pct",
        "worst_return_pct",
        "worst_dd_pct",
        "median_pf",
        "min_accepted",
        "median_events_per_day",
    ]
    return keep[cols].sort_values(
        ["window_days", "rule", "scenario", "config"]
    ).reset_index(drop=True)


def _failure_report_slice(failure_diagnostics: pd.DataFrame) -> pd.DataFrame:
    if failure_diagnostics.empty:
        return failure_diagnostics
    keep = failure_diagnostics[
        (failure_diagnostics["scenario"].isin(["punitive_40bps", "nightmare_60bps"]))
        & (failure_diagnostics["window_days"].isin([30, 45]))
        & (failure_diagnostics["events"] >= 5)
        & (failure_diagnostics["failed_events"] > 0)
        & (failure_diagnostics["passed_events"] > 0)
    ].copy()
    cols = [
        "scenario",
        "window_days",
        "feature",
        "value",
        "events",
        "failed_events",
        "failed_window_share",
        "failed_avg_r",
        "passed_avg_r",
        "failed_pf",
        "passed_pf",
        "failed_win_rate",
    ]
    return keep[cols].sort_values(
        ["failed_window_share", "failed_events", "failed_avg_r"],
        ascending=[False, False, True],
    ).head(20).reset_index(drop=True)


def _review_packet_summary(review_packet: pd.DataFrame) -> pd.DataFrame:
    if review_packet.empty:
        return review_packet
    rows = []
    for bucket, group in review_packet.groupby("review_bucket", dropna=False):
        rows.append({
            "review_bucket": bucket,
            "rows": int(len(group)),
            "symbols": int(group["symbol"].nunique()),
            "avg_outcome_r": float(pd.to_numeric(group["outcome_1.5r"], errors="coerce").mean()),
            "worst_outcome_r": float(pd.to_numeric(group["outcome_1.5r"], errors="coerce").min()),
        })
    return pd.DataFrame(rows).sort_values(["review_bucket"]).reset_index(drop=True)


def _manual_review_summary(review_audit: pd.DataFrame) -> pd.DataFrame:
    if review_audit.empty:
        return review_audit
    rows: list[dict] = []
    for keys, group in review_audit.groupby(["setup_name", "session"], dropna=False):
        notes = group["user_notes"].fillna("").astype(str).str.lower()
        rows.append({
            "setup_name": keys[0],
            "session": keys[1],
            "reviewed": int(len(group)),
            "good": int((group["user_label"] == "good").sum()),
            "bad": int((group["user_label"] == "bad").sum()),
            "skip": int((group["user_label"] == "skip").sum()),
            "unlabeled": int((group["user_label"] == "unlabeled").sum()),
            "mentions_against_trend": int(notes.str.contains("against", regex=False).sum()),
            "mentions_confirmation": int(notes.str.contains("confirmation", regex=False).sum()),
            "mentions_consolidation": int(notes.str.contains("consolidation", regex=False).sum()),
            "mentions_target": int(notes.str.contains("target", regex=False).sum()),
        })
    return pd.DataFrame(rows).sort_values(["bad", "reviewed"], ascending=[False, False]).reset_index(drop=True)


def _frequency_expansion_report_slice(frequency_expansion: pd.DataFrame) -> pd.DataFrame:
    if frequency_expansion.empty:
        return frequency_expansion
    keep = frequency_expansion[
        (frequency_expansion["window"].isin(["60d", "30d"]))
        & (frequency_expansion["scenario"].isin(["baseline", "punitive_40bps"]))
    ].copy()
    cols = [
        "window",
        "variant",
        "scenario",
        "candidates",
        "accepted",
        "symbols",
        "events_per_symbol_week",
        "gross_return_pct",
        "max_dd_pct",
        "profit_factor",
        "win_rate",
        "frequency_verdict",
    ]
    return keep[cols].sort_values(
        ["window", "scenario", "gross_return_pct"],
        ascending=[True, True, False],
    ).groupby(["window", "scenario"], group_keys=False).head(10).reset_index(drop=True)


def _direction_audit_report_slice(direction_audit: pd.DataFrame) -> pd.DataFrame:
    if direction_audit.empty:
        return direction_audit
    feature_order = [
        "direction_stack",
        "mtf_mode",
        "structure_confirmation",
        "ema_stack",
        "session_vwap_state",
        "session_vwap_extension",
        "vwap_direction_agreement",
        "shock_alignment",
        "compression_state",
        "setup_name",
    ]
    keep = direction_audit[
        (direction_audit["scope"] == "strict")
        & (direction_audit["feature"].isin(feature_order))
        & (direction_audit["events"] >= 5)
    ].copy()
    if keep.empty:
        keep = direction_audit[direction_audit["events"] >= 5].copy()
    cols = [
        "scope",
        "feature",
        "value",
        "events",
        "events_per_symbol_week",
        "avg_r",
        "profit_factor",
        "win_rate",
        "direction_accuracy",
        "bad_direction_rate",
        "bad_entry_rate",
        "stop_rate",
        "median_mfe_r",
        "median_mae_r",
    ]
    keep["_feature_order"] = keep["feature"].map({name: i for i, name in enumerate(feature_order)}).fillna(99)
    return keep[cols + ["_feature_order"]].sort_values(
        ["_feature_order", "avg_r", "events"],
        ascending=[True, False, False],
    ).drop(columns=["_feature_order"]).groupby("feature", group_keys=False).head(6).reset_index(drop=True)


def _contribution_report_slice(contribution: pd.DataFrame) -> pd.DataFrame:
    if contribution.empty:
        return contribution
    keep = contribution[contribution["dimension"].isin(["symbol", "setup_name", "session_utc"])].copy()
    cols = [
        "dimension",
        "value",
        "events",
        "total_r",
        "share_of_total_r",
        "avg_r",
        "profit_factor",
        "win_rate",
    ]
    return keep[cols].sort_values(["dimension", "total_r"], ascending=[True, False]).groupby("dimension").head(8).reset_index(drop=True)


def _format_report_table(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_float_dtype(out[col]):
            out[col] = out[col].map(lambda x: "inf" if x == float("inf") else f"{x:.3f}")
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
    parser = argparse.ArgumentParser(description="Run foundation crypto trade forensics and indicator chemistry.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--target-model", default="fixed_2r")
    parser.add_argument("--management-model", default="hold_target_expiry")
    parser.add_argument("--risk-pct", type=float, default=0.002)
    parser.add_argument("--max-open", type=int, default=6)
    parser.add_argument("--max-open-per-symbol", type=int, default=1)
    parser.add_argument("--daily-loss-limit-pct", type=float, default=0.005)
    args = parser.parse_args()

    result = run_foundation_trade_forensics(
        Path(args.input),
        output_dir=Path(args.output_dir),
        config=ForensicsRunConfig(
            target_model=args.target_model,
            management_model=args.management_model,
            risk_per_trade_pct=args.risk_pct,
            max_open_trades=args.max_open,
            max_open_per_symbol=args.max_open_per_symbol,
            daily_loss_limit_pct=args.daily_loss_limit_pct,
        ),
    )
    print(result["rules"].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
