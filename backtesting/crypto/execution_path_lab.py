"""Execution-path lab for promoted event-atlas buckets.

This answers a narrower question than the atlas: after a signal exists, is the
entry/management actually executable, or did the atlas only find drift into a
time-based expiry close?
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.crypto.direction_layer import (
    DirectionLayerConfig,
    ema_state,
    has_direction_confirmation,
    has_opposing_spike,
    recent_shock_state,
    structure_at,
)
from backtesting.crypto.event_atlas import _atr, _bar_delta, _next_round_number, _session_utc, _vol_bucket
from backtesting.crypto.index_structure import DEFAULT_SYMBOLS
from backtesting.engine.data import load_data
from backtesting.features.structure import build_structure_index


@dataclass(frozen=True)
class ExecutionConfig:
    lookback_bars: int = 24
    horizon_bars: int = 24
    atr_period: int = 14
    taker_fee: float = 0.0004
    maker_fee: float = 0.0002
    min_stop_pct: float = 0.001
    retest_bars: int = 8
    context_tf: str = "240"
    time_stop_bars: int = 16
    expiry_haircut_r: float = 0.0
    include_raw_entries: bool = True
    include_structure_confirmed_entries: bool = True
    include_ema_confirmed_entries: bool = False
    stale_retest_bars: int = 4
    continuation_stale_retest_bars: int = 8
    min_target_r: float = 1.2
    target_models: tuple[str, ...] = ("fixed_1_5r", "fixed_2r", "structure_swing_low", "round_number")
    suppress_duplicate_zones: bool = True
    duplicate_zone_tolerance_pct: float = 0.0005
    duplicate_cooldown_bars: int = 12
    direction_config: DirectionLayerConfig = DirectionLayerConfig()


def run_survivor_execution_lab(
    *,
    symbols: list[str],
    exchanges: list[str],
    days: int = 400,
    tf: str = "15",
    output_dir: Path = Path("backtesting/results/event_atlas"),
    config: ExecutionConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    cfg = config or ExecutionConfig()
    rows: list[pd.DataFrame] = []
    for exchange in exchanges:
        for symbol in symbols:
            df = load_data(symbol, tf=tf, days=days, asset_type="crypto", exchange=exchange, crypto_source="merged")
            structure = _load_structure_cache(exchange, symbol, cfg.context_tf)
            entry_structure = _load_structure_cache(exchange, symbol, tf)
            result = evaluate_bearish_fvg_survivor(
                df,
                symbol=symbol,
                exchange=exchange,
                tf=tf,
                structure=structure,
                entry_structure=entry_structure,
                config=cfg,
            )
            if not result.empty:
                rows.append(result)
            print(f"  {exchange}/{symbol} {tf}: {len(result)} execution rows", flush=True)
    trades = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    summary = summarize_execution(trades)
    output_dir.mkdir(parents=True, exist_ok=True)
    trades.to_csv(output_dir / "survivor_execution_paths.csv", index=False)
    summary.to_csv(output_dir / "survivor_execution_summary.csv", index=False)
    return trades, summary


def evaluate_bearish_fvg_survivor(
    df: pd.DataFrame,
    *,
    symbol: str,
    exchange: str,
    tf: str = "15",
    structure: pd.DataFrame | None = None,
    entry_structure: pd.DataFrame | None = None,
    config: ExecutionConfig | None = None,
) -> pd.DataFrame:
    cfg = config or ExecutionConfig()
    data = _prepare(df)
    if len(data) < cfg.lookback_bars + cfg.horizon_bars + cfg.retest_bars + 5:
        return pd.DataFrame()

    atr = _atr(data, cfg.atr_period)
    if entry_structure is None or entry_structure.empty:
        entry_structure = build_structure_index(data)
    atr_pct = atr / data["close"]
    prev_high = data["high"].shift(1).rolling(cfg.lookback_bars).max()
    rows: list[dict] = []
    seen_zones: dict[tuple[int, int], int] = {}
    max_i = len(data) - cfg.horizon_bars - cfg.retest_bars - 2
    for i in range(max(cfg.lookback_bars, 2), max_i):
        if not np.isfinite(atr.iat[i]) or atr.iat[i] <= 0:
            continue
        if not _is_survivor_context(data, i, atr_pct, structure, cfg):
            continue
        c1_low = float(data["low"].iat[i - 2])
        c3_high = float(data["high"].iat[i])
        if c3_high >= c1_low:
            continue
        fvg_top = c1_low
        fvg_bottom = c3_high
        fvg_ce = (fvg_top + fvg_bottom) / 2.0
        if cfg.suppress_duplicate_zones and _is_duplicate_zone(i, fvg_top, fvg_bottom, seen_zones, cfg):
            continue
        stop = float(prev_high.iat[i])
        if not np.isfinite(stop):
            continue
        base = {
            "exchange": exchange,
            "symbol": symbol,
            "tf": str(tf),
            "signal_i": i,
            "bar_ts": data["ts"].iat[i],
            "signal_ts": data["ts"].iat[i] + _bar_delta(data),
            "fvg_top": fvg_top,
            "fvg_bottom": fvg_bottom,
            "fvg_ce": fvg_ce,
            "stop_model": "prior_swing",
            "ctx_240_regime": "bull",
            "session_utc": "late_us",
            "vol_bucket": "high",
        }
        for plan in _entry_plans(data, i, stop, fvg_top, fvg_ce, atr, entry_structure, cfg):
            rows.extend(_score_short_path(data, i, stop, cfg, base, entry_structure=entry_structure, **plan))
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out[~out["invalid"]].reset_index(drop=True)


def summarize_execution(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    rows = []
    for keys, group in trades.groupby(["entry_model", "target_model", "management_model"]):
        entry_model, target_model, management_model = keys
        net = group["net_r"].astype(float)
        wins = net[net > 0]
        losses = net[net < 0]
        pf = float(wins.sum() / abs(losses.sum())) if abs(losses.sum()) > 0 else np.inf
        rows.append({
            "entry_model": entry_model,
            "target_model": target_model,
            "management_model": management_model,
            "events": int(len(group)),
            "symbols": int(group["symbol"].nunique()),
            "exchanges": int(group["exchange"].nunique()),
            "fill_rate": float(group["filled"].mean()),
            "avg_net_r": float(net.mean()),
            "median_net_r": float(net.median()),
            "profit_factor": pf,
            "target_rate": float(group["hit_target"].mean()),
            "stop_rate": float(group["hit_stop"].mean()),
            "expiry_rate": float((group["exit_reason"] == "expiry").mean()),
            "hit_1r_rate": float(group["hit_1r"].mean()),
            "avg_bars_to_entry": float(group["bars_to_entry"].mean()),
            "avg_bars_to_exit": float(group["bars_to_exit"].mean()),
            "median_mfe_r": float(group["mfe_r"].median()),
            "median_mae_r": float(group["mae_r"].median()),
        })
    return pd.DataFrame(rows).sort_values(["avg_net_r", "profit_factor"], ascending=[False, False]).reset_index(drop=True)


def _entry_plans(
    data: pd.DataFrame,
    i: int,
    stop: float,
    fvg_top: float,
    fvg_ce: float,
    atr: pd.Series,
    entry_structure: pd.DataFrame,
    cfg: ExecutionConfig,
) -> list[dict]:
    raw_plans = []
    next_i = i + 1
    raw_plans.append({"entry_model": "next_open", "entry_i": next_i, "entry": float(data["open"].iat[next_i]), "filled": True, "bars_to_entry": 1})
    raw_plans.extend(_limit_short_plan(data, i, stop, fvg_ce, "fvg_ce_retest", cfg))
    raw_plans.extend(_limit_short_plan(data, i, stop, fvg_top, "fvg_top_retest", cfg))
    raw_plans.extend(_continuation_short_plan(data, i, stop, cfg))
    plans = []
    if cfg.include_raw_entries:
        for plan in raw_plans:
            plans.append({**plan, "confirmation_model": "none", "confirmation_ts": pd.NaT, "spike_filter": "none"})
    if cfg.include_structure_confirmed_entries:
        for plan in raw_plans:
            confirmed = _confirmed_short_plan(data, i, plan, atr, entry_structure, cfg, require_ema=False)
            if confirmed is not None:
                plans.append(confirmed)
    if cfg.include_ema_confirmed_entries:
        for plan in raw_plans:
            confirmed = _confirmed_short_plan(data, i, plan, atr, entry_structure, cfg, require_ema=True)
            if confirmed is not None:
                plans.append(confirmed)
    return plans


def _confirmed_short_plan(
    data: pd.DataFrame,
    signal_i: int,
    plan: dict,
    atr: pd.Series,
    entry_structure: pd.DataFrame,
    cfg: ExecutionConfig,
    require_ema: bool = False,
) -> dict | None:
    entry_i = int(plan["entry_i"])
    entry_ts = data["ts"].iat[entry_i]
    signal_ts = data["ts"].iat[signal_i] + _bar_delta(data)
    shock = recent_shock_state(data, entry_i=entry_i, atr=atr, config=cfg.direction_config)
    stale = int(plan["bars_to_entry"]) > cfg.stale_retest_bars
    if stale:
        allow_continuation = (
            shock["direction"] == "bearish"
            and int(plan["bars_to_entry"]) <= cfg.continuation_stale_retest_bars
        )
        if not allow_continuation:
            return None
    spike, spike_reason = has_opposing_spike(
        data,
        direction="short",
        entry_i=entry_i,
        atr=atr,
        config=cfg.direction_config,
    )
    if spike:
        return None
    ok, reason, confirmation_ts = has_direction_confirmation(
        entry_structure,
        direction="short",
        signal_ts=signal_ts,
        entry_ts=entry_ts,
        bar_delta=_bar_delta(data),
        config=cfg.direction_config,
    )
    if not ok:
        return None
    if shock["direction"] == "bullish" and pd.notna(shock["shock_ts"]):
        if pd.isna(confirmation_ts) or pd.Timestamp(confirmation_ts) <= pd.Timestamp(shock["shock_ts"]):
            return None
    ema = ema_state(data, entry_i=entry_i, config=cfg.direction_config)
    if require_ema and ema["state"] != "bearish":
        return None
    prefix = "ema_structure_confirmed" if require_ema else "structure_confirmed"
    return {
        **plan,
        "entry_model": f"{prefix}_{plan['entry_model']}",
        "confirmation_model": reason,
        "confirmation_ts": confirmation_ts,
        "spike_filter": spike_reason,
        "shock_state": shock["direction"],
        "shock_reason": shock["reason"],
        "ema_state": ema["state"],
        "ema_fast": ema["fast"],
        "ema_slow": ema["slow"],
    }


def _limit_short_plan(data: pd.DataFrame, i: int, stop: float, entry_price: float, name: str, cfg: ExecutionConfig) -> list[dict]:
    if entry_price >= stop:
        return []
    end = min(i + cfg.retest_bars + 1, len(data) - cfg.horizon_bars - 1)
    for j in range(i + 1, end + 1):
        if float(data["high"].iat[j]) >= entry_price:
            return [{"entry_model": name, "entry_i": j, "entry": entry_price, "filled": True, "bars_to_entry": j - i}]
    return []


def _continuation_short_plan(data: pd.DataFrame, i: int, stop: float, cfg: ExecutionConfig) -> list[dict]:
    trigger = float(data["low"].iat[i])
    end = min(i + cfg.retest_bars + 1, len(data) - cfg.horizon_bars - 1)
    for j in range(i + 1, end + 1):
        if float(data["low"].iat[j]) < trigger:
            entry = min(float(data["open"].iat[j + 1]), trigger)
            if entry < stop:
                return [{"entry_model": "break_continuation", "entry_i": j + 1, "entry": entry, "filled": True, "bars_to_entry": j + 1 - i}]
    return []


def _score_short_path(
    data: pd.DataFrame,
    signal_i: int,
    stop: float,
    cfg: ExecutionConfig,
    base: dict,
    *,
    entry_model: str,
    entry_i: int,
    entry: float,
    filled: bool,
    bars_to_entry: int,
    confirmation_model: str = "none",
    confirmation_ts: pd.Timestamp | pd.NaT = pd.NaT,
    spike_filter: str = "none",
    shock_state: str = "none",
    shock_reason: str = "none",
    ema_state: str = "unknown",
    ema_fast: float = np.nan,
    ema_slow: float = np.nan,
    entry_structure: pd.DataFrame | None = None,
) -> dict:
    min_stop = entry * cfg.min_stop_pct
    stop = max(stop, entry + min_stop)
    risk = stop - entry
    if risk <= 0 or entry_i >= len(data) - 1:
        return {**base, "entry_model": entry_model, "invalid": True}
    fwd = data.iloc[entry_i:entry_i + cfg.horizon_bars]
    mfe_r = (entry - float(fwd["low"].min())) / risk
    mae_r = (entry - float(fwd["high"].max())) / risk
    rows = []
    targets = _short_target_candidates(data, entry_i, entry, risk, entry_structure, cfg)
    for target_model, target in targets.items():
        target_r = (entry - target) / risk
        if target_r < cfg.min_target_r:
            continue
        for management_model in [
            "hold_target_expiry",
            "be_after_half_target",
            "be_after_1r",
            "partial_1r_hold",
            "partial_1r_be",
            "partial_1r_be_after_half_target",
            "time_stop",
            "market_expiry_haircut",
        ]:
            outcome = _managed_short_outcome(fwd, entry, stop, target, risk, cfg, management_model)
            rows.append({
                **base,
                "entry_model": entry_model,
                "target_model": target_model,
                "management_model": management_model,
                "entry_ts": data["ts"].iat[entry_i],
                "entry": entry,
                "stop": stop,
                "target": target,
                "risk_price": risk,
                "target_r": target_r,
                "confirmation_model": confirmation_model,
                "confirmation_ts": confirmation_ts,
                "spike_filter": spike_filter,
                "shock_state": shock_state,
                "shock_reason": shock_reason,
                "ema_state": ema_state,
                "ema_fast": ema_fast,
                "ema_slow": ema_slow,
                "gross_r": outcome["gross_r"],
                "cost_r": outcome["cost_r"],
                "net_r": outcome["net_r"],
                "mfe_r": mfe_r,
                "mae_r": mae_r,
                "hit_1r": outcome["hit_1r"],
                "hit_target": outcome["hit_target"],
                "hit_stop": outcome["hit_stop"],
                "exit_reason": outcome["exit_reason"],
                "bars_to_entry": bars_to_entry,
                "bars_to_exit": outcome["bars_to_exit"],
                "filled": filled,
                "invalid": False,
            })
    return rows


def _short_target_candidates(
    data: pd.DataFrame,
    entry_i: int,
    entry: float,
    risk: float,
    entry_structure: pd.DataFrame | None,
    cfg: ExecutionConfig,
) -> dict[str, float]:
    candidates = {
        "fixed_1_5r": entry - 1.5 * risk,
        "fixed_2r": entry - 2.0 * risk,
        "round_number": _next_round_number(entry, "short"),
    }
    if entry_structure is not None and not entry_structure.empty:
        s = structure_at(entry_structure, data["ts"].iat[entry_i])
        if s is not None:
            for col in ["short_target_1", "last_swing_low", "last_ll"]:
                value = s.get(col, np.nan)
                if np.isfinite(value) and float(value) < entry:
                    candidates["structure_swing_low"] = float(value)
                    break
    return {
        k: float(v) for k, v in candidates.items()
        if k in cfg.target_models and np.isfinite(v) and float(v) < entry
    }


def _is_duplicate_zone(
    i: int,
    fvg_top: float,
    fvg_bottom: float,
    seen_zones: dict[tuple[int, int], int],
    cfg: ExecutionConfig,
) -> bool:
    tolerance = max(abs(fvg_top) * cfg.duplicate_zone_tolerance_pct, 1e-12)
    key = (round(fvg_top / tolerance), round(fvg_bottom / tolerance))
    last_i = seen_zones.get(key)
    if last_i is not None and i - last_i <= cfg.duplicate_cooldown_bars:
        return True
    seen_zones[key] = i
    return False


def _managed_short_outcome(
    fwd: pd.DataFrame,
    entry: float,
    stop: float,
    target: float,
    risk: float,
    cfg: ExecutionConfig,
    management_model: str,
) -> dict:
    one_r = entry - risk
    half_target = entry - 0.5 * (entry - target)
    active_stop = stop
    hit_1r = False
    partial_taken = False
    gross_locked = 0.0
    exit_reason = "expiry"
    exit_price = float(fwd["close"].iat[-1])
    bars_to_exit = len(fwd)
    hit_target = False
    hit_stop = False
    max_bars = min(len(fwd), cfg.time_stop_bars) if management_model == "time_stop" else len(fwd)

    for offset, row in enumerate(fwd.iloc[:max_bars].itertuples(index=False), start=1):
        high = float(row.high)
        low = float(row.low)
        if high >= active_stop:
            exit_reason = "stop" if active_stop != entry else "breakeven"
            exit_price = active_stop
            hit_stop = active_stop != entry
            bars_to_exit = offset
            break
        if low <= target:
            exit_reason = "target"
            exit_price = target
            hit_target = True
            hit_1r = True
            bars_to_exit = offset
            break
        if low <= half_target and management_model in {"be_after_half_target", "partial_1r_be_after_half_target"}:
            active_stop = entry
        if low <= one_r and not hit_1r:
            hit_1r = True
            if management_model in {"be_after_1r", "partial_1r_be", "partial_1r_be_after_half_target"}:
                active_stop = entry
            if management_model in {"partial_1r_hold", "partial_1r_be", "partial_1r_be_after_half_target"}:
                gross_locked = 0.5
                partial_taken = True

    if management_model == "time_stop" and exit_reason == "expiry" and len(fwd) >= max_bars:
        exit_price = float(fwd["close"].iat[max_bars - 1])
        bars_to_exit = max_bars

    remainder_r = (entry - exit_price) / risk
    gross_r = (0.5 * remainder_r + gross_locked) if partial_taken else remainder_r
    exit_fee = cfg.taker_fee if exit_reason in {"stop", "expiry", "breakeven"} else cfg.maker_fee
    cost_r = ((entry * cfg.taker_fee) + (exit_price * exit_fee)) / risk
    if partial_taken:
        # Extra partial exit fee approximation at the 1R take-profit.
        cost_r += (one_r * cfg.maker_fee) / risk * 0.5
    net_r = gross_r - cost_r
    if management_model == "market_expiry_haircut" and exit_reason == "expiry":
        net_r -= cfg.expiry_haircut_r
    return {
        "gross_r": gross_r,
        "cost_r": cost_r,
        "net_r": net_r,
        "hit_1r": hit_1r,
        "hit_target": hit_target,
        "hit_stop": hit_stop,
        "exit_reason": exit_reason,
        "bars_to_exit": bars_to_exit,
    }


def _is_survivor_context(
    data: pd.DataFrame,
    i: int,
    atr_pct: pd.Series,
    structure: pd.DataFrame | None,
    cfg: ExecutionConfig,
) -> bool:
    if _session_utc(data["ts"].iat[i]) != "late_us":
        return False
    if not np.isfinite(atr_pct.iat[i]) or _vol_bucket(float(atr_pct.iat[i])) != "high":
        return False
    if structure is None or structure.empty:
        return False
    signal_ts = data["ts"].iat[i] + _bar_delta(data)
    s = structure.copy()
    s["known_after_ts"] = pd.to_datetime(s["known_after_ts"], utc=True, errors="coerce")
    s = s[s["known_after_ts"] <= signal_ts].dropna(subset=["known_after_ts"])
    if s.empty or "regime" not in s.columns:
        return False
    return str(s.sort_values("known_after_ts").iloc[-1]["regime"]) == "bull"


def _prepare(df: pd.DataFrame) -> pd.DataFrame:
    data = df[["ts", "open", "high", "low", "close"]].copy()
    data["ts"] = pd.to_datetime(data["ts"], utc=True, errors="coerce")
    for col in ["open", "high", "low", "close"]:
        data[col] = pd.to_numeric(data[col], errors="coerce")
    return data.dropna().sort_values("ts").reset_index(drop=True)


def _load_structure_cache(exchange: str, symbol: str, tf: str, root: Path = Path("data/features/structure/L2_R2")) -> pd.DataFrame:
    path = root / exchange / symbol / f"{tf}.parquet"
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_parquet(path)
    except Exception:
        return pd.DataFrame()


def main() -> int:
    parser = argparse.ArgumentParser(description="Execution-path lab for the holdout survivor bucket.")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--exchange", default="both", choices=["binance", "bybit", "both"])
    parser.add_argument("--days", type=int, default=400)
    parser.add_argument("--tf", default="15")
    parser.add_argument("--expiry-haircut-r", type=float, default=0.10)
    parser.add_argument("--time-stop-bars", type=int, default=16)
    parser.add_argument("--include-ema-confirmed", action="store_true")
    parser.add_argument("--output-dir", default="backtesting/results/event_atlas")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    exchanges = ["binance", "bybit"] if args.exchange == "both" else [args.exchange]
    trades, summary = run_survivor_execution_lab(
        symbols=symbols,
        exchanges=exchanges,
        days=args.days,
        tf=args.tf,
        output_dir=Path(args.output_dir),
        config=ExecutionConfig(
            expiry_haircut_r=args.expiry_haircut_r,
            time_stop_bars=args.time_stop_bars,
            include_ema_confirmed_entries=args.include_ema_confirmed,
        ),
    )
    print(f"Execution rows: {len(trades)}")
    if not summary.empty:
        print(summary.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
