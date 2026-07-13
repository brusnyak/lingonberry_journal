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

This is the single, configurable tool for the structure/direction foundation
layer -- one CLI with a --mode flag, not a new throwaway script per question.
Every mode takes --symbols/--days/--global-tf/--local-tf/--mini-tf, so
re-running at a different interval or timeframe is a flag change, not a new
file. Modes (2026-07-13, CLEAN.md Phase 21):
  direction-accuracy   symmetric-R direction call only (Phase 15/16)
  real-sltp            actual structural SL/target, real R-multiples (Phase 17)
  null-test            randomized-direction control on the real-sltp walk,
                        the check that told apart Phase 17 (fails) from
                        Phase 20 (4/6 pairs pass) -- previously only ever run
                        as a one-off inline script, now reusable
  rolling-stability     rolling calendar-window stability check (Phase 16)
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from backtesting.crypto.data import load_crypto
from backtesting.crypto.event_atlas import _atr
from backtesting.crypto.structure_direction_accuracy import _walk_outcome
from backtesting.features.structure import StructureConfig, build_structure_index

TIERS = ("global", "local", "mini")
DEFAULT_TF_MAP = {"global": "240", "local": "30", "mini": "5"}
DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "BNBUSDT"]


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


# ── Real structural SL/target (reuses PropFirmStructureV1's existing fields --
# not a new stop/target mechanism, see CLEAN.md Phase 17) ─────────────────────


def _first_finite(*values) -> float:
    for v in values:
        if v is not None and np.isfinite(v):
            return float(v)
    return np.nan


def structural_stop_target(structure_row: pd.Series, direction: str, entry: float, min_rr: float = 1.5) -> tuple[float, float]:
    """(sl, tp) from the existing structural fields -- same fallback pattern as
    PropFirmStructureV1: structural level for the stop, structural target
    floored at min_rr if the nearest opposing level is closer than that."""
    if direction == "long":
        sl = _first_finite(structure_row.get("long_structural_sl"), structure_row.get("last_swing_low"))
        if not np.isfinite(sl) or sl >= entry:
            return np.nan, np.nan
        risk = entry - sl
        tp = max(_first_finite(structure_row.get("long_target_1"), entry + min_rr * risk), entry + min_rr * risk)
    else:
        sl = _first_finite(structure_row.get("short_structural_sl"), structure_row.get("last_swing_high"))
        if not np.isfinite(sl) or sl <= entry:
            return np.nan, np.nan
        risk = sl - entry
        tp = min(_first_finite(structure_row.get("short_target_1"), entry - min_rr * risk), entry - min_rr * risk)
    return sl, tp


def walk_structural_outcome(
    bars: pd.DataFrame,
    entry_i: int,
    direction: str,
    sl: float,
    tp: float,
    horizon: int = 200,
    track_excursion: bool = False,
) -> dict | None:
    """First-touch walk forward with the real (asymmetric) structural SL/TP.
    Returns r_multiple (None on same-bar ambiguous touch treated as loss, 0.0
    on expiry) plus mfe_r/mae_r if track_excursion. None if risk is invalid."""
    entry = float(bars["close"].iat[entry_i])
    risk = abs(entry - sl)
    if risk <= 0:
        return None
    target_r = abs(tp - entry) / risk
    end_i = min(entry_i + horizon, len(bars) - 1)
    mfe = mae = 0.0
    r_multiple = 0.0  # expiry default
    hit = False
    for j in range(entry_i + 1, end_i + 1):
        hi = float(bars["high"].iat[j])
        lo = float(bars["low"].iat[j])
        if direction == "long":
            hit_tp, hit_sl = hi >= tp, lo <= sl
            if track_excursion:
                mfe = max(mfe, (hi - entry) / risk)
                mae = max(mae, (entry - lo) / risk)
        else:
            hit_tp, hit_sl = lo <= tp, hi >= sl
            if track_excursion:
                mfe = max(mfe, (entry - lo) / risk)
                mae = max(mae, (hi - entry) / risk)
        if hit_tp and hit_sl:
            r_multiple, hit = -1.0, False
            break
        if hit_tp:
            r_multiple, hit = target_r, True
            break
        if hit_sl:
            r_multiple, hit = -1.0, False
            break
    result = {"r_multiple": r_multiple, "hit": hit, "risk_price": risk}
    if track_excursion:
        result["mfe_r"] = mfe
        result["mae_r"] = -mae
    return result


