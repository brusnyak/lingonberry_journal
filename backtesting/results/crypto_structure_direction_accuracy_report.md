# Crypto Structure/Direction Accuracy -- standalone, no FVG

Tests the causal HTF structure regime (`bull`/`bear`, `data/features/structure/L2_R2`,
the same label already used across the foundation layer) in isolation, decoupled from
any entry pattern. At every regime *transition* (fresh directional call, not every bar
of a persistent trend), takes a symmetric 1:1 R position (ATR(15m) stop = ATR(15m)
target) and walks the 15m path forward.

Scope: 6 core pairs, `binance`, merged source (full history, not exchange-scoped),
**400 days** (2025-06 -> 2026-07, actual span). Structure timeframes: 60m, 240m.
Horizons: 24 / 48 / 96 bars (6h / 12h / 24h at 15m).

## Result

36 cells (6 symbols x 2 structure TFs x 3 horizons), `direction_accuracy` range:
**42.8% -- 53.4%**. No cell clears 54%. Several sit meaningfully *below* 50%
(BTC/BNB/DOGE/XRP at 240m all in the 42.8-44.9% range across every horizon tested)
-- not noise-neutral, mildly anti-predictive on those pairs/timeframe.

| structure_tf | symbol | n_calls (24/48/96h) | direction_accuracy (24/48/96h) |
|---|---|---|---|
| 240 | BTCUSDT | 112 | 43.8% / 43.8% / 43.8% |
| 240 | ETHUSDT | 103 | 51.5% / 51.5% / 51.5% |
| 240 | SOLUSDT | 103 | 52.9% / 53.4% / 53.4% |
| 240 | XRPUSDT | 108 | 42.9% / 44.4% / 44.4% |
| 240 | DOGEUSDT | 115 | 44.7% / 44.3% / 44.3% |
| 240 | BNBUSDT | 109 | 44.9% / 44.9% / 44.9% |
| 60 | BTCUSDT | 441 | 51.8% / 51.9% / 52.2% |
| 60 | ETHUSDT | 459 | 49.1% / 49.1% / 49.2% |
| 60 | SOLUSDT | 450 | 48.6% / 48.6% / 48.6% |
| 60 | XRPUSDT | 437 | 49.3% / 49.2% / 49.2% |
| 60 | DOGEUSDT | 446 | 42.5% / 42.8% / 42.8% |
| 60 | BNBUSDT | 441 | 48.1% / 48.1% / 48.1% |

Full 36-row table: `crypto_structure_direction_accuracy.csv` (gitignored, rerun to
regenerate: `python3 -m backtesting.crypto.structure_direction_accuracy --days 400`).

## Interpretation

The causal HTF structure regime, tested on its own merit with symmetric R (no
target-optimization, no entry-pattern selection bias), has **no measurable directional
edge on a full year of real data**. This is not a small-sample artifact -- n=103-459
calls per cell, largely non-overlapping (transitions only), across 6 pairs and both
HTFs. It is consistent with, and now confirms independent of the FVG-selection
question, Phase 12's finding of 35-56% direction accuracy inside the FVG-triggered
basket: the apparent PF/return edge in that basket is not coming from the direction
call. It is coming from entry timing, target/stop placement, or session/time-of-day
structure layered on top of a coin-flip (or slightly worse) direction signal.

## What this does and doesn't rule out

- Does not rule out that some *specific* entry trigger (FVG retest, sweep, session
  time) has real selection value on its own, independent of HTF trend context -- that
  is a different, still-open question (the London/NY/Late-US session buckets in
  Phase 12 are a candidate place to look, decoupled from the trend-alignment framing).
- Does not rule out that a different structure definition (swing count, ADX-based,
  EMA-slope, market-cap-relative) would do better -- only that *this* implementation
  (swing-based HH/HL/LH/LL -> bull/bear) does not.
- Rules out, with real evidence rather than assumption: "align entries with HTF
  structure direction" as a source of edge in this engine, at 60m or 240m, on 15m
  entries, across all 6 core pairs.
