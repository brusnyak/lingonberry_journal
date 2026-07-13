"""Global -> local -> mini-trend direction cascade.

Per-tier direction:
  - global (240m) / local (30m): swing-structure regime (bull/bear) AND
    EMA(21/55) slope must agree -- same combined signal validated in
    structure_direction_accuracy's single-TF test.
  - mini (5m): EMA(21/55) slope alone (no structure -- swing detection at
    this granularity is mostly noise, per the pivot-window finding in
    CLEAN.md Phase 14).

A trade candidate requires ALL enabled tiers to agree in direction (strict
AND). Each stage is evaluated independently -- own regime-transition points,
own symmetric-R outcome walk -- so adding tiers can be compared stage by
stage, not just the final one.

An entry (1m) tier was tried and dropped (2026-07-13, CLEAN.md Phase 15/16):
it slightly lowered accuracy as a 4th independent direction vote and capped
history to ~106 days. Left out of the active pipeline rather than kept as
unused dead code; may return later as a within-window timing trigger instead
of a direction vote, if that's tested and shown to help.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from backtesting.crypto.data import load_crypto
from backtesting.crypto.event_atlas import _atr
from backtesting.crypto.structure_direction_accuracy import _walk_outcome
from backtesting.features.structure import StructureConfig, build_structure_index

TIERS = ("global", "local", "mini")
DEFAULT_TF_MAP = {"global": "240", "local": "30", "mini": "5"}


def vec_ema_state(ohlcv: pd.DataFrame, fast: int = 21, slow: int = 55) -> pd.Series:
    """Vectorized EMA(fast/slow) slope state -- bullish/bearish/mixed per bar.

    Equivalent to direction_layer.ema_state's classification rule, but computed
    once over the whole series instead of recomputing the EWM per bar (the
    per-bar helper is O(n^2) over a full series and only meant for one-off
    lookups at a single entry index).
    """
    close = pd.to_numeric(ohlcv["close"], errors="coerce")
    f = close.ewm(span=fast, adjust=False).mean()
    s = close.ewm(span=slow, adjust=False).mean()
    slope = f.diff()
    bullish = (close > f) & (f >= s) & (slope >= 0)
    bearish = (close < f) & (f <= s) & (slope <= 0)
    out = pd.Series("mixed", index=ohlcv.index)
    out[bullish] = "bullish"
    out[bearish] = "bearish"
    return out


def structure_ema_direction(ohlcv: pd.DataFrame, left: int = 2, right: int = 2) -> pd.DataFrame:
    """bull/bear/neutral per bar -- requires swing-structure regime AND EMA slope to agree."""
    ohlcv = ohlcv.reset_index(drop=True)
    structure = build_structure_index(ohlcv, StructureConfig(left=left, right=right))
    struct_regime = structure["regime"].astype(str)
    ema_states = vec_ema_state(ohlcv)
    direction = pd.Series("neutral", index=ohlcv.index)
    direction[(struct_regime == "bull") & (ema_states == "bullish")] = "bull"
    direction[(struct_regime == "bear") & (ema_states == "bearish")] = "bear"
    return pd.DataFrame({"ts": pd.to_datetime(ohlcv["ts"], utc=True).values, "direction": direction.values})


def ema_only_direction(ohlcv: pd.DataFrame) -> pd.DataFrame:
    """bull/bear/neutral per bar from EMA slope alone (used for mini/entry tiers)."""
    ohlcv = ohlcv.reset_index(drop=True)
    states = vec_ema_state(ohlcv)
    direction = states.map({"bullish": "bull", "bearish": "bear"}).fillna("neutral")
    return pd.DataFrame({"ts": pd.to_datetime(ohlcv["ts"], utc=True).values, "direction": direction.values})


def asof_direction(fine_ts: pd.Series, coarse_dir: pd.DataFrame) -> np.ndarray:
    """Causal as-of join: latest coarse-tier direction known at/before each fine-tier bar."""
    fine_ts = pd.to_datetime(fine_ts, utc=True)
    coarse = coarse_dir.sort_values("ts")
    coarse_ts = pd.to_datetime(coarse["ts"], utc=True)
    idx = coarse_ts.to_numpy().searchsorted(fine_ts.to_numpy(), side="right") - 1
    idx = np.clip(idx, 0, len(coarse) - 1)
    return coarse["direction"].to_numpy()[idx]


def evaluate_direction_series(base: pd.DataFrame, combo: np.ndarray, horizon: int = 48, atr_period: int = 14) -> dict:
    """Walk forward from every fresh bull/bear agreement point, symmetric ATR R."""
    combo = pd.Series(combo)
    changed = combo.ne(combo.shift(1)) & combo.isin(["bull", "bear"])
    atr = _atr(base, atr_period)
    outcomes = []
    for i in np.where(changed.to_numpy())[0]:
        a = atr.iat[i] if i < len(atr) else np.nan
        if not (a > 0) or i >= len(base) - 1:
            continue
        direction = "long" if combo.iat[i] == "bull" else "short"
        outcomes.append(_walk_outcome(base, i, direction, a, a, horizon))
    n = len(outcomes)
    wins = outcomes.count("win")
    losses = outcomes.count("loss")
    decided = wins + losses
    return {"n": n, "decided": decided, "direction_accuracy": wins / decided if decided else np.nan}


@dataclass(frozen=True)
class CascadeConfig:
    tf_map: dict = field(default_factory=lambda: dict(DEFAULT_TF_MAP))
    days: dict = field(default_factory=lambda: {"global": 400, "local": 400, "mini": 400})
    exchange: str = "binance"
    source: str = "merged"
    horizon_bars: int = 48


def build_mini_stage_series(symbol: str, config: CascadeConfig | None = None) -> tuple[pd.DataFrame, np.ndarray]:
    """Return (mini-tf bars, combo direction array) for the active global+local+mini
    cascade -- the shared computation both `run_cascade` and rolling-window stability
    checks are built on, so a window slice and the full-history number agree by
    construction (same combo array, just sliced by entry timestamp)."""
    cfg = config or CascadeConfig()
    bars = {
        tier: load_crypto(symbol, tf=cfg.tf_map[tier], days=cfg.days[tier], exchange=cfg.exchange, source=cfg.source).reset_index(drop=True)
        for tier in TIERS
    }
    if any(b.empty for b in bars.values()):
        return pd.DataFrame(), np.array([])

    dir_global = structure_ema_direction(bars["global"])
    dir_local = structure_ema_direction(bars["local"])
    dir_mini = ema_only_direction(bars["mini"])

    g = asof_direction(bars["mini"]["ts"], dir_global)
    l = asof_direction(bars["mini"]["ts"], dir_local)
    m = dir_mini["direction"].to_numpy()
    combo = np.where((g == l) & (l == m) & (g != "neutral"), g, "neutral")
    return bars["mini"], combo


def run_cascade(symbol: str, config: CascadeConfig | None = None) -> dict[str, dict]:
    """Stage-by-stage cascade: global+local, +mini. Each stage's `direction_accuracy`
    is independently evaluated on its own tier's bars, so adding a tier can be compared."""
    cfg = config or CascadeConfig()
    bars_global = load_crypto(symbol, tf=cfg.tf_map["global"], days=cfg.days["global"], exchange=cfg.exchange, source=cfg.source).reset_index(drop=True)
    bars_local = load_crypto(symbol, tf=cfg.tf_map["local"], days=cfg.days["local"], exchange=cfg.exchange, source=cfg.source).reset_index(drop=True)
    if bars_global.empty or bars_local.empty:
        return {}

    dir_global = structure_ema_direction(bars_global)
    dir_local = structure_ema_direction(bars_local)
    g_local = asof_direction(bars_local["ts"], dir_global)
    l_local = dir_local["direction"].to_numpy()
    combo_local = np.where((g_local == l_local) & (g_local != "neutral"), g_local, "neutral")
    stage_global_local = evaluate_direction_series(bars_local, combo_local, cfg.horizon_bars)

    bars_mini, combo_mini = build_mini_stage_series(symbol, cfg)
    if bars_mini.empty:
        return {"global_local": stage_global_local}
    stage_plus_mini = evaluate_direction_series(bars_mini, combo_mini, cfg.horizon_bars)

    return {
        "global_local": stage_global_local,
        "plus_mini": stage_plus_mini,
    }


