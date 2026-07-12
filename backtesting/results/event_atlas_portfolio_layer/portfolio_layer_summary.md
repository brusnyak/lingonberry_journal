# Portfolio Layer Checkpoint

Generated: 2026-07-12.

## Question

Does the best execution bucket still look decent after portfolio throttles?

Bucket:

- entry: `structure_confirmed_fvg_top_retest`;
- target: `fixed_1_5r`;
- management: `partial_1r_be`;
- candidate trades: `185`.

## Implementation

Added `backtesting/crypto/portfolio_validation.py`.

Risk controls:

- risk per trade;
- max concurrent trades;
- max open positions per symbol;
- symbol cooldown after a loss;
- daily loss cap;
- account-level return and drawdown metrics.

## Conservative Throttle

Command:

```bash
PYTHONPATH=. python -m backtesting.crypto.portfolio_validation \
  --input backtesting/results/event_atlas_target_layer/survivor_execution_paths.csv \
  --entry-model structure_confirmed_fvg_top_retest \
  --target-model fixed_1_5r \
  --management-model partial_1r_be \
  --risk-pct 0.0015 \
  --max-open 3 \
  --max-open-per-symbol 1 \
  --daily-loss-limit-pct 0.0075 \
  --output-dir backtesting/results/event_atlas_portfolio_layer
```

Result:

| Candidates | Accepted | Return | Max DD | Daily Max DD | Return/DD | PF | Avg R | Stop | Expiry |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 185 | 78 | +4.17% | 0.65% | 0.59% | 6.39 | 2.50 | +0.356 | 19.2% | 37.2% |

This is clean but underpowered.

## Throttle Scan

Best profiles under `2%` max drawdown:

| Risk | Max open | Daily cap | Accepted | Return | Max DD | Daily DD | Return/DD | PF | Avg R |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.25% | uncapped | 0.75% | 99 | +10.11% | 1.71% | 1.61% | 5.91 | 2.85 | +0.409 |
| 0.25% | 6 | 0.75% | 97 | +9.55% | 1.71% | 1.61% | 5.58 | 2.75 | +0.394 |
| 0.25% | 4 | 0.75% | 87 | +8.36% | 1.32% | 1.21% | 6.35 | 2.71 | +0.384 |
| 0.20% | uncapped | 0.50% | 98 | +8.20% | 1.26% | 1.18% | 6.49 | 2.93 | +0.418 |
| 0.20% | 6 | 0.50% | 96 | +7.74% | 1.26% | 1.18% | 6.13 | 2.82 | +0.403 |

## Verdict

The portfolio layer did not kill the candidate.

Best practical research setting:

- risk per trade: `0.20%`;
- max open: `6` or uncapped after exchange/symbol caps;
- max open per symbol: `1`;
- daily loss cap: `0.50%`;
- expected in-sample return: about `+7.7%` to `+8.2%`;
- drawdown proxy: about `1.2%-1.3%`;
- PF: about `2.8%-2.9`.

This is now worth manual chart review and walk-forward execution validation.
It is still not ready for live cTrader/funded-account deployment.

## What Still Blocks Deployment

1. This is in-sample over one 60-day slice.
2. No final walk-forward execution validation yet.
3. No forward-paper/demo run yet.
4. No slippage/fill latency model beyond current cost approximation.
5. No kill-switch implementation for live execution.

Live funded deployment is premature. Paper/demo/dry-run only.
