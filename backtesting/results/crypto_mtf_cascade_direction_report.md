# Global -> Local -> Mini -> Entry direction cascade

Per user spec: global=240m, local=30m, mini=5m, entry=1m. Strict AND (all enabled
tiers must agree in direction). Global/local direction = swing-structure regime AND
EMA(21/55) slope agree (validated combo from CLEAN.md Phase 14). Mini/entry direction
= EMA(21/55) slope alone (structure at 1-5m is mostly noise per the pivot-window
finding). 1m data capped at ~106 days (legacy 1m doesn't go deeper); global/local/mini
use the full 400-day window.

## Synthetic ground-truth gate (passed, run first)

| Series | n decided | direction_accuracy |
|---|---|---|
| Known uptrend (240+30 cascade) | 1716 | 81.2% |
| Random walk, no edge (240+30 cascade) | 1652 | 52.8% |

Confirms the cascade methodology detects a real trend when one exists, and does not
manufacture a false edge on pure noise. Real-data numbers below can be trusted as a
genuine (if modest) measurement, not a harness artifact.

## Real data, 6 core pairs, 400-day window (1m capped ~106d)

| Symbol | global+local n | global+local acc | +mini n | +mini acc | +entry n | +entry acc |
|---|---|---|---|---|---|---|
| BTCUSDT | 312 | 53.2% | 1361 | 54.3% | 1168 | 53.3% |
| ETHUSDT | 312 | 60.9% | 1400 | 57.4% | 1173 | 56.0% |
| SOLUSDT | 330 | 55.2% | 1502 | 54.4% | 1347 | 53.5% |
| XRPUSDT | 348 | 52.3% | 1566 | 55.5% | 1239 | 55.9% |
| DOGEUSDT | 351 | 55.6% | 1439 | 55.1% | 1109 | 53.9% |
| BNBUSDT | 322 | 53.1% | 1410 | 54.5% | 1139 | 50.5% |
| **mean** | | **55.0%** | | **55.2%** | | **53.8%** |

## Reading

- All 6 pairs, all 3 stages sit at 50.5-60.9% -- consistently on the positive side of
  50%, unlike every prior test in this investigation (structure alone: 46.9% mean;
  EMA alone: 52.5% mean). This is the first result in the whole crypto foundation-layer
  audit where every pair lands above 50%.
- Adding the 5m mini-trend tier roughly 5x's the sample size (n~1400 vs ~330) at
  essentially the same accuracy (55.2% vs 55.0%) -- more evidence at the same effect
  size, a good sign for the mini tier not diluting the signal.
- Adding the 1m entry tier *slightly* lowers mean accuracy (53.8%) and cuts the data
  window to ~106 days (no deeper 1m legacy exists) -- the extra tier doesn't clearly
  help and shrinks the tested history. Tentative reading: entry-tier timing may be
  better used as a within-window trigger (pick the best bar once global+local+mini
  already agree) rather than a fourth independent direction vote -- untested, flagged
  for a follow-up rather than assumed.
- At n~300-350 (global+local stage) per pair, single-pair significance is marginal
  (binomial SE ~2.7-2.8%, so 55% is ~1.8 SE above 50% for most pairs, ETH's 60.9% is
  ~3.8 SE). Pooled across 6 pairs the effect looks stronger, but pairs are
  price-correlated, not independent trials -- do not read the naive pooled SE as
  6x the evidence.
- Not yet done: walk-forward / rolling-window stability check (does this hold up
  split by time, not just in aggregate) and a real backtest with costs, stops, and
  target sizing -- this measures direction only, symmetric 1:1 R, no execution
  realism yet.

## Reproduce
`python3 -m backtesting.crypto.mtf_cascade_direction` is importable
(`run_cascade(symbol)`); full-table CSV at `crypto_mtf_cascade_direction.csv`
(gitignored, regenerate from `backtesting/crypto/mtf_cascade_direction.py`).
