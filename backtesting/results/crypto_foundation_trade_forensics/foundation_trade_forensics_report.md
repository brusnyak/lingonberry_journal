# Crypto Foundation Trade Forensics

Purpose: de-duplicate the MTF structure journal into physical trades and test simple indicator chemistry.

## Test Scope
- Interval: `15m`.
- Concrete execution: `fixed_2r` + `hold_target_expiry`.
- Risk model: `0.20%` risk/trade, max `6` open, max `1` per symbol, daily loss cap `0.50%`.
- Entry span: `2026-05-13 16:45:00+00:00` to `2026-07-11 23:45:00+00:00`.
- Physical events: `378`.
- Strict candidate events: `113`.

## Rule Matrix
| window | rule | candidates | accepted | symbols | events_in_window | events_per_day | events_per_symbol_week | avg_duration_h | median_duration_h | acceptance_rate | exchanges | total_r | avg_r | median_r | profit_factor | gross_return_pct | max_dd_pct | daily_max_dd_pct | return_to_dd | win_rate | stop_rate | expiry_rate | risk_per_trade_pct | max_open_trades | max_open_per_symbol | daily_loss_limit_pct | median_mfe_r | p75_mfe_r | target_exits | post8_more_1r_after_target | post16_more_1r_after_target |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 60d | all_physical_fixed2_hold | 378 | 315 | 14 | 378.000 | 6.375 | 3.188 | 4.772 | 6.000 | 0.833 | 1 | 69.809 | 0.222 | 0.079 | 1.716 | 0.140 | 0.022 | 0.022 | 6.269 | 0.537 | 0.206 | 0.629 | 0.002 | 6 | 1 | 0.005 | 0.897 | 1.577 | 65 | 0.400 | 0.538 |
| 60d | strict_candidates | 113 | 112 | 14 | 113.000 | 1.906 | 0.953 | 4.511 | 6.000 | 0.991 | 1 | 63.374 | 0.566 | 0.497 | 3.251 | 0.127 | 0.008 | 0.007 | 16.729 | 0.670 | 0.179 | 0.554 | 0.002 | 6 | 1 | 0.005 | 1.275 | 2.146 | 30 | 0.367 | 0.500 |
| 60d | strict_late_us_no_weak_ema | 70 | 69 | 14 | 70.000 | 1.181 | 0.590 | 4.429 | 6.000 | 0.986 | 1 | 52.406 | 0.760 | 0.982 | 4.648 | 0.105 | 0.005 | 0.005 | 22.635 | 0.739 | 0.145 | 0.507 | 0.002 | 6 | 1 | 0.005 | 1.658 | 2.673 | 24 | 0.458 | 0.625 |
| 60d | strict_ema_stack_confirmed | 49 | 48 | 13 | 49.000 | 0.826 | 0.445 | 4.592 | 6.000 | 0.980 | 1 | 39.013 | 0.813 | 1.054 | 5.110 | 0.078 | 0.005 | 0.005 | 17.166 | 0.771 | 0.146 | 0.500 | 0.002 | 6 | 1 | 0.005 | 1.633 | 2.613 | 17 | 0.529 | 0.647 |
| 60d | strict_late_us_vwap_agrees | 53 | 52 | 12 | 53.000 | 0.894 | 0.521 | 4.509 | 6.000 | 0.981 | 1 | 38.265 | 0.736 | 0.549 | 6.019 | 0.077 | 0.004 | 0.003 | 17.192 | 0.769 | 0.077 | 0.615 | 0.002 | 6 | 1 | 0.005 | 1.387 | 2.872 | 16 | 0.500 | 0.625 |
| 60d | late_us_fade | 70 | 70 | 14 | 70.000 | 1.181 | 0.590 | 4.671 | 6.000 | 1.000 | 1 | 28.710 | 0.410 | 0.418 | 2.335 | 0.057 | 0.009 | 0.008 | 6.727 | 0.600 | 0.229 | 0.557 | 0.002 | 6 | 1 | 0.005 | 1.025 | 1.766 | 15 | 0.200 | 0.333 |
| 60d | strict_vwap_agrees | 38 | 37 | 11 | 38.000 | 0.641 | 0.408 | 4.770 | 6.000 | 0.974 | 1 | 26.756 | 0.723 | 0.536 | 7.396 | 0.054 | 0.002 | 0.002 | 23.196 | 0.811 | 0.054 | 0.676 | 0.002 | 6 | 1 | 0.005 | 1.223 | 1.986 | 10 | 0.600 | 0.700 |
| 60d | ny_13_range_reversal | 29 | 29 | 12 | 29.000 | 0.489 | 0.285 | 3.914 | 6.000 | 1.000 | 1 | 25.093 | 0.865 | 1.016 | 6.151 | 0.050 | 0.003 | 0.003 | 14.854 | 0.759 | 0.103 | 0.517 | 0.002 | 6 | 1 | 0.005 | 1.856 | 3.579 | 11 | 0.455 | 0.636 |
| 60d | late_us_fade_no_aligned_shock | 59 | 59 | 14 | 59.000 | 0.995 | 0.498 | 4.576 | 6.000 | 1.000 | 1 | 24.996 | 0.424 | 0.381 | 2.390 | 0.050 | 0.009 | 0.008 | 5.857 | 0.593 | 0.220 | 0.542 | 0.002 | 6 | 1 | 0.005 | 1.042 | 1.833 | 14 | 0.214 | 0.357 |
| 60d | strict_direction_quality | 19 | 18 | 10 | 19.000 | 0.320 | 0.224 | 4.645 | 6.000 | 0.947 | 1 | 15.753 | 0.875 | 0.783 | 9.910 | 0.032 | 0.002 | 0.002 | 15.133 | 0.889 | 0.056 | 0.611 | 0.002 | 6 | 1 | 0.005 | 1.387 | 2.992 | 6 | 0.833 | 0.833 |
| 60d | ny_13_expanded_or_opposing | 11 | 11 | 7 | 11.000 | 0.186 | 0.186 | 3.295 | 3.000 | 1.000 | 1 | 9.922 | 0.902 | 1.915 | 4.423 | 0.020 | 0.002 | 0.002 | 8.021 | 0.727 | 0.182 | 0.273 | 0.002 | 6 | 1 | 0.005 | 2.683 | 3.591 | 6 | 0.167 | 0.333 |
| 60d | london_trend_aligned | 14 | 13 | 9 | 14.000 | 0.236 | 0.184 | 4.946 | 6.000 | 0.929 | 1 | 9.571 | 0.736 | 0.536 | 6.413 | 0.019 | 0.002 | 0.002 | 9.194 | 0.846 | 0.077 | 0.615 | 0.002 | 6 | 1 | 0.005 | 1.448 | 2.582 | 4 | 0.750 | 0.750 |
| 60d | london_trend_ema_bullish | 14 | 13 | 9 | 14.000 | 0.236 | 0.184 | 4.946 | 6.000 | 0.929 | 1 | 9.571 | 0.736 | 0.536 | 6.413 | 0.019 | 0.002 | 0.002 | 9.194 | 0.846 | 0.077 | 0.615 | 0.002 | 6 | 1 | 0.005 | 1.448 | 2.582 | 4 | 0.750 | 0.750 |
| 60d | london_trend_rsi_not_overbought | 9 | 8 | 8 | 9.000 | 0.152 | 0.133 | 5.250 | 6.000 | 0.889 | 1 | 4.086 | 0.511 | 0.466 | 4.926 | 0.008 | 0.002 | 0.002 | 3.926 | 0.875 | 0.125 | 0.750 | 0.002 | 6 | 1 | 0.005 | 0.900 | 1.508 | 1 | 1.000 | 1.000 |
| 60d | late_us_fade_vwap_agrees | 10 | 10 | 8 | 10.000 | 0.169 | 0.148 | 5.625 | 6.000 | 1.000 | 1 | 3.601 | 0.360 | 0.420 | 4.658 | 0.007 | 0.001 | 0.001 | 6.454 | 0.700 | 0.000 | 0.900 | 0.002 | 6 | 1 | 0.005 | 0.625 | 1.066 | 1 | 0.000 | 0.000 |
| first30d | strict_late_us_no_weak_ema | 13 | 13 | 9 | 13.000 | 0.435 | 0.338 | 4.404 | 6.000 | 1.000 | 1 | 7.000 | 0.538 | 0.993 | 2.748 | 0.014 | 0.005 | 0.005 | 3.023 | 0.692 | 0.231 | 0.615 | 0.002 | 6 | 1 | 0.005 | 1.500 | 1.944 | 2 | 1.000 | 1.000 |
| first30d | strict_ema_stack_confirmed | 7 | 7 | 6 | 7.000 | 0.234 | 0.273 | 5.107 | 6.000 | 1.000 | 1 | 6.504 | 0.929 | 1.202 | 7.032 | 0.013 | 0.002 | 0.000 | 6.032 | 0.857 | 0.143 | 0.714 | 0.002 | 6 | 1 | 0.005 | 1.500 | 1.770 | 1 | 1.000 | 1.000 |
| first30d | strict_vwap_agrees | 9 | 9 | 7 | 9.000 | 0.301 | 0.301 | 5.028 | 6.000 | 1.000 | 1 | 5.731 | 0.637 | 0.602 | 6.207 | 0.011 | 0.002 | 0.002 | 5.207 | 0.889 | 0.111 | 0.778 | 0.002 | 6 | 1 | 0.005 | 1.068 | 1.375 | 1 | 1.000 | 1.000 |
| first30d | strict_late_us_vwap_agrees | 12 | 12 | 9 | 12.000 | 0.401 | 0.312 | 4.792 | 6.000 | 1.000 | 1 | 5.566 | 0.464 | 0.528 | 2.902 | 0.011 | 0.003 | 0.003 | 3.295 | 0.750 | 0.167 | 0.750 | 0.002 | 6 | 1 | 0.005 | 1.120 | 1.814 | 1 | 1.000 | 1.000 |
| first30d | strict_candidates | 26 | 26 | 10 | 26.000 | 0.869 | 0.608 | 4.587 | 6.000 | 1.000 | 1 | 5.387 | 0.207 | 0.142 | 1.596 | 0.011 | 0.006 | 0.005 | 1.694 | 0.538 | 0.269 | 0.615 | 0.002 | 6 | 1 | 0.005 | 1.034 | 1.705 | 3 | 0.667 | 0.667 |