def evaluate_real_sltp_series(bars: pd.DataFrame, structure: pd.DataFrame, combo: np.ndarray, min_rr: float = 1.5, horizon: int = 200) -> dict:
    """Same signal points as evaluate_direction_series, but real asymmetric
    structural SL/TP instead of symmetric ATR R -- CLEAN.md Phase 17/20."""
    combo_s = pd.Series(combo)
    changed = combo_s.ne(combo_s.shift(1)) & combo_s.isin(["bull", "bear"])
    r_multiples: list[float] = []
    for i in np.where(changed.to_numpy())[0]:
        if i >= len(bars) - 1:
            continue
        direction = "long" if combo_s.iat[i] == "bull" else "short"
        entry = float(bars["close"].iat[i])
        sl, tp = structural_stop_target(structure.iloc[i], direction, entry, min_rr)
        if not np.isfinite(sl):
            continue
        outcome = walk_structural_outcome(bars, i, direction, sl, tp, horizon)
        if outcome is not None:
            r_multiples.append(outcome["r_multiple"])
    r = np.array(r_multiples)
    n = len(r)
    wins = (r > 0).sum()
    losses = (r <= 0).sum()
    gross_win = r[r > 0].sum()
    gross_loss = -r[r <= 0].sum()
    return {
        "n": n,
        "win_rate": wins / n if n else np.nan,
        "avg_r": r.mean() if n else np.nan,
        "pf": gross_win / gross_loss if gross_loss > 0 else (np.inf if gross_win > 0 else np.nan),
    }


def null_test_real_sltp(
    bars: pd.DataFrame,
    structure: pd.DataFrame,
    combo: np.ndarray,
    *,
    min_rr: float = 1.5,
    horizon: int = 200,
    n_seeds: int = 20,
) -> dict:
    """Randomize direction on the same signal timestamps, same real structural
    SL/TP mechanism -- tells apart a real directional edge from an R:R
    structure that rides drift regardless of direction (CLEAN.md Phase 17: the
    check that found symmetric-looking positive PF wasn't real for most
    pairs; Phase 20: the same check confirmed 4/6 pairs ARE real). Previously
    only ever run as a one-off inline script -- this is that logic, reusable."""
    real = evaluate_real_sltp_series(bars, structure, combo, min_rr, horizon)
    combo_s = pd.Series(combo)
    changed = combo_s.ne(combo_s.shift(1)) & combo_s.isin(["bull", "bear"])
    idxs = np.where(changed.to_numpy())[0]

    null_means = []
    for seed in range(n_seeds):
        rng = np.random.default_rng(seed)
        r_multiples = []
        for i in idxs:
            if i >= len(bars) - 1:
                continue
            direction = "long" if rng.random() < 0.5 else "short"
            entry = float(bars["close"].iat[i])
            sl, tp = structural_stop_target(structure.iloc[i], direction, entry, min_rr)
            if not np.isfinite(sl):
                continue
            outcome = walk_structural_outcome(bars, i, direction, sl, tp, horizon)
            if outcome is not None:
                r_multiples.append(outcome["r_multiple"])
        null_means.append(np.mean(r_multiples) if r_multiples else np.nan)

    null_mean = float(np.nanmean(null_means))
    percentile = float((np.array(null_means) < real["avg_r"]).mean() * 100) if np.isfinite(real["avg_r"]) else np.nan
    return {**real, "null_mean_avg_r": null_mean, "percentile": percentile}


def build_global_local_series(symbol: str, config: CascadeConfig | None = None) -> tuple[pd.DataFrame, pd.DataFrame, np.ndarray]:
    """(local bars, local structure index, combo direction array) for the
    global+local-only stage -- used by real-sltp/null-test at that stage."""
    cfg = config or CascadeConfig()
    bars_global = load_crypto(symbol, tf=cfg.tf_map["global"], days=cfg.days["global"], exchange=cfg.exchange, source=cfg.source).reset_index(drop=True)
    bars_local = load_crypto(symbol, tf=cfg.tf_map["local"], days=cfg.days["local"], exchange=cfg.exchange, source=cfg.source).reset_index(drop=True)
    if bars_global.empty or bars_local.empty:
        return pd.DataFrame(), pd.DataFrame(), np.array([])
    structure_local = build_structure_index(bars_local, StructureConfig(left=2, right=2))
    dir_global = structure_ema_direction(bars_global)
    dir_local = structure_ema_direction(bars_local)
    g = asof_direction(bars_local["ts"], dir_global)
    l = dir_local["direction"].to_numpy()
    combo = np.where((g == l) & (g != "neutral"), g, "neutral")
    return bars_local, structure_local, combo


