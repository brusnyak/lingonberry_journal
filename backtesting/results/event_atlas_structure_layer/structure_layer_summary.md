# Structure Layer Checkpoint

Generated: 2026-07-12.

## Question

Does adding causal structure confirmation and an opposing-spike filter improve
the crypto bearish-FVG survivor branch?

## Implementation

Added `backtesting/crypto/direction_layer.py`.

The layer currently tests:

- latest structure row available by `known_after_ts <= entry_ts`;
- short confirmation via latest bear regime, `bos_down`, `choch_down`,
  `bearish_bos`, or `bearish_choch`;
- opposing bullish displacement before a short entry;
- no use of pivot timestamps for decision-time joins.

Execution lab now emits both raw and `structure_confirmed_*` entry models so
the layer can be measured instead of assumed.

## Full Reviewed-Symbol Run

Command:

```bash
PYTHONPATH=. python -m backtesting.crypto.execution_path_lab \
  --symbols 1000PEPEUSDT,AAVEUSDT,AVAXUSDT,DOGEUSDT,ETHUSDT,LINKUSDT,NEARUSDT,SOLUSDT,SUIUSDT,WLDUSDT,XRPUSDT \
  --exchange both \
  --days 60 \
  --tf 15 \
  --expiry-haircut-r 0.10 \
  --output-dir backtesting/results/event_atlas_structure_layer
```

Rows: `28,680`.

Layer aggregate:

| Layer | Rows | Buckets | Avg bucket R | Best avg R | Best PF | Mean stop rate | Mean median MAE |
|---|---:|---:|---:|---:|---:|---:|---:|
| Raw | 18,828 | 24 | +0.241 | +0.353 | 2.41 | 18.2% | -0.445R |
| Structure confirmed | 9,852 | 24 | +0.223 | +0.355 | 2.67 | 14.3% | -0.339R |

Top bucket:

| Entry | Management | Events | Avg R | Median R | PF | Stop rate | Expiry rate |
|---|---|---:|---:|---:|---:|---:|---:|
| structure_confirmed_fvg_top_retest | hold_2r_expiry | 288 | +0.355 | +0.245 | 2.44 | 19.1% | 64.9% |

## Verdict

Structure confirmation helps risk quality, not enough to call direction solved.

What improved:

- Lower stop rate.
- Lower adverse excursion.
- Best PF improved.
- The best overall bucket is now structure-confirmed.

What did not improve enough:

- Average bucket R is slightly lower.
- Expiry rate is still too high.
- Confirmation cuts sample size by about half.

This means the next layer should not be another entry tweak. The next test is
target and exit construction:

1. Compare fixed `2R` against nearest causal structure/liquidity target.
2. Add explicit stale-retest invalidation.
3. Add duplicate suppression per FVG zone.
4. Score rejected trades separately so manual UI review can verify whether the
   filter rejects the same trades a human rejects.

## Research Anchors

- Moskowitz, Ooi, and Pedersen document cross-asset time-series momentum,
  supporting direction as a measurable state rather than an ICT label:
  https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf
- Brock, Lakonishok, and LeBaron is a useful baseline for testing simple price
  and breakout rules before complex discretionary concepts:
  https://finance.martinsewell.com/stylized-facts/dependence/BrockLakonishokLeBaron1992.pdf
- Freqtrade's lookahead-analysis documentation is a practical reminder that
  full-dataframe backtests can silently leak future candles:
  https://www.freqtrade.io/en/stable/lookahead-analysis/
- Recent formal work frames lookahead freedom as an availability-time problem,
  matching this repo's `known_after_ts` contract:
  https://arxiv.org/abs/2607.04958