## Cost And Slippage Stress
| window | rule | scenario | candidates | accepted | median_extra_cost_r | gross_return_pct | max_dd_pct | profit_factor | win_rate | return_to_dd |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 30d | late_us_fade | baseline | 53 | 53 | 0.000 | 0.055 | 0.009 | 2.782 | 0.642 | 6.431 |
| 30d | late_us_fade | punitive_40bps | 53 | 52 | 0.334 | 0.019 | 0.014 | 1.437 | 0.635 | 1.357 |
| 30d | late_us_fade | nightmare_60bps | 53 | 50 | 0.501 | -0.000 | 0.023 | 0.993 | 0.520 | -0.014 |
| 30d | strict_candidates | baseline | 87 | 86 | 0.000 | 0.116 | 0.008 | 4.034 | 0.709 | 15.307 |
| 30d | strict_candidates | punitive_40bps | 87 | 85 | 0.328 | 0.053 | 0.011 | 1.986 | 0.659 | 5.054 |
| 30d | strict_candidates | nightmare_60bps | 87 | 84 | 0.492 | 0.018 | 0.017 | 1.276 | 0.536 | 1.043 |
| 30d | strict_direction_quality | baseline | 16 | 15 | 0.000 | 0.027 | 0.002 | 8.541 | 0.867 | 12.807 |
| 30d | strict_direction_quality | punitive_40bps | 16 | 15 | 0.213 | 0.016 | 0.002 | 4.256 | 0.733 | 6.536 |
| 30d | strict_direction_quality | nightmare_60bps | 16 | 15 | 0.319 | 0.011 | 0.003 | 2.625 | 0.600 | 3.556 |
| 30d | strict_ema_stack_confirmed | baseline | 42 | 41 | 0.000 | 0.065 | 0.005 | 4.844 | 0.756 | 14.234 |
| 30d | strict_ema_stack_confirmed | punitive_40bps | 42 | 41 | 0.376 | 0.029 | 0.007 | 2.078 | 0.683 | 4.045 |
| 30d | strict_ema_stack_confirmed | nightmare_60bps | 42 | 41 | 0.564 | 0.012 | 0.012 | 1.342 | 0.585 | 1.018 |
| 30d | strict_late_us_no_weak_ema | baseline | 57 | 56 | 0.000 | 0.091 | 0.005 | 5.383 | 0.750 | 19.980 |
| 30d | strict_late_us_no_weak_ema | punitive_40bps | 57 | 56 | 0.364 | 0.044 | 0.007 | 2.283 | 0.661 | 5.914 |
| 30d | strict_late_us_no_weak_ema | nightmare_60bps | 57 | 56 | 0.545 | 0.020 | 0.013 | 1.463 | 0.571 | 1.573 |
| 30d | strict_late_us_vwap_agrees | baseline | 41 | 40 | 0.000 | 0.065 | 0.004 | 7.961 | 0.775 | 14.691 |
| 30d | strict_late_us_vwap_agrees | punitive_40bps | 41 | 40 | 0.296 | 0.036 | 0.008 | 3.506 | 0.675 | 4.581 |
| 30d | strict_late_us_vwap_agrees | nightmare_60bps | 41 | 40 | 0.443 | 0.021 | 0.010 | 2.114 | 0.525 | 2.011 |
| 30d | strict_vwap_agrees | baseline | 29 | 28 | 0.000 | 0.042 | 0.002 | 7.820 | 0.786 | 18.228 |
| 30d | strict_vwap_agrees | punitive_40bps | 29 | 28 | 0.202 | 0.024 | 0.003 | 3.722 | 0.679 | 8.720 |
| 30d | strict_vwap_agrees | nightmare_60bps | 29 | 28 | 0.303 | 0.015 | 0.003 | 2.294 | 0.536 | 4.701 |
| 60d | late_us_fade | baseline | 70 | 70 | 0.000 | 0.057 | 0.009 | 2.335 | 0.600 | 6.727 |
| 60d | late_us_fade | punitive_40bps | 70 | 69 | 0.281 | 0.016 | 0.014 | 1.264 | 0.580 | 1.140 |
| 60d | late_us_fade | nightmare_60bps | 70 | 67 | 0.421 | -0.006 | 0.023 | 0.910 | 0.493 | -0.258 |
| 60d | strict_candidates | baseline | 113 | 112 | 0.000 | 0.127 | 0.008 | 3.251 | 0.670 | 16.729 |
| 60d | strict_candidates | punitive_40bps | 113 | 111 | 0.308 | 0.049 | 0.013 | 1.609 | 0.613 | 3.724 |
| 60d | strict_candidates | nightmare_60bps | 113 | 109 | 0.462 | 0.010 | 0.017 | 1.106 | 0.523 | 0.574 |
| 60d | strict_direction_quality | baseline | 19 | 18 | 0.000 | 0.032 | 0.002 | 9.910 | 0.889 | 15.133 |
| 60d | strict_direction_quality | punitive_40bps | 19 | 18 | 0.218 | 0.020 | 0.002 | 4.917 | 0.778 | 7.865 |
| 60d | strict_direction_quality | nightmare_60bps | 19 | 18 | 0.328 | 0.014 | 0.003 | 2.997 | 0.667 | 4.371 |
| 60d | strict_ema_stack_confirmed | baseline | 49 | 48 | 0.000 | 0.078 | 0.005 | 5.110 | 0.771 | 17.166 |
| 60d | strict_ema_stack_confirmed | punitive_40bps | 49 | 48 | 0.336 | 0.039 | 0.007 | 2.303 | 0.708 | 5.412 |
| 60d | strict_ema_stack_confirmed | nightmare_60bps | 49 | 48 | 0.504 | 0.020 | 0.012 | 1.530 | 0.625 | 1.734 |
| 60d | strict_late_us_no_weak_ema | baseline | 70 | 69 | 0.000 | 0.105 | 0.005 | 4.648 | 0.739 | 22.635 |
| 60d | strict_late_us_no_weak_ema | punitive_40bps | 70 | 69 | 0.350 | 0.047 | 0.008 | 1.996 | 0.652 | 6.030 |
| 60d | strict_late_us_no_weak_ema | nightmare_60bps | 70 | 68 | 0.525 | 0.021 | 0.014 | 1.378 | 0.588 | 1.553 |
| 60d | strict_late_us_vwap_agrees | baseline | 53 | 52 | 0.000 | 0.077 | 0.004 | 6.019 | 0.769 | 17.192 |
| 60d | strict_late_us_vwap_agrees | punitive_40bps | 53 | 52 | 0.296 | 0.037 | 0.008 | 2.509 | 0.673 | 4.837 |
| 60d | strict_late_us_vwap_agrees | nightmare_60bps | 53 | 52 | 0.443 | 0.017 | 0.010 | 1.536 | 0.558 | 1.657 |
| 60d | strict_vwap_agrees | baseline | 38 | 37 | 0.000 | 0.054 | 0.002 | 7.396 | 0.811 | 23.196 |
| 60d | strict_vwap_agrees | punitive_40bps | 38 | 37 | 0.205 | 0.029 | 0.005 | 3.307 | 0.703 | 5.390 |
| 60d | strict_vwap_agrees | nightmare_60bps | 38 | 37 | 0.307 | 0.017 | 0.008 | 1.983 | 0.595 | 2.057 |

