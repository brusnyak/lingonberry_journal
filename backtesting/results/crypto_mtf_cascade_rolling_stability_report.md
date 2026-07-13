# Global+local+mini cascade -- rolling 30-day stability check

Entry tier (1m) dropped per direction (slightly hurt accuracy, capped history to
~106d). Standing cascade: global(240m)+local(30m) structure+EMA agreement, AND
mini(5m) EMA-slope agreement. Rolling 30-day windows, 7-day step, over the full
400-day span -- 53 windows/pair, 318 total.

## Result

| Symbol | Windows (n>=5 calls) | % windows > 50% | Median acc | Worst | Best |
|---|---|---|---|---|---|
| BTCUSDT | 53 | 67.9% | 52.5% | 29.4% | 70.9% |
| ETHUSDT | 52 | 90.4% | 56.5% | 40.6% | 70.9% |
| SOLUSDT | 53 | 77.4% | 55.1% | 40.0% | 63.6% |
| XRPUSDT | 53 | 81.1% | 55.1% | 45.0% | 66.3% |
| DOGEUSDT | 53 | 79.2% | 55.4% | 43.3% | 63.4% |
| BNBUSDT | 53 | 73.6% | 55.2% | 41.6% | 67.8% |
| **pooled** | 318 | **78.2%** | **55.2%** | | |

## Reading

- Median per-pair accuracy (55.1-56.5%) closely matches the earlier full-window
  aggregate (55.2% mean) -- the signal is not concentrated in one lucky stretch,
  it's the typical window.
- 67.9-90.4% of rolling windows land above 50% per pair, pooled 78.2% across 318
  windows -- meaningfully more windows than the "foundation" layer's earlier n=3-7
  window rolling checks (CLEAN.md Phase 12), and calendar-stepped rather than a
  handful of heavily-overlapping slices of one short span.
- Worst windows do dip well below 50% (29.4% on BTC, 40-45% on others) -- this is
  not universally positive, some 30-day stretches are genuinely bad for the signal.
  Consistent with a real, modest edge riding on top of noisy short-term windows, not
  a guarantee.
- Still direction-only, symmetric 1:1 R, no costs -- this says the *direction call*
  is stable across time, not that a tradeable strategy exists yet. Per user
  direction: stop/target design (structural, not symmetric ATR) is the next step,
  since risk:reward shape changes what "accuracy" should even mean here.

## Reproduce
`backtesting.crypto.mtf_cascade_direction.rolling_stability(symbol, window_days=30,
step_days=7)`. Full table: `crypto_mtf_cascade_rolling_stability.csv` (gitignored).
