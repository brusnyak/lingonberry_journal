# Crypto Direction Filter Validation

Date: 2026-07-13.

## Purpose

- Test add-on direction filters against canonical setup candidates.
- Keep the setup/event logic fixed; only direction gating changes.
- Reject filters that improve stats by deleting most trades.

## Meaningful Filter Winners

_empty_

## Verdict Counts

| direction_filter | verdict | rows |
| --- | --- | --- |
| all_ema_aligned | neutral | 6 |
| all_ema_aligned | reject_too_sparse | 24 |
| base | base | 30 |
| confirmed_only | neutral | 19 |
| confirmed_only | worse | 11 |
| full_trend | reject_too_sparse | 30 |
| global_middle_ema_aligned | neutral | 6 |
| global_middle_ema_aligned | reject_too_sparse | 24 |
| local_ema_aligned | neutral | 18 |
| local_ema_aligned | reject_too_sparse | 12 |
| middle_local_ema_aligned | neutral | 18 |
| middle_local_ema_aligned | reject_too_sparse | 12 |
| not_counter_structure | neutral | 18 |
| not_counter_structure | reject_too_sparse | 12 |
| regime_aligned | neutral | 12 |
| regime_aligned | reject_too_sparse | 18 |

## Best Rows By Direction Accuracy Delta

