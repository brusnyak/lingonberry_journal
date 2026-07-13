# Crypto Foundation Layer Audit

Date: 2026-07-13.

## Verdict

Do not add another recognition layer yet.

The current engine has enough experimental logic. The weak point is not lack of
pattern vocabulary. The weak point is confidence that each foundation layer is
independently correct and stable:

1. direction,
2. entry trigger,
3. stop geometry,
4. target model,
5. management model,
6. portfolio throttles,
7. validation / holdout.

## Current Layers

| Layer | Current Implementation | Confidence | Reason |
| --- | --- | --- | --- |
| Data loading | Binance/Bybit exchange-scoped OHLCV through `load_data` | Medium | Enough for research, but exchange/source coverage still needs formal freshness and gap reports per run. |
| Structure availability | `known_after_ts` structure lookup | Medium-high | Causal lookup exists; must remain mandatory for any multi-timeframe feature. |
| Direction context | 4H structure regime, 1H/15m EMA state, session, shock state | Medium | Useful filters exist, but direction accuracy is still only around 50-56% on better setups. |
| Setup event | FVG event/retest matrix | Medium | Event generation is frequent and executable, but broad buckets are noisy. |
| Entry trigger | next open, CE retest, edge retest, structure-confirmed variants | Medium-low | Some entry priorities work, but too many variants can duplicate the same trade if not canonicalized. |
| Stop model | prior swing / minimum distance | Medium | Stop rates are not the primary failure on stronger setups, but stops still need path review. |
| Target model | fixed 1.5R and 2R in matrix; canonical harness defaults to 2R | Medium-low | 2R works on 15m winners; 1.5R helps on weak 5m. Target must be setup/timeframe-specific. |
| Management | hold, BE after half target, partial 1R + BE | Low-medium | Current canonical promotion mainly uses BE-after-half or hold. Needs direct A/B validation. |
| Portfolio risk | max open trades, max per symbol, cooldown, daily loss limit | Medium | Basic throttle is implemented and de-duped, but no deployment-grade live simulation yet. |
| Validation | 30d, 60d, 5m/15m comparisons | Low-medium | Good start, but not enough rolling holdout evidence. |

## Proven

- Duplicate execution bug was real and fixed.
- Broad London-long is not good enough:
  - `all_london_long`: `361` accepted, `+0.017R avg`, `PF 1.04`, `5.70% max DD`.
- Canonical setup selection is necessary:
  - removes duplicate raw/confirmed executions;
  - emits one selected execution per signal;
  - makes UI review meaningful.
- Best current `15m/60d` module:
  - `late_us_short_bull_flush_ce`,
  - `85` accepted,
  - `+0.493R avg`,
  - `PF 3.23`,
  - `60.0%` win rate,
  - `15.3%` stop rate,
  - `52.9%` expiry rate.
- Best current `15m/30d` module:
  - `london_long_middle_local_next_open`,
  - `42` accepted,
  - `+0.796R avg`,
  - `PF 5.99`,
  - `76.2%` win rate,
  - `9.5%` stop rate.

## Assumed

- Binance price action is sufficient for first-pass crypto research; no need to duplicate Bybit/Binance for every test.
- 15m should be the primary signal timeframe.
- 5m should be an entry-refinement layer, not the main strategy-search layer.
- Session logic matters, but it needs setup-specific validation.

## Unknown / Weak

- Whether London strength is persistent or just the latest 30d regime.
- Whether EMA filters genuinely improve direction accuracy out-of-sample.
- Whether session setups transfer across assets or only work on a few names.
- Whether current BE management exits too early or saves enough drawdown to justify lost upside.
- Whether fixed `2R` is better than nearest liquidity / prior high-low target after holdout.
- Whether direction accuracy can be pushed materially above 55-60% without overfitting.

## Target Test: Fixed 1.5R vs Fixed 2R

Controlled test: same setup filters and entry priority; only target changed.

| Window | Setup | Better Target | Evidence |
| --- | --- | --- | --- |
| 15m/30d | London long next-open | 2R | `+0.796R` vs `+0.684R`; PF `5.99` vs `5.49`. |
| 15m/30d | London long retest | 2R | `+0.758R` vs `+0.624R`; PF `5.58` vs `4.48`. |
| 15m/30d | Late-US bull flush short | 2R by avg R, 1.5R by DD | `2R +0.510R`; `1.5R +0.474R`, lower DD. |
| 15m/60d | Late-US bull flush short | 2R by avg R, 1.5R by DD | `2R +0.493R`; `1.5R +0.482R`, lower DD. |
| 15m/60d | London long retest | 2R by avg R, 1.5R by DD | `2R +0.320R`; `1.5R +0.280R`, slightly better return/DD. |
| 5m/30d | London long retest | 1.5R | `1.5R +0.191R`; `2R +0.042R`. |
| 5m/30d | London long next-open | 1.5R | `1.5R +0.141R`; `2R +0.020R`. |

