# Crypto Canonical Session Harness

Date: 2026-07-13.

## Purpose

- Collapse broad matrix variants into one selected execution per setup signal.
- Compare session hypotheses by per-trade R, return/DD, stop rate, and accepted frequency.
- Prevent raw/confirmed duplicates from being counted as separate trades.

## Summary

| setup_name | candidates | accepted | symbols | candidate_per_symbol_day | accepted_per_symbol_day | avg_r | median_r | profit_factor | gross_return_pct | max_dd_pct | daily_max_dd_pct | return_to_dd | win_rate | stop_rate | expiry_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| late_us_short_bull_flush_ce | 152 | 85 | 11 | +0.234 | +0.131 | +0.493 | +0.386 | +3.226 | 8.38% | 0.92% | 0.79% | +9.080 | 60.00% | 15.29% | 52.94% |
| london_long_middle_local_retest | 163 | 76 | 10 | +0.319 | +0.149 | +0.320 | +0.246 | +2.158 | 4.86% | 1.59% | 0.88% | +3.051 | 55.26% | 18.42% | 44.74% |
| london_long_middle_local_next_open | 163 | 75 | 10 | +0.319 | +0.147 | +0.291 | +0.137 | +2.003 | 4.36% | 2.20% | 1.48% | +1.982 | 54.67% | 20.00% | 45.33% |
| late_us_short_bearish_trend_ce | 97 | 56 | 11 | +0.191 | +0.110 | +0.248 | +0.168 | +1.799 | 2.77% | 1.57% | 1.57% | +1.764 | 58.93% | 25.00% | 60.71% |
| ny_long_neutral_reversal_ce | 322 | 147 | 11 | +0.522 | +0.238 | +0.090 | -0.051 | +1.291 | 2.65% | 3.23% | 3.18% | +0.820 | 45.58% | 21.09% | 57.14% |

## Rule

- Promote setups only after holdout/rolling validation.
- Favor high return/DD and low stop rate over raw trade count.
- If a setup needs duplicate variants to look good, reject it.
