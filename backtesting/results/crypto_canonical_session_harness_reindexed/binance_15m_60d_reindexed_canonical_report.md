# Crypto Canonical Session Harness

Date: 2026-07-13.

## Purpose

- Collapse broad matrix variants into one selected execution per setup signal.
- Compare session hypotheses by per-trade R, return/DD, stop rate, and accepted frequency.
- Prevent raw/confirmed duplicates from being counted as separate trades.

## Summary

| setup_name | candidates | accepted | symbols | candidate_per_symbol_day | accepted_per_symbol_day | avg_r | median_r | profit_factor | gross_return_pct | max_dd_pct | daily_max_dd_pct | return_to_dd | win_rate | stop_rate | expiry_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| late_us_short_bull_flush_ce | 136 | 78 | 14 | +0.164 | +0.094 | +0.394 | +0.384 | +2.361 | 6.15% | 0.87% | 0.78% | +7.050 | 57.69% | 21.79% | 50.00% |
| ny_long_neutral_reversal_ce | 411 | 199 | 14 | +0.505 | +0.245 | +0.207 | -0.059 | +1.783 | 8.25% | 1.63% | 1.63% | +5.063 | 45.23% | 16.08% | 54.77% |
| london_long_middle_local_next_open | 98 | 47 | 14 | +0.137 | +0.066 | +0.308 | +0.219 | +2.206 | 2.90% | 1.30% | 1.04% | +2.221 | 61.70% | 17.02% | 51.06% |
| london_long_middle_local_retest | 98 | 47 | 14 | +0.137 | +0.066 | +0.272 | +0.272 | +2.029 | 2.56% | 1.23% | 0.97% | +2.081 | 59.57% | 17.02% | 51.06% |
| late_us_short_bearish_trend_ce | 74 | 46 | 13 | +0.105 | +0.066 | +0.038 | +0.058 | +1.129 | 0.35% | 2.05% | 2.05% | +0.169 | 54.35% | 19.57% | 76.09% |

## Rule

- Promote setups only after holdout/rolling validation.
- Favor high return/DD and low stop rate over raw trade count.
- If a setup needs duplicate variants to look good, reject it.