## Extreme Configuration Matrix
| window | rule | scenario | config | risk_per_trade_pct | max_open_trades | daily_loss_limit_pct | accepted | gross_return_pct | max_dd_pct | daily_max_dd_pct | profit_factor | win_rate | return_to_dd |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 30d | late_us_fade | baseline | base | 0.002 | 6 | 0.005 | 53 | 0.055 | 0.009 | 0.008 | 2.782 | 0.642 | 6.431 |
| 30d | late_us_fade | baseline | conservative | 0.002 | 4 | 0.004 | 43 | 0.034 | 0.006 | 0.006 | 2.795 | 0.651 | 5.274 |
| 30d | late_us_fade | baseline | prop_strict | 0.003 | 4 | 0.004 | 42 | 0.059 | 0.011 | 0.009 | 3.059 | 0.667 | 5.528 |
| 30d | late_us_fade | nightmare_60bps | base | 0.002 | 6 | 0.005 | 50 | -0.000 | 0.023 | 0.017 | 0.993 | 0.520 | -0.014 |
| 30d | late_us_fade | nightmare_60bps | conservative | 0.002 | 4 | 0.004 | 42 | -0.000 | 0.015 | 0.014 | 0.998 | 0.524 | -0.004 |
| 30d | late_us_fade | nightmare_60bps | prop_strict | 0.003 | 4 | 0.004 | 40 | 0.006 | 0.021 | 0.021 | 1.136 | 0.550 | 0.292 |
| 30d | late_us_fade | punitive_40bps | base | 0.002 | 6 | 0.005 | 52 | 0.019 | 0.014 | 0.013 | 1.437 | 0.635 | 1.357 |
| 30d | late_us_fade | punitive_40bps | conservative | 0.002 | 4 | 0.004 | 42 | 0.012 | 0.010 | 0.010 | 1.455 | 0.643 | 1.151 |
| 30d | late_us_fade | punitive_40bps | prop_strict | 0.003 | 4 | 0.004 | 41 | 0.024 | 0.017 | 0.017 | 1.637 | 0.659 | 1.432 |
| 30d | strict_candidates | baseline | base | 0.002 | 6 | 0.005 | 86 | 0.116 | 0.008 | 0.007 | 4.034 | 0.709 | 15.307 |
| 30d | strict_candidates | baseline | conservative | 0.002 | 4 | 0.004 | 75 | 0.076 | 0.006 | 0.005 | 4.101 | 0.720 | 13.307 |
| 30d | strict_candidates | baseline | prop_strict | 0.003 | 4 | 0.004 | 74 | 0.129 | 0.009 | 0.006 | 4.394 | 0.730 | 13.593 |
| 30d | strict_candidates | nightmare_60bps | base | 0.002 | 6 | 0.005 | 84 | 0.018 | 0.017 | 0.012 | 1.276 | 0.536 | 1.043 |
| 30d | strict_candidates | nightmare_60bps | conservative | 0.002 | 4 | 0.004 | 73 | 0.010 | 0.013 | 0.011 | 1.231 | 0.521 | 0.734 |
| 30d | strict_candidates | nightmare_60bps | prop_strict | 0.003 | 4 | 0.004 | 71 | 0.026 | 0.017 | 0.012 | 1.427 | 0.535 | 1.570 |
| 30d | strict_candidates | punitive_40bps | base | 0.002 | 6 | 0.005 | 85 | 0.053 | 0.011 | 0.007 | 1.986 | 0.659 | 5.054 |
| 30d | strict_candidates | punitive_40bps | conservative | 0.002 | 4 | 0.004 | 74 | 0.034 | 0.008 | 0.005 | 1.974 | 0.662 | 4.256 |
| 30d | strict_candidates | punitive_40bps | prop_strict | 0.003 | 4 | 0.004 | 72 | 0.057 | 0.013 | 0.012 | 2.080 | 0.667 | 4.328 |
| 30d | strict_direction_quality | baseline | base | 0.002 | 6 | 0.005 | 15 | 0.027 | 0.002 | 0.002 | 8.541 | 0.867 | 12.807 |
| 30d | strict_direction_quality | baseline | conservative | 0.002 | 4 | 0.004 | 15 | 0.020 | 0.002 | 0.002 | 8.541 | 0.867 | 12.807 |
| 30d | strict_direction_quality | baseline | prop_strict | 0.003 | 4 | 0.004 | 15 | 0.033 | 0.003 | 0.003 | 8.541 | 0.867 | 12.807 |
| 30d | strict_direction_quality | nightmare_60bps | base | 0.002 | 6 | 0.005 | 15 | 0.011 | 0.003 | 0.003 | 2.625 | 0.600 | 3.556 |
| 30d | strict_direction_quality | nightmare_60bps | conservative | 0.002 | 4 | 0.004 | 15 | 0.008 | 0.002 | 0.002 | 2.625 | 0.600 | 3.556 |
| 30d | strict_direction_quality | nightmare_60bps | prop_strict | 0.003 | 4 | 0.004 | 15 | 0.014 | 0.004 | 0.003 | 2.625 | 0.600 | 3.556 |
| 30d | strict_direction_quality | punitive_40bps | base | 0.002 | 6 | 0.005 | 15 | 0.016 | 0.002 | 0.002 | 4.256 | 0.733 | 6.536 |
| 30d | strict_direction_quality | punitive_40bps | conservative | 0.002 | 4 | 0.004 | 15 | 0.012 | 0.002 | 0.002 | 4.256 | 0.733 | 6.536 |
| 30d | strict_direction_quality | punitive_40bps | prop_strict | 0.003 | 4 | 0.004 | 15 | 0.020 | 0.003 | 0.003 | 4.256 | 0.733 | 6.536 |
| 30d | strict_ema_stack_confirmed | baseline | base | 0.002 | 6 | 0.005 | 41 | 0.065 | 0.005 | 0.005 | 4.844 | 0.756 | 14.234 |
| 30d | strict_ema_stack_confirmed | baseline | conservative | 0.002 | 4 | 0.004 | 37 | 0.041 | 0.003 | 0.003 | 4.387 | 0.757 | 11.990 |
| 30d | strict_ema_stack_confirmed | baseline | prop_strict | 0.003 | 4 | 0.004 | 37 | 0.068 | 0.006 | 0.006 | 4.387 | 0.757 | 11.990 |
| 30d | strict_ema_stack_confirmed | nightmare_60bps | base | 0.002 | 6 | 0.005 | 41 | 0.012 | 0.012 | 0.009 | 1.342 | 0.585 | 1.018 |
| 30d | strict_ema_stack_confirmed | nightmare_60bps | conservative | 0.002 | 4 | 0.004 | 37 | 0.005 | 0.008 | 0.006 | 1.204 | 0.568 | 0.593 |
| 30d | strict_ema_stack_confirmed | nightmare_60bps | prop_strict | 0.003 | 4 | 0.004 | 36 | 0.013 | 0.009 | 0.006 | 1.377 | 0.583 | 1.507 |
| 30d | strict_ema_stack_confirmed | punitive_40bps | base | 0.002 | 6 | 0.005 | 41 | 0.029 | 0.007 | 0.007 | 2.078 | 0.683 | 4.045 |
| 30d | strict_ema_stack_confirmed | punitive_40bps | conservative | 0.002 | 4 | 0.004 | 37 | 0.017 | 0.005 | 0.005 | 1.881 | 0.676 | 3.104 |
| 30d | strict_ema_stack_confirmed | punitive_40bps | prop_strict | 0.003 | 4 | 0.004 | 36 | 0.032 | 0.005 | 0.005 | 2.173 | 0.694 | 6.793 |
| 30d | strict_late_us_no_weak_ema | baseline | base | 0.002 | 6 | 0.005 | 56 | 0.091 | 0.005 | 0.005 | 5.383 | 0.750 | 19.980 |
| 30d | strict_late_us_no_weak_ema | baseline | conservative | 0.002 | 4 | 0.004 | 51 | 0.058 | 0.003 | 0.003 | 4.843 | 0.745 | 16.892 |
| 30d | strict_late_us_no_weak_ema | baseline | prop_strict | 0.003 | 4 | 0.004 | 51 | 0.096 | 0.006 | 0.006 | 4.843 | 0.745 | 16.892 |
| 30d | strict_late_us_no_weak_ema | nightmare_60bps | base | 0.002 | 6 | 0.005 | 56 | 0.020 | 0.013 | 0.010 | 1.463 | 0.571 | 1.573 |
| 30d | strict_late_us_no_weak_ema | nightmare_60bps | conservative | 0.002 | 4 | 0.004 | 51 | 0.009 | 0.009 | 0.007 | 1.307 | 0.549 | 1.029 |
| 30d | strict_late_us_no_weak_ema | nightmare_60bps | prop_strict | 0.003 | 4 | 0.004 | 49 | 0.025 | 0.010 | 0.008 | 1.591 | 0.571 | 2.430 |
| 30d | strict_late_us_no_weak_ema | punitive_40bps | base | 0.002 | 6 | 0.005 | 56 | 0.044 | 0.007 | 0.007 | 2.283 | 0.661 | 5.914 |
| 30d | strict_late_us_no_weak_ema | punitive_40bps | conservative | 0.002 | 4 | 0.004 | 51 | 0.025 | 0.006 | 0.005 | 2.053 | 0.647 | 4.199 |
| 30d | strict_late_us_no_weak_ema | punitive_40bps | prop_strict | 0.003 | 4 | 0.004 | 50 | 0.047 | 0.009 | 0.008 | 2.298 | 0.660 | 5.429 |
| 30d | strict_late_us_vwap_agrees | baseline | base | 0.002 | 6 | 0.005 | 40 | 0.065 | 0.004 | 0.003 | 7.961 | 0.775 | 14.691 |
| 30d | strict_late_us_vwap_agrees | baseline | conservative | 0.002 | 4 | 0.004 | 39 | 0.046 | 0.003 | 0.002 | 7.542 | 0.769 | 13.807 |
| 30d | strict_late_us_vwap_agrees | baseline | prop_strict | 0.003 | 4 | 0.004 | 39 | 0.077 | 0.006 | 0.003 | 7.542 | 0.769 | 13.807 |
| 30d | strict_late_us_vwap_agrees | nightmare_60bps | base | 0.002 | 6 | 0.005 | 40 | 0.021 | 0.010 | 0.010 | 2.114 | 0.525 | 2.011 |
| 30d | strict_late_us_vwap_agrees | nightmare_60bps | conservative | 0.002 | 4 | 0.004 | 39 | 0.013 | 0.008 | 0.008 | 1.941 | 0.513 | 1.699 |
| 30d | strict_late_us_vwap_agrees | nightmare_60bps | prop_strict | 0.003 | 4 | 0.004 | 38 | 0.026 | 0.009 | 0.009 | 2.342 | 0.526 | 2.904 |
| 30d | strict_late_us_vwap_agrees | punitive_40bps | base | 0.002 | 6 | 0.005 | 40 | 0.036 | 0.008 | 0.008 | 3.506 | 0.675 | 4.581 |
| 30d | strict_late_us_vwap_agrees | punitive_40bps | conservative | 0.002 | 4 | 0.004 | 39 | 0.024 | 0.006 | 0.006 | 3.262 | 0.667 | 4.135 |
| 30d | strict_late_us_vwap_agrees | punitive_40bps | prop_strict | 0.003 | 4 | 0.004 | 39 | 0.040 | 0.010 | 0.010 | 3.262 | 0.667 | 4.135 |
| 30d | strict_vwap_agrees | baseline | base | 0.002 | 6 | 0.005 | 28 | 0.042 | 0.002 | 0.002 | 7.820 | 0.786 | 18.228 |
| 30d | strict_vwap_agrees | baseline | conservative | 0.002 | 4 | 0.004 | 28 | 0.032 | 0.002 | 0.002 | 7.820 | 0.786 | 18.228 |
| 30d | strict_vwap_agrees | baseline | prop_strict | 0.003 | 4 | 0.004 | 28 | 0.053 | 0.003 | 0.003 | 7.820 | 0.786 | 18.228 |
| 30d | strict_vwap_agrees | nightmare_60bps | base | 0.002 | 6 | 0.005 | 28 | 0.015 | 0.003 | 0.003 | 2.294 | 0.536 | 4.701 |
| 30d | strict_vwap_agrees | nightmare_60bps | conservative | 0.002 | 4 | 0.004 | 28 | 0.011 | 0.002 | 0.002 | 2.294 | 0.536 | 4.701 |
| 30d | strict_vwap_agrees | nightmare_60bps | prop_strict | 0.003 | 4 | 0.004 | 28 | 0.018 | 0.004 | 0.004 | 2.294 | 0.536 | 4.701 |
| 30d | strict_vwap_agrees | punitive_40bps | base | 0.002 | 6 | 0.005 | 28 | 0.024 | 0.003 | 0.003 | 3.722 | 0.679 | 8.720 |
| 30d | strict_vwap_agrees | punitive_40bps | conservative | 0.002 | 4 | 0.004 | 28 | 0.018 | 0.002 | 0.002 | 3.722 | 0.679 | 8.720 |
| 30d | strict_vwap_agrees | punitive_40bps | prop_strict | 0.003 | 4 | 0.004 | 28 | 0.030 | 0.003 | 0.003 | 3.722 | 0.679 | 8.720 |
| 60d | late_us_fade | baseline | base | 0.002 | 6 | 0.005 | 70 | 0.057 | 0.009 | 0.008 | 2.335 | 0.600 | 6.727 |
| 60d | late_us_fade | baseline | conservative | 0.002 | 4 | 0.004 | 60 | 0.036 | 0.006 | 0.006 | 2.288 | 0.600 | 5.629 |
| 60d | late_us_fade | baseline | prop_strict | 0.003 | 4 | 0.004 | 59 | 0.063 | 0.011 | 0.009 | 2.429 | 0.610 | 5.883 |
| 60d | late_us_fade | nightmare_60bps | base | 0.002 | 6 | 0.005 | 67 | -0.006 | 0.023 | 0.017 | 0.910 | 0.493 | -0.258 |
| 60d | late_us_fade | nightmare_60bps | conservative | 0.002 | 4 | 0.004 | 59 | -0.005 | 0.015 | 0.014 | 0.879 | 0.492 | -0.351 |
| 60d | late_us_fade | nightmare_60bps | prop_strict | 0.003 | 4 | 0.004 | 57 | -0.003 | 0.021 | 0.021 | 0.960 | 0.509 | -0.131 |
| 60d | late_us_fade | punitive_40bps | base | 0.002 | 6 | 0.005 | 69 | 0.016 | 0.014 | 0.013 | 1.264 | 0.580 | 1.140 |
| 60d | late_us_fade | punitive_40bps | conservative | 0.002 | 4 | 0.004 | 59 | 0.009 | 0.010 | 0.010 | 1.235 | 0.576 | 0.877 |
| 60d | late_us_fade | punitive_40bps | prop_strict | 0.003 | 4 | 0.004 | 58 | 0.020 | 0.017 | 0.017 | 1.335 | 0.586 | 1.158 |
| 60d | strict_candidates | baseline | base | 0.002 | 6 | 0.005 | 112 | 0.127 | 0.008 | 0.007 | 3.251 | 0.670 | 16.729 |
| 60d | strict_candidates | baseline | conservative | 0.002 | 4 | 0.004 | 101 | 0.085 | 0.006 | 0.005 | 3.233 | 0.673 | 14.907 |
| 60d | strict_candidates | baseline | prop_strict | 0.003 | 4 | 0.004 | 100 | 0.144 | 0.009 | 0.006 | 3.377 | 0.680 | 15.192 |
| 60d | strict_candidates | nightmare_60bps | base | 0.002 | 6 | 0.005 | 109 | 0.010 | 0.017 | 0.013 | 1.106 | 0.523 | 0.574 |
| 60d | strict_candidates | nightmare_60bps | conservative | 0.002 | 4 | 0.004 | 98 | 0.006 | 0.012 | 0.010 | 1.087 | 0.520 | 0.454 |
| 60d | strict_candidates | nightmare_60bps | prop_strict | 0.003 | 4 | 0.004 | 95 | 0.022 | 0.017 | 0.013 | 1.237 | 0.537 | 1.306 |
| 60d | strict_candidates | punitive_40bps | base | 0.002 | 6 | 0.005 | 111 | 0.049 | 0.013 | 0.011 | 1.609 | 0.613 | 3.724 |
| 60d | strict_candidates | punitive_40bps | conservative | 0.002 | 4 | 0.004 | 99 | 0.034 | 0.008 | 0.007 | 1.656 | 0.616 | 4.344 |
| 60d | strict_candidates | punitive_40bps | prop_strict | 0.003 | 4 | 0.004 | 97 | 0.058 | 0.013 | 0.012 | 1.705 | 0.619 | 4.416 |
| 60d | strict_direction_quality | baseline | base | 0.002 | 6 | 0.005 | 18 | 0.032 | 0.002 | 0.002 | 9.910 | 0.889 | 15.133 |
| 60d | strict_direction_quality | baseline | conservative | 0.002 | 4 | 0.004 | 18 | 0.024 | 0.002 | 0.002 | 9.910 | 0.889 | 15.133 |
| 60d | strict_direction_quality | baseline | prop_strict | 0.003 | 4 | 0.004 | 18 | 0.039 | 0.003 | 0.003 | 9.910 | 0.889 | 15.133 |
| 60d | strict_direction_quality | nightmare_60bps | base | 0.002 | 6 | 0.005 | 18 | 0.014 | 0.003 | 0.003 | 2.997 | 0.667 | 4.371 |
| 60d | strict_direction_quality | nightmare_60bps | conservative | 0.002 | 4 | 0.004 | 18 | 0.010 | 0.002 | 0.002 | 2.997 | 0.667 | 4.371 |
| 60d | strict_direction_quality | nightmare_60bps | prop_strict | 0.003 | 4 | 0.004 | 18 | 0.017 | 0.004 | 0.003 | 2.997 | 0.667 | 4.371 |
| 60d | strict_direction_quality | punitive_40bps | base | 0.002 | 6 | 0.005 | 18 | 0.020 | 0.002 | 0.002 | 4.917 | 0.778 | 7.865 |
| 60d | strict_direction_quality | punitive_40bps | conservative | 0.002 | 4 | 0.004 | 18 | 0.015 | 0.002 | 0.002 | 4.917 | 0.778 | 7.865 |
| 60d | strict_direction_quality | punitive_40bps | prop_strict | 0.003 | 4 | 0.004 | 18 | 0.025 | 0.003 | 0.003 | 4.917 | 0.778 | 7.865 |
| 60d | strict_ema_stack_confirmed | baseline | base | 0.002 | 6 | 0.005 | 48 | 0.078 | 0.005 | 0.005 | 5.110 | 0.771 | 17.166 |
| 60d | strict_ema_stack_confirmed | baseline | conservative | 0.002 | 4 | 0.004 | 44 | 0.051 | 0.003 | 0.003 | 4.717 | 0.773 | 14.922 |
| 60d | strict_ema_stack_confirmed | baseline | prop_strict | 0.003 | 4 | 0.004 | 44 | 0.085 | 0.006 | 0.006 | 4.717 | 0.773 | 14.922 |
| 60d | strict_ema_stack_confirmed | nightmare_60bps | base | 0.002 | 6 | 0.005 | 48 | 0.020 | 0.012 | 0.009 | 1.530 | 0.625 | 1.734 |
| 60d | strict_ema_stack_confirmed | nightmare_60bps | conservative | 0.002 | 4 | 0.004 | 44 | 0.011 | 0.008 | 0.006 | 1.417 | 0.614 | 1.337 |
| 60d | strict_ema_stack_confirmed | nightmare_60bps | prop_strict | 0.003 | 4 | 0.004 | 43 | 0.024 | 0.009 | 0.006 | 1.599 | 0.628 | 2.676 |
| 60d | strict_ema_stack_confirmed | punitive_40bps | base | 0.002 | 6 | 0.005 | 48 | 0.039 | 0.007 | 0.007 | 2.303 | 0.708 | 5.412 |
| 60d | strict_ema_stack_confirmed | punitive_40bps | conservative | 0.002 | 4 | 0.004 | 44 | 0.024 | 0.005 | 0.005 | 2.139 | 0.705 | 4.472 |
| 60d | strict_ema_stack_confirmed | punitive_40bps | prop_strict | 0.003 | 4 | 0.004 | 43 | 0.045 | 0.005 | 0.005 | 2.432 | 0.721 | 9.390 |
| 60d | strict_late_us_no_weak_ema | baseline | base | 0.002 | 6 | 0.005 | 69 | 0.105 | 0.005 | 0.005 | 4.648 | 0.739 | 22.635 |
| 60d | strict_late_us_no_weak_ema | baseline | conservative | 0.002 | 4 | 0.004 | 64 | 0.070 | 0.003 | 0.003 | 4.287 | 0.734 | 20.028 |
| 60d | strict_late_us_no_weak_ema | baseline | prop_strict | 0.003 | 4 | 0.004 | 64 | 0.116 | 0.006 | 0.006 | 4.287 | 0.734 | 20.028 |
| 60d | strict_late_us_no_weak_ema | nightmare_60bps | base | 0.002 | 6 | 0.005 | 68 | 0.021 | 0.014 | 0.010 | 1.378 | 0.588 | 1.553 |
| 60d | strict_late_us_no_weak_ema | nightmare_60bps | conservative | 0.002 | 4 | 0.004 | 63 | 0.012 | 0.008 | 0.007 | 1.306 | 0.571 | 1.489 |
| 60d | strict_late_us_no_weak_ema | nightmare_60bps | prop_strict | 0.003 | 4 | 0.004 | 61 | 0.030 | 0.008 | 0.008 | 1.530 | 0.590 | 3.784 |
| 60d | strict_late_us_no_weak_ema | punitive_40bps | base | 0.002 | 6 | 0.005 | 69 | 0.047 | 0.008 | 0.008 | 1.996 | 0.652 | 6.030 |
| 60d | strict_late_us_no_weak_ema | punitive_40bps | conservative | 0.002 | 4 | 0.004 | 63 | 0.032 | 0.005 | 0.005 | 2.012 | 0.651 | 5.854 |
| 60d | strict_late_us_no_weak_ema | punitive_40bps | prop_strict | 0.003 | 4 | 0.004 | 62 | 0.058 | 0.009 | 0.008 | 2.214 | 0.661 | 6.728 |
| 60d | strict_late_us_vwap_agrees | baseline | base | 0.002 | 6 | 0.005 | 52 | 0.077 | 0.004 | 0.003 | 6.019 | 0.769 | 17.192 |
| 60d | strict_late_us_vwap_agrees | baseline | conservative | 0.002 | 4 | 0.004 | 51 | 0.054 | 0.003 | 0.003 | 5.764 | 0.765 | 16.319 |
| 60d | strict_late_us_vwap_agrees | baseline | prop_strict | 0.003 | 4 | 0.004 | 51 | 0.091 | 0.006 | 0.004 | 5.764 | 0.765 | 16.319 |
| 60d | strict_late_us_vwap_agrees | nightmare_60bps | base | 0.002 | 6 | 0.005 | 52 | 0.017 | 0.010 | 0.010 | 1.536 | 0.558 | 1.657 |
| 60d | strict_late_us_vwap_agrees | nightmare_60bps | conservative | 0.002 | 4 | 0.004 | 51 | 0.011 | 0.008 | 0.008 | 1.452 | 0.549 | 1.396 |
| 60d | strict_late_us_vwap_agrees | nightmare_60bps | prop_strict | 0.003 | 4 | 0.004 | 50 | 0.022 | 0.013 | 0.013 | 1.612 | 0.560 | 1.778 |
| 60d | strict_late_us_vwap_agrees | punitive_40bps | base | 0.002 | 6 | 0.005 | 52 | 0.037 | 0.008 | 0.008 | 2.509 | 0.673 | 4.837 |
| 60d | strict_late_us_vwap_agrees | punitive_40bps | conservative | 0.002 | 4 | 0.004 | 51 | 0.025 | 0.006 | 0.006 | 2.382 | 0.667 | 4.431 |
| 60d | strict_late_us_vwap_agrees | punitive_40bps | prop_strict | 0.003 | 4 | 0.004 | 51 | 0.042 | 0.010 | 0.010 | 2.382 | 0.667 | 4.431 |
| 60d | strict_vwap_agrees | baseline | base | 0.002 | 6 | 0.005 | 37 | 0.054 | 0.002 | 0.002 | 7.396 | 0.811 | 23.196 |
| 60d | strict_vwap_agrees | baseline | conservative | 0.002 | 4 | 0.004 | 37 | 0.040 | 0.002 | 0.002 | 7.396 | 0.811 | 23.196 |
| 60d | strict_vwap_agrees | baseline | prop_strict | 0.003 | 4 | 0.004 | 37 | 0.067 | 0.003 | 0.003 | 7.396 | 0.811 | 23.196 |
| 60d | strict_vwap_agrees | nightmare_60bps | base | 0.002 | 6 | 0.005 | 37 | 0.017 | 0.008 | 0.008 | 1.983 | 0.595 | 2.057 |
| 60d | strict_vwap_agrees | nightmare_60bps | conservative | 0.002 | 4 | 0.004 | 37 | 0.013 | 0.006 | 0.006 | 1.983 | 0.595 | 2.057 |
| 60d | strict_vwap_agrees | nightmare_60bps | prop_strict | 0.003 | 4 | 0.004 | 37 | 0.021 | 0.010 | 0.010 | 1.983 | 0.595 | 2.057 |
| 60d | strict_vwap_agrees | punitive_40bps | base | 0.002 | 6 | 0.005 | 37 | 0.029 | 0.005 | 0.005 | 3.307 | 0.703 | 5.390 |
| 60d | strict_vwap_agrees | punitive_40bps | conservative | 0.002 | 4 | 0.004 | 37 | 0.022 | 0.004 | 0.004 | 3.307 | 0.703 | 5.390 |
| 60d | strict_vwap_agrees | punitive_40bps | prop_strict | 0.003 | 4 | 0.004 | 37 | 0.036 | 0.007 | 0.007 | 3.307 | 0.703 | 5.390 |

