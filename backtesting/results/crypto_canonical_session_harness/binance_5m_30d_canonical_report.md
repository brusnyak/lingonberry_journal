# Crypto Canonical Session Harness

Date: 2026-07-13.

## Purpose

- Collapse broad matrix variants into one selected execution per setup signal.
- Compare session hypotheses by per-trade R, return/DD, stop rate, and accepted frequency.
- Prevent raw/confirmed duplicates from being counted as separate trades.

## Summary

| setup_name | candidates | accepted | symbols | candidate_per_symbol_day | accepted_per_symbol_day | avg_r | median_r | profit_factor | gross_return_pct | max_dd_pct | daily_max_dd_pct | return_to_dd | win_rate | stop_rate | expiry_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| late_us_short_bull_flush_ce | 343 | 70 | 10 | +1.110 | +0.226 | +0.073 | -0.088 | +1.220 | 1.03% | 2.94% | 2.94% | +0.349 | 45.71% | 24.29% | 52.86% |
| london_long_middle_local_retest | 223 | 45 | 11 | +0.697 | +0.141 | +0.042 | -0.146 | +1.109 | 0.38% | 1.76% | 1.43% | +0.214 | 40.00% | 24.44% | 46.67% |
| london_long_middle_local_next_open | 223 | 44 | 11 | +0.697 | +0.137 | +0.020 | -0.172 | +1.051 | 0.18% | 1.79% | 1.43% | +0.098 | 38.64% | 25.00% | 45.45% |
| ny_long_neutral_reversal_ce | 396 | 81 | 11 | +1.238 | +0.253 | -0.023 | -0.132 | +0.945 | -0.37% | 1.84% | 1.84% | -0.199 | 37.04% | 30.86% | 39.51% |
| late_us_short_bearish_trend_ce | 47 | 19 | 8 | +0.216 | +0.087 | -0.205 | -0.201 | +0.562 | -0.78% | 1.16% | 0.92% | -0.673 | 31.58% | 31.58% | 63.16% |

## Rule

- Promote setups only after holdout/rolling validation.
- Favor high return/DD and low stop rate over raw trade count.
- If a setup needs duplicate variants to look good, reject it.
