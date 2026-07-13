"""Crypto price-action event atlas.

This module labels events and their forward outcomes. It is research
infrastructure, not a strategy: every row is a hypothesis candidate that still
needs bucket validation before it deserves execution code.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.crypto.index_structure import DEFAULT_SYMBOLS
from backtesting.engine.data import load_data


DEFAULT_EVENTS = (
    "sweep_reclaim",
    "failed_breakout",
    "displacement",
    "inside_compression",
    "fvg_formation",
)


@dataclass(frozen=True)
class EventAtlasConfig:
    lookback_bars: int = 24
    horizon_bars: int = 24
    atr_period: int = 14
    atr_stop_mult: float = 0.25
    min_stop_pct: float = 0.001
    displacement_atr: float = 1.5
    displacement_close_frac: float = 0.25
    compression_bars: int = 3
    taker_fee: float = 0.0004
    maker_fee: float = 0.0002
    stop_models: tuple[str, ...] = ("event_extreme", "prior_swing", "atr")
    target_models: tuple[str, ...] = ("fixed_1r", "fixed_2r", "prior_opposite", "round_number")


def build_event_atlas(
    df: pd.DataFrame,
    *,
    symbol: str,
    exchange: str,
    tf: str,
    config: EventAtlasConfig | None = None,
    structure: pd.DataFrame | None = None,
    context_tf: str | None = None,
) -> pd.DataFrame:
    """Return event rows with forward cost-adjusted R outcomes."""
    cfg = config or EventAtlasConfig()
    data = _prepare_ohlcv(df)
    if len(data) < cfg.lookback_bars + cfg.horizon_bars + 5:
        return pd.DataFrame()

    atr = _atr(data, cfg.atr_period)
    atr_pct = atr / data["close"]
    prev_high = data["high"].shift(1).rolling(cfg.lookback_bars).max()
    prev_low = data["low"].shift(1).rolling(cfg.lookback_bars).min()
    body = (data["close"] - data["open"]).abs()
    candle_range = (data["high"] - data["low"]).replace(0, np.nan)
    upper_close = data["high"] - (candle_range * cfg.displacement_close_frac)
    lower_close = data["low"] + (candle_range * cfg.displacement_close_frac)

    rows: list[dict] = []
    max_i = len(data) - cfg.horizon_bars - 2
    for i in range(cfg.lookback_bars, max_i):
        if not np.isfinite(atr.iat[i]) or atr.iat[i] <= 0:
            continue
        base = {
            "exchange": exchange,
            "symbol": symbol,
            "tf": str(tf),
            "bar_ts": data["ts"].iat[i],
            "signal_ts": data["ts"].iat[i] + _bar_delta(data),
            "atr": float(atr.iat[i]),
            "atr_pct": float(atr_pct.iat[i]) if np.isfinite(atr_pct.iat[i]) else np.nan,
            "vol_bucket": _vol_bucket(float(atr_pct.iat[i])) if np.isfinite(atr_pct.iat[i]) else "unknown",
            "session_utc": _session_utc(data["ts"].iat[i]),
            "prev_high": float(prev_high.iat[i]) if np.isfinite(prev_high.iat[i]) else np.nan,
            "prev_low": float(prev_low.iat[i]) if np.isfinite(prev_low.iat[i]) else np.nan,
        }

        if data["low"].iat[i] < prev_low.iat[i] and data["close"].iat[i] > prev_low.iat[i]:
            rows.extend(_score_event_variants(data, i, "sweep_reclaim_low", "long", float(data["low"].iat[i]), cfg, base))
        if data["high"].iat[i] > prev_high.iat[i] and data["close"].iat[i] < prev_high.iat[i]:
            rows.extend(_score_event_variants(data, i, "sweep_reclaim_high", "short", float(data["high"].iat[i]), cfg, base))

        if data["close"].iat[i - 1] > prev_high.iat[i - 1] and data["close"].iat[i] < prev_high.iat[i]:
            rows.extend(_score_event_variants(data, i, "failed_breakout_high", "short", float(data["high"].iat[i]), cfg, base))
        if data["close"].iat[i - 1] < prev_low.iat[i - 1] and data["close"].iat[i] > prev_low.iat[i]:
            rows.extend(_score_event_variants(data, i, "failed_breakout_low", "long", float(data["low"].iat[i]), cfg, base))

        if body.iat[i] >= cfg.displacement_atr * atr.iat[i]:
            if data["close"].iat[i] >= upper_close.iat[i]:
                stop = float(data["low"].iat[i] - cfg.atr_stop_mult * atr.iat[i])
                rows.extend(_score_event_variants(data, i, "bullish_displacement", "long", stop, cfg, base))
            elif data["close"].iat[i] <= lower_close.iat[i]:
                stop = float(data["high"].iat[i] + cfg.atr_stop_mult * atr.iat[i])
                rows.extend(_score_event_variants(data, i, "bearish_displacement", "short", stop, cfg, base))

        if _is_compression(data, i, cfg.compression_bars, atr.iat[i]):
            low_stop = float(data["low"].iloc[i - cfg.compression_bars + 1:i + 1].min())
            high_stop = float(data["high"].iloc[i - cfg.compression_bars + 1:i + 1].max())
            rows.extend(_score_event_variants(data, i, "inside_compression_long", "long", low_stop, cfg, base))
            rows.extend(_score_event_variants(data, i, "inside_compression_short", "short", high_stop, cfg, base))

        if i >= 2:
            c1_high = data["high"].iat[i - 2]
            c1_low = data["low"].iat[i - 2]
            if data["low"].iat[i] > c1_high:
                rows.extend(_score_event_variants(data, i, "bullish_fvg_formation", "long", float(data["low"].iat[i - 1]), cfg, base))
            elif data["high"].iat[i] < c1_low:
                rows.extend(_score_event_variants(data, i, "bearish_fvg_formation", "short", float(data["high"].iat[i - 1]), cfg, base))

    events = pd.DataFrame(rows)
    if events.empty:
        return events
    if "invalid" in events.columns:
        events = events[~events["invalid"].fillna(False)].reset_index(drop=True)
    if events.empty:
        return events
    if structure is not None and not structure.empty:
        events = attach_structure_context(events, structure, context_tf=context_tf or tf)
    return events


def attach_structure_context(events: pd.DataFrame, structure: pd.DataFrame, *, context_tf: str) -> pd.DataFrame:
    """Causally attach the latest structure row known before each signal."""
    right = structure.copy()
    right["known_after_ts"] = pd.to_datetime(right["known_after_ts"], utc=True, errors="coerce")
    right = right.dropna(subset=["known_after_ts"]).sort_values("known_after_ts")
    keep = [
        "known_after_ts", "regime", "structure_label", "bos_up", "bos_down",
        "choch_up", "choch_down", "sweep_high", "sweep_low",
    ]
    keep = [c for c in keep if c in right.columns]
    right = right[keep].rename(columns={c: f"ctx_{context_tf}_{c}" for c in keep if c != "known_after_ts"})

    left = events.copy()
    left["signal_ts"] = pd.to_datetime(left["signal_ts"], utc=True, errors="coerce")
    left = left.sort_values("signal_ts")
    out = pd.merge_asof(
        left,
        right,
        left_on="signal_ts",
        right_on="known_after_ts",
        direction="backward",
    )
    return out.drop(columns=["known_after_ts"], errors="ignore")


def summarize_events(events: pd.DataFrame, *, min_events: int = 30) -> pd.DataFrame:
    """Aggregate event outcomes by exchange/symbol/timeframe/event/direction."""
    if events.empty:
        return pd.DataFrame()
    group_cols = ["exchange", "symbol", "tf", "event", "direction", "stop_model", "target_model"]
    events = _ensure_group_columns(events, group_cols)
    return _summarize_groups(events, group_cols, min_events=min_events)


def summarize_context_buckets(
    events: pd.DataFrame,
    *,
    context_cols: list[str] | None = None,
    min_events: int = 100,
) -> pd.DataFrame:
    """Aggregate outcomes by event plan plus causal context buckets."""
    if events.empty:
        return pd.DataFrame()
    if context_cols is None:
        context_cols = [c for c in ["ctx_240_regime", "session_utc", "vol_bucket"] if c in events.columns]
    group_cols = ["event", "direction", "stop_model", "target_model", *context_cols]
    events = _ensure_group_columns(events, group_cols)
    return _summarize_groups(events, group_cols, min_events=min_events)


def _summarize_groups(events: pd.DataFrame, group_cols: list[str], *, min_events: int) -> pd.DataFrame:
    rows = []
    for keys, group in events.groupby(group_cols, dropna=False):
        net = group["net_r"].astype(float)
        wins = net[net > 0]
        losses = net[net < 0]
        profit_factor = float(wins.sum() / abs(losses.sum())) if abs(losses.sum()) > 0 else np.inf
        rows.append({
            **dict(zip(group_cols, keys)),
            "events": int(len(group)),
            "symbols": int(group["symbol"].nunique()) if "symbol" in group.columns else 0,
            "exchanges": int(group["exchange"].nunique()) if "exchange" in group.columns else 0,
            "avg_net_r": float(net.mean()),
            "median_net_r": float(net.median()),
            "profit_factor": profit_factor,
            "hit_1r_rate": float(group["hit_1r"].mean()),
            "hit_target_rate": float(group["hit_target"].mean()) if "hit_target" in group.columns else float(group["hit_2r"].mean()),
            "hit_2r_rate": float(group["hit_2r"].mean()) if "hit_2r" in group.columns else 0.0,
            "stop_rate": float(group["hit_stop"].mean()),
            "mfe_r_median": float(group["mfe_r"].median()),
            "mae_r_median": float(group["mae_r"].median()),
            "research_ready": bool(len(group) >= min_events),
        })
    out = pd.DataFrame(rows)
    return out.sort_values(["research_ready", "avg_net_r", "events"], ascending=[False, False, False]).reset_index(drop=True)


def _ensure_group_columns(events: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    out = events.copy()
    for col in group_cols:
        if col not in out.columns:
            out[col] = "unknown"
    return out


def run_atlas(
    *,
    symbols: list[str],
    exchanges: list[str],
    tfs: list[str],
    days: int,
    context_tf: str = "240",
    output_dir: Path = Path("backtesting/results/event_atlas"),
    config: EventAtlasConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    cfg = config or EventAtlasConfig()
    all_events = []
    for exchange in exchanges:
        for symbol in symbols:
            context = _load_structure_cache(exchange, symbol, context_tf)
            for tf in tfs:
                df = load_data(symbol, tf=tf, days=days, asset_type="crypto", exchange=exchange, crypto_source="merged")
                events = build_event_atlas(
                    df,
                    symbol=symbol,
                    exchange=exchange,
                    tf=tf,
                    config=cfg,
                    structure=context,
                    context_tf=context_tf,
                )
                if not events.empty:
                    all_events.append(events)
                print(f"  {exchange}/{symbol} {tf}: {len(events)} events", flush=True)

    events_df = pd.concat(all_events, ignore_index=True) if all_events else pd.DataFrame()
    summary = summarize_events(events_df)
    context_summary = summarize_context_buckets(events_df)
    output_dir.mkdir(parents=True, exist_ok=True)
    events_df.to_parquet(output_dir / "crypto_event_atlas.parquet", index=False)
    events_df.to_csv(output_dir / "crypto_event_atlas.csv", index=False)
    summary.to_csv(output_dir / "crypto_event_atlas_summary.csv", index=False)
    context_summary.to_csv(output_dir / "crypto_event_context_summary.csv", index=False)
    return events_df, summary


def _score_event_variants(
    data: pd.DataFrame,
    i: int,
    event: str,
    direction: str,
    raw_stop: float,
    cfg: EventAtlasConfig,
    base: dict,
) -> list[dict]:
    rows: list[dict] = []
    for stop_model, stop in _stop_candidates(data, i, direction, raw_stop, cfg, base).items():
        for target_model, target in _target_candidates(data, i, direction, stop, cfg, base).items():
            rows.append(_score_event(
                data,
                i,
                event,
                direction,
                stop,
                cfg,
                base,
                stop_model=stop_model,
                target_model=target_model,
                target_price=target,
            ))
    return rows


def _score_event(
    data: pd.DataFrame,
    i: int,
    event: str,
    direction: str,
    raw_stop: float,
    cfg: EventAtlasConfig,
    base: dict,
    *,
    stop_model: str = "event_extreme",
    target_model: str = "fixed_2r",
    target_price: float | None = None,
) -> dict:
    entry_i = i + 1
    entry = float(data["open"].iat[entry_i])
    min_stop = entry * cfg.min_stop_pct
    if direction == "long":
        stop = min(raw_stop, entry - min_stop)
        risk = entry - stop
        target_1r = entry + risk
        target_2r = entry + 2.0 * risk
        target = target_price if target_price is not None else target_2r
    else:
        stop = max(raw_stop, entry + min_stop)
        risk = stop - entry
        target_1r = entry - risk
        target_2r = entry - 2.0 * risk
        target = target_price if target_price is not None else target_2r

    if risk <= 0 or not np.isfinite(risk) or not _valid_target(entry, target, direction):
        return {
            **base,
            "event": event,
            "direction": direction,
            "stop_model": stop_model,
            "target_model": target_model,
            "invalid": True,
        }

    fwd = data.iloc[entry_i:entry_i + cfg.horizon_bars]
    gross_r, exit_price, exit_reason, hit_1r, hit_2r, hit_target, hit_stop, bars_to_exit = _forward_outcome(
        fwd, direction, entry, stop, target_1r, target_2r, float(target), risk
    )
    mfe_r, mae_r = _mfe_mae(fwd, direction, entry, risk)
    is_stop = exit_reason == "stop"
    is_target = exit_reason in {"target_1r", "target_2r"}
    exit_fee = cfg.taker_fee if is_stop or not is_target else cfg.maker_fee
    cost_r = ((entry * cfg.taker_fee) + (exit_price * exit_fee)) / risk

    return {
        **base,
        "event": event,
        "direction": direction,
        "stop_model": stop_model,
        "target_model": target_model,
        "entry_ts": data["ts"].iat[entry_i],
        "entry": entry,
        "stop": float(stop),
        "risk_price": float(risk),
        "target_1r": float(target_1r),
        "target_2r": float(target_2r),
        "target": float(target),
        "target_r": float(abs(target - entry) / risk),
        "gross_r": float(gross_r),
        "cost_r": float(cost_r),
        "net_r": float(gross_r - cost_r),
        "mfe_r": float(mfe_r),
        "mae_r": float(mae_r),
        "hit_1r": bool(hit_1r),
        "hit_2r": bool(hit_2r),
        "hit_target": bool(hit_target),
        "hit_stop": bool(hit_stop),
        "exit_reason": exit_reason,
        "bars_to_exit": int(bars_to_exit),
        "invalid": False,
    }


def _forward_outcome(
    fwd: pd.DataFrame,
    direction: str,
    entry: float,
    stop: float,
    target_1r: float,
    target_2r: float,
    target: float,
    risk: float,
) -> tuple[float, float, str, bool, bool, bool, bool, int]:
    hit_1r = False
    for offset, row in enumerate(fwd.itertuples(index=False), start=1):
        high = float(row.high)
        low = float(row.low)
        if direction == "long":
            if low <= stop:
                return -1.0, stop, "stop", hit_1r, False, False, True, offset
            if high >= target:
                gross_r = (target - entry) / risk
                return gross_r, target, "target", True, target >= target_2r, True, False, offset
            if high >= target_2r:
                return 2.0, target_2r, "target_2r", True, True, True, False, offset
            if high >= target_1r:
                hit_1r = True
        else:
            if high >= stop:
                return -1.0, stop, "stop", hit_1r, False, False, True, offset
            if low <= target:
                gross_r = (entry - target) / risk
                return gross_r, target, "target", True, target <= target_2r, True, False, offset
            if low <= target_2r:
                return 2.0, target_2r, "target_2r", True, True, True, False, offset
            if low <= target_1r:
                hit_1r = True
    close = float(fwd["close"].iat[-1])
    gross_r = (close - entry) / risk if direction == "long" else (entry - close) / risk
    return gross_r, close, "expiry", hit_1r, False, False, False, len(fwd)


def _stop_candidates(
    data: pd.DataFrame,
    i: int,
    direction: str,
    raw_stop: float,
    cfg: EventAtlasConfig,
    base: dict,
) -> dict[str, float]:
    entry = float(data["open"].iat[i + 1])
    atr_now = float(base["atr"])
    if direction == "long":
        candidates = {
            "event_extreme": raw_stop,
            "prior_swing": float(base["prev_low"]) if np.isfinite(base["prev_low"]) else raw_stop,
            "atr": entry - atr_now,
        }
    else:
        candidates = {
            "event_extreme": raw_stop,
            "prior_swing": float(base["prev_high"]) if np.isfinite(base["prev_high"]) else raw_stop,
            "atr": entry + atr_now,
        }
    return {k: v for k, v in candidates.items() if k in cfg.stop_models and np.isfinite(v)}


def _target_candidates(
    data: pd.DataFrame,
    i: int,
    direction: str,
    stop: float,
    cfg: EventAtlasConfig,
    base: dict,
) -> dict[str, float]:
    entry = float(data["open"].iat[i + 1])
    risk = abs(entry - stop)
    if risk <= 0 or not np.isfinite(risk):
        return {}
    if direction == "long":
        candidates = {
            "fixed_1r": entry + risk,
            "fixed_2r": entry + 2.0 * risk,
            "prior_opposite": float(base["prev_high"]) if np.isfinite(base["prev_high"]) else np.nan,
            "round_number": _next_round_number(entry, direction),
        }
    else:
        candidates = {
            "fixed_1r": entry - risk,
            "fixed_2r": entry - 2.0 * risk,
            "prior_opposite": float(base["prev_low"]) if np.isfinite(base["prev_low"]) else np.nan,
            "round_number": _next_round_number(entry, direction),
        }
    return {
        k: v for k, v in candidates.items()
        if k in cfg.target_models and np.isfinite(v) and _valid_target(entry, v, direction)
    }


def _valid_target(entry: float, target: float | None, direction: str) -> bool:
    if target is None or not np.isfinite(target):
        return False
    return target > entry if direction == "long" else target < entry


def _next_round_number(price: float, direction: str) -> float:
    """Return a simple psychologically relevant round level for crypto."""
    if price <= 0:
        return np.nan
    magnitude = 10 ** np.floor(np.log10(price))
    step = magnitude / 10.0
    if price >= 10_000:
        step = 1_000.0
    elif price >= 1_000:
        step = 100.0
    elif price >= 100:
        step = 10.0
    elif price >= 10:
        step = 1.0
    elif price >= 1:
        step = 0.1
    elif price >= 0.1:
        step = 0.01
    if direction == "long":
        return float(np.ceil(price / step) * step)
    return float(np.floor(price / step) * step)


def _vol_bucket(atr_pct: float) -> str:
    if atr_pct < 0.0015:
        return "low"
    if atr_pct < 0.004:
        return "normal"
    return "high"


def _session_utc(ts: pd.Timestamp) -> str:
    hour = pd.Timestamp(ts).hour
    if 0 <= hour < 7:
        return "asia"
    if 7 <= hour < 13:
        return "london"
    if 13 <= hour < 20:
        return "ny"
    return "late_us"


def _mfe_mae(fwd: pd.DataFrame, direction: str, entry: float, risk: float) -> tuple[float, float]:
    if direction == "long":
        mfe = (float(fwd["high"].max()) - entry) / risk
        mae = (float(fwd["low"].min()) - entry) / risk
    else:
        mfe = (entry - float(fwd["low"].min())) / risk
        mae = (entry - float(fwd["high"].max())) / risk
    return mfe, mae


def _is_compression(data: pd.DataFrame, i: int, bars: int, atr_now: float) -> bool:
    if i - bars < 1:
        return False
    window = data.iloc[i - bars + 1:i + 1]
    mother_high = data["high"].iat[i - bars]
    mother_low = data["low"].iat[i - bars]
    inside = bool((window["high"] <= mother_high).all() and (window["low"] >= mother_low).all())
    narrow = bool((window["high"].max() - window["low"].min()) <= 1.25 * atr_now)
    return inside and narrow


def _atr(df: pd.DataFrame, period: int) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def _prepare_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    data = df[["ts", "open", "high", "low", "close"] + (["volume"] if "volume" in df.columns else [])].copy()
    data["ts"] = pd.to_datetime(data["ts"], utc=True, errors="coerce")
    for col in ["open", "high", "low", "close"]:
        data[col] = pd.to_numeric(data[col], errors="coerce")
    return data.dropna(subset=["ts", "open", "high", "low", "close"]).sort_values("ts").reset_index(drop=True)


def _bar_delta(df: pd.DataFrame) -> pd.Timedelta:
    if len(df) < 2:
        return pd.Timedelta(minutes=1)
    delta = df["ts"].diff().dropna().median()
    return delta if pd.notna(delta) and delta > pd.Timedelta(0) else pd.Timedelta(minutes=1)


def _load_structure_cache(exchange: str, symbol: str, tf: str, root: Path = Path("data/features/structure/L2_R2")) -> pd.DataFrame:
    path = root / exchange / symbol / f"{tf}.parquet"
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_parquet(path)
    except Exception:
        return pd.DataFrame()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build crypto price-action event atlas.")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--exchange", default="both", choices=["binance", "bybit", "both"])
    parser.add_argument("--tfs", default="5,15")
    parser.add_argument("--days", type=int, default=400)
    parser.add_argument("--context-tf", default="240")
    parser.add_argument("--lookback-bars", type=int, default=24)
    parser.add_argument("--horizon-bars", type=int, default=24)
    parser.add_argument("--output-dir", default="backtesting/results/event_atlas")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    exchanges = ["binance", "bybit"] if args.exchange == "both" else [args.exchange]
    tfs = [tf.strip() for tf in args.tfs.split(",") if tf.strip()]
    cfg = EventAtlasConfig(lookback_bars=args.lookback_bars, horizon_bars=args.horizon_bars)

    print("Building crypto event atlas")
    print(f"  Symbols: {len(symbols)}")
    print(f"  Exchanges: {', '.join(exchanges)}")
    print(f"  TFs: {', '.join(tfs)}")
    print(f"  Days: {args.days}")
    events, summary = run_atlas(
        symbols=symbols,
        exchanges=exchanges,
        tfs=tfs,
        days=args.days,
        context_tf=args.context_tf,
        output_dir=Path(args.output_dir),
        config=cfg,
    )
    print(f"Events: {len(events)}")
    if not summary.empty:
        print(summary.head(20).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