## Rolling Validation Summary
| window_days | rule | scenario | config | windows | pass_rate | negative_windows | median_return_pct | worst_return_pct | worst_dd_pct | median_pf | min_accepted | median_events_per_day |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 30 | late_us_fade | baseline | base | 5 | 0.600 | 0 | 0.015 | 0.003 | 0.009 | 2.157 | 16 | 0.600 |
| 30 | late_us_fade | baseline | conservative | 5 | 0.800 | 0 | 0.012 | 0.002 | 0.006 | 2.299 | 14 | 0.600 |
| 30 | late_us_fade | nightmare_60bps | base | 5 | 0.400 | 2 | 0.001 | -0.006 | 0.024 | 1.070 | 16 | 0.600 |
| 30 | late_us_fade | nightmare_60bps | conservative | 5 | 0.200 | 2 | 0.003 | -0.004 | 0.015 | 1.231 | 14 | 0.600 |
| 30 | late_us_fade | punitive_40bps | base | 5 | 0.400 | 1 | 0.007 | -0.003 | 0.013 | 1.290 | 16 | 0.600 |
| 30 | late_us_fade | punitive_40bps | conservative | 5 | 0.200 | 1 | 0.006 | -0.002 | 0.010 | 1.500 | 14 | 0.600 |
| 30 | strict_candidates | baseline | base | 5 | 1.000 | 0 | 0.044 | 0.011 | 0.008 | 3.237 | 26 | 1.300 |
| 30 | strict_candidates | baseline | conservative | 5 | 1.000 | 0 | 0.031 | 0.008 | 0.006 | 3.365 | 26 | 1.300 |
| 30 | strict_candidates | nightmare_60bps | base | 5 | 0.000 | 1 | 0.013 | -0.008 | 0.017 | 1.239 | 25 | 1.300 |
| 30 | strict_candidates | nightmare_60bps | conservative | 5 | 0.000 | 1 | 0.009 | -0.006 | 0.014 | 1.210 | 25 | 1.300 |
| 30 | strict_candidates | punitive_40bps | base | 5 | 0.400 | 1 | 0.021 | -0.004 | 0.013 | 1.744 | 26 | 1.300 |
| 30 | strict_candidates | punitive_40bps | conservative | 5 | 0.800 | 1 | 0.017 | -0.001 | 0.008 | 1.886 | 25 | 1.300 |
| 30 | strict_direction_quality | baseline | base | 5 | 0.000 | 0 | 0.017 | 0.005 | 0.002 | 8.026 | 3 | 0.367 |
| 30 | strict_direction_quality | baseline | conservative | 5 | 0.000 | 0 | 0.013 | 0.004 | 0.002 | 8.026 | 3 | 0.367 |
| 30 | strict_direction_quality | nightmare_60bps | base | 5 | 0.000 | 0 | 0.007 | 0.003 | 0.003 | 3.154 | 3 | 0.367 |
| 30 | strict_direction_quality | nightmare_60bps | conservative | 5 | 0.000 | 0 | 0.005 | 0.002 | 0.002 | 3.154 | 3 | 0.367 |
| 30 | strict_direction_quality | punitive_40bps | base | 5 | 0.000 | 0 | 0.011 | 0.003 | 0.002 | 4.726 | 3 | 0.367 |
| 30 | strict_direction_quality | punitive_40bps | conservative | 5 | 0.000 | 0 | 0.008 | 0.002 | 0.002 | 4.726 | 3 | 0.367 |
| 30 | strict_ema_stack_confirmed | baseline | base | 5 | 0.600 | 0 | 0.027 | 0.013 | 0.005 | 5.221 | 7 | 0.567 |
| 30 | strict_ema_stack_confirmed | baseline | conservative | 5 | 0.600 | 0 | 0.020 | 0.010 | 0.003 | 5.221 | 7 | 0.567 |
| 30 | strict_ema_stack_confirmed | nightmare_60bps | base | 5 | 0.400 | 0 | 0.012 | 0.008 | 0.012 | 2.058 | 7 | 0.567 |
| 30 | strict_ema_stack_confirmed | nightmare_60bps | conservative | 5 | 0.600 | 0 | 0.006 | 0.006 | 0.008 | 2.058 | 7 | 0.567 |
| 30 | strict_ema_stack_confirmed | punitive_40bps | base | 5 | 0.600 | 0 | 0.017 | 0.010 | 0.007 | 2.967 | 7 | 0.567 |
| 30 | strict_ema_stack_confirmed | punitive_40bps | conservative | 5 | 0.600 | 0 | 0.013 | 0.007 | 0.005 | 2.967 | 7 | 0.567 |
| 30 | strict_late_us_no_weak_ema | baseline | base | 5 | 0.800 | 0 | 0.037 | 0.014 | 0.005 | 3.994 | 13 | 0.867 |
| 30 | strict_late_us_no_weak_ema | baseline | conservative | 5 | 0.800 | 0 | 0.025 | 0.010 | 0.003 | 3.679 | 13 | 0.867 |
| 30 | strict_late_us_no_weak_ema | nightmare_60bps | base | 5 | 0.200 | 0 | 0.012 | 0.001 | 0.013 | 1.479 | 12 | 0.867 |
| 30 | strict_late_us_no_weak_ema | nightmare_60bps | conservative | 5 | 0.800 | 0 | 0.007 | 0.000 | 0.010 | 1.265 | 12 | 0.867 |
| 30 | strict_late_us_no_weak_ema | punitive_40bps | base | 5 | 0.800 | 0 | 0.018 | 0.003 | 0.008 | 1.940 | 13 | 0.867 |
| 30 | strict_late_us_no_weak_ema | punitive_40bps | conservative | 5 | 0.800 | 0 | 0.013 | 0.005 | 0.007 | 1.941 | 12 | 0.867 |
| 30 | strict_late_us_vwap_agrees | baseline | base | 5 | 0.800 | 0 | 0.035 | 0.011 | 0.005 | 5.409 | 12 | 0.800 |
| 30 | strict_late_us_vwap_agrees | baseline | conservative | 5 | 0.800 | 0 | 0.023 | 0.008 | 0.004 | 4.919 | 12 | 0.800 |
| 30 | strict_late_us_vwap_agrees | nightmare_60bps | base | 5 | 0.000 | 2 | 0.009 | -0.004 | 0.010 | 1.556 | 12 | 0.800 |
| 30 | strict_late_us_vwap_agrees | nightmare_60bps | conservative | 5 | 0.200 | 2 | 0.005 | -0.003 | 0.008 | 1.396 | 12 | 0.800 |
| 30 | strict_late_us_vwap_agrees | punitive_40bps | base | 5 | 0.200 | 0 | 0.018 | 0.001 | 0.008 | 2.403 | 12 | 0.800 |
| 30 | strict_late_us_vwap_agrees | punitive_40bps | conservative | 5 | 0.800 | 0 | 0.011 | 0.001 | 0.006 | 2.160 | 12 | 0.800 |
| 30 | strict_vwap_agrees | baseline | base | 5 | 0.600 | 0 | 0.020 | 0.011 | 0.002 | 6.207 | 9 | 0.500 |
| 30 | strict_vwap_agrees | baseline | conservative | 5 | 0.600 | 0 | 0.015 | 0.008 | 0.002 | 6.207 | 9 | 0.500 |
| 30 | strict_vwap_agrees | nightmare_60bps | base | 5 | 0.400 | 1 | 0.004 | -0.003 | 0.008 | 1.462 | 9 | 0.500 |
| 30 | strict_vwap_agrees | nightmare_60bps | conservative | 5 | 0.600 | 1 | 0.003 | -0.002 | 0.006 | 1.462 | 9 | 0.500 |
| 30 | strict_vwap_agrees | punitive_40bps | base | 5 | 0.600 | 0 | 0.009 | 0.002 | 0.005 | 2.484 | 9 | 0.500 |
| 30 | strict_vwap_agrees | punitive_40bps | conservative | 5 | 0.600 | 0 | 0.007 | 0.001 | 0.004 | 2.484 | 9 | 0.500 |
| 45 | late_us_fade | baseline | base | 3 | 0.333 | 0 | 0.016 | 0.010 | 0.009 | 1.668 | 27 | 0.756 |
| 45 | late_us_fade | baseline | conservative | 3 | 1.000 | 0 | 0.014 | 0.008 | 0.007 | 1.909 | 25 | 0.756 |
| 45 | late_us_fade | nightmare_60bps | base | 3 | 0.000 | 3 | -0.005 | -0.012 | 0.024 | 0.809 | 27 | 0.756 |
| 45 | late_us_fade | nightmare_60bps | conservative | 3 | 0.000 | 3 | -0.003 | -0.004 | 0.017 | 0.886 | 25 | 0.756 |
| 45 | late_us_fade | punitive_40bps | base | 3 | 0.000 | 2 | -0.000 | -0.003 | 0.014 | 0.987 | 27 | 0.756 |
| 45 | late_us_fade | punitive_40bps | conservative | 3 | 0.000 | 0 | 0.002 | 0.001 | 0.011 | 1.108 | 25 | 0.756 |
| 45 | strict_candidates | baseline | base | 3 | 1.000 | 0 | 0.076 | 0.046 | 0.008 | 3.035 | 56 | 1.600 |
| 45 | strict_candidates | baseline | conservative | 3 | 1.000 | 0 | 0.056 | 0.032 | 0.006 | 3.199 | 53 | 1.600 |
| 45 | strict_candidates | nightmare_60bps | base | 3 | 0.000 | 1 | 0.002 | -0.003 | 0.018 | 1.026 | 54 | 1.600 |
| 45 | strict_candidates | nightmare_60bps | conservative | 3 | 0.000 | 1 | 0.004 | -0.003 | 0.014 | 1.105 | 51 | 1.600 |
| 45 | strict_candidates | punitive_40bps | base | 3 | 0.000 | 0 | 0.026 | 0.013 | 0.013 | 1.470 | 56 | 1.600 |
| 45 | strict_candidates | punitive_40bps | conservative | 3 | 1.000 | 0 | 0.024 | 0.011 | 0.008 | 1.681 | 52 | 1.600 |
| 45 | strict_direction_quality | baseline | base | 3 | 0.000 | 0 | 0.025 | 0.016 | 0.002 | 8.026 | 12 | 0.311 |
| 45 | strict_direction_quality | baseline | conservative | 3 | 0.000 | 0 | 0.019 | 0.012 | 0.002 | 8.026 | 12 | 0.311 |
| 45 | strict_direction_quality | nightmare_60bps | base | 3 | 0.000 | 0 | 0.012 | 0.006 | 0.003 | 3.154 | 12 | 0.311 |
| 45 | strict_direction_quality | nightmare_60bps | conservative | 3 | 0.000 | 0 | 0.009 | 0.005 | 0.002 | 3.154 | 12 | 0.311 |
| 45 | strict_direction_quality | punitive_40bps | base | 3 | 0.000 | 0 | 0.016 | 0.010 | 0.002 | 4.726 | 12 | 0.311 |
| 45 | strict_direction_quality | punitive_40bps | conservative | 3 | 0.000 | 0 | 0.012 | 0.007 | 0.002 | 4.726 | 12 | 0.311 |
| 45 | strict_ema_stack_confirmed | baseline | base | 3 | 0.667 | 0 | 0.053 | 0.027 | 0.005 | 5.171 | 19 | 0.756 |
| 45 | strict_ema_stack_confirmed | baseline | conservative | 3 | 0.667 | 0 | 0.038 | 0.020 | 0.003 | 4.691 | 19 | 0.756 |
| 45 | strict_ema_stack_confirmed | nightmare_60bps | base | 3 | 0.333 | 0 | 0.014 | 0.010 | 0.012 | 1.611 | 19 | 0.756 |
| 45 | strict_ema_stack_confirmed | nightmare_60bps | conservative | 3 | 0.667 | 0 | 0.011 | 0.007 | 0.008 | 1.692 | 19 | 0.756 |
| 45 | strict_ema_stack_confirmed | punitive_40bps | base | 3 | 0.667 | 0 | 0.027 | 0.016 | 0.007 | 2.458 | 19 | 0.756 |
| 45 | strict_ema_stack_confirmed | punitive_40bps | conservative | 3 | 0.667 | 0 | 0.020 | 0.012 | 0.005 | 2.476 | 19 | 0.756 |
| 45 | strict_late_us_no_weak_ema | baseline | base | 3 | 1.000 | 0 | 0.072 | 0.040 | 0.005 | 4.286 | 34 | 1.156 |
| 45 | strict_late_us_no_weak_ema | baseline | conservative | 3 | 1.000 | 0 | 0.049 | 0.027 | 0.003 | 4.076 | 33 | 1.156 |
| 45 | strict_late_us_no_weak_ema | nightmare_60bps | base | 3 | 0.000 | 0 | 0.013 | 0.005 | 0.013 | 1.302 | 33 | 1.156 |
| 45 | strict_late_us_no_weak_ema | nightmare_60bps | conservative | 3 | 1.000 | 0 | 0.008 | 0.002 | 0.007 | 1.274 | 32 | 1.156 |
| 45 | strict_late_us_no_weak_ema | punitive_40bps | base | 3 | 0.667 | 0 | 0.030 | 0.014 | 0.008 | 1.854 | 34 | 1.156 |
| 45 | strict_late_us_no_weak_ema | punitive_40bps | conservative | 3 | 1.000 | 0 | 0.022 | 0.011 | 0.005 | 1.964 | 32 | 1.156 |
| 45 | strict_late_us_vwap_agrees | baseline | base | 3 | 1.000 | 0 | 0.058 | 0.038 | 0.004 | 5.293 | 33 | 0.844 |
| 45 | strict_late_us_vwap_agrees | baseline | conservative | 3 | 1.000 | 0 | 0.041 | 0.026 | 0.003 | 5.018 | 32 | 0.844 |
| 45 | strict_late_us_vwap_agrees | nightmare_60bps | base | 3 | 0.000 | 0 | 0.014 | 0.003 | 0.010 | 1.480 | 33 | 0.844 |
| 45 | strict_late_us_vwap_agrees | nightmare_60bps | conservative | 3 | 0.000 | 0 | 0.008 | 0.000 | 0.008 | 1.382 | 32 | 0.844 |
| 45 | strict_late_us_vwap_agrees | punitive_40bps | base | 3 | 0.000 | 0 | 0.029 | 0.015 | 0.008 | 2.332 | 33 | 0.844 |
| 45 | strict_late_us_vwap_agrees | punitive_40bps | conservative | 3 | 1.000 | 0 | 0.019 | 0.009 | 0.006 | 2.189 | 32 | 0.844 |
| 45 | strict_vwap_agrees | baseline | base | 3 | 1.000 | 0 | 0.036 | 0.023 | 0.002 | 5.993 | 20 | 0.556 |
| 45 | strict_vwap_agrees | baseline | conservative | 3 | 1.000 | 0 | 0.027 | 0.017 | 0.002 | 5.993 | 20 | 0.556 |
| 45 | strict_vwap_agrees | nightmare_60bps | base | 3 | 0.333 | 0 | 0.009 | 0.005 | 0.008 | 1.691 | 20 | 0.556 |
| 45 | strict_vwap_agrees | nightmare_60bps | conservative | 3 | 1.000 | 0 | 0.007 | 0.004 | 0.006 | 1.691 | 20 | 0.556 |
| 45 | strict_vwap_agrees | punitive_40bps | base | 3 | 1.000 | 0 | 0.018 | 0.011 | 0.005 | 2.795 | 20 | 0.556 |
| 45 | strict_vwap_agrees | punitive_40bps | conservative | 3 | 1.000 | 0 | 0.014 | 0.008 | 0.004 | 2.795 | 20 | 0.556 |

