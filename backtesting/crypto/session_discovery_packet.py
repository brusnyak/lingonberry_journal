"""Manual session-discovery packet exporter for crypto.

This is not a strategy. It exports compact symbol-week evidence so we can
manually label missed and taken intraday setups before converting anything into
deterministic rules.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.crypto.data import load_crypto
from backtesting.crypto.event_atlas import _atr
from backtesting.crypto.session_range_setup_lab import (
    SETUP_SESSIONS,
    SessionRangeConfig,
    build_indicator_features,
    reference_direction,
    reference_features,
    session_range_signal,
    trade_candidate,
    trade_feature_context,
)
from backtesting.crypto.simple_setup_lab import session_bucket
from backtesting.features.structure import StructureConfig, build_structure_index

DEFAULT_DISCOVERY_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT"]


@dataclass(frozen=True)
class DiscoveryPacketConfig:
    days: int = 90
    exchange: str = "binance"
    source: str = "merged"
    entry_tf: str = "15"
    output_dir: str = "backtesting/results/crypto_session_discovery_packet"
    weeks: tuple[pd.Timestamp, ...] = ()
    recent_weeks: int = 1
    context_days: int = 1
    setups: tuple[str, ...] = (
        "london_asia_fakeout",
        "london_asia_breakout",
        "ny_london_reversal",
        "ny_london_breakout",
    )
    min_rr: float = 1.5
    horizon_bars: int = 96
    max_stress_cost_r: float | None = 0.25


def build_discovery_packet(symbol: str, cfg: DiscoveryPacketConfig) -> dict[str, pd.DataFrame]:
    bars = load_crypto(symbol, tf=cfg.entry_tf, days=cfg.days, exchange=cfg.exchange, source=cfg.source).reset_index(drop=True)
    if bars.empty:
        return {"bars": pd.DataFrame(), "sessions": pd.DataFrame(), "candidates": pd.DataFrame()}

    bars = prepare_bar_features(bars)
    selected = select_review_windows(bars, cfg)
    if selected.empty:
        return {"bars": pd.DataFrame(), "sessions": pd.DataFrame(), "candidates": pd.DataFrame()}

    sessions = summarize_sessions(symbol, selected)
    candidates = find_session_candidates(symbol, bars, selected, cfg)
    bars_out = review_bars(symbol, selected)
    return {"bars": bars_out, "sessions": sessions, "candidates": candidates}


def prepare_bar_features(bars: pd.DataFrame) -> pd.DataFrame:
    out = bars.copy().reset_index(drop=True)
    out["_source_i"] = out.index
    out["ts"] = pd.to_datetime(out["ts"], utc=True)
    out["day"] = out["ts"].dt.floor("D")
    out["week_start"] = monday_week_start(out["ts"])
    out["session_utc"] = out["ts"].map(session_bucket)
    atr_values = _atr(out, 14)
    indicators = build_indicator_features(out, atr_values)
    structure = build_structure_index(out, StructureConfig(left=2, right=2))

    out["atr"] = atr_values
    for col in ["ema21", "ema55", "ema21_slope_5", "vwap", "vwap_slope_12", "vwap_z_score"]:
        out[col] = indicators[col] if col in indicators else np.nan
    for col in [
        "structure_label",
        "regime",
        "bos_up",
        "bos_down",
        "choch_up",
        "choch_down",
        "sweep_high",
        "sweep_low",
        "last_swing_high",
        "last_swing_low",
        "last_hh",
        "last_hl",
        "last_lh",
        "last_ll",
        "long_structural_sl",
        "short_structural_sl",
        "long_target_1",
        "short_target_1",
    ]:
        out[col] = structure[col] if col in structure else np.nan
    out["bar_return_atr"] = (out["close"] - out["open"]) / out["atr"].replace(0, np.nan)
    out["range_atr"] = (out["high"] - out["low"]) / out["atr"].replace(0, np.nan)
    return out


def select_review_windows(bars: pd.DataFrame, cfg: DiscoveryPacketConfig) -> pd.DataFrame:
    if bars.empty:
        return bars
    week_starts = [pd.Timestamp(w, tz="UTC") if pd.Timestamp(w).tzinfo is None else pd.Timestamp(w).tz_convert("UTC") for w in cfg.weeks]
    if not week_starts:
        unique_weeks = sorted(pd.to_datetime(bars["week_start"], utc=True).dropna().unique())
        week_starts = [pd.Timestamp(w) for w in unique_weeks[-cfg.recent_weeks:]]
    masks = []
    for week in week_starts:
        start = week - pd.Timedelta(days=cfg.context_days)
        end = week + pd.Timedelta(days=7 + cfg.context_days)
        masks.append((bars["ts"] >= start) & (bars["ts"] < end))
    if not masks:
        return bars.iloc[0:0].copy()
    mask = masks[0].copy()
    for extra in masks[1:]:
        mask |= extra
    return bars.loc[mask].copy().reset_index(drop=True)


def summarize_sessions(symbol: str, bars: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (day, session), group in bars.groupby(["day", "session_utc"], sort=True):
        atr = float(group["atr"].median())
        high = float(group["high"].max())
        low = float(group["low"].min())
        open_ = float(group["open"].iloc[0])
        close = float(group["close"].iloc[-1])
        rng = high - low
        rows.append(
            {
                "symbol": symbol,
                "day": pd.Timestamp(day),
                "session_utc": session,
                "bars": int(len(group)),
                "start_ts": group["ts"].iloc[0],
                "end_ts": group["ts"].iloc[-1],
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "range_atr": rng / atr if np.isfinite(atr) and atr > 0 else np.nan,
                "return_atr": (close - open_) / atr if np.isfinite(atr) and atr > 0 else np.nan,
                "close_location": (close - low) / rng if rng > 0 else np.nan,
                "dominant_regime": mode_or_missing(group["regime"]),
                "bos_up": int(group["bos_up"].sum()),
                "bos_down": int(group["bos_down"].sum()),
                "choch_up": int(group["choch_up"].sum()),
                "choch_down": int(group["choch_down"].sum()),
                "sweep_high": int(group["sweep_high"].sum()),
                "sweep_low": int(group["sweep_low"].sum()),
            }
        )
    return pd.DataFrame(rows)


def find_session_candidates(symbol: str, all_bars: pd.DataFrame, selected: pd.DataFrame, cfg: DiscoveryPacketConfig) -> pd.DataFrame:
    if selected.empty:
        return pd.DataFrame()
    all_bars = all_bars.reset_index(drop=True)
    selected_indices = set(selected["_source_i"] if "_source_i" in selected.columns else selected.index)
    atr_values = all_bars["atr"]
    indicator_features = build_indicator_features(all_bars, atr_values)
    rows = []
    for setup in cfg.setups:
        setup_cfg = SessionRangeConfig(
            days=cfg.days,
            exchange=cfg.exchange,
            source=cfg.source,
            entry_tf=cfg.entry_tf,
            setup=setup,
            min_rr=cfg.min_rr,
            horizon_bars=cfg.horizon_bars,
            max_stress_cost_r=cfg.max_stress_cost_r,
        )
        rows.extend(_setup_candidates(symbol, all_bars, selected_indices, atr_values, indicator_features, setup_cfg))
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows).sort_values(["entry_ts", "symbol", "setup"]).reset_index(drop=True)
    out["manual_label"] = ""
    out["manual_reason"] = ""
    return out


def _setup_candidates(
    symbol: str,
    bars: pd.DataFrame,
    selected_indices: set[int],
    atr_values: pd.Series,
    indicator_features: pd.DataFrame,
    cfg: SessionRangeConfig,
) -> list[dict]:
    reference_session, trade_session, mode = SETUP_SESSIONS[cfg.setup]
    rows = []
    for day, day_bars in bars.groupby("day", sort=True):
        if not set(day_bars.index).intersection(selected_indices):
            continue
        ref = day_bars[day_bars["session_utc"].eq(reference_session)]
        trade = day_bars[day_bars["session_utc"].eq(trade_session)]
        if ref.empty or trade.empty:
            continue
        ref_high = float(ref["high"].max())
        ref_low = float(ref["low"].min())
        ref_mid = (ref_high + ref_low) / 2.0
        ref_end_i = int(ref.index[-1])
        atr_now = float(atr_values.iat[ref_end_i])
        if not np.isfinite(atr_now) or atr_now <= 0:
            continue
        ref_range_atr = (ref_high - ref_low) / atr_now
        ref_features = reference_features(ref, ref_high, ref_low, atr_now, cfg)
        ref_bias = reference_direction(ref, ref_high, ref_low, atr_now, cfg)

        swept_high = False
        swept_low = False
        for i in trade.index:
            i = int(i)
            if i not in selected_indices:
                continue
            atr_i = float(atr_values.iat[i])
            if not np.isfinite(atr_i) or atr_i <= 0:
                continue
            swept_high = swept_high or float(bars["high"].iat[i]) > ref_high
            swept_low = swept_low or float(bars["low"].iat[i]) < ref_low
            signal = session_range_signal(
                mode=mode,
                close=float(bars["close"].iat[i]),
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
                i,
                signal,
                atr_i,
                indicator_features,
                ref_features,
                ref_high,
                ref_low,
                ref_mid,
            )
            candidate, stage = trade_candidate(symbol, bars, atr_values, i, signal, cfg, ref_high, ref_low, ref_range_atr, features)
            row = {
                "symbol": symbol,
                "setup": cfg.setup,
                "day": pd.Timestamp(day),
                "candidate_stage": stage,
                "entry_ts": pd.Timestamp(bars["ts"].iat[i]),
                "direction": signal,
                "reference_session": reference_session,
                "trade_session": trade_session,
                "reference_high": ref_high,
                "reference_low": ref_low,
                "reference_range_atr": ref_range_atr,
                "reference_bias": ref_bias or "",
                "structure_label": str(bars["structure_label"].iat[i]),
                "regime": str(bars["regime"].iat[i]),
                "bos_up": bool(bars["bos_up"].iat[i]),
                "bos_down": bool(bars["bos_down"].iat[i]),
                "choch_up": bool(bars["choch_up"].iat[i]),
                "choch_down": bool(bars["choch_down"].iat[i]),
                "sweep_high": bool(swept_high),
                "sweep_low": bool(swept_low),
                "close": float(bars["close"].iat[i]),
                "atr": atr_i,
            }
            if candidate:
                row.update(candidate)
                row["passes_stress_cost"] = bool(cfg.max_stress_cost_r is None or float(candidate["stress_cost_r"]) <= cfg.max_stress_cost_r)
            else:
                row["passes_stress_cost"] = False
            rows.append(row)
    return rows


def review_bars(symbol: str, bars: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "ts",
        "day",
        "week_start",
        "session_utc",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "atr",
        "range_atr",
        "bar_return_atr",
        "ema21",
        "ema55",
        "ema21_slope_5",
        "vwap",
        "vwap_slope_12",
        "vwap_z_score",
        "structure_label",
        "regime",
        "bos_up",
        "bos_down",
        "choch_up",
        "choch_down",
        "sweep_high",
        "sweep_low",
        "last_swing_high",
        "last_swing_low",
        "last_hh",
        "last_hl",
        "last_lh",
        "last_ll",
        "long_structural_sl",
        "short_structural_sl",
        "long_target_1",
        "short_target_1",
    ]
    out = bars[[c for c in cols if c in bars.columns]].copy()
    out.insert(0, "symbol", symbol)
    return out


def write_discovery_packet(symbol: str, packet: dict[str, pd.DataFrame], cfg: DiscoveryPacketConfig) -> list[Path]:
    out_dir = Path(cfg.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, df in packet.items():
        path = out_dir / f"{symbol}_{cfg.entry_tf}m_{name}.csv"
        df.to_csv(path, index=False)
        written.append(path)
    review_path = out_dir / f"{symbol}_{cfg.entry_tf}m_review.md"
    review_path.write_text(build_review_note(symbol, packet, cfg), encoding="utf-8")
    written.append(review_path)
    return written


def build_review_note(symbol: str, packet: dict[str, pd.DataFrame], cfg: DiscoveryPacketConfig) -> str:
    bars = packet.get("bars", pd.DataFrame())
    sessions = packet.get("sessions", pd.DataFrame())
    candidates = packet.get("candidates", pd.DataFrame())
    lines = [
        f"# {symbol} Manual Session Discovery Packet",
        "",
        "Purpose: label real tradeable intraday moves before writing rules.",
        "",
        "Review labels:",
        "- valid_long / valid_short: trade was visible without hindsight",
        "- skip: no clean setup",
        "- missed_move: price moved but setup was not objectively tradable at the time",
        "",
        "Files:",
        f"- `{symbol}_{cfg.entry_tf}m_bars.csv`: bar context with session, ATR, EMA/VWAP, structure.",
        f"- `{symbol}_{cfg.entry_tf}m_sessions.csv`: day/session summary.",
        f"- `{symbol}_{cfg.entry_tf}m_candidates.csv`: current setup candidates plus forward outcome.",
        "",
        "Counts:",
        f"- bars: {len(bars)}",
        f"- sessions: {len(sessions)}",
        f"- candidates: {len(candidates)}",
    ]
    if not candidates.empty and "setup" in candidates:
        by_setup = candidates.groupby("setup").size().rename("candidates").reset_index().to_string(index=False)
        lines.extend(["", "Candidates by setup:", "```", by_setup, "```"])
    return "\n".join(lines) + "\n"


def mode_or_missing(values: pd.Series) -> str:
    values = values.dropna().astype(str)
    if values.empty:
        return ""
    mode = values.mode()
    return "" if mode.empty else str(mode.iloc[0])


def monday_week_start(ts: pd.Series) -> pd.Series:
    ts = pd.to_datetime(ts, utc=True)
    return ts.dt.floor("D") - pd.to_timedelta(ts.dt.weekday, unit="D")


def parse_weeks(value: str) -> tuple[pd.Timestamp, ...]:
    if not value.strip():
        return ()
    return tuple(pd.Timestamp(part.strip(), tz="UTC") for part in value.split(",") if part.strip())


def parse_csv(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def main() -> int:
    parser = argparse.ArgumentParser(description="Export manual crypto session-discovery packets.")
    parser.add_argument("--symbols", default=",".join(DEFAULT_DISCOVERY_SYMBOLS))
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--entry-tf", default="15")
    parser.add_argument("--weeks", default="", help="Comma-separated UTC week starts, e.g. 2026-06-01,2026-06-08.")
    parser.add_argument("--recent-weeks", type=int, default=1)
    parser.add_argument("--context-days", type=int, default=1)
    parser.add_argument("--setups", default="london_asia_fakeout,london_asia_breakout,ny_london_reversal,ny_london_breakout")
    parser.add_argument("--min-rr", type=float, default=1.5)
    parser.add_argument("--horizon-bars", type=int, default=96)
    parser.add_argument("--max-stress-cost-r", type=float, default=0.25)
    parser.add_argument("--output-dir", default="backtesting/results/crypto_session_discovery_packet")
    args = parser.parse_args()

    cfg = DiscoveryPacketConfig(
        days=args.days,
        entry_tf=str(args.entry_tf),
        output_dir=args.output_dir,
        weeks=parse_weeks(args.weeks),
        recent_weeks=args.recent_weeks,
        context_days=args.context_days,
        setups=parse_csv(args.setups),
        min_rr=args.min_rr,
        horizon_bars=args.horizon_bars,
        max_stress_cost_r=args.max_stress_cost_r,
    )
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    symbols = [s for s in symbols if s != "DOGEUSDT"]
    all_written = []
    for symbol in symbols:
        packet = build_discovery_packet(symbol, cfg)
        all_written.extend(write_discovery_packet(symbol, packet, cfg))
    print(f"wrote {len(all_written)} files to {Path(cfg.output_dir)}")
    for path in all_written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
