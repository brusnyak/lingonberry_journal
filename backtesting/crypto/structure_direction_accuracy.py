"""Standalone structure/direction accuracy test -- no FVG, no entry pattern.

Answers one question in isolation: does the causal HTF structure regime
(bull/bear from data/features/structure/L2_R2, already used across the
foundation layer) predict forward price direction at all, before any entry
trigger (FVG retest, sweep, etc.) is layered on top?

At every causal regime *transition* (not every bar -- avoids counting one
persistent trend hundreds of times) on a chosen structure timeframe, take a
position in the implied direction using ATR(15m) as symmetric stop/target
(1:1 R, no target-optimization bias) and walk the 15m path forward for a
fixed horizon. This is the same trend_up/trend_down/pullback logic the rest
of the foundation layer relies on, tested on its own, on real full-year
history (not the ~47-day L2_R2 slice the FVG-triggered basket was tested on).
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.crypto.data import load_crypto
from backtesting.crypto.event_atlas import _atr

DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "BNBUSDT"]
STRUCTURE_ROOT = Path("data/features/structure/L2_R2")


@dataclass(frozen=True)
class DirectionAccuracyConfig:
    entry_tf: str = "15"
    days: int = 400
    exchange: str = "binance"
    atr_period: int = 14
    r_mult: float = 1.0
    horizons_bars: tuple[int, ...] = (24, 48, 96)


def _load_structure(symbol: str, exchange: str, tf: str) -> pd.DataFrame:
    path = STRUCTURE_ROOT / exchange / symbol / f"{tf}.parquet"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path)
    df["known_after_ts"] = pd.to_datetime(df["known_after_ts"], utc=True, errors="coerce")
    return df.dropna(subset=["known_after_ts"]).sort_values("known_after_ts").reset_index(drop=True)


def _regime_transitions(structure: pd.DataFrame) -> pd.DataFrame:
    """Rows where regime changes to bull/bear (a fresh directional call)."""
    reg = structure["regime"].astype(str)
    changed = reg.ne(reg.shift(1))
    out = structure[changed & reg.isin(["bull", "bear"])].copy()
    return out


def _walk_outcome(
    ohlcv: pd.DataFrame,
    entry_i: int,
    direction: str,
    stop_dist: float,
    target_dist: float,
    horizon: int,
) -> str:
    """Return 'win', 'loss', or 'expiry' -- first-touch, causal (only bars after entry_i)."""
    entry_price = float(ohlcv["close"].iat[entry_i])
    end_i = min(entry_i + horizon, len(ohlcv) - 1)
    if direction == "long":
        target_level = entry_price + target_dist
        stop_level = entry_price - stop_dist
    else:
        target_level = entry_price - target_dist
        stop_level = entry_price + stop_dist
    for j in range(entry_i + 1, end_i + 1):
        high = float(ohlcv["high"].iat[j])
        low = float(ohlcv["low"].iat[j])
        hit_target = high >= target_level if direction == "long" else low <= target_level
        hit_stop = low <= stop_level if direction == "long" else high >= stop_level
        if hit_target and hit_stop:
            return "loss"  # ambiguous same-bar touch -- conservative, count as loss
        if hit_target:
            return "win"
        if hit_stop:
            return "loss"
    return "expiry"


def run_direction_accuracy(
    *,
    symbols: list[str] = None,
    structure_tfs: tuple[str, ...] = ("60", "240"),
    config: DirectionAccuracyConfig | None = None,
) -> pd.DataFrame:
    cfg = config or DirectionAccuracyConfig()
    symbols = symbols or DEFAULT_SYMBOLS
    rows: list[dict] = []

    for symbol in symbols:
        ohlcv = load_crypto(symbol, tf=cfg.entry_tf, days=cfg.days, exchange=cfg.exchange, source="merged")
        if ohlcv.empty:
            continue
        ohlcv = ohlcv.reset_index(drop=True)
        atr = _atr(ohlcv, cfg.atr_period)

        for structure_tf in structure_tfs:
            structure = _load_structure(symbol, cfg.exchange, structure_tf)
            if structure.empty:
                continue
            transitions = _regime_transitions(structure)
            if transitions.empty:
                continue

            for horizon in cfg.horizons_bars:
                outcomes = []
                for _, srow in transitions.iterrows():
                    known_ts = srow["known_after_ts"]
                    idx = ohlcv["ts"].searchsorted(known_ts, side="right")
                    if idx >= len(ohlcv) - 1:
                        continue
                    entry_i = int(idx)
                    atr_now = float(atr.iat[entry_i]) if entry_i < len(atr) else np.nan
                    if not np.isfinite(atr_now) or atr_now <= 0:
                        continue
                    direction = "long" if srow["regime"] == "bull" else "short"
                    outcome = _walk_outcome(
                        ohlcv, entry_i, direction,
                        stop_dist=atr_now * cfg.r_mult,
                        target_dist=atr_now * cfg.r_mult,
                        horizon=horizon,
                    )
                    outcomes.append(outcome)

                if not outcomes:
                    continue
                n = len(outcomes)
                wins = outcomes.count("win")
                losses = outcomes.count("loss")
                expiries = outcomes.count("expiry")
                decided = wins + losses
                rows.append({
                    "symbol": symbol,
                    "structure_tf": structure_tf,
                    "horizon_bars": horizon,
                    "n_calls": n,
                    "wins": wins,
                    "losses": losses,
                    "expiries": expiries,
                    "direction_accuracy": wins / decided if decided else np.nan,
                    "expiry_rate": expiries / n if n else np.nan,
                })

    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Standalone structure/direction accuracy test (no FVG).")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--structure-tfs", default="60,240")
    parser.add_argument("--days", type=int, default=400)
    parser.add_argument("--horizons", default="24,48,96")
    parser.add_argument("--output", default="backtesting/results/crypto_structure_direction_accuracy.csv")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    structure_tfs = tuple(t.strip() for t in args.structure_tfs.split(",") if t.strip())
    horizons = tuple(int(h) for h in args.horizons.split(",") if h.strip())
    cfg = DirectionAccuracyConfig(days=args.days, horizons_bars=horizons)

    result = run_direction_accuracy(symbols=symbols, structure_tfs=structure_tfs, config=cfg)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(out, index=False)
    print(result.sort_values(["structure_tf", "horizon_bars", "symbol"]).to_string(index=False))
    print(f"\nSaved to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