## Rolling Failure Diagnostics
| scenario | window_days | feature | value | events | failed_events | failed_window_share | failed_avg_r | passed_avg_r | failed_pf | passed_pf | failed_win_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| punitive_40bps | 30 | atr_pct_bucket | high | 16 | 12 | 0.750 | 1.249 | 1.249 | 19.247 | 19.247 | 0.750 |
| punitive_40bps | 30 | symbol | WLDUSDT | 21 | 15 | 0.714 | 1.030 | 0.723 | 14.436 | 5.665 | 0.733 |
| punitive_40bps | 30 | entry_hour_utc | 23 | 14 | 10 | 0.714 | 1.097 | 0.287 | 8.097 | 1.429 | 0.900 |
| punitive_40bps | 30 | symbol | NEARUSDT | 20 | 12 | 0.600 | -0.144 | 0.136 | 0.664 | 1.360 | 0.583 |
| punitive_40bps | 30 | symbol | HYPEUSDT | 22 | 13 | 0.591 | -0.475 | 0.029 | 0.361 | 1.042 | 0.154 |
| punitive_40bps | 30 | volume_bucket | low | 20 | 11 | 0.550 | -0.195 | 0.082 | 0.550 | 1.198 | 0.364 |
| punitive_40bps | 30 | symbol | BNBUSDT | 11 | 6 | 0.545 | -0.436 | 0.479 | 0.494 | 2.394 | 0.333 |
| punitive_40bps | 30 | symbol | BTCUSDT | 13 | 7 | 0.538 | 0.268 | 0.383 | 3.095 | 3.099 | 0.571 |
| punitive_40bps | 30 | exit_reason | stop | 41 | 22 | 0.537 | -1.472 | -1.456 | 0.000 | 0.000 | 0.000 |
| punitive_40bps | 30 | session_vwap_extension | normal | 60 | 32 | 0.533 | 0.092 | 0.337 | 1.217 | 2.118 | 0.531 |
| punitive_40bps | 30 | shock_alignment | aligned_shock | 48 | 25 | 0.521 | -0.110 | 0.408 | 0.793 | 2.398 | 0.600 |
| punitive_40bps | 30 | entry_hour_utc | 22 | 25 | 13 | 0.520 | -0.773 | -0.065 | 0.024 | 0.885 | 0.154 |
| punitive_40bps | 30 | global_ema_state | bearish | 33 | 17 | 0.515 | 0.149 | 0.853 | 1.413 | 18.282 | 0.647 |
| punitive_40bps | 30 | entry_hour_utc | 21 | 37 | 19 | 0.514 | 0.105 | 0.176 | 1.320 | 1.506 | 0.526 |
| punitive_40bps | 30 | local_ema_state | mixed | 127 | 65 | 0.512 | 0.096 | 0.216 | 1.243 | 1.621 | 0.538 |
| punitive_40bps | 30 | rsi_bucket | bearish_mid | 59 | 30 | 0.508 | -0.026 | 0.334 | 0.937 | 2.021 | 0.533 |
| punitive_40bps | 30 | vwap_direction_agreement | agrees | 75 | 38 | 0.507 | 0.217 | 0.513 | 1.860 | 4.259 | 0.684 |
| punitive_40bps | 30 | compression_state | expanded | 44 | 22 | 0.500 | 0.234 | 0.605 | 1.442 | 2.786 | 0.636 |
| punitive_40bps | 30 | symbol | DOGEUSDT | 22 | 11 | 0.500 | -0.341 | 0.856 | 0.420 | 287.034 | 0.364 |
| punitive_40bps | 30 | local_ema_state | bearish | 16 | 8 | 0.500 | -0.092 | 0.734 | 0.860 | 8.439 | 0.625 |