def rolling_stability(
    symbol: str,
    *,
    window_days: int = 30,
    step_days: int = 7,
    config: CascadeConfig | None = None,
    horizon_bars: int = 48,
) -> pd.DataFrame:
    """Split the plus-mini cascade into rolling calendar windows and measure direction
    accuracy per window -- does the aggregate 55%-ish number hold up across time, or is
    it concentrated in one stretch of the 400-day span."""
    cfg = config or CascadeConfig()
    bars, combo = build_mini_stage_series(symbol, cfg)
    if bars.empty:
        return pd.DataFrame()

    ts = pd.to_datetime(bars["ts"], utc=True)
    combo_series = pd.Series(combo)
    changed = combo_series.ne(combo_series.shift(1)) & combo_series.isin(["bull", "bear"])
    atr = _atr(bars, 14)

    start = ts.min()
    end_all = ts.max()
    rows = []
    while start + pd.Timedelta(days=window_days) <= end_all:
        window_end = start + pd.Timedelta(days=window_days)
        in_window = (ts >= start) & (ts < window_end)
        idxs = np.where(changed.to_numpy() & in_window.to_numpy())[0]
        outcomes = []
        for i in idxs:
            a = atr.iat[i] if i < len(atr) else np.nan
            if not (a > 0) or i >= len(bars) - 1:
                continue
            direction = "long" if combo_series.iat[i] == "bull" else "short"
            outcomes.append(_walk_outcome(bars, i, direction, a, a, horizon_bars))
        n = len(outcomes)
        wins = outcomes.count("win")
        losses = outcomes.count("loss")
        decided = wins + losses
        rows.append({
            "window_start": start,
            "window_end": window_end,
            "n": n,
            "decided": decided,
            "direction_accuracy": wins / decided if decided else np.nan,
        })
        start += pd.Timedelta(days=step_days)

    return pd.DataFrame(rows)
