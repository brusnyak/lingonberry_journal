"""Export global+local+mini cascade signals as a review-UI-compatible CSV.

Reuses the existing structural SL/target layer (build_structure_index's
long/short_structural_sl and long/short_target_1 -- the same fields
PropFirmStructureV1 already uses) rather than inventing a new stop/target
mechanism. Purpose: let a human visually check the cascade's structure/
direction calls in the review UI (webapp/templates/review.html's
"LOAD FOUNDATION REVIEW" pattern), the same way foundation_review_packet.csv
is already used.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.crypto.data import load_crypto
from backtesting.crypto.mtf_cascade_direction import (
    CascadeConfig,
    asof_direction,
    structural_stop_target,
    structure_ema_direction,
    walk_structural_outcome,
)
from backtesting.features.structure import StructureConfig, build_structure_index

DEFAULT_OUTPUT = Path("backtesting/results/crypto_mtf_cascade_direction/cascade_review_packet.csv")
PREDICTOR = "crypto_cascade_global_local_mini"


def _session_utc(ts: pd.Timestamp) -> str:
    h = ts.hour
    if 7 <= h < 12:
        return "london"
    if 12 <= h < 17:
        return "ny"
    if 17 <= h < 22:
        return "late_us"
    return "asia"


def build_cascade_review_packet(
    symbols: list[str],
    *,
    config: CascadeConfig | None = None,
    min_rr: float = 1.5,
    exchange: str = "binance",
    max_rows_per_symbol: int = 75,
) -> pd.DataFrame:
    """max_rows_per_symbol must stay below the review UI's default fetch limit
    (80, webapp/templates/review.html). The UI sorts by review_bucket (best
    before worst) then truncates to that limit -- if a symbol has more real
    winners than the limit (every pair here does: 128-170 wins out of
    300-350 signals), truncation silently drops every loser and displays a
    fake ~100% win rate. Capping the export below the UI's limit means
    nothing gets truncated, so the true win rate (40-52% per symbol, matches
    the Phase 17 backtest exactly) is what actually renders. Thinning is
    systematic (evenly spaced through time), not outcome-filtered, so it
    preserves both the time spread and the real win/loss ratio."""
    cfg = config or CascadeConfig()
    rows: list[dict] = []
    for symbol in symbols:
        bars_global = load_crypto(symbol, tf=cfg.tf_map["global"], days=cfg.days["global"], exchange=exchange, source=cfg.source).reset_index(drop=True)
        bars_local = load_crypto(symbol, tf=cfg.tf_map["local"], days=cfg.days["local"], exchange=exchange, source=cfg.source).reset_index(drop=True)
        if bars_global.empty or bars_local.empty:
            continue

        dir_global = structure_ema_direction(bars_global)
        dir_local = structure_ema_direction(bars_local)
        structure_local = build_structure_index(bars_local, StructureConfig(left=2, right=2))

        g = asof_direction(bars_local["ts"], dir_global)
        l = dir_local["direction"].to_numpy()
        combo = np.where((g == l) & (g != "neutral"), g, "neutral")
        combo_s = pd.Series(combo)
        changed = combo_s.ne(combo_s.shift(1)) & combo_s.isin(["bull", "bear"])

        symbol_rows: list[dict] = []
        for i in np.where(changed.to_numpy())[0]:
            if i >= len(bars_local) - 1:
                continue
            direction = "long" if combo_s.iat[i] == "bull" else "short"
            srow = structure_local.iloc[i]
            entry = float(bars_local["close"].iat[i])
            sl, tp = structural_stop_target(srow, direction, entry, min_rr)
            if not np.isfinite(sl):
                continue

            outcome = walk_structural_outcome(bars_local, i, direction, sl, tp, track_excursion=True)
            if outcome is None:
                continue
            ts = pd.Timestamp(bars_local["ts"].iat[i])
            symbol_rows.append({
                "ts": ts.isoformat(),
                "symbol": symbol,
                "exchange": exchange,
                "tf": cfg.tf_map["local"],
                "predictor": PREDICTOR,
                "session": _session_utc(ts),
                "direction": direction,
                "entry_price": entry,
                "sl": sl,
                "tp1": tp,
                "risk_price": outcome["risk_price"],
                "outcome_1.5r": outcome["r_multiple"],
                "hit_1.5r": outcome["hit"],
                "mfe_r": outcome["mfe_r"],
                "mae_r": outcome["mae_r"],
                "exit_reason": "target" if outcome["hit"] else "stop",
                "review_bucket": "sample",  # neutral -- must NOT correlate with win/loss, see docstring
                "notes_hint": "Global(240m)+local(30m) structure+EMA agreement, structural SL/target (reused from PropFirmStructureV1) -- verify the direction call visually, not just the R outcome.",
            })

        if len(symbol_rows) > max_rows_per_symbol:
            step = len(symbol_rows) / max_rows_per_symbol
            symbol_rows = [symbol_rows[int(i * step)] for i in range(max_rows_per_symbol)]
        rows.extend(symbol_rows)

    return pd.DataFrame(rows)


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Export cascade signals as a review-UI CSV.")
    parser.add_argument("--symbols", default="BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,DOGEUSDT,BNBUSDT")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    df = build_cascade_review_packet(symbols)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"{len(df)} rows -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