| window | setup_name | target_model | management_model | direction_filter | accepted | accepted_keep_rate | avg_r | avg_r_delta | direction_accuracy | direction_accuracy_delta | bad_entry_rate | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 15m_60d_reindexed | late_us_short_bull_flush_ce | fixed_1_5r | partial_1r_be_after_half_target | local_ema_aligned | 3 | 3.9% | +0.345 | +0.079 | 66.7% | +18.6% | 66.7% | reject_too_sparse |
| 15m_60d_reindexed | late_us_short_bull_flush_ce | fixed_1_5r | be_after_half_target | local_ema_aligned | 3 | 3.9% | +0.257 | -0.031 | 66.7% | +18.6% | 66.7% | reject_too_sparse |
| 15m_60d_reindexed | late_us_short_bull_flush_ce | fixed_1_5r | hold_target_expiry | local_ema_aligned | 3 | 3.7% | +0.257 | -0.085 | 66.7% | +14.8% | 66.7% | reject_too_sparse |
| 15m_60d_reindexed | late_us_short_bull_flush_ce | fixed_2r | partial_1r_be_after_half_target | local_ema_aligned | 3 | 3.8% | -0.000 | -0.320 | 66.7% | +14.1% | 66.7% | reject_too_sparse |
| 15m_60d_reindexed | late_us_short_bull_flush_ce | fixed_2r | be_after_half_target | local_ema_aligned | 3 | 3.8% | -0.251 | -0.646 | 66.7% | +14.1% | 66.7% | reject_too_sparse |
| 15m_60d_reindexed | late_us_short_bull_flush_ce | fixed_2r | hold_target_expiry | local_ema_aligned | 3 | 3.8% | -0.585 | -0.922 | 66.7% | +14.1% | 66.7% | reject_too_sparse |
| 15m_60d_reindexed | late_us_short_bearish_trend_ce | fixed_1_5r | hold_target_expiry | confirmed_only | 42 | 91.3% | +0.181 | +0.069 | 31.0% | +0.5% | 19.0% | neutral |
| 15m_60d_reindexed | late_us_short_bearish_trend_ce | fixed_1_5r | be_after_half_target | confirmed_only | 42 | 91.3% | +0.158 | +0.045 | 31.0% | +0.5% | 19.0% | neutral |
| 15m_60d_reindexed | late_us_short_bearish_trend_ce | fixed_1_5r | partial_1r_be_after_half_target | confirmed_only | 42 | 91.3% | +0.178 | +0.027 | 31.0% | +0.5% | 19.0% | neutral |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_1_5r | partial_1r_be_after_half_target | local_ema_aligned | 50 | 100.0% | +0.302 | +0.000 | 46.0% | +0.0% | 24.0% | neutral |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_1_5r | partial_1r_be_after_half_target | middle_local_ema_aligned | 50 | 100.0% | +0.302 | +0.000 | 46.0% | +0.0% | 24.0% | neutral |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_1_5r | partial_1r_be_after_half_target | regime_aligned | 50 | 100.0% | +0.302 | +0.000 | 46.0% | +0.0% | 24.0% | neutral |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_1_5r | partial_1r_be_after_half_target | not_counter_structure | 50 | 100.0% | +0.302 | +0.000 | 46.0% | +0.0% | 24.0% | neutral |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_1_5r | hold_target_expiry | local_ema_aligned | 49 | 100.0% | +0.323 | +0.000 | 46.9% | +0.0% | 22.4% | neutral |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_1_5r | hold_target_expiry | middle_local_ema_aligned | 49 | 100.0% | +0.323 | +0.000 | 46.9% | +0.0% | 22.4% | neutral |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_1_5r | hold_target_expiry | regime_aligned | 49 | 100.0% | +0.323 | +0.000 | 46.9% | +0.0% | 22.4% | neutral |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_1_5r | hold_target_expiry | not_counter_structure | 49 | 100.0% | +0.323 | +0.000 | 46.9% | +0.0% | 22.4% | neutral |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_1_5r | be_after_half_target | local_ema_aligned | 49 | 100.0% | +0.279 | +0.000 | 44.9% | +0.0% | 24.5% | neutral |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_1_5r | be_after_half_target | middle_local_ema_aligned | 49 | 100.0% | +0.279 | +0.000 | 44.9% | +0.0% | 24.5% | neutral |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_1_5r | be_after_half_target | regime_aligned | 49 | 100.0% | +0.279 | +0.000 | 44.9% | +0.0% | 24.5% | neutral |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_1_5r | be_after_half_target | not_counter_structure | 49 | 100.0% | +0.279 | +0.000 | 44.9% | +0.0% | 24.5% | neutral |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_1_5r | be_after_half_target | local_ema_aligned | 48 | 100.0% | +0.303 | +0.000 | 45.8% | +0.0% | 22.9% | neutral |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_1_5r | be_after_half_target | middle_local_ema_aligned | 48 | 100.0% | +0.303 | +0.000 | 45.8% | +0.0% | 22.9% | neutral |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_1_5r | be_after_half_target | regime_aligned | 48 | 100.0% | +0.303 | +0.000 | 45.8% | +0.0% | 22.9% | neutral |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_1_5r | be_after_half_target | not_counter_structure | 48 | 100.0% | +0.303 | +0.000 | 45.8% | +0.0% | 22.9% | neutral |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_1_5r | partial_1r_be_after_half_target | local_ema_aligned | 48 | 100.0% | +0.310 | +0.000 | 45.8% | +0.0% | 22.9% | neutral |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_1_5r | partial_1r_be_after_half_target | middle_local_ema_aligned | 48 | 100.0% | +0.310 | +0.000 | 45.8% | +0.0% | 22.9% | neutral |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_1_5r | partial_1r_be_after_half_target | regime_aligned | 48 | 100.0% | +0.310 | +0.000 | 45.8% | +0.0% | 22.9% | neutral |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_1_5r | partial_1r_be_after_half_target | not_counter_structure | 48 | 100.0% | +0.310 | +0.000 | 45.8% | +0.0% | 22.9% | neutral |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_2r | partial_1r_be_after_half_target | local_ema_aligned | 48 | 100.0% | +0.297 | +0.000 | 43.8% | +0.0% | 22.9% | neutral |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_2r | partial_1r_be_after_half_target | middle_local_ema_aligned | 48 | 100.0% | +0.297 | +0.000 | 43.8% | +0.0% | 22.9% | neutral |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_2r | partial_1r_be_after_half_target | regime_aligned | 48 | 100.0% | +0.297 | +0.000 | 43.8% | +0.0% | 22.9% | neutral |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_2r | partial_1r_be_after_half_target | not_counter_structure | 48 | 100.0% | +0.297 | +0.000 | 43.8% | +0.0% | 22.9% | neutral |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_1_5r | hold_target_expiry | local_ema_aligned | 47 | 100.0% | +0.270 | +0.000 | 46.8% | +0.0% | 21.3% | neutral |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_1_5r | hold_target_expiry | middle_local_ema_aligned | 47 | 100.0% | +0.270 | +0.000 | 46.8% | +0.0% | 21.3% | neutral |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_1_5r | hold_target_expiry | regime_aligned | 47 | 100.0% | +0.270 | +0.000 | 46.8% | +0.0% | 21.3% | neutral |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_1_5r | hold_target_expiry | not_counter_structure | 47 | 100.0% | +0.270 | +0.000 | 46.8% | +0.0% | 21.3% | neutral |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_2r | be_after_half_target | local_ema_aligned | 47 | 100.0% | +0.308 | +0.000 | 42.6% | +0.0% | 23.4% | neutral |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_2r | be_after_half_target | middle_local_ema_aligned | 47 | 100.0% | +0.308 | +0.000 | 42.6% | +0.0% | 23.4% | neutral |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_2r | be_after_half_target | regime_aligned | 47 | 100.0% | +0.308 | +0.000 | 42.6% | +0.0% | 23.4% | neutral |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_2r | be_after_half_target | not_counter_structure | 47 | 100.0% | +0.308 | +0.000 | 42.6% | +0.0% | 23.4% | neutral |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_2r | partial_1r_be_after_half_target | local_ema_aligned | 47 | 100.0% | +0.302 | +0.000 | 42.6% | +0.0% | 23.4% | neutral |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_2r | partial_1r_be_after_half_target | middle_local_ema_aligned | 47 | 100.0% | +0.302 | +0.000 | 42.6% | +0.0% | 23.4% | neutral |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_2r | partial_1r_be_after_half_target | regime_aligned | 47 | 100.0% | +0.302 | +0.000 | 42.6% | +0.0% | 23.4% | neutral |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_2r | partial_1r_be_after_half_target | not_counter_structure | 47 | 100.0% | +0.302 | +0.000 | 42.6% | +0.0% | 23.4% | neutral |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_2r | hold_target_expiry | local_ema_aligned | 47 | 100.0% | +0.323 | +0.000 | 44.7% | +0.0% | 21.3% | neutral |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_2r | hold_target_expiry | middle_local_ema_aligned | 47 | 100.0% | +0.323 | +0.000 | 44.7% | +0.0% | 21.3% | neutral |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_2r | hold_target_expiry | regime_aligned | 47 | 100.0% | +0.323 | +0.000 | 44.7% | +0.0% | 21.3% | neutral |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_2r | hold_target_expiry | not_counter_structure | 47 | 100.0% | +0.323 | +0.000 | 44.7% | +0.0% | 21.3% | neutral |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_2r | be_after_half_target | local_ema_aligned | 47 | 100.0% | +0.272 | +0.000 | 42.6% | +0.0% | 23.4% | neutral |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_2r | be_after_half_target | middle_local_ema_aligned | 47 | 100.0% | +0.272 | +0.000 | 42.6% | +0.0% | 23.4% | neutral |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_2r | be_after_half_target | regime_aligned | 47 | 100.0% | +0.272 | +0.000 | 42.6% | +0.0% | 23.4% | neutral |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_2r | be_after_half_target | not_counter_structure | 47 | 100.0% | +0.272 | +0.000 | 42.6% | +0.0% | 23.4% | neutral |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_2r | hold_target_expiry | local_ema_aligned | 46 | 100.0% | +0.280 | +0.000 | 43.5% | +0.0% | 21.7% | neutral |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_2r | hold_target_expiry | middle_local_ema_aligned | 46 | 100.0% | +0.280 | +0.000 | 43.5% | +0.0% | 21.7% | neutral |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_2r | hold_target_expiry | regime_aligned | 46 | 100.0% | +0.280 | +0.000 | 43.5% | +0.0% | 21.7% | neutral |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_2r | hold_target_expiry | not_counter_structure | 46 | 100.0% | +0.280 | +0.000 | 43.5% | +0.0% | 21.7% | neutral |
| 15m_60d_reindexed | late_us_short_bearish_trend_ce | fixed_1_5r | hold_target_expiry | local_ema_aligned | 46 | 100.0% | +0.112 | +0.000 | 30.4% | +0.0% | 21.7% | neutral |
| 15m_60d_reindexed | late_us_short_bearish_trend_ce | fixed_1_5r | hold_target_expiry | middle_local_ema_aligned | 46 | 100.0% | +0.112 | +0.000 | 30.4% | +0.0% | 21.7% | neutral |
| 15m_60d_reindexed | late_us_short_bearish_trend_ce | fixed_1_5r | hold_target_expiry | global_middle_ema_aligned | 46 | 100.0% | +0.112 | +0.000 | 30.4% | +0.0% | 21.7% | neutral |

## Decision Rules

- Promote only filters marked `direction_improver` or `return_improver`.
- Ignore filters with `accepted < 30` or `accepted_keep_rate < 35%`.
- If no add-on filter improves direction cleanly, the next work is better regime definition, not more entry filters.