## Review Packet
| review_bucket | rows | symbols | avg_outcome_r | worst_outcome_r |
| --- | --- | --- | --- | --- |
| clean_winner | 12 | 8 | 1.935 | 1.895 |
| high_mae_winner | 7 | 6 | 0.995 | 0.031 |
| low_return_baseline | 12 | 8 | 0.603 | -0.589 |
| nightmare_failed_loser | 12 | 7 | -1.263 | -1.516 |
| punitive_failed_loser | 12 | 7 | -1.657 | -2.424 |
| target_too_short_winner | 12 | 8 | 1.472 | 0.718 |

## Saved Manual Review Audit
| setup_name | session | reviewed | good | bad | skip | unlabeled | mentions_against_trend | mentions_confirmation | mentions_consolidation | mentions_target |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| late_us_short_bull_flush_ce | late_us | 15 | 7 | 6 | 1 | 1 | 7 | 7 | 1 | 2 |
| ny_long_neutral_reversal_ce | ny | 15 | 10 | 3 | 2 | 0 | 4 | 3 | 2 | 1 |
| london_long_middle_local_retest | london | 4 | 3 | 1 | 0 | 0 | 1 | 0 | 0 | 0 |

## Frequency Expansion Matrix
| window | variant | scenario | candidates | accepted | symbols | events_per_symbol_week | gross_return_pct | max_dd_pct | profit_factor | win_rate | frequency_verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 30d | all_foundation_physical | baseline | 238 | 173 | 14 | 4.021 | 0.077 | 0.019 | 2.028 | 0.584 | candidate_frequency_improves |
| 30d | strict_current | baseline | 87 | 75 | 14 | 1.470 | 0.076 | 0.006 | 4.101 | 0.720 | candidate_frequency_improves |
| 30d | strict_late_us_no_mixed_ema | baseline | 56 | 49 | 14 | 0.946 | 0.055 | 0.003 | 5.162 | 0.755 | quality_ok_frequency_sparse |
| 30d | strict_ema_not_mixed | baseline | 47 | 42 | 14 | 0.794 | 0.049 | 0.005 | 4.909 | 0.762 | quality_ok_frequency_sparse |
| 30d | strict_no_countertrend | baseline | 48 | 44 | 13 | 0.873 | 0.046 | 0.007 | 4.232 | 0.727 | quality_ok_frequency_sparse |
| 30d | ny_london_plus_non_strict_confirmed | baseline | 151 | 121 | 14 | 2.551 | 0.046 | 0.017 | 1.895 | 0.562 | candidate_frequency_improves |
| 30d | strict_no_late_us | baseline | 34 | 32 | 10 | 0.731 | 0.043 | 0.003 | 8.702 | 0.812 | quality_ok_frequency_sparse |
| 30d | strict_late_us_bearish_ema | baseline | 34 | 32 | 10 | 0.731 | 0.043 | 0.003 | 8.702 | 0.812 | quality_ok_frequency_sparse |
| 30d | strict_current | punitive_40bps | 87 | 74 | 14 | 1.470 | 0.034 | 0.008 | 1.974 | 0.662 | candidate_frequency_improves |
| 30d | strict_late_us_no_mixed_ema | punitive_40bps | 56 | 49 | 14 | 0.946 | 0.025 | 0.006 | 2.161 | 0.653 | quality_ok_frequency_sparse |
| 30d | strict_no_late_us | punitive_40bps | 34 | 32 | 10 | 0.731 | 0.024 | 0.005 | 3.712 | 0.688 | quality_ok_frequency_sparse |
| 30d | strict_late_us_bearish_ema | punitive_40bps | 34 | 32 | 10 | 0.731 | 0.024 | 0.005 | 3.712 | 0.688 | quality_ok_frequency_sparse |
| 30d | strict_no_countertrend | punitive_40bps | 48 | 43 | 13 | 0.873 | 0.022 | 0.008 | 2.160 | 0.628 | quality_ok_frequency_sparse |
| 30d | strict_ema_not_mixed | punitive_40bps | 47 | 39 | 14 | 0.794 | 0.017 | 0.010 | 1.871 | 0.641 | quality_ok_frequency_sparse |
| 30d | all_foundation_physical | punitive_40bps | 238 | 145 | 14 | 4.021 | -0.004 | 0.027 | 0.952 | 0.469 | reject_more_trades_break_edge |
| 30d | ny_london_plus_non_strict_confirmed | punitive_40bps | 151 | 111 | 14 | 2.551 | -0.007 | 0.025 | 0.895 | 0.450 | reject_more_trades_break_edge |
| 60d | strict_current | baseline | 113 | 101 | 14 | 0.953 | 0.085 | 0.006 | 3.233 | 0.673 | quality_ok_frequency_sparse |
| 60d | all_foundation_physical | baseline | 378 | 274 | 14 | 3.188 | 0.078 | 0.019 | 1.590 | 0.544 | candidate_frequency_improves |
| 60d | strict_late_us_no_mixed_ema | baseline | 71 | 64 | 13 | 0.599 | 0.067 | 0.004 | 4.325 | 0.719 | quality_ok_frequency_sparse |
| 60d | strict_ema_not_mixed | baseline | 56 | 50 | 14 | 0.472 | 0.057 | 0.004 | 4.780 | 0.740 | quality_ok_frequency_sparse |
| 60d | strict_no_countertrend | baseline | 60 | 56 | 13 | 0.545 | 0.052 | 0.007 | 3.562 | 0.714 | quality_ok_frequency_sparse |
| 60d | strict_late_us_bearish_ema | baseline | 44 | 42 | 12 | 0.433 | 0.050 | 0.003 | 6.001 | 0.786 | quality_ok_frequency_sparse |
| 60d | strict_no_late_us | baseline | 43 | 41 | 12 | 0.423 | 0.049 | 0.003 | 5.932 | 0.780 | quality_ok_frequency_sparse |
| 60d | ny_london_plus_non_strict_confirmed | baseline | 244 | 203 | 14 | 2.058 | 0.048 | 0.017 | 1.491 | 0.522 | candidate_frequency_improves |
| 60d | strict_current | punitive_40bps | 113 | 99 | 14 | 0.953 | 0.034 | 0.008 | 1.656 | 0.616 | quality_ok_frequency_sparse |
| 60d | strict_late_us_no_mixed_ema | punitive_40bps | 71 | 63 | 13 | 0.599 | 0.030 | 0.006 | 2.024 | 0.635 | quality_ok_frequency_sparse |
| 60d | strict_ema_not_mixed | punitive_40bps | 56 | 49 | 14 | 0.472 | 0.028 | 0.006 | 2.264 | 0.653 | quality_ok_frequency_sparse |
| 60d | strict_late_us_bearish_ema | punitive_40bps | 44 | 42 | 12 | 0.433 | 0.024 | 0.005 | 2.445 | 0.667 | quality_ok_frequency_sparse |
| 60d | strict_no_late_us | punitive_40bps | 43 | 41 | 12 | 0.423 | 0.023 | 0.005 | 2.409 | 0.659 | quality_ok_frequency_sparse |
| 60d | strict_no_countertrend | punitive_40bps | 60 | 55 | 13 | 0.545 | 0.020 | 0.008 | 1.703 | 0.618 | quality_ok_frequency_sparse |
| 60d | all_foundation_physical | punitive_40bps | 378 | 235 | 14 | 3.188 | -0.035 | 0.051 | 0.782 | 0.434 | reject_more_trades_break_edge |
| 60d | ny_london_plus_non_strict_confirmed | punitive_40bps | 244 | 181 | 14 | 2.058 | -0.040 | 0.060 | 0.679 | 0.398 | reject_more_trades_break_edge |

