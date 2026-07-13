# Crypto Canonical Session Harness

Date: 2026-07-13.

## Purpose

- Collapse broad matrix variants into one selected execution per setup signal.
- Compare session hypotheses by per-trade R, return/DD, stop rate, and accepted frequency.
- Prevent raw/confirmed duplicates from being counted as separate trades.

## Summary

| setup_name | candidates | accepted | symbols | candidate_per_symbol_day | accepted_per_symbol_day | avg_r | median_r | profit_factor | gross_return_pct | max_dd_pct | daily_max_dd_pct | return_to_dd | win_rate | stop_rate | expiry_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| london_long_middle_local_next_open | 94 | 42 | 10 | +0.334 | +0.149 | +0.796 | +0.784 | +5.991 | 6.69% | 0.44% | 0.40% | +15.324 | 76.19% | 9.52% | 47.62% |
| london_long_middle_local_retest | 94 | 43 | 10 | +0.334 | +0.153 | +0.758 | +0.702 | +5.582 | 6.52% | 0.44% | 0.40% | +14.934 | 74.42% | 9.30% | 46.51% |
| late_us_short_bull_flush_ce | 115 | 63 | 11 | +0.372 | +0.204 | +0.510 | +0.451 | +3.068 | 6.43% | 0.89% | 0.79% | +7.260 | 61.90% | 17.46% | 52.38% |
| ny_long_neutral_reversal_ce | 125 | 65 | 11 | +0.434 | +0.226 | +0.161 | -0.043 | +1.520 | 2.09% | 1.86% | 1.39% | +1.128 | 46.15% | 21.54% | 53.85% |
| late_us_short_bearish_trend_ce | 28 | 18 | 7 | +0.234 | +0.150 | -0.244 | -1.039 | +0.605 | -0.88% | 1.26% | 1.06% | -0.698 | 33.33% | 55.56% | 27.78% |

## Rule

- Promote setups only after holdout/rolling validation.
- Favor high return/DD and low stop rate over raw trade count.
- If a setup needs duplicate variants to look good, reject it.
