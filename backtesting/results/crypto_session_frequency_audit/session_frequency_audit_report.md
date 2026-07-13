# Crypto Session Frequency Audit

Date: 2026-07-13.

## Verdict

- Frequency is not an executable-event problem. It is a strategy-filter and review-sampling problem.
- The UI sample was intentionally small. It did not represent all London candidates.
- Loosening all London-long filters is a bad strategy: it creates many more trades but destroys expectancy and drawdown.
- The only frequency expansion worth testing next is additional causal entry types inside the same London context, not all ignored entries.

## Module Summary

| module | candidates | accepted | symbols | avg_r | profit_factor | gross_return_pct | max_dd_pct | stop_rate | expiry_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| london_current | 143 | 69 | 10 | +0.347 | +2.262 | 4.78% | 1.75% | 18.84% | 46.38% |
| late_us_current | 74 | 53 | 11 | +0.355 | +2.140 | 3.76% | 1.84% | 22.64% | 54.72% |

## London Variants

| variant | candidates | accepted | symbols | avg_r | profit_factor | gross_return_pct | max_dd_pct | stop_rate | expiry_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ctx_bull_all_middle_local_long | 627 | 78 | 10 | +0.350 | +2.262 | 5.45% | 1.82% | 19.23% | 46.15% |
| ctx_bull_any_entry_confirm | 267 | 73 | 10 | +0.373 | +2.417 | 5.45% | 1.35% | 17.81% | 46.58% |
| current | 143 | 69 | 10 | +0.347 | +2.262 | 4.78% | 1.75% | 18.84% | 46.38% |
| drop_ctx_keep_ema_confirm | 155 | 73 | 11 | +0.295 | +1.983 | 4.31% | 1.96% | 20.55% | 46.58% |
| all_london_long_fixed2_be | 993 | 320 | 11 | +0.008 | +1.020 | 0.54% | 6.39% | 30.94% | 44.69% |

## London Filter Funnel

| stage | candidates | accepted | symbols | accepted_avg_r | accepted_pf | accepted_return_pct | accepted_dd_pct | accepted_stop_rate | accepted_expiry_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| all_london_long_fixed2_be | 5147 | 355 | 11 | -0.017 | +0.960 | -1.21% | 6.42% | 32.11% | 42.54% |
| plus_ctx_bull | 3720 | 315 | 11 | -0.004 | +0.991 | -0.25% | 6.13% | 33.02% | 38.41% |
| plus_middle_local_bullish | 627 | 78 | 10 | +0.350 | +2.262 | 5.45% | 1.82% | 19.23% | 46.15% |
| plus_structure_confirmed_next_open | 146 | 70 | 10 | +0.345 | +2.273 | 4.83% | 1.75% | 18.57% | 47.14% |
| current_with_latest_bull_regime | 143 | 69 | 10 | +0.347 | +2.262 | 4.78% | 1.75% | 18.84% | 46.38% |

## Session/Direction Reality Check

The raw London-long universe contains many executable rows per symbol, but most are not profitable as a module.

| symbol | session_utc | direction | rows | avg_r | profit_factor | stop_rate | expiry_rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| WLDUSDT | late_us | short | 247 | +0.230 | +1.870 | 16.60% | 49.80% |
| ETHUSDT | late_us | short | 303 | +0.223 | +1.767 | 20.13% | 53.80% |
| AVAXUSDT | late_us | short | 220 | +0.220 | +1.702 | 23.18% | 50.00% |
| XRPUSDT | late_us | short | 246 | +0.217 | +1.670 | 22.36% | 56.50% |
| SUIUSDT | late_us | short | 278 | +0.195 | +1.731 | 19.42% | 57.19% |
| DOGEUSDT | late_us | short | 328 | +0.192 | +1.543 | 28.66% | 47.87% |
| SOLUSDT | late_us | short | 282 | +0.185 | +1.673 | 19.50% | 54.96% |
| AAVEUSDT | late_us | short | 304 | +0.165 | +1.542 | 19.41% | 55.59% |
| AVAXUSDT | asia | short | 434 | +0.120 | +1.438 | 16.82% | 63.59% |
| NEARUSDT | late_us | short | 330 | +0.113 | +1.437 | 19.39% | 62.42% |
| WLDUSDT | asia | short | 400 | +0.102 | +1.360 | 23.00% | 53.00% |
| WLDUSDT | ny | long | 491 | +0.086 | +1.261 | 18.53% | 63.34% |
| LINKUSDT | late_us | short | 296 | +0.081 | +1.206 | 31.42% | 43.92% |
| 1000PEPEUSDT | asia | short | 430 | +0.080 | +1.241 | 25.12% | 51.40% |
| 1000PEPEUSDT | late_us | short | 301 | +0.077 | +1.216 | 28.57% | 54.15% |
| SOLUSDT | ny | short | 460 | +0.067 | +1.206 | 20.00% | 55.22% |
| 1000PEPEUSDT | ny | short | 440 | +0.059 | +1.183 | 23.86% | 49.09% |
| AAVEUSDT | london | long | 591 | +0.051 | +1.132 | 30.29% | 39.93% |
| AAVEUSDT | late_us | long | 308 | +0.044 | +1.113 | 28.57% | 41.23% |
| DOGEUSDT | asia | short | 432 | +0.044 | +1.148 | 14.81% | 62.04% |

## Review Packet

- UI review packet: `backtesting/results/review_samples/crypto_london_frequency_audit_review_samples.csv`.
- It includes current London winners/losers and hindsight near-miss winners/losers.
- Treat near-miss winners as diagnostic only. Using them directly is hindsight leakage.

## Research Implication

- Session research supports separate modules: London trend-continuation, late-US flush/countertrend, optional Asia pullback/flush.
- Consolidation should be tested as a precondition: narrow pre-session range, breakout/displacement, then retest/engulfing confirmation.
- Candle patterns should be tested as entry confirmation, not standalone signals. First candidates: engulfing/reversal strength, wick rejection at FVG CE, inside-bar compression break.