## Direction Audit
| scope | feature | value | events | events_per_symbol_week | avg_r | profit_factor | win_rate | direction_accuracy | bad_direction_rate | bad_entry_rate | stop_rate | median_mfe_r | median_mae_r |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| strict | direction_stack | neutral/bear/neutral | 7 | 0.241 | 0.826 | 25.769 | 0.857 | 0.714 | 0.143 | 0.000 | 0.000 | 1.765 | -0.474 |
| strict | direction_stack | neutral/bear/bull | 5 | 1.092 | 0.754 | 4.428 | 0.800 | 0.800 | 0.200 | 0.200 | 0.200 | 1.375 | -0.154 |
| strict | direction_stack | bull/bull/bull | 38 | 0.352 | 0.668 | 3.969 | 0.711 | 0.605 | 0.132 | 0.158 | 0.158 | 1.515 | -0.315 |
| strict | direction_stack | bull/neutral/bull | 8 | 0.148 | 0.571 | 2.420 | 0.625 | 0.500 | 0.250 | 0.500 | 0.375 | 1.475 | -1.003 |
| strict | direction_stack | bull/bull/neutral | 19 | 0.208 | 0.433 | 3.349 | 0.684 | 0.421 | 0.316 | 0.105 | 0.105 | 0.824 | -0.300 |
| strict | direction_stack | bull/neutral/bear | 5 | 0.167 | 0.267 | 1.870 | 0.600 | 0.800 | 0.200 | 0.200 | 0.200 | 1.068 | -0.424 |
| strict | mtf_mode | trend_aligned | 14 | 0.386 | 0.752 | 6.954 | 0.857 | 0.571 | 0.071 | 0.071 | 0.071 | 1.448 | -0.121 |
| strict | mtf_mode | range_or_transition | 46 | 0.419 | 0.676 | 3.642 | 0.696 | 0.696 | 0.152 | 0.217 | 0.196 | 1.605 | -0.517 |
| strict | mtf_mode | countertrend | 53 | 0.456 | 0.429 | 2.555 | 0.604 | 0.509 | 0.245 | 0.189 | 0.189 | 1.008 | -0.487 |
| strict | structure_confirmation | mtf_and_local | 14 | 0.386 | 0.752 | 6.954 | 0.857 | 0.571 | 0.071 | 0.071 | 0.071 | 1.448 | -0.121 |
| strict | structure_confirmation | unconfirmed | 39 | 0.361 | 0.559 | 3.167 | 0.641 | 0.564 | 0.256 | 0.179 | 0.179 | 1.347 | -0.421 |
| strict | structure_confirmation | range_unconfirmed | 26 | 0.268 | 0.549 | 2.846 | 0.654 | 0.615 | 0.154 | 0.269 | 0.231 | 1.605 | -0.626 |
| strict | structure_confirmation | local_only | 34 | 0.313 | 0.520 | 3.065 | 0.647 | 0.618 | 0.176 | 0.176 | 0.176 | 1.166 | -0.485 |
| strict | ema_stack | bearish/bearish/mixed | 9 | 0.269 | 1.350 | inf | 1.000 | 0.889 | 0.111 | 0.000 | 0.000 | 1.771 | -0.157 |
| strict | ema_stack | mixed/bullish/bullish | 14 | 0.386 | 0.752 | 6.954 | 0.857 | 0.571 | 0.071 | 0.071 | 0.071 | 1.448 | -0.121 |
| strict | ema_stack | bullish/bullish/bullish | 26 | 0.303 | 0.665 | 3.238 | 0.654 | 0.692 | 0.077 | 0.231 | 0.231 | 1.658 | -0.548 |
| strict | ema_stack | bullish/bullish/mixed | 43 | 0.364 | 0.255 | 1.796 | 0.558 | 0.395 | 0.372 | 0.256 | 0.233 | 0.672 | -0.477 |
| strict | session_vwap_state | below | 24 | 0.263 | 0.620 | 4.363 | 0.667 | 0.667 | 0.167 | 0.083 | 0.083 | 1.150 | -0.423 |
| strict | session_vwap_state | above | 83 | 0.757 | 0.573 | 3.070 | 0.675 | 0.590 | 0.193 | 0.229 | 0.217 | 1.375 | -0.463 |
| strict | session_vwap_state | near | 6 | 0.132 | 0.315 | 3.508 | 0.667 | 0.333 | 0.167 | 0.000 | 0.000 | 0.894 | -0.650 |
| strict | session_vwap_extension | normal | 30 | 0.296 | 0.693 | 4.440 | 0.700 | 0.633 | 0.200 | 0.133 | 0.133 | 1.166 | -0.476 |
| strict | session_vwap_extension | extended | 47 | 0.433 | 0.574 | 3.495 | 0.702 | 0.574 | 0.191 | 0.149 | 0.149 | 1.500 | -0.296 |
| strict | session_vwap_extension | stretched | 36 | 0.365 | 0.460 | 2.467 | 0.611 | 0.583 | 0.167 | 0.278 | 0.250 | 1.237 | -0.475 |
| strict | vwap_direction_agreement | agrees | 38 | 0.414 | 0.729 | 7.624 | 0.816 | 0.605 | 0.184 | 0.053 | 0.053 | 1.223 | -0.196 |
| strict | vwap_direction_agreement | opposes | 69 | 0.584 | 0.503 | 2.496 | 0.594 | 0.609 | 0.188 | 0.275 | 0.261 | 1.445 | -0.570 |
| strict | vwap_direction_agreement | near_vwap | 6 | 0.132 | 0.315 | 3.508 | 0.667 | 0.333 | 0.167 | 0.000 | 0.000 | 0.894 | -0.650 |
| strict | shock_alignment | opposing_shock | 15 | 0.207 | 1.073 | 6.288 | 0.733 | 0.800 | 0.000 | 0.133 | 0.133 | 2.497 | -0.587 |
| strict | shock_alignment | aligned_shock | 25 | 0.354 | 0.583 | 3.431 | 0.720 | 0.600 | 0.200 | 0.200 | 0.200 | 1.275 | -0.203 |
| strict | shock_alignment | no_shock | 73 | 0.618 | 0.461 | 2.762 | 0.644 | 0.548 | 0.219 | 0.192 | 0.178 | 1.068 | -0.454 |
| strict | compression_state | expanded | 25 | 0.232 | 0.706 | 4.018 | 0.680 | 0.760 | 0.160 | 0.160 | 0.160 | 1.683 | -0.177 |
| strict | compression_state | normal | 88 | 0.745 | 0.531 | 3.093 | 0.670 | 0.545 | 0.193 | 0.193 | 0.182 | 1.114 | -0.482 |
| strict | setup_name | ny_long_neutral_reversal_ce | 29 | 0.302 | 0.865 | 6.151 | 0.759 | 0.793 | 0.069 | 0.103 | 0.103 | 1.856 | -0.527 |
| strict | setup_name | london_long_middle_local_retest | 13 | 0.359 | 0.736 | 6.413 | 0.846 | 0.538 | 0.077 | 0.077 | 0.077 | 1.387 | -0.125 |
| strict | setup_name | late_us_short_bull_flush_ce | 70 | 0.592 | 0.410 | 2.335 | 0.600 | 0.514 | 0.257 | 0.243 | 0.229 | 1.025 | -0.482 |

