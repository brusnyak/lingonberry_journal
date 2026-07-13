# Shock/EMA Execution-Layer Checkpoint

Date: 2026-07-13.

## Scope

- Symbols: `1000PEPEUSDT`, `AAVEUSDT`, `AVAXUSDT`, `DOGEUSDT`, `ETHUSDT`,
  `LINKUSDT`, `NEARUSDT`, `SOLUSDT`, `SUIUSDT`, `WLDUSDT`, `XRPUSDT`.
- Exchanges: Binance and Bybit.
- Timeframe: `15m`.
- Lookback: `60d`.
- Output: `backtesting/results/event_atlas_shock_layer/`.
- Execution rows: `78,744`.

## What Changed

- Added causal large-displacement state:
  - bearish shock can permit a stale retest as continuation;
  - bullish shock blocks short entries unless fresh bearish confirmation exists
    after the shock.
- Added management variants:
  - breakeven after price reaches `50%` of target distance;
  - partial at `1R` plus breakeven after `50%` target progress.
- Added EMA state as an optional research variant behind
  `--include-ema-confirmed`.

## Best Practical Bucket

Bucket:

- entry: `structure_confirmed_fvg_top_retest`;
- target: `fixed_1_5r`;
- management: `partial_1r_be_after_half_target`;
- events: `192`;
- symbols: `11`;
- exchanges: `2`.

Stats:

- avg R: `+0.371`;
- median R: `+0.466`;
- PF: `2.99`;
- target rate: `27.6%`;
- stop rate: `13.0%`;
- expiry rate: `39.6%`;
- median MFE: `+1.14R`;
- median MAE: `-0.42R`.

Comparison to prior best bucket:

- prior best: `structure_confirmed_fvg_top_retest + fixed_1_5r + partial_1r_be`;
- prior events: `185`;
- prior avg R: about `+0.378`;
- prior PF: about `2.69`;
- prior stop rate: about `17.3%`.

Verdict: expectancy is roughly flat to slightly lower, but risk quality
improved. The stop-rate reduction is the useful result.

## Portfolio Proxy

Same bucket with `max_open_trades=6`, `max_open_per_symbol=1`,
`daily_loss_limit_pct=0.50%`:

- risk/trade `0.20%`: `101` accepted, `+7.51%` return, `0.90%` max DD,
  return/DD `8.33`, PF `2.82`;
- risk/trade `0.25%`: `97` accepted, `+9.21%` return, `1.13%` max DD,
  return/DD `8.17`, PF `2.85`.

Verdict: `0.20%` risk/trade is the cleaner research setting. `0.25%` still fits
under `2%` DD in this sample but is a worse default until walk-forward confirms.

## EMA Verdict

EMA did not beat structure confirmation as a primary direction filter.

Observed aggregate from the exploratory EMA-inclusive run:

- `structure_confirmed_fvg_top_retest`: weighted avg R `+0.326`;
- `ema_structure_confirmed_fvg_top_retest`: weighted avg R `+0.262`;
- EMA reduced sample size and did not improve the practical bucket.

Verdict: keep EMA optional. Do not make EMA a strategy gate unless it wins a
walk-forward or symbol-filter test.

## Current Judgment

The user review was directionally correct:

- the stop model was not the main problem;
- entry/direction state and target/management were the next broken layers;
- violent price movement must change market state, not be ignored.

This branch is stronger than the previous one, but still not deployable.

Next test:

1. Run discovery/holdout on the shock-aware bucket.
2. Add symbol walk-forward promotion/rejection.
3. Generate UI review samples from:
   - accepted winners;
   - accepted losers;
   - stale-continuation entries;
   - bullish-shock rejections.
4. Only after that, consider a paper strategy.