Conclusion: lowering RR globally is wrong. `2R` is still the best raw target for
the strongest `15m` setups. `1.5R` is useful for weaker/noisier `5m` paths and
some drawdown control. Target selection should become a setup/timeframe-specific
model, not a fixed ideology.

## Overfit Risk

Current risk is medium-high.

Reasons:

- Many modules already exist.
- Some strongest numbers come from short 30d windows.
- Direction accuracy is not yet high enough to justify complex entry logic.
- The same broad event universe can generate too many variants around the same
  price area if canonicalization is not enforced.

Hard rule: no setup gets promoted unless it survives:

1. exact-execution de-duplication,
2. 30d discovery and separate 30d holdout,
3. 60d combined sanity check,
4. per-symbol contribution check,
5. path forensics: MFE, MAE, bars to 1R, target, stop, expiry,
6. UI review of best winners, worst losers, bad-direction losers, and
   target-too-far cases.

## Recommended Next Work

Build a foundation validation harness before adding more price-action
recognition:

1. For each accepted candidate, record layer outcomes:
   - direction correct: MFE >= 1R,
   - entry bad: MAE <= -1R before 1R,
   - stop bad: stop hit after favorable move >= 1R,
   - target too far: MFE >= 1R but no target before expiry,
   - management bad: BE/partial exit loses materially vs hold.
2. Run the same canonical setups across:
   - 15m/30d,
   - 15m/60d,
   - 5m/30d only as entry-refinement evidence.
3. A/B only foundation choices:
   - 1.5R vs 2R,
   - hold vs BE-after-half,
   - CE retest vs next-open,
   - EMA-aligned vs structure-only direction.
4. Promote only setups where the failure mode is clear and fixable.

Next implementation target:

- `crypto_foundation_validation.py`
- output one row per setup/window/target/management/entry model;
- include direction accuracy, clean path, bad entry, stop failure, target too
  far, expiry rate, return/DD, and per-symbol contribution.

## 2026-07-13 MTF Structure Journal Update

Implemented `crypto_structure_regime_journal_reindexed` to join each accepted
trade to causal 15m / 60m / 240m structure rows by `known_after_ts`, then label:

- `trend_aligned`: local, 60m, and 240m structure agree with trade direction.
- `pullback_in_uptrend/downtrend`: 60m and 240m agree, local structure is
  neutral or opposed.
- `range_or_transition`: 60m or 240m is neutral.
- `countertrend`: trade direction opposes both 60m and 240m.
- `conflict`: 60m and 240m disagree.

Coverage:

- `2,546` accepted trades journaled.
- `14` symbols.
- Entry span: `2026-05-13 16:45 UTC` to `2026-07-11 23:45 UTC`.

Measured result:

| Setup / Bucket | Trades | Avg R | PF | Win Rate | Direction Acc | Bad Entry |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| London long retest, trend aligned | 81 | +0.668 | 5.93 | 81.5% | 55.6% | 7.4% |
| London long next-open, trend aligned | 81 | +0.663 | 5.90 | 81.5% | 55.6% | 7.4% |
| London long retest, pullback in uptrend | 70 | -0.214 | 0.63 | 40.0% | 38.6% | 65.7% |
| London long next-open, pullback in uptrend | 70 | -0.214 | 0.63 | 40.0% | 38.6% | 65.7% |
| NY long neutral reversal, range/transition | 1,228 | +0.177 | 1.66 | 49.8% | 46.0% | 19.6% |
| Late-US short bull flush, countertrend | 319 | +0.408 | 2.69 | 61.8% | 49.5% | 19.4% |

Blunt interpretation:

- Single-timeframe structure is not enough. That assumption is now proven.
- Higher-timeframe pullback is not automatically valid. In current London-long
  data, it is actively bad because entry quality collapses: `65.7%` bad-entry
  rate.
- For London longs, the foundation should require full 15m/60m/240m alignment
  or a separate, stricter pullback-entry model.
- Range/transition should not be treated as trend. It can work for reversal
  setups (`NY 13:00 UTC` remains strong), but that is a different setup family.
- Late-US bull-flush short remains a special case: it profits while formally
  countertrend, so it should be modeled as a shock/fade setup, not a trend setup.

Next rule to test, not assume:

1. London longs: allow only `trend_aligned` first; reject `pullback_in_uptrend`
   until a separate confirmation trigger fixes bad entries.
2. NY neutral reversal: keep `range_or_transition`, but only validate session
   slices and shock buckets out-of-sample.
3. Late-US shorts: split into explicit shock/fade logic; do not force EMA/HTF
   trend filters onto it.

## 2026-07-13 Foundation Trade Forensics Update

Implemented `crypto_foundation_trade_forensics` to collapse target/management
variants into one physical execution row, then measure frequency, duration,
portfolio return/DD, post-target continuation, and simple indicator filters.

Scope:

- Interval: `15m`.
- Concrete execution tested first: `fixed_2r` + `hold_target_expiry`.
- Risk model: `0.20%` per trade, max `6` open trades, max `1` open per symbol,
  daily loss cap `0.50%`.