## Concentration
| dimension | value | events | total_r | share_of_total_r | avg_r | profit_factor | win_rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| session_utc | ny | 28 | 9.101 | 0.397 | 0.325 | 2.074 | 0.643 |
| session_utc | late_us | 58 | 7.826 | 0.342 | 0.135 | 1.327 | 0.586 |
| session_utc | london | 13 | 5.984 | 0.261 | 0.460 | 3.388 | 0.692 |
| setup_name | ny_long_neutral_reversal_ce | 28 | 9.101 | 0.397 | 0.325 | 2.074 | 0.643 |
| setup_name | late_us_short_bull_flush_ce | 58 | 7.826 | 0.342 | 0.135 | 1.327 | 0.586 |
| setup_name | london_long_middle_local_retest | 13 | 5.984 | 0.261 | 0.460 | 3.388 | 0.692 |
| symbol | WLDUSDT | 7 | 5.506 | 0.240 | 0.787 | 10.142 | 0.714 |
| symbol | XRPUSDT | 11 | 4.406 | 0.192 | 0.401 | 2.237 | 0.727 |
| symbol | ETHUSDT | 13 | 4.077 | 0.178 | 0.314 | 1.786 | 0.769 |
| symbol | LINKUSDT | 7 | 2.880 | 0.126 | 0.411 | 3.228 | 0.714 |
| symbol | 1000PEPEUSDT | 3 | 2.852 | 0.124 | 0.951 | inf | 1.000 |
| symbol | AAVEUSDT | 10 | 2.360 | 0.103 | 0.236 | 1.848 | 0.400 |
| symbol | DOGEUSDT | 9 | 2.099 | 0.092 | 0.233 | 1.646 | 0.556 |
| symbol | NEARUSDT | 8 | 1.783 | 0.078 | 0.223 | 1.904 | 0.625 |

## Frequency By Symbol
| symbol | events | events_per_day | events_per_week | avg_r | profit_factor | win_rate | median_duration_h | median_mfe_r | p75_mfe_r | median_mae_r | strict_events |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BNBUSDT | 38 | 0.641 | 4.486 | 0.137 | 1.394 | 0.553 | 6.000 | 0.794 | 1.283 | -0.554 | 9 |
| XRPUSDT | 37 | 0.624 | 4.368 | 0.368 | 2.500 | 0.568 | 6.000 | 1.163 | 2.000 | -0.485 | 12 |
| ETHUSDT | 36 | 0.607 | 4.250 | 0.577 | 4.030 | 0.667 | 6.000 | 1.112 | 2.034 | -0.265 | 14 |
| DOGEUSDT | 34 | 0.573 | 4.014 | 0.291 | 1.857 | 0.559 | 6.000 | 0.836 | 1.718 | -0.452 | 11 |
| LINKUSDT | 32 | 0.540 | 3.778 | 0.097 | 1.261 | 0.500 | 6.000 | 0.813 | 1.592 | -0.581 | 8 |
| BTCUSDT | 31 | 0.523 | 3.660 | 0.345 | 2.361 | 0.613 | 6.000 | 1.044 | 1.448 | -0.300 | 8 |
| AAVEUSDT | 31 | 0.523 | 3.660 | 0.245 | 1.857 | 0.581 | 6.000 | 0.765 | 1.269 | -0.506 | 10 |
| 1000PEPEUSDT | 26 | 0.439 | 3.070 | 0.304 | 2.246 | 0.577 | 6.000 | 0.833 | 1.504 | -0.492 | 5 |
| NEARUSDT | 26 | 0.439 | 3.070 | 0.022 | 1.056 | 0.385 | 6.000 | 0.610 | 1.509 | -0.748 | 9 |
| SOLUSDT | 23 | 0.388 | 2.715 | -0.049 | 0.887 | 0.478 | 6.000 | 0.874 | 1.561 | -0.735 | 7 |
| HYPEUSDT | 22 | 0.371 | 2.597 | 0.192 | 1.555 | 0.545 | 6.000 | 0.865 | 1.358 | -0.434 | 8 |
| SUIUSDT | 16 | 0.270 | 1.889 | -0.086 | 0.748 | 0.500 | 6.000 | 0.945 | 1.270 | -0.527 | 3 |
| AVAXUSDT | 15 | 0.253 | 1.771 | -0.032 | 0.893 | 0.467 | 6.000 | 1.071 | 1.489 | -0.714 | 2 |
| WLDUSDT | 11 | 0.186 | 1.299 | 0.787 | 5.879 | 0.636 | 6.000 | 1.304 | 2.552 | -0.468 | 7 |

## Setup Summary
| setup_name | mtf_mode | events | events_per_day | events_per_week | avg_r | profit_factor | win_rate | median_duration_h | median_mfe_r | p75_mfe_r | median_mae_r | strict_events |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| london_long_middle_local_next_open | conflict | 2 | 0.034 | 0.236 | 1.018 | inf | 1.000 | 3.375 | 5.180 | 7.510 | -0.307 | 0 |
| london_long_middle_local_retest | conflict | 5 | 0.084 | 0.590 | 1.008 | inf | 1.000 | 6.000 | 1.473 | 2.902 | -0.235 | 0 |
| london_long_middle_local_next_open | trend_aligned | 1 | 0.017 | 0.118 | 0.956 | inf | 1.000 | 6.000 | 1.508 | 1.508 | -0.117 | 1 |
| london_long_middle_local_retest | trend_aligned | 13 | 0.219 | 1.535 | 0.736 | 6.413 | 0.846 | 6.000 | 1.387 | 2.872 | -0.125 | 13 |
| london_long_middle_local_next_open | range_or_transition | 5 | 0.084 | 0.590 | 0.668 | 4.112 | 0.800 | 4.250 | 1.071 | 2.084 | -0.449 | 0 |
| late_us_short_bull_flush_ce | countertrend | 53 | 0.894 | 6.257 | 0.429 | 2.555 | 0.604 | 6.000 | 1.008 | 1.720 | -0.487 | 53 |
| late_us_short_bull_flush_ce | range_or_transition | 17 | 0.287 | 2.007 | 0.352 | 1.869 | 0.588 | 4.250 | 1.060 | 2.154 | -0.477 | 17 |
| london_long_middle_local_retest | range_or_transition | 18 | 0.304 | 2.125 | 0.269 | 1.998 | 0.667 | 6.000 | 0.907 | 1.322 | -0.441 | 0 |
| ny_long_neutral_reversal_ce | range_or_transition | 199 | 3.356 | 23.494 | 0.199 | 1.668 | 0.497 | 6.000 | 0.877 | 1.562 | -0.534 | 29 |
| late_us_short_bearish_trend_ce | range_or_transition | 46 | 0.776 | 5.431 | 0.038 | 1.129 | 0.543 | 6.000 | 0.586 | 1.152 | -0.409 | 0 |
| late_us_short_bull_flush_ce | conflict | 8 | 0.135 | 0.944 | -0.298 | 0.569 | 0.375 | 3.625 | 1.115 | 1.737 | -1.948 | 0 |
| london_long_middle_local_retest | pullback_in_uptrend | 11 | 0.186 | 1.299 | -0.388 | 0.445 | 0.364 | 2.750 | 0.905 | 1.441 | -1.605 | 0 |

## Management Comparison
| scope | target_model | management_model | events | avg_r | profit_factor | win_rate | target_rate | stop_rate | expiry_rate | breakeven_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| all | fixed_2r | be_after_half_target | 378 | 0.259 | 2.006 | 0.516 | 0.164 | 0.167 | 0.556 | 0.114 |
| all | fixed_2r | partial_1r_be_after_half_target | 382 | 0.241 | 1.969 | 0.628 | 0.165 | 0.168 | 0.552 | 0.115 |
| all | fixed_2r | hold_target_expiry | 378 | 0.236 | 1.775 | 0.550 | 0.172 | 0.206 | 0.622 | 0.000 |
| all | fixed_1_5r | hold_target_expiry | 392 | 0.222 | 1.761 | 0.569 | 0.263 | 0.199 | 0.538 | 0.000 |
| all | fixed_1_5r | partial_1r_be_after_half_target | 392 | 0.210 | 1.883 | 0.579 | 0.222 | 0.156 | 0.464 | 0.158 |
| all | fixed_1_5r | be_after_half_target | 389 | 0.201 | 1.818 | 0.501 | 0.221 | 0.157 | 0.465 | 0.157 |
| strict | fixed_2r | be_after_half_target | 113 | 0.595 | 3.791 | 0.646 | 0.265 | 0.150 | 0.496 | 0.088 |
| strict | fixed_2r | hold_target_expiry | 113 | 0.569 | 3.285 | 0.673 | 0.265 | 0.177 | 0.558 | 0.000 |
| strict | fixed_1_5r | hold_target_expiry | 116 | 0.512 | 3.142 | 0.690 | 0.431 | 0.172 | 0.397 | 0.000 |
| strict | fixed_2r | partial_1r_be_after_half_target | 113 | 0.490 | 3.365 | 0.735 | 0.265 | 0.150 | 0.496 | 0.088 |
| strict | fixed_1_5r | be_after_half_target | 112 | 0.468 | 3.301 | 0.625 | 0.375 | 0.143 | 0.348 | 0.134 |
| strict | fixed_1_5r | partial_1r_be_after_half_target | 112 | 0.424 | 3.131 | 0.679 | 0.375 | 0.143 | 0.348 | 0.134 |

## Verdict
- Structure improves quality, but strict filtering lowers per-symbol frequency below a few trades per week.
- Frequency has to come from more independent setup families or lower-timeframe entry expansion, not from weakening the MTF filter.
- EMA helps only if the rule matrix improves return/DD without starving trades; otherwise it is descriptive, not a gate.
- Post-target continuation is measured because fixed 2R may be too short for clean London/NY winners.
- Stress scenarios convert extra bps into R, so tight-stop trades are penalized harder.
- Extreme configs vary risk, concurrency, daily lockout, and friction with fixed signal rules.
- Rolling validation is the promotion gate; aggregate 60d performance is not enough.
- Review packet targets failed rolling windows and clean winners; it is not a random sample.
- Saved manual labels mostly flag direction/confirmation defects, especially late-US countertrend shorts.
- Frequency expansion rejects broad non-strict additions when they improve count but break punitive-cost expectancy.
- Direction audit keeps legacy stops fixed and tests whether structure, EMA, VWAP, shock, and compression explain direction quality.
- Legacy stop construction is intentionally unchanged; direction research treats stop quality as a dependent metric, not a tuning knob.
- Current direction-gate candidate: `strict_late_us_no_weak_ema`; it improves weak-window behavior without starving frequency as badly as pure VWAP agreement.
- Pure VWAP agreement is cleaner but too sparse for the main engine; keep it as a review/research slice until more setup families exist.
- Concentration is measured on strict candidates with conservative risk under punitive costs.
