# Crypto Direction Filter Validation

Date: 2026-07-13.

## Purpose

- Test add-on direction filters against canonical setup candidates.
- Keep the setup/event logic fixed; only direction gating changes.
- Reject filters that improve stats by deleting most trades.

## Meaningful Filter Winners

| window | setup_name | target_model | management_model | direction_filter | accepted | accepted_keep_rate | avg_r | avg_r_delta | direction_accuracy | direction_accuracy_delta | bad_entry_rate | bad_entry_rate_delta | return_to_dd | return_to_dd_delta | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 15m_60d | late_us_short_bearish_trend_ce | fixed_1_5r | partial_1r_be_after_half_target | confirmed_only | 38 | 67.9% | +0.358 | +0.176 | 50.0% | +3.6% | 13.2% | -15.4% | +5.071 | +3.775 | return_improver |
| 15m_60d | late_us_short_bearish_trend_ce | fixed_1_5r | be_after_half_target | confirmed_only | 38 | 67.9% | +0.334 | +0.157 | 50.0% | +3.6% | 13.2% | -15.4% | +4.335 | +3.073 | return_improver |
| 15m_60d | late_us_short_bearish_trend_ce | fixed_2r | partial_1r_be_after_half_target | confirmed_only | 38 | 67.9% | +0.391 | +0.154 | 50.0% | +3.6% | 13.2% | -15.4% | +5.534 | +3.850 | return_improver |
| 15m_60d | late_us_short_bearish_trend_ce | fixed_2r | hold_target_expiry | confirmed_only | 38 | 67.9% | +0.401 | +0.153 | 50.0% | +3.6% | 13.2% | -15.4% | +5.205 | +3.441 | return_improver |

## Verdict Counts

| direction_filter | verdict | rows |
| --- | --- | --- |
| all_ema_aligned | neutral | 6 |
| all_ema_aligned | reject_too_sparse | 84 |
| base | base | 90 |
| confirmed_only | neutral | 38 |
| confirmed_only | reject_too_sparse | 12 |
| confirmed_only | return_improver | 4 |
| confirmed_only | worse | 36 |
| full_trend | reject_too_sparse | 90 |
| global_middle_ema_aligned | neutral | 6 |
| global_middle_ema_aligned | reject_too_sparse | 84 |
| local_ema_aligned | neutral | 45 |
| local_ema_aligned | reject_too_sparse | 36 |
| local_ema_aligned | worse | 9 |
| middle_local_ema_aligned | neutral | 42 |
| middle_local_ema_aligned | reject_too_sparse | 48 |
| not_counter_structure | neutral | 42 |
| not_counter_structure | reject_too_sparse | 48 |
| regime_aligned | neutral | 36 |
| regime_aligned | reject_too_sparse | 54 |

## Best Rows By Direction Accuracy Delta

