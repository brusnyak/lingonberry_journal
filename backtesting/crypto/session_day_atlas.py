"""Daily/session path atlas for crypto setup research.

This is diagnostic code, not a strategy. It labels the actual intraday path of
each symbol-day so skipped days can be reviewed as market conditions instead of
just "no signal".
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from backtesting.crypto.data import load_crypto
from backtesting.crypto.simple_setup_lab import SimpleSetupConfig, direction_context, session_bucket


@dataclass(frozen=True)
class DayAtlasConfig:
    days: int = 180
    exchange: str = "binance"
    source: str = "merged"
    global_tf: str = "240"
    local_tf: str = "30"
    entry_tf: str = "15"
    context_mode: str = "strict"
    context_structure_left: int = 2
    context_structure_right: int = 2


def build_session_day_atlas(symbols: list[str], cfg: DayAtlasConfig | None = None) -> pd.DataFrame:
    config = cfg or DayAtlasConfig()
    rows: list[dict] = []
    for symbol in symbols:
        bars = {
            "global": load_crypto(symbol, tf=config.global_tf, days=config.days, exchange=config.exchange, source=config.source).reset_index(drop=True),
            "local": load_crypto(symbol, tf=config.local_tf, days=config.days, exchange=config.exchange, source=config.source).reset_index(drop=True),
            "entry": load_crypto(symbol, tf=config.entry_tf, days=config.days, exchange=config.exchange, source=config.source).reset_index(drop=True),
        }
        if any(df.empty for df in bars.values()):
            continue
        combo = direction_context(
            bars["global"],
            bars["local"],
            bars["entry"],
            mode=config.context_mode,
            structure_left=config.context_structure_left,
            structure_right=config.context_structure_right,
        )
        rows.extend(label_session_days(symbol, bars["entry"], combo).to_dict("records"))
    return pd.DataFrame(rows).sort_values(["symbol", "day"]).reset_index(drop=True) if rows else pd.DataFrame()


def label_session_days(symbol: str, entry_bars: pd.DataFrame, combo: np.ndarray) -> pd.DataFrame:
    data = entry_bars.copy().reset_index(drop=True)
    data["ts"] = pd.to_datetime(data["ts"], utc=True)
    data["day"] = data["ts"].dt.date
    data["session_utc"] = data["ts"].map(session_bucket)
    combo_s = pd.Series(combo, index=data.index).astype(str)
    rows = []
    for day, group in data.groupby("day", sort=True):
        idx = group.index
        combo_day = combo_s.loc[idx]
        active = combo_day.isin(["bull", "bear"])
        day_open = float(group["open"].iloc[0])
        day_close = float(group["close"].iloc[-1])
        day_high = float(group["high"].max())
        day_low = float(group["low"].min())
        day_range = max(day_high - day_low, 0.0)
        efficiency = abs(day_close - day_open) / day_range if day_range > 0 else np.nan
        asia = _session_stats(group, "asia")
        london = _session_stats(group, "london")
        ny = _session_stats(group, "ny")
        rows.append(
            {
                "symbol": symbol,
                "day": day,
                "bars": int(len(group)),
                "active_context_bars": int(active.sum()),
                "bull_context_bars": int((combo_day == "bull").sum()),
                "bear_context_bars": int((combo_day == "bear").sum()),
                "neutral_context_bars": int((combo_day == "neutral").sum()),
                "day_return_pct": (day_close / day_open - 1.0) * 100.0 if day_open else np.nan,
                "day_range_pct": day_range / day_open * 100.0 if day_open else np.nan,
                "directional_efficiency": efficiency,
                "asia_range_pct": asia["range_pct"],
                "london_range_pct": london["range_pct"],
                "ny_range_pct": ny["range_pct"],
                "london_swept_asia_high": _swept_high(london, asia),
                "london_swept_asia_low": _swept_low(london, asia),
                "ny_swept_asia_high": _swept_high(ny, asia),
                "ny_swept_asia_low": _swept_low(ny, asia),
                "ny_swept_london_high": _swept_high(ny, london),
                "ny_swept_london_low": _swept_low(ny, london),
                "day_path": classify_day_path(day_open, day_close, day_range, asia, london, ny),
            }
        )
    return pd.DataFrame(rows)


def classify_day_path(day_open: float, day_close: float, day_range: float, asia: dict, london: dict, ny: dict) -> str:
    if day_range <= 0 or not np.isfinite(day_range):
        return "unknown"
    efficiency = abs(day_close - day_open) / day_range
    range_pct = day_range / day_open * 100.0 if day_open else np.nan
    london_sweep_high = _swept_high(london, asia)
    london_sweep_low = _swept_low(london, asia)
    ny_sweep_high = _swept_high(ny, london) or _swept_high(ny, asia)
    ny_sweep_low = _swept_low(ny, london) or _swept_low(ny, asia)
    if np.isfinite(range_pct) and range_pct < 0.75:
        return "range"
    if efficiency < 0.25:
        if london_sweep_high or london_sweep_low or ny_sweep_high or ny_sweep_low:
            return "sweep_revert"
        return "range"
    if day_close > day_open and efficiency >= 0.45:
        return "directional_up"
    if day_close < day_open and efficiency >= 0.45:
        return "directional_down"
    if ny_sweep_high or ny_sweep_low:
        return "ny_sweep"
    if london_sweep_high or london_sweep_low:
        return "london_sweep"
    return "transition"


def _session_stats(day_bars: pd.DataFrame, session: str) -> dict:
    part = day_bars[day_bars["session_utc"] == session]
    if part.empty:
        return {"open": np.nan, "close": np.nan, "high": np.nan, "low": np.nan, "range_pct": np.nan}
    open_ = float(part["open"].iloc[0])
    high = float(part["high"].max())
    low = float(part["low"].min())
    close = float(part["close"].iloc[-1])
    return {
        "open": open_,
        "close": close,
        "high": high,
        "low": low,
        "range_pct": (high - low) / open_ * 100.0 if open_ else np.nan,
    }


def _swept_high(session: dict, reference: dict) -> bool:
    return bool(np.isfinite(session.get("high", np.nan)) and np.isfinite(reference.get("high", np.nan)) and session["high"] > reference["high"])


def _swept_low(session: dict, reference: dict) -> bool:
    return bool(np.isfinite(session.get("low", np.nan)) and np.isfinite(reference.get("low", np.nan)) and session["low"] < reference["low"])


def atlas_summary(atlas: pd.DataFrame) -> pd.DataFrame:
    if atlas.empty:
        return pd.DataFrame()
    grouped = atlas.groupby(["day_path"], dropna=False).agg(
        days=("day", "count"),
        active_context_rate=("active_context_bars", lambda s: float((s > 0).mean())),
        median_active_context_bars=("active_context_bars", "median"),
        median_day_range_pct=("day_range_pct", "median"),
        median_efficiency=("directional_efficiency", "median"),
        london_sweep_asia_high_rate=("london_swept_asia_high", "mean"),
        london_sweep_asia_low_rate=("london_swept_asia_low", "mean"),
        ny_sweep_london_high_rate=("ny_swept_london_high", "mean"),
        ny_sweep_london_low_rate=("ny_swept_london_low", "mean"),
    )
    return grouped.reset_index().sort_values(["days"], ascending=False).reset_index(drop=True)