def build_full_cascade_series(symbol: str, config: CascadeConfig | None = None) -> tuple[pd.DataFrame, pd.DataFrame, np.ndarray]:
    """(mini bars, mini structure index, combo direction array) for the full
    global+local+mini stage -- used by real-sltp/null-test at that stage."""
    cfg = config or CascadeConfig()
    bars_mini, combo = build_mini_stage_series(symbol, cfg)
    if bars_mini.empty:
        return pd.DataFrame(), pd.DataFrame(), np.array([])
    structure_mini = build_structure_index(bars_mini, StructureConfig(left=2, right=2))
    return bars_mini, structure_mini, combo


# ── CLI ─────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="Configurable structure/direction cascade lab -- one tool, not a new script per question.")
    parser.add_argument("--mode", required=True, choices=["direction-accuracy", "real-sltp", "null-test", "rolling-stability"])
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--stage", default="plus_mini", choices=["global_local", "plus_mini"], help="Which cascade stage to evaluate (real-sltp/null-test modes).")
    parser.add_argument("--days", type=int, default=400)
    parser.add_argument("--global-tf", default="240")
    parser.add_argument("--local-tf", default="30")
    parser.add_argument("--mini-tf", default="5")
    parser.add_argument("--exchange", default="binance")
    parser.add_argument("--source", default="merged", choices=["exchange", "legacy", "merged"])
    parser.add_argument("--min-rr", type=float, default=1.5)
    parser.add_argument("--horizon", type=int, default=200)
    parser.add_argument("--seeds", type=int, default=20, help="Null-test mode only.")
    parser.add_argument("--window-days", type=int, default=30, help="Rolling-stability mode only.")
    parser.add_argument("--step-days", type=int, default=7, help="Rolling-stability mode only.")
    parser.add_argument("--output", default="", help="Optional CSV path to save the result table.")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    cfg = CascadeConfig(
        tf_map={"global": args.global_tf, "local": args.local_tf, "mini": args.mini_tf},
        days={"global": args.days, "local": args.days, "mini": args.days},
        exchange=args.exchange,
        source=args.source,
    )

    rows: list[dict] = []
    if args.mode == "direction-accuracy":
        for symbol in symbols:
            result = run_cascade(symbol, cfg)
            for stage, r in result.items():
                rows.append({"symbol": symbol, "stage": stage, **r})

    elif args.mode == "real-sltp":
        builder = build_global_local_series if args.stage == "global_local" else build_full_cascade_series
        for symbol in symbols:
            bars, structure, combo = builder(symbol, cfg)
            if bars.empty:
                continue
            result = evaluate_real_sltp_series(bars, structure, combo, args.min_rr, args.horizon)
            rows.append({"symbol": symbol, "stage": args.stage, **result})

    elif args.mode == "null-test":
        builder = build_global_local_series if args.stage == "global_local" else build_full_cascade_series
        for symbol in symbols:
            bars, structure, combo = builder(symbol, cfg)
            if bars.empty:
                continue
            result = null_test_real_sltp(bars, structure, combo, min_rr=args.min_rr, horizon=args.horizon, n_seeds=args.seeds)
            rows.append({"symbol": symbol, "stage": args.stage, **result})

    elif args.mode == "rolling-stability":
        for symbol in symbols:
            r = rolling_stability(symbol, window_days=args.window_days, step_days=args.step_days, config=cfg)
            r["symbol"] = symbol
            rows.append(r)
        result_df = pd.concat(rows, ignore_index=True) if rows and isinstance(rows[0], pd.DataFrame) else pd.DataFrame(rows)
        print(result_df.to_string(index=False))
        if args.output:
            result_df.to_csv(args.output, index=False)
        return 0

    result_df = pd.DataFrame(rows)
    print(result_df.to_string(index=False))
    if args.output:
        result_df.to_csv(args.output, index=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