| window | setup_name | target_model | management_model | direction_filter | accepted | accepted_keep_rate | avg_r | avg_r_delta | direction_accuracy | direction_accuracy_delta | bad_entry_rate | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 15m_60d | late_us_short_bull_flush_ce | fixed_1_5r | be_after_half_target | local_ema_aligned | 2 | 2.2% | +0.941 | +0.459 | 100.0% | +46.2% | 50.0% | reject_too_sparse |
| 15m_60d | late_us_short_bull_flush_ce | fixed_1_5r | hold_target_expiry | local_ema_aligned | 2 | 2.2% | +0.941 | +0.441 | 100.0% | +46.1% | 50.0% | reject_too_sparse |
| 15m_60d | late_us_short_bull_flush_ce | fixed_1_5r | partial_1r_be_after_half_target | local_ema_aligned | 2 | 2.2% | +1.074 | +0.630 | 100.0% | +45.7% | 50.0% | reject_too_sparse |
| 15m_60d | late_us_short_bull_flush_ce | fixed_2r | partial_1r_be_after_half_target | local_ema_aligned | 2 | 2.4% | +0.556 | +0.132 | 100.0% | +43.5% | 50.0% | reject_too_sparse |
| 15m_60d | late_us_short_bull_flush_ce | fixed_2r | be_after_half_target | local_ema_aligned | 2 | 2.4% | +0.179 | -0.314 | 100.0% | +43.5% | 50.0% | reject_too_sparse |
| 15m_60d | late_us_short_bull_flush_ce | fixed_2r | hold_target_expiry | local_ema_aligned | 2 | 2.4% | -0.321 | -0.777 | 100.0% | +43.5% | 50.0% | reject_too_sparse |
| 15m_30d | late_us_short_bull_flush_ce | fixed_1_5r | be_after_half_target | local_ema_aligned | 1 | 1.5% | +1.428 | +0.954 | 100.0% | +42.6% | 100.0% | reject_too_sparse |
| 15m_30d | late_us_short_bull_flush_ce | fixed_1_5r | hold_target_expiry | local_ema_aligned | 1 | 1.5% | +1.428 | +0.914 | 100.0% | +42.4% | 100.0% | reject_too_sparse |
| 15m_30d | late_us_short_bull_flush_ce | fixed_1_5r | partial_1r_be_after_half_target | local_ema_aligned | 1 | 1.4% | +1.428 | +0.997 | 100.0% | +42.0% | 100.0% | reject_too_sparse |
| 15m_30d | late_us_short_bull_flush_ce | fixed_2r | partial_1r_be_after_half_target | local_ema_aligned | 1 | 1.6% | +0.392 | -0.023 | 100.0% | +41.3% | 100.0% | reject_too_sparse |
| 15m_30d | late_us_short_bull_flush_ce | fixed_2r | be_after_half_target | local_ema_aligned | 1 | 1.6% | -0.096 | -0.607 | 100.0% | +41.3% | 100.0% | reject_too_sparse |
| 15m_30d | late_us_short_bull_flush_ce | fixed_2r | hold_target_expiry | local_ema_aligned | 1 | 1.6% | -1.097 | -1.599 | 100.0% | +41.3% | 100.0% | reject_too_sparse |
| 5m_30d | late_us_short_bearish_trend_ce | fixed_2r | partial_1r_be_after_half_target | confirmed_only | 13 | 68.4% | +0.258 | +0.475 | 38.5% | +22.7% | 7.7% | reject_too_sparse |
| 5m_30d | late_us_short_bearish_trend_ce | fixed_1_5r | partial_1r_be_after_half_target | confirmed_only | 13 | 68.4% | +0.138 | +0.437 | 38.5% | +22.7% | 7.7% | reject_too_sparse |
| 5m_30d | late_us_short_bearish_trend_ce | fixed_2r | be_after_half_target | confirmed_only | 13 | 68.4% | +0.201 | +0.406 | 38.5% | +22.7% | 7.7% | reject_too_sparse |
| 5m_30d | late_us_short_bearish_trend_ce | fixed_2r | hold_target_expiry | confirmed_only | 13 | 68.4% | +0.179 | +0.384 | 38.5% | +22.7% | 7.7% | reject_too_sparse |
| 5m_30d | late_us_short_bearish_trend_ce | fixed_1_5r | hold_target_expiry | confirmed_only | 13 | 68.4% | +0.155 | +0.377 | 38.5% | +22.7% | 7.7% | reject_too_sparse |
| 5m_30d | late_us_short_bearish_trend_ce | fixed_1_5r | be_after_half_target | confirmed_only | 13 | 68.4% | +0.067 | +0.364 | 38.5% | +22.7% | 7.7% | reject_too_sparse |
| 15m_30d | late_us_short_bearish_trend_ce | fixed_2r | hold_target_expiry | confirmed_only | 9 | 50.0% | +0.141 | +0.385 | 55.6% | +11.1% | 33.3% | reject_too_sparse |
| 15m_30d | late_us_short_bearish_trend_ce | fixed_2r | be_after_half_target | confirmed_only | 9 | 50.0% | +0.243 | +0.325 | 55.6% | +11.1% | 33.3% | reject_too_sparse |
| 15m_30d | late_us_short_bearish_trend_ce | fixed_1_5r | partial_1r_be_after_half_target | confirmed_only | 9 | 50.0% | +0.310 | +0.308 | 55.6% | +11.1% | 33.3% | reject_too_sparse |
| 15m_30d | late_us_short_bearish_trend_ce | fixed_2r | partial_1r_be_after_half_target | confirmed_only | 9 | 50.0% | +0.267 | +0.295 | 55.6% | +11.1% | 33.3% | reject_too_sparse |
| 15m_30d | late_us_short_bearish_trend_ce | fixed_1_5r | be_after_half_target | confirmed_only | 9 | 50.0% | +0.286 | +0.283 | 55.6% | +11.1% | 33.3% | reject_too_sparse |
| 15m_30d | late_us_short_bearish_trend_ce | fixed_1_5r | hold_target_expiry | confirmed_only | 9 | 50.0% | +0.188 | +0.157 | 55.6% | +11.1% | 33.3% | reject_too_sparse |
| 15m_30d | london_long_middle_local_retest | fixed_1_5r | be_after_half_target | confirmed_only | 41 | 91.1% | +0.697 | +0.072 | 68.3% | +3.8% | 12.2% | neutral |
| 15m_60d | late_us_short_bearish_trend_ce | fixed_1_5r | partial_1r_be_after_half_target | confirmed_only | 38 | 67.9% | +0.358 | +0.176 | 50.0% | +3.6% | 13.2% | return_improver |
| 15m_60d | late_us_short_bearish_trend_ce | fixed_1_5r | be_after_half_target | confirmed_only | 38 | 67.9% | +0.334 | +0.157 | 50.0% | +3.6% | 13.2% | return_improver |
| 15m_60d | late_us_short_bearish_trend_ce | fixed_2r | partial_1r_be_after_half_target | confirmed_only | 38 | 67.9% | +0.391 | +0.154 | 50.0% | +3.6% | 13.2% | return_improver |
| 15m_60d | late_us_short_bearish_trend_ce | fixed_2r | hold_target_expiry | confirmed_only | 38 | 67.9% | +0.401 | +0.153 | 50.0% | +3.6% | 13.2% | return_improver |
| 15m_60d | late_us_short_bearish_trend_ce | fixed_2r | be_after_half_target | confirmed_only | 38 | 67.9% | +0.372 | +0.144 | 50.0% | +3.6% | 13.2% | neutral |
| 15m_60d | late_us_short_bearish_trend_ce | fixed_1_5r | hold_target_expiry | confirmed_only | 38 | 67.9% | +0.406 | +0.094 | 50.0% | +3.6% | 13.2% | neutral |
| 15m_30d | london_long_middle_local_retest | fixed_1_5r | hold_target_expiry | confirmed_only | 41 | 89.1% | +0.748 | +0.067 | 68.3% | +3.1% | 12.2% | neutral |
| 15m_30d | london_long_middle_local_retest | fixed_1_5r | partial_1r_be_after_half_target | confirmed_only | 41 | 89.1% | +0.675 | +0.055 | 68.3% | +3.1% | 12.2% | neutral |
| 15m_60d | london_long_middle_local_next_open | fixed_2r | partial_1r_be_after_half_target | confirmed_only | 70 | 92.1% | +0.356 | +0.058 | 52.9% | +2.9% | 25.7% | neutral |
| 15m_60d | london_long_middle_local_next_open | fixed_2r | hold_target_expiry | confirmed_only | 67 | 95.7% | +0.378 | +0.034 | 53.7% | +2.3% | 22.4% | neutral |
| 15m_60d | london_long_middle_local_retest | fixed_1_5r | partial_1r_be_after_half_target | confirmed_only | 71 | 88.8% | +0.346 | +0.025 | 53.5% | +2.3% | 25.4% | neutral |
| 15m_60d | london_long_middle_local_retest | fixed_1_5r | be_after_half_target | confirmed_only | 71 | 91.0% | +0.318 | +0.038 | 53.5% | +2.2% | 25.4% | neutral |
| 15m_30d | london_long_middle_local_retest | fixed_2r | be_after_half_target | confirmed_only | 40 | 93.0% | +0.783 | +0.025 | 65.0% | +2.2% | 12.5% | neutral |
| 15m_60d | london_long_middle_local_next_open | fixed_2r | be_after_half_target | confirmed_only | 70 | 93.3% | +0.353 | +0.063 | 52.9% | +2.2% | 25.7% | neutral |
| 5m_30d | london_long_middle_local_retest | fixed_1_5r | hold_target_expiry | confirmed_only | 48 | 100.0% | +0.220 | +0.093 | 41.7% | +2.1% | 22.9% | neutral |
| 5m_30d | london_long_middle_local_next_open | fixed_2r | partial_1r_be_after_half_target | confirmed_only | 50 | 100.0% | +0.192 | +0.082 | 46.0% | +2.0% | 22.0% | neutral |
| 5m_30d | london_long_middle_local_retest | fixed_2r | partial_1r_be_after_half_target | confirmed_only | 51 | 100.0% | +0.209 | +0.081 | 47.1% | +2.0% | 21.6% | neutral |
| 15m_60d | london_long_middle_local_retest | fixed_1_5r | hold_target_expiry | confirmed_only | 68 | 91.9% | +0.389 | +0.039 | 54.4% | +1.7% | 22.1% | neutral |
| 15m_60d | london_long_middle_local_retest | fixed_2r | partial_1r_be_after_half_target | confirmed_only | 70 | 89.7% | +0.346 | +0.011 | 52.9% | +1.6% | 25.7% | neutral |
| 15m_60d | london_long_middle_local_retest | fixed_2r | be_after_half_target | confirmed_only | 70 | 92.1% | +0.346 | +0.027 | 52.9% | +1.5% | 25.7% | neutral |
| 15m_30d | london_long_middle_local_retest | fixed_2r | hold_target_expiry | confirmed_only | 40 | 90.9% | +0.823 | +0.009 | 65.0% | +1.4% | 12.5% | neutral |
| 15m_30d | london_long_middle_local_retest | fixed_2r | partial_1r_be_after_half_target | confirmed_only | 40 | 90.9% | +0.695 | +0.004 | 65.0% | +1.4% | 12.5% | neutral |
| 5m_30d | london_long_middle_local_retest | fixed_2r | hold_target_expiry | confirmed_only | 44 | 97.8% | +0.218 | +0.106 | 43.2% | +1.0% | 25.0% | neutral |
| 15m_60d | london_long_middle_local_next_open | fixed_1_5r | partial_1r_be_after_half_target | confirmed_only | 71 | 91.0% | +0.306 | +0.008 | 53.5% | +1.0% | 25.4% | neutral |
| 15m_60d | london_long_middle_local_retest | fixed_2r | hold_target_expiry | confirmed_only | 67 | 93.1% | +0.430 | +0.018 | 53.7% | +1.0% | 22.4% | neutral |
| 5m_30d | london_long_middle_local_next_open | fixed_2r | hold_target_expiry | confirmed_only | 43 | 97.7% | +0.189 | +0.111 | 41.9% | +1.0% | 25.6% | neutral |
| 5m_30d | london_long_middle_local_next_open | fixed_1_5r | hold_target_expiry | confirmed_only | 46 | 97.9% | +0.179 | +0.094 | 41.3% | +0.9% | 23.9% | neutral |
| 15m_30d | london_long_middle_local_next_open | fixed_2r | hold_target_expiry | confirmed_only | 40 | 95.2% | +0.817 | +0.039 | 65.0% | +0.7% | 12.5% | neutral |
| 15m_30d | london_long_middle_local_next_open | fixed_2r | be_after_half_target | confirmed_only | 40 | 95.2% | +0.829 | +0.033 | 65.0% | +0.7% | 12.5% | neutral |
| 15m_30d | london_long_middle_local_next_open | fixed_2r | partial_1r_be_after_half_target | confirmed_only | 40 | 95.2% | +0.732 | +0.026 | 65.0% | +0.7% | 12.5% | neutral |
| 15m_60d | london_long_middle_local_next_open | fixed_1_5r | be_after_half_target | confirmed_only | 71 | 92.2% | +0.276 | +0.009 | 53.5% | +0.3% | 25.4% | neutral |
| 15m_60d | london_long_middle_local_next_open | fixed_1_5r | hold_target_expiry | confirmed_only | 68 | 94.4% | +0.324 | +0.016 | 54.4% | +0.2% | 22.1% | neutral |
| 15m_30d | london_long_middle_local_next_open | fixed_1_5r | hold_target_expiry | confirmed_only | 41 | 93.2% | +0.685 | +0.018 | 68.3% | +0.1% | 12.2% | neutral |
| 15m_30d | london_long_middle_local_next_open | fixed_1_5r | partial_1r_be_after_half_target | confirmed_only | 41 | 93.2% | +0.676 | +0.012 | 68.3% | +0.1% | 12.2% | neutral |
| 15m_30d | london_long_middle_local_next_open | fixed_1_5r | be_after_half_target | confirmed_only | 41 | 93.2% | +0.696 | +0.012 | 68.3% | +0.1% | 12.2% | neutral |

## Decision Rules

- Promote only filters marked `direction_improver` or `return_improver`.
- Ignore filters with `accepted < 30` or `accepted_keep_rate < 35%`.
- If no add-on filter improves direction cleanly, the next work is better regime definition, not more entry filters.
