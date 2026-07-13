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
    by_symbol = summarize_by_symbol(events)
    by_setup = summarize(events, ["setup_name", "mtf_mode"])
    management = compare_management_variants(journal)

    output_dir.mkdir(parents=True, exist_ok=True)
    events.to_csv(output_dir / "foundation_physical_trade_journal.csv", index=False)
    rules.to_csv(output_dir / "foundation_rule_matrix.csv", index=False)
    stress.to_csv(output_dir / "foundation_stress_matrix.csv", index=False)
    by_symbol.to_csv(output_dir / "foundation_frequency_by_symbol.csv", index=False)
    by_setup.to_csv(output_dir / "foundation_summary_by_setup.csv", index=False)
    management.to_csv(output_dir / "foundation_management_comparison.csv", index=False)
    _write_report(events, rules, stress, by_symbol, by_setup, management, output_dir / "foundation_trade_forensics_report.md", cfg)
    return {
        "events": events,
        "rules": rules,
        "stress": stress,
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
    return {
        "all_physical_fixed2_hold": pd.Series(True, index=events.index),
        "strict_candidates": events.apply(is_strict_candidate, axis=1),
        "london_trend_aligned": events["setup_name"].astype(str).str.contains("london_long_middle_local", na=False)
        & (events["mtf_mode"] == "trend_aligned"),
        "london_trend_ema_bullish": events["setup_name"].astype(str).str.contains("london_long_middle_local", na=False)
        & (events["mtf_mode"] == "trend_aligned")
        & (events["ema_21_55_state"] == "bullish"),
        "london_trend_rsi_not_overbought": events["setup_name"].astype(str).str.contains("london_long_middle_local", na=False)
        & (events["mtf_mode"] == "trend_aligned")
        & (pd.to_numeric(events["rsi_14"], errors="coerce") <= 70),
        "ny_13_range_reversal": (events["setup_name"] == "ny_long_neutral_reversal_ce")
        & (events["entry_hour_utc"].astype(int) == 13)
        & (events["mtf_mode"] == "range_or_transition"),
        "ny_13_expanded_or_opposing": (events["setup_name"] == "ny_long_neutral_reversal_ce")
        & (events["entry_hour_utc"].astype(int) == 13)
        & (events["mtf_mode"] == "range_or_transition")
        & ((events["compression_state"] == "expanded") | (events["shock_alignment"] == "opposing_shock")),
        "late_us_fade": (events["setup_name"] == "late_us_short_bull_flush_ce")
        & (events["mtf_mode"].isin(["countertrend", "range_or_transition"])),
        "late_us_fade_no_aligned_shock": (events["setup_name"] == "late_us_short_bull_flush_ce")
        & (events["mtf_mode"].isin(["countertrend", "range_or_transition"]))
        & (events["shock_alignment"] != "aligned_shock"),
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
    keep_rules = {
        "all_physical_fixed2_hold",
        "strict_candidates",
        "ny_13_range_reversal",
        "late_us_fade",
        "london_trend_aligned",
    }
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
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _stress_report_slice(stress: pd.DataFrame) -> pd.DataFrame:
    if stress.empty:
        return stress
    keep = stress[
        (stress["window"].isin(["60d", "first30d", "30d"]))
        & (stress["rule"].isin(["strict_candidates", "ny_13_range_reversal", "late_us_fade", "london_trend_aligned"]))
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
