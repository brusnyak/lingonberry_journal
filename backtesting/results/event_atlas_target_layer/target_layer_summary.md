# Target And Risk Layer Checkpoint

Generated: 2026-07-12.

## Question

Can the structure-confirmed bearish-FVG survivor branch reach acceptable
risk/reward while keeping drawdown low?

## Implementation

Updated `backtesting/crypto/execution_path_lab.py`.

Added:

- explicit target models: `fixed_1_5r`, `fixed_2r`, `structure_swing_low`,
  `round_number`;
- `target_model` in execution summaries;
- minimum target-R gate;
- stale retest rejection for structure-confirmed entries;
- duplicate FVG-zone suppression;
- causal structure target lookup through `known_after_ts <= entry_ts`.

## Run

```bash
PYTHONPATH=. python -m backtesting.crypto.execution_path_lab \
  --symbols 1000PEPEUSDT,AAVEUSDT,AVAXUSDT,DOGEUSDT,ETHUSDT,LINKUSDT,NEARUSDT,SOLUSDT,SUIUSDT,WLDUSDT,XRPUSDT \
  --exchange both \
  --days 60 \
  --tf 15 \
  --expiry-haircut-r 0.10 \
  --output-dir backtesting/results/event_atlas_target_layer
```

Rows: `58,584`.

## Layer Aggregate

| Layer | Rows | Buckets | Avg bucket R | Best avg R | Best PF | Mean stop rate | Mean expiry |
|---|---:|---:|---:|---:|---:|---:|---:|
| Raw | 41,334 | 96 | +0.167 | +0.344 | 2.53 | 23.2% | 57.9% |
| Structure confirmed | 17,250 | 96 | +0.226 | +0.576 | 2.70 | 17.9% | 64.2% |

## Target Model Aggregate

| Target model | Rows | Weighted avg R | Weighted stop | Weighted expiry | Max PF |
|---|---:|---:|---:|---:|---:|
| fixed_1_5r | 24,834 | +0.221 | 17.0% | 60.3% | 2.69 |
| fixed_2r | 24,834 | +0.209 | 17.4% | 69.4% | 2.66 |
| round_number | 5,268 | +0.178 | 22.8% | 67.4% | 2.64 |
| structure_swing_low | 3,648 | +0.088 | 27.7% | 47.4% | 2.70 |

Verdict: structure swing targets are too sparse/fragile right now. Fixed
`1.5R` is the best broad target. Fixed `2R` can still work with BE management
but has more expiry.

## Best Robust Bucket

Filter:

- events `>= 150`;
- symbols `>= 8`;
- both exchanges;
- average R `>= +0.25`;
- PF `>= 2.0`;
- stop rate `<= 22%`.

Best practical bucket:

| Entry | Target | Management | Events | Avg R | Median R | PF | Target rate | Stop rate | Expiry |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| structure_confirmed_fvg_top_retest | fixed_1_5r | partial_1r_be | 185 | +0.378 | +0.510 | 2.69 | 31.4% | 17.3% | 40.0% |

Alternative:

| Entry | Target | Management | Events | Avg R | Median R | PF | Target rate | Stop rate | Expiry |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| structure_confirmed_fvg_top_retest | fixed_2r | be_after_1r | 185 | +0.382 | +0.266 | 2.64 | 16.2% | 17.3% | 53.5% |

## Risk Sizing Proxy

For `structure_confirmed_fvg_top_retest + fixed_1_5r + partial_1r_be`:

- trades: `185`;
- total R: `+69.94R`;
- average: `+0.378R`;
- median: `+0.510R`;
- daily drawdown proxy: `10.56R`;
- trade-sequence drawdown proxy: `11.40R`.

Position risk mapping:

| Risk per trade | Gross return | Daily DD proxy | Trade-sequence DD proxy |
|---:|---:|---:|---:|
| 0.10% | +6.99% | 1.06% | 1.14% |
| 0.15% | +10.49% | 1.58% | 1.71% |
| 0.25% | +17.49% | 2.64% | 2.85% |

Practical risk cap: `0.10%-0.15%` per trade. `0.25%` starts pushing drawdown
above the low-DD goal.

## Verdict

This is the first decent candidate, not a deployable strategy.

What is good:

- RR is no longer negative.
- Sample is not tiny: `185` trades, `11` symbols, Binance+Bybit.
- PF around `2.6-2.7`.
- Stop rate around `17%`.
- Drawdown can be kept under about `2%` if trade risk is capped at `0.15%`.

What is still weak:

- Expiry is still high at `40%`.
- No portfolio concurrency/risk throttle yet.
- No walk-forward validation on this final execution bucket yet.
- No UI packet of accepted/rejected trades for human review yet.

Next test:

1. Build a portfolio/risk-throttle validator for the selected bucket.
2. Add walk-forward validation on execution buckets, not just event buckets.
3. Export UI review samples: accepted winners, accepted losers, rejected stale
   retests, rejected no-confirmation setups.