- Full window: `2026-05-13 16:45 UTC` to `2026-07-11 23:45 UTC`.

Measured result:

| Window | Rule | Events | Events / Day | Events / Symbol / Week | Return | Max DD | PF | Win Rate | Median Duration |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 60d | all physical fixed-2R hold | 378 | 6.38 | 3.19 | +13.96% | 2.23% | 1.72 | 53.7% | 6.0h |
| 60d | strict candidates | 113 | 1.91 | 0.95 | +12.67% | 0.76% | 3.25 | 67.0% | 6.0h |
| 30d | all physical fixed-2R hold | 238 | 8.04 | 4.02 | +12.92% | 2.25% | 2.12 | 56.9% | 6.0h |
| 30d | strict candidates | 87 | 2.94 | 1.47 | +11.60% | 0.76% | 4.03 | 70.9% | 6.0h |
| 30d | NY 13 range reversal | 20 | 0.68 | 0.43 | +4.19% | 0.28% | 11.78 | 80.0% | 3.1h |
| 30d | Late-US fade | 53 | 1.79 | 0.96 | +5.49% | 0.85% | 2.78 | 64.2% | 6.0h |
| 30d | London trend aligned | 14 | 0.47 | 0.37 | +1.91% | 0.21% | 6.41 | 84.6% | 6.0h |

Indicator chemistry:

- London `trend_aligned` and `EMA 21/55 bullish` are identical in this sample:
  EMA did not add information after MTF structure alignment.
- London RSI-not-overbought reduced trades from `14` to `9` and reduced return;
  it is not a useful gate yet.
- NY `expanded_or_opposing` improved average R but starved frequency: only `7`
  events in 30d.
- Late-US `no_aligned_shock` slightly improved average R but reduced events from
  `53` to `44`; useful as a risk slice, not yet a hard filter.

Blunt interpretation:

- The strict structure layer improves quality materially: lower DD, higher PF,
  higher win rate.
- Per-symbol frequency is still not enough for "few trades per week per asset."
  In the recent 30d strict set, frequency is only `1.47` events per symbol per
  week across the basket average.
- The way to increase frequency is not to weaken the structure filter. That
  gives more trades but worse DD and PF.
- Frequency needs more independent setup families:
  1. trend continuation,
  2. range reversal,
  3. shock/fade,
  4. lower-timeframe entry expansion under the same HTF context.
- Current stats are good for research and candidate promotion, not deployment.
  They still need walk-forward / holdout and UI review of individual winners and
  losers.

## 2026-07-13 Cost Stress Update

Added cost/slippage stress to `crypto_foundation_trade_forensics`.

Method:

- Convert extra friction into R: `extra_cost_r = total_bps / 10000 * entry / risk`.
- This intentionally penalizes tight-stop trades harder.
- Scenarios:
  - `realistic_10bps`: 6 bps round-trip fee + 2 bps slippage per side.
  - `high_22bps`: 12 bps round-trip fee + 5 bps slippage per side.
  - `punitive_40bps`: 20 bps round-trip fee + 10 bps slippage per side.
  - `nightmare_60bps`: 30 bps round-trip fee + 15 bps slippage per side.

Strict candidate stress:

| Window | Scenario | Return | Max DD | PF | Win Rate | Return/DD |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 60d | baseline | +12.67% | 0.76% | 3.25 | 67.0% | 16.73 |
| 60d | high 22 bps | +8.51% | 0.92% | 2.26 | 63.1% | 9.24 |
| 60d | punitive 40 bps | +4.92% | 1.32% | 1.61 | 61.3% | 3.72 |
| 60d | nightmare 60 bps | +1.00% | 1.75% | 1.11 | 52.3% | 0.57 |
| first 30d | baseline | +1.08% | 0.64% | 1.60 | 53.8% | 1.69 |
| first 30d | high 22 bps | +0.26% | 0.81% | 1.12 | 50.0% | 0.32 |
| first 30d | punitive 40 bps | -0.41% | 1.32% | 0.85 | 46.2% | -0.31 |
| 30d | baseline | +11.60% | 0.76% | 4.03 | 70.9% | 15.31 |
| 30d | high 22 bps | +8.25% | 0.92% | 2.82 | 67.1% | 8.96 |
| 30d | punitive 40 bps | +5.33% | 1.05% | 1.99 | 65.9% | 5.05 |
| 30d | nightmare 60 bps | +1.82% | 1.75% | 1.28 | 53.6% | 1.04 |

Blunt interpretation:

- The strict structure basket survives realistic, high, and punitive friction.
- It does not have enough margin to trust under nightmare `60 bps` friction.
- First 30d is weak and fails punitive `40 bps`; recent 30d is strong. This is
  regime dependence, not deployment stability.
- NY 13 range reversal and London trend-aligned are the most friction-resistant
  modules, but sample size is still small.
- Late-US fade is useful but cost-sensitive; it dies around nightmare friction.
- Next required validation is walk-forward / holdout, not more indicator gates.
