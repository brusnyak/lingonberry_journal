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
| 60d | late_us_fade | 70 | 70 | 14 | 70.000 | 1.181 | 0.590 | 4.671 | 6.000 | 1.000 | 1 | 28.710 | 0.410 | 0.418 | 2.335 | 0.057 | 0.009 | 0.008 | 6.727 | 0.600 | 0.229 | 0.557 | 0.002 | 6 | 1 | 0.005 | 1.025 | 1.766 | 15 | 0.200 | 0.333 |
| 60d | ny_13_range_reversal | 29 | 29 | 12 | 29.000 | 0.489 | 0.285 | 3.914 | 6.000 | 1.000 | 1 | 25.093 | 0.865 | 1.016 | 6.151 | 0.050 | 0.003 | 0.003 | 14.854 | 0.759 | 0.103 | 0.517 | 0.002 | 6 | 1 | 0.005 | 1.856 | 3.579 | 11 | 0.455 | 0.636 |
| 60d | late_us_fade_no_aligned_shock | 59 | 59 | 14 | 59.000 | 0.995 | 0.498 | 4.576 | 6.000 | 1.000 | 1 | 24.996 | 0.424 | 0.381 | 2.390 | 0.050 | 0.009 | 0.008 | 5.857 | 0.593 | 0.220 | 0.542 | 0.002 | 6 | 1 | 0.005 | 1.042 | 1.833 | 14 | 0.214 | 0.357 |
| 60d | ny_13_expanded_or_opposing | 11 | 11 | 7 | 11.000 | 0.186 | 0.186 | 3.295 | 3.000 | 1.000 | 1 | 9.922 | 0.902 | 1.915 | 4.423 | 0.020 | 0.002 | 0.002 | 8.021 | 0.727 | 0.182 | 0.273 | 0.002 | 6 | 1 | 0.005 | 2.683 | 3.591 | 6 | 0.167 | 0.333 |
| 60d | london_trend_aligned | 14 | 13 | 9 | 14.000 | 0.236 | 0.184 | 4.946 | 6.000 | 0.929 | 1 | 9.571 | 0.736 | 0.536 | 6.413 | 0.019 | 0.002 | 0.002 | 9.194 | 0.846 | 0.077 | 0.615 | 0.002 | 6 | 1 | 0.005 | 1.448 | 2.582 | 4 | 0.750 | 0.750 |
| 60d | london_trend_ema_bullish | 14 | 13 | 9 | 14.000 | 0.236 | 0.184 | 4.946 | 6.000 | 0.929 | 1 | 9.571 | 0.736 | 0.536 | 6.413 | 0.019 | 0.002 | 0.002 | 9.194 | 0.846 | 0.077 | 0.615 | 0.002 | 6 | 1 | 0.005 | 1.448 | 2.582 | 4 | 0.750 | 0.750 |
| 60d | london_trend_rsi_not_overbought | 9 | 8 | 8 | 9.000 | 0.152 | 0.133 | 5.250 | 6.000 | 0.889 | 1 | 4.086 | 0.511 | 0.466 | 4.926 | 0.008 | 0.002 | 0.002 | 3.926 | 0.875 | 0.125 | 0.750 | 0.002 | 6 | 1 | 0.005 | 0.900 | 1.508 | 1 | 1.000 | 1.000 |
| first30d | strict_candidates | 26 | 26 | 10 | 26.000 | 0.869 | 0.608 | 4.587 | 6.000 | 1.000 | 1 | 5.387 | 0.207 | 0.142 | 1.596 | 0.011 | 0.006 | 0.005 | 1.694 | 0.538 | 0.269 | 0.615 | 0.002 | 6 | 1 | 0.005 | 1.034 | 1.705 | 3 | 0.667 | 0.667 |
| first30d | ny_13_range_reversal | 9 | 9 | 7 | 9.000 | 0.301 | 0.301 | 4.389 | 6.000 | 1.000 | 1 | 4.124 | 0.458 | 0.993 | 2.409 | 0.008 | 0.003 | 0.003 | 2.441 | 0.667 | 0.222 | 0.667 | 0.002 | 6 | 1 | 0.005 | 1.375 | 1.944 | 1 | 1.000 | 1.000 |
| first30d | all_physical_fixed2_hold | 146 | 112 | 14 | 146.000 | 4.880 | 2.440 | 5.029 | 6.000 | 0.767 | 1 | 3.925 | 0.035 | -0.076 | 1.095 | 0.008 | 0.014 | 0.014 | 0.581 | 0.455 | 0.268 | 0.634 | 0.002 | 6 | 1 | 0.005 | 0.742 | 1.419 | 14 | 0.357 | 0.571 |
| first30d | late_us_fade_no_aligned_shock | 15 | 15 | 6 | 15.000 | 0.501 | 0.585 | 4.667 | 6.000 | 1.000 | 1 | 1.912 | 0.127 | -0.185 | 1.377 | 0.004 | 0.007 | 0.005 | 0.563 | 0.467 | 0.267 | 0.600 | 0.002 | 6 | 1 | 0.005 | 0.672 | 1.506 | 2 | 0.500 | 0.500 |
| first30d | late_us_fade | 17 | 17 | 6 | 17.000 | 0.568 | 0.663 | 4.691 | 6.000 | 1.000 | 1 | 1.263 | 0.074 | -0.185 | 1.207 | 0.003 | 0.008 | 0.006 | 0.312 | 0.471 | 0.294 | 0.588 | 0.002 | 6 | 1 | 0.005 | 0.578 | 1.500 | 2 | 0.500 | 0.500 |
| first30d | london_trend_aligned | 0 | 0 | 0 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.002 | 6 | 1 | 0.005 | 0.000 | 0.000 | 0 | 0.000 | 0.000 |
| first30d | london_trend_ema_bullish | 0 | 0 | 0 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.002 | 6 | 1 | 0.005 | 0.000 | 0.000 | 0 | 0.000 | 0.000 |
| first30d | london_trend_rsi_not_overbought | 0 | 0 | 0 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.002 | 6 | 1 | 0.005 | 0.000 | 0.000 | 0 | 0.000 | 0.000 |
| first30d | ny_13_expanded_or_opposing | 4 | 4 | 3 | 4.000 | 0.134 | 0.312 | 4.562 | 6.000 | 1.000 | 1 | -0.607 | -0.152 | -0.182 | 0.668 | -0.001 | 0.002 | 0.001 | -0.491 | 0.500 | 0.250 | 0.750 | 0.002 | 6 | 1 | 0.005 | 1.116 | 1.987 | 0 | 0.000 | 0.000 |
| 30d | all_physical_fixed2_hold | 238 | 209 | 14 | 238.000 | 8.042 | 4.021 | 4.645 | 6.000 | 0.878 | 1 | 64.600 | 0.309 | 0.163 | 2.123 | 0.129 | 0.023 | 0.023 | 5.733 | 0.569 | 0.167 | 0.636 | 0.002 | 6 | 1 | 0.005 | 0.951 | 1.763 | 51 | 0.412 | 0.529 |
| 30d | strict_candidates | 87 | 86 | 14 | 87.000 | 2.940 | 1.470 | 4.489 | 6.000 | 0.989 | 1 | 57.987 | 0.674 | 0.565 | 4.034 | 0.116 | 0.008 | 0.007 | 15.307 | 0.709 | 0.151 | 0.535 | 0.002 | 6 | 1 | 0.005 | 1.387 | 2.189 | 27 | 0.333 | 0.481 |

## Cost And Slippage Stress
| window | rule | scenario | candidates | accepted | median_extra_cost_r | gross_return_pct | max_dd_pct | profit_factor | win_rate | return_to_dd |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 30d | late_us_fade | baseline | 53 | 53 | 0.000 | 0.055 | 0.009 | 2.782 | 0.642 | 6.431 |
| 30d | late_us_fade | realistic_10bps | 53 | 52 | 0.084 | 0.047 | 0.009 | 2.480 | 0.635 | 5.026 |
| 30d | late_us_fade | high_22bps | 53 | 52 | 0.184 | 0.036 | 0.011 | 1.991 | 0.635 | 3.309 |
| 30d | late_us_fade | punitive_40bps | 53 | 52 | 0.334 | 0.019 | 0.014 | 1.437 | 0.635 | 1.357 |
| 30d | late_us_fade | nightmare_60bps | 53 | 50 | 0.501 | -0.000 | 0.023 | 0.993 | 0.520 | -0.014 |
| 30d | london_trend_aligned | baseline | 14 | 13 | 0.000 | 0.019 | 0.002 | 6.413 | 0.846 | 9.194 |
| 30d | london_trend_aligned | realistic_10bps | 14 | 13 | 0.049 | 0.017 | 0.002 | 5.657 | 0.846 | 7.938 |
| 30d | london_trend_aligned | high_22bps | 14 | 13 | 0.107 | 0.015 | 0.002 | 4.805 | 0.769 | 6.580 |
| 30d | london_trend_aligned | punitive_40bps | 14 | 13 | 0.195 | 0.012 | 0.002 | 3.388 | 0.692 | 4.795 |
| 30d | london_trend_aligned | nightmare_60bps | 14 | 13 | 0.293 | 0.008 | 0.003 | 2.223 | 0.538 | 2.676 |
| 30d | ny_13_range_reversal | baseline | 20 | 20 | 0.000 | 0.042 | 0.003 | 11.780 | 0.800 | 15.181 |
| 30d | ny_13_range_reversal | realistic_10bps | 20 | 20 | 0.106 | 0.037 | 0.003 | 9.544 | 0.800 | 11.994 |
| 30d | ny_13_range_reversal | high_22bps | 20 | 20 | 0.232 | 0.031 | 0.004 | 7.077 | 0.700 | 8.426 |
| 30d | ny_13_range_reversal | punitive_40bps | 20 | 20 | 0.423 | 0.023 | 0.005 | 4.422 | 0.700 | 4.484 |
| 30d | ny_13_range_reversal | nightmare_60bps | 20 | 20 | 0.634 | 0.013 | 0.008 | 2.487 | 0.600 | 1.762 |
| 30d | strict_candidates | baseline | 87 | 86 | 0.000 | 0.116 | 0.008 | 4.034 | 0.709 | 15.307 |
| 30d | strict_candidates | realistic_10bps | 87 | 85 | 0.082 | 0.102 | 0.008 | 3.541 | 0.706 | 12.252 |
| 30d | strict_candidates | high_22bps | 87 | 85 | 0.180 | 0.082 | 0.009 | 2.819 | 0.671 | 8.955 |
| 30d | strict_candidates | punitive_40bps | 87 | 85 | 0.328 | 0.053 | 0.011 | 1.986 | 0.659 | 5.054 |
| 30d | strict_candidates | nightmare_60bps | 87 | 84 | 0.492 | 0.018 | 0.017 | 1.276 | 0.536 | 1.043 |
| 60d | late_us_fade | baseline | 70 | 70 | 0.000 | 0.057 | 0.009 | 2.335 | 0.600 | 6.727 |
| 60d | late_us_fade | realistic_10bps | 70 | 69 | 0.070 | 0.049 | 0.009 | 2.074 | 0.594 | 5.148 |
| 60d | late_us_fade | high_22bps | 70 | 69 | 0.154 | 0.035 | 0.011 | 1.698 | 0.580 | 3.264 |
| 60d | late_us_fade | punitive_40bps | 70 | 69 | 0.281 | 0.016 | 0.014 | 1.264 | 0.580 | 1.140 |
| 60d | late_us_fade | nightmare_60bps | 70 | 67 | 0.421 | -0.006 | 0.023 | 0.910 | 0.493 | -0.258 |
| 60d | london_trend_aligned | baseline | 14 | 13 | 0.000 | 0.019 | 0.002 | 6.413 | 0.846 | 9.194 |
| 60d | london_trend_aligned | realistic_10bps | 14 | 13 | 0.049 | 0.017 | 0.002 | 5.657 | 0.846 | 7.938 |
| 60d | london_trend_aligned | high_22bps | 14 | 13 | 0.107 | 0.015 | 0.002 | 4.805 | 0.769 | 6.580 |
| 60d | london_trend_aligned | punitive_40bps | 14 | 13 | 0.195 | 0.012 | 0.002 | 3.388 | 0.692 | 4.795 |
| 60d | london_trend_aligned | nightmare_60bps | 14 | 13 | 0.293 | 0.008 | 0.003 | 2.223 | 0.538 | 2.676 |
| 60d | ny_13_range_reversal | baseline | 29 | 29 | 0.000 | 0.050 | 0.003 | 6.151 | 0.759 | 14.854 |
| 60d | ny_13_range_reversal | realistic_10bps | 29 | 29 | 0.096 | 0.043 | 0.004 | 4.859 | 0.759 | 11.509 |
| 60d | ny_13_range_reversal | high_22bps | 29 | 29 | 0.212 | 0.035 | 0.004 | 3.629 | 0.690 | 8.262 |
| 60d | ny_13_range_reversal | punitive_40bps | 29 | 29 | 0.385 | 0.022 | 0.005 | 2.280 | 0.655 | 3.997 |
| 60d | ny_13_range_reversal | nightmare_60bps | 29 | 29 | 0.577 | 0.007 | 0.009 | 1.332 | 0.586 | 0.848 |
| 60d | strict_candidates | baseline | 113 | 112 | 0.000 | 0.127 | 0.008 | 3.251 | 0.670 | 16.729 |
| 60d | strict_candidates | realistic_10bps | 113 | 111 | 0.077 | 0.109 | 0.008 | 2.813 | 0.667 | 13.101 |
| 60d | strict_candidates | high_22bps | 113 | 111 | 0.169 | 0.085 | 0.009 | 2.255 | 0.631 | 9.237 |
| 60d | strict_candidates | punitive_40bps | 113 | 111 | 0.308 | 0.049 | 0.013 | 1.609 | 0.613 | 3.724 |
| 60d | strict_candidates | nightmare_60bps | 113 | 109 | 0.462 | 0.010 | 0.017 | 1.106 | 0.523 | 0.574 |
| first30d | late_us_fade | baseline | 17 | 17 | 0.000 | 0.003 | 0.008 | 1.207 | 0.471 | 0.312 |
| first30d | late_us_fade | realistic_10bps | 17 | 17 | 0.027 | 0.001 | 0.009 | 1.088 | 0.471 | 0.124 |
| first30d | late_us_fade | high_22bps | 17 | 17 | 0.060 | -0.000 | 0.011 | 0.966 | 0.412 | -0.045 |
| first30d | late_us_fade | punitive_40bps | 17 | 17 | 0.110 | -0.003 | 0.013 | 0.820 | 0.412 | -0.228 |
| first30d | late_us_fade | nightmare_60bps | 17 | 17 | 0.165 | -0.006 | 0.015 | 0.693 | 0.412 | -0.370 |
| first30d | london_trend_aligned | baseline | 0 | 0 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| first30d | london_trend_aligned | realistic_10bps | 0 | 0 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| first30d | london_trend_aligned | high_22bps | 0 | 0 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| first30d | london_trend_aligned | punitive_40bps | 0 | 0 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| first30d | london_trend_aligned | nightmare_60bps | 0 | 0 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| first30d | ny_13_range_reversal | baseline | 9 | 9 | 0.000 | 0.008 | 0.003 | 2.409 | 0.667 | 2.441 |
| first30d | ny_13_range_reversal | realistic_10bps | 9 | 9 | 0.096 | 0.006 | 0.004 | 1.867 | 0.667 | 1.577 |
| first30d | ny_13_range_reversal | high_22bps | 9 | 9 | 0.212 | 0.003 | 0.004 | 1.388 | 0.667 | 0.739 |
| first30d | ny_13_range_reversal | punitive_40bps | 9 | 9 | 0.385 | -0.001 | 0.005 | 0.889 | 0.556 | -0.210 |
| first30d | ny_13_range_reversal | nightmare_60bps | 9 | 9 | 0.577 | -0.006 | 0.009 | 0.568 | 0.556 | -0.664 |
| first30d | strict_candidates | baseline | 26 | 26 | 0.000 | 0.011 | 0.006 | 1.596 | 0.538 | 1.694 |
| first30d | strict_candidates | realistic_10bps | 26 | 26 | 0.048 | 0.007 | 0.007 | 1.353 | 0.538 | 1.037 |
| first30d | strict_candidates | high_22bps | 26 | 26 | 0.105 | 0.003 | 0.008 | 1.116 | 0.500 | 0.322 |
| first30d | strict_candidates | punitive_40bps | 26 | 26 | 0.192 | -0.004 | 0.013 | 0.847 | 0.462 | -0.310 |
| first30d | strict_candidates | nightmare_60bps | 26 | 25 | 0.288 | -0.008 | 0.016 | 0.715 | 0.480 | -0.504 |

## Extreme Configuration Matrix
| window | rule | scenario | config | risk_per_trade_pct | max_open_trades | daily_loss_limit_pct | accepted | gross_return_pct | max_dd_pct | daily_max_dd_pct | profit_factor | win_rate | return_to_dd |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 30d | late_us_fade | baseline | aggressive | 0.003 | 8 | 0.010 | 53 | 0.082 | 0.013 | 0.011 | 2.782 | 0.642 | 6.431 |
| 30d | late_us_fade | baseline | base | 0.002 | 6 | 0.005 | 53 | 0.055 | 0.009 | 0.008 | 2.782 | 0.642 | 6.431 |
| 30d | late_us_fade | baseline | micro_risk_tight | 0.001 | 3 | 0.003 | 37 | 0.018 | 0.004 | 0.004 | 2.555 | 0.622 | 4.182 |
| 30d | late_us_fade | baseline | prop_strict | 0.003 | 4 | 0.004 | 42 | 0.059 | 0.011 | 0.009 | 3.059 | 0.667 | 5.528 |
| 30d | late_us_fade | nightmare_60bps | aggressive | 0.003 | 8 | 0.010 | 52 | -0.001 | 0.036 | 0.026 | 0.985 | 0.519 | -0.032 |
| 30d | late_us_fade | nightmare_60bps | base | 0.002 | 6 | 0.005 | 50 | -0.000 | 0.023 | 0.017 | 0.993 | 0.520 | -0.014 |
| 30d | late_us_fade | nightmare_60bps | micro_risk_tight | 0.001 | 3 | 0.003 | 36 | -0.002 | 0.011 | 0.011 | 0.907 | 0.528 | -0.165 |
| 30d | late_us_fade | nightmare_60bps | prop_strict | 0.003 | 4 | 0.004 | 40 | 0.006 | 0.021 | 0.021 | 1.136 | 0.550 | 0.292 |
| 30d | late_us_fade | punitive_40bps | aggressive | 0.003 | 8 | 0.010 | 52 | 0.028 | 0.020 | 0.019 | 1.437 | 0.635 | 1.357 |
| 30d | late_us_fade | punitive_40bps | base | 0.002 | 6 | 0.005 | 52 | 0.019 | 0.014 | 0.013 | 1.437 | 0.635 | 1.357 |
| 30d | late_us_fade | punitive_40bps | micro_risk_tight | 0.001 | 3 | 0.003 | 36 | 0.005 | 0.008 | 0.008 | 1.325 | 0.611 | 0.663 |
| 30d | late_us_fade | punitive_40bps | prop_strict | 0.003 | 4 | 0.004 | 41 | 0.024 | 0.017 | 0.017 | 1.637 | 0.659 | 1.432 |
| 30d | ny_13_range_reversal | baseline | aggressive | 0.003 | 8 | 0.010 | 20 | 0.063 | 0.004 | 0.001 | 11.780 | 0.800 | 15.181 |
| 30d | ny_13_range_reversal | baseline | base | 0.002 | 6 | 0.005 | 20 | 0.042 | 0.003 | 0.001 | 11.780 | 0.800 | 15.181 |
| 30d | ny_13_range_reversal | baseline | micro_risk_tight | 0.001 | 3 | 0.003 | 17 | 0.020 | 0.000 | 0.000 | 23.556 | 0.824 | 59.566 |
| 30d | ny_13_range_reversal | baseline | prop_strict | 0.003 | 4 | 0.004 | 19 | 0.048 | 0.003 | 0.001 | 10.781 | 0.789 | 13.776 |
| 30d | ny_13_range_reversal | nightmare_60bps | aggressive | 0.003 | 8 | 0.010 | 20 | 0.020 | 0.011 | 0.011 | 2.487 | 0.600 | 1.762 |
| 30d | ny_13_range_reversal | nightmare_60bps | base | 0.002 | 6 | 0.005 | 20 | 0.013 | 0.008 | 0.008 | 2.487 | 0.600 | 1.762 |
| 30d | ny_13_range_reversal | nightmare_60bps | micro_risk_tight | 0.001 | 3 | 0.003 | 17 | 0.007 | 0.002 | 0.002 | 3.382 | 0.588 | 3.156 |
| 30d | ny_13_range_reversal | nightmare_60bps | prop_strict | 0.003 | 4 | 0.004 | 18 | 0.017 | 0.005 | 0.005 | 3.420 | 0.611 | 3.206 |
| 30d | ny_13_range_reversal | punitive_40bps | aggressive | 0.003 | 8 | 0.010 | 20 | 0.034 | 0.008 | 0.007 | 4.422 | 0.700 | 4.484 |
| 30d | ny_13_range_reversal | punitive_40bps | base | 0.002 | 6 | 0.005 | 20 | 0.023 | 0.005 | 0.005 | 4.422 | 0.700 | 4.484 |
| 30d | ny_13_range_reversal | punitive_40bps | micro_risk_tight | 0.001 | 3 | 0.003 | 17 | 0.011 | 0.001 | 0.001 | 6.836 | 0.706 | 9.986 |
| 30d | ny_13_range_reversal | punitive_40bps | prop_strict | 0.003 | 4 | 0.004 | 19 | 0.025 | 0.006 | 0.006 | 3.955 | 0.684 | 3.872 |
| 30d | strict_candidates | baseline | aggressive | 0.003 | 8 | 0.010 | 87 | 0.177 | 0.011 | 0.010 | 4.084 | 0.713 | 15.559 |
| 30d | strict_candidates | baseline | base | 0.002 | 6 | 0.005 | 86 | 0.116 | 0.008 | 0.007 | 4.034 | 0.709 | 15.307 |
| 30d | strict_candidates | baseline | micro_risk_tight | 0.001 | 3 | 0.003 | 67 | 0.045 | 0.004 | 0.003 | 4.168 | 0.716 | 11.808 |
| 30d | strict_candidates | baseline | prop_strict | 0.003 | 4 | 0.004 | 74 | 0.129 | 0.009 | 0.006 | 4.394 | 0.730 | 13.593 |
| 30d | strict_candidates | nightmare_60bps | aggressive | 0.003 | 8 | 0.010 | 86 | 0.033 | 0.024 | 0.014 | 1.337 | 0.547 | 1.386 |
| 30d | strict_candidates | nightmare_60bps | base | 0.002 | 6 | 0.005 | 84 | 0.018 | 0.017 | 0.012 | 1.276 | 0.536 | 1.043 |
| 30d | strict_candidates | nightmare_60bps | micro_risk_tight | 0.001 | 3 | 0.003 | 66 | 0.007 | 0.009 | 0.008 | 1.259 | 0.530 | 0.686 |
| 30d | strict_candidates | nightmare_60bps | prop_strict | 0.003 | 4 | 0.004 | 71 | 0.026 | 0.017 | 0.012 | 1.427 | 0.535 | 1.570 |
| 30d | strict_candidates | punitive_40bps | aggressive | 0.003 | 8 | 0.010 | 86 | 0.082 | 0.016 | 0.011 | 2.015 | 0.663 | 5.203 |
| 30d | strict_candidates | punitive_40bps | base | 0.002 | 6 | 0.005 | 85 | 0.053 | 0.011 | 0.007 | 1.986 | 0.659 | 5.054 |
| 30d | strict_candidates | punitive_40bps | micro_risk_tight | 0.001 | 3 | 0.003 | 66 | 0.020 | 0.007 | 0.004 | 1.969 | 0.652 | 3.003 |
| 30d | strict_candidates | punitive_40bps | prop_strict | 0.003 | 4 | 0.004 | 72 | 0.057 | 0.013 | 0.012 | 2.080 | 0.667 | 4.328 |
| 60d | late_us_fade | baseline | aggressive | 0.003 | 8 | 0.010 | 70 | 0.086 | 0.013 | 0.011 | 2.335 | 0.600 | 6.727 |
| 60d | late_us_fade | baseline | base | 0.002 | 6 | 0.005 | 70 | 0.057 | 0.009 | 0.008 | 2.335 | 0.600 | 6.727 |
| 60d | late_us_fade | baseline | micro_risk_tight | 0.001 | 3 | 0.003 | 54 | 0.019 | 0.004 | 0.004 | 2.104 | 0.574 | 4.548 |
| 60d | late_us_fade | baseline | prop_strict | 0.003 | 4 | 0.004 | 59 | 0.063 | 0.011 | 0.009 | 2.429 | 0.610 | 5.883 |
| 60d | late_us_fade | nightmare_60bps | aggressive | 0.003 | 8 | 0.010 | 69 | -0.010 | 0.036 | 0.026 | 0.906 | 0.493 | -0.271 |
| 60d | late_us_fade | nightmare_60bps | base | 0.002 | 6 | 0.005 | 67 | -0.006 | 0.023 | 0.017 | 0.910 | 0.493 | -0.258 |
| 60d | late_us_fade | nightmare_60bps | micro_risk_tight | 0.001 | 3 | 0.003 | 53 | -0.005 | 0.011 | 0.011 | 0.830 | 0.491 | -0.442 |
| 60d | late_us_fade | nightmare_60bps | prop_strict | 0.003 | 4 | 0.004 | 57 | -0.003 | 0.021 | 0.021 | 0.960 | 0.509 | -0.131 |
| 60d | late_us_fade | punitive_40bps | aggressive | 0.003 | 8 | 0.010 | 69 | 0.023 | 0.020 | 0.019 | 1.264 | 0.580 | 1.140 |
| 60d | late_us_fade | punitive_40bps | base | 0.002 | 6 | 0.005 | 69 | 0.016 | 0.014 | 0.013 | 1.264 | 0.580 | 1.140 |
| 60d | late_us_fade | punitive_40bps | micro_risk_tight | 0.001 | 3 | 0.003 | 53 | 0.004 | 0.008 | 0.008 | 1.152 | 0.547 | 0.471 |
| 60d | late_us_fade | punitive_40bps | prop_strict | 0.003 | 4 | 0.004 | 58 | 0.020 | 0.017 | 0.017 | 1.335 | 0.586 | 1.158 |
| 60d | ny_13_range_reversal | baseline | aggressive | 0.003 | 8 | 0.010 | 29 | 0.075 | 0.005 | 0.005 | 6.151 | 0.759 | 14.854 |
| 60d | ny_13_range_reversal | baseline | base | 0.002 | 6 | 0.005 | 29 | 0.050 | 0.003 | 0.003 | 6.151 | 0.759 | 14.854 |
| 60d | ny_13_range_reversal | baseline | micro_risk_tight | 0.001 | 3 | 0.003 | 25 | 0.024 | 0.002 | 0.002 | 7.208 | 0.760 | 13.963 |
| 60d | ny_13_range_reversal | baseline | prop_strict | 0.003 | 4 | 0.004 | 28 | 0.058 | 0.004 | 0.004 | 5.752 | 0.750 | 13.704 |
| 60d | ny_13_range_reversal | nightmare_60bps | aggressive | 0.003 | 8 | 0.010 | 29 | 0.011 | 0.013 | 0.013 | 1.332 | 0.586 | 0.848 |
| 60d | ny_13_range_reversal | nightmare_60bps | base | 0.002 | 6 | 0.005 | 29 | 0.007 | 0.009 | 0.009 | 1.332 | 0.586 | 0.848 |
| 60d | ny_13_range_reversal | nightmare_60bps | micro_risk_tight | 0.001 | 3 | 0.003 | 25 | 0.004 | 0.004 | 0.004 | 1.401 | 0.560 | 0.871 |
| 60d | ny_13_range_reversal | nightmare_60bps | prop_strict | 0.003 | 4 | 0.004 | 27 | 0.010 | 0.011 | 0.011 | 1.414 | 0.593 | 0.906 |
| 60d | ny_13_range_reversal | punitive_40bps | aggressive | 0.003 | 8 | 0.010 | 29 | 0.033 | 0.008 | 0.008 | 2.280 | 0.655 | 3.997 |
| 60d | ny_13_range_reversal | punitive_40bps | base | 0.002 | 6 | 0.005 | 29 | 0.022 | 0.005 | 0.005 | 2.280 | 0.655 | 3.997 |
| 60d | ny_13_range_reversal | punitive_40bps | micro_risk_tight | 0.001 | 3 | 0.003 | 25 | 0.010 | 0.003 | 0.003 | 2.481 | 0.640 | 3.842 |
| 60d | ny_13_range_reversal | punitive_40bps | prop_strict | 0.003 | 4 | 0.004 | 28 | 0.023 | 0.007 | 0.007 | 2.096 | 0.643 | 3.424 |
| 60d | strict_candidates | baseline | aggressive | 0.003 | 8 | 0.010 | 113 | 0.193 | 0.011 | 0.010 | 3.285 | 0.673 | 16.981 |
| 60d | strict_candidates | baseline | base | 0.002 | 6 | 0.005 | 112 | 0.127 | 0.008 | 0.007 | 3.251 | 0.670 | 16.729 |
| 60d | strict_candidates | baseline | micro_risk_tight | 0.001 | 3 | 0.003 | 92 | 0.050 | 0.004 | 0.003 | 3.157 | 0.663 | 13.184 |
| 60d | strict_candidates | baseline | prop_strict | 0.003 | 4 | 0.004 | 100 | 0.144 | 0.009 | 0.006 | 3.377 | 0.680 | 15.192 |
| 60d | strict_candidates | nightmare_60bps | aggressive | 0.003 | 8 | 0.010 | 112 | 0.016 | 0.029 | 0.025 | 1.110 | 0.527 | 0.550 |
| 60d | strict_candidates | nightmare_60bps | base | 0.002 | 6 | 0.005 | 109 | 0.010 | 0.017 | 0.013 | 1.106 | 0.523 | 0.574 |
| 60d | strict_candidates | nightmare_60bps | micro_risk_tight | 0.001 | 3 | 0.003 | 90 | 0.003 | 0.009 | 0.007 | 1.085 | 0.522 | 0.386 |
| 60d | strict_candidates | nightmare_60bps | prop_strict | 0.003 | 4 | 0.004 | 95 | 0.022 | 0.017 | 0.013 | 1.237 | 0.537 | 1.306 |
| 60d | strict_candidates | punitive_40bps | aggressive | 0.003 | 8 | 0.010 | 112 | 0.076 | 0.020 | 0.016 | 1.629 | 0.616 | 3.843 |
| 60d | strict_candidates | punitive_40bps | base | 0.002 | 6 | 0.005 | 111 | 0.049 | 0.013 | 0.011 | 1.609 | 0.613 | 3.724 |
| 60d | strict_candidates | punitive_40bps | micro_risk_tight | 0.001 | 3 | 0.003 | 91 | 0.018 | 0.007 | 0.006 | 1.540 | 0.593 | 2.448 |
| 60d | strict_candidates | punitive_40bps | prop_strict | 0.003 | 4 | 0.004 | 97 | 0.058 | 0.013 | 0.012 | 1.705 | 0.619 | 4.416 |
| first30d | late_us_fade | baseline | aggressive | 0.003 | 8 | 0.010 | 17 | 0.004 | 0.012 | 0.009 | 1.207 | 0.471 | 0.312 |
| first30d | late_us_fade | baseline | base | 0.002 | 6 | 0.005 | 17 | 0.003 | 0.008 | 0.006 | 1.207 | 0.471 | 0.312 |
| first30d | late_us_fade | baseline | micro_risk_tight | 0.001 | 3 | 0.003 | 17 | 0.001 | 0.004 | 0.003 | 1.207 | 0.471 | 0.312 |
| first30d | late_us_fade | baseline | prop_strict | 0.003 | 4 | 0.004 | 17 | 0.003 | 0.010 | 0.007 | 1.207 | 0.471 | 0.312 |
| first30d | late_us_fade | nightmare_60bps | aggressive | 0.003 | 8 | 0.010 | 17 | -0.009 | 0.023 | 0.019 | 0.693 | 0.412 | -0.370 |
| first30d | late_us_fade | nightmare_60bps | base | 0.002 | 6 | 0.005 | 17 | -0.006 | 0.015 | 0.013 | 0.693 | 0.412 | -0.370 |
| first30d | late_us_fade | nightmare_60bps | micro_risk_tight | 0.001 | 3 | 0.003 | 17 | -0.003 | 0.008 | 0.006 | 0.693 | 0.412 | -0.370 |
| first30d | late_us_fade | nightmare_60bps | prop_strict | 0.003 | 4 | 0.004 | 17 | -0.007 | 0.019 | 0.016 | 0.693 | 0.412 | -0.370 |
| first30d | late_us_fade | punitive_40bps | aggressive | 0.003 | 8 | 0.010 | 17 | -0.004 | 0.019 | 0.016 | 0.820 | 0.412 | -0.228 |
| first30d | late_us_fade | punitive_40bps | base | 0.002 | 6 | 0.005 | 17 | -0.003 | 0.013 | 0.010 | 0.820 | 0.412 | -0.228 |
| first30d | late_us_fade | punitive_40bps | micro_risk_tight | 0.001 | 3 | 0.003 | 17 | -0.001 | 0.006 | 0.005 | 0.820 | 0.412 | -0.228 |
| first30d | late_us_fade | punitive_40bps | prop_strict | 0.003 | 4 | 0.004 | 17 | -0.004 | 0.016 | 0.013 | 0.820 | 0.412 | -0.228 |
| first30d | ny_13_range_reversal | baseline | aggressive | 0.003 | 8 | 0.010 | 9 | 0.012 | 0.005 | 0.005 | 2.409 | 0.667 | 2.441 |
| first30d | ny_13_range_reversal | baseline | base | 0.002 | 6 | 0.005 | 9 | 0.008 | 0.003 | 0.003 | 2.409 | 0.667 | 2.441 |
| first30d | ny_13_range_reversal | baseline | micro_risk_tight | 0.001 | 3 | 0.003 | 8 | 0.004 | 0.002 | 0.002 | 2.332 | 0.625 | 2.308 |
| first30d | ny_13_range_reversal | baseline | prop_strict | 0.003 | 4 | 0.004 | 9 | 0.010 | 0.004 | 0.004 | 2.409 | 0.667 | 2.441 |
| first30d | ny_13_range_reversal | nightmare_60bps | aggressive | 0.003 | 8 | 0.010 | 9 | -0.009 | 0.013 | 0.013 | 0.568 | 0.556 | -0.664 |
| first30d | ny_13_range_reversal | nightmare_60bps | base | 0.002 | 6 | 0.005 | 9 | -0.006 | 0.009 | 0.009 | 0.568 | 0.556 | -0.664 |
| first30d | ny_13_range_reversal | nightmare_60bps | micro_risk_tight | 0.001 | 3 | 0.003 | 8 | -0.003 | 0.004 | 0.004 | 0.564 | 0.500 | -0.666 |
| first30d | ny_13_range_reversal | nightmare_60bps | prop_strict | 0.003 | 4 | 0.004 | 9 | -0.007 | 0.011 | 0.011 | 0.568 | 0.556 | -0.664 |
| first30d | ny_13_range_reversal | punitive_40bps | aggressive | 0.003 | 8 | 0.010 | 9 | -0.002 | 0.008 | 0.008 | 0.889 | 0.556 | -0.210 |
| first30d | ny_13_range_reversal | punitive_40bps | base | 0.002 | 6 | 0.005 | 9 | -0.001 | 0.005 | 0.005 | 0.889 | 0.556 | -0.210 |
| first30d | ny_13_range_reversal | punitive_40bps | micro_risk_tight | 0.001 | 3 | 0.003 | 8 | -0.001 | 0.003 | 0.003 | 0.871 | 0.500 | -0.244 |
| first30d | ny_13_range_reversal | punitive_40bps | prop_strict | 0.003 | 4 | 0.004 | 9 | -0.001 | 0.007 | 0.007 | 0.889 | 0.556 | -0.210 |
| first30d | strict_candidates | baseline | aggressive | 0.003 | 8 | 0.010 | 26 | 0.016 | 0.010 | 0.007 | 1.596 | 0.538 | 1.694 |
| first30d | strict_candidates | baseline | base | 0.002 | 6 | 0.005 | 26 | 0.011 | 0.006 | 0.005 | 1.596 | 0.538 | 1.694 |
| first30d | strict_candidates | baseline | micro_risk_tight | 0.001 | 3 | 0.003 | 25 | 0.004 | 0.003 | 0.002 | 1.463 | 0.520 | 1.316 |
| first30d | strict_candidates | baseline | prop_strict | 0.003 | 4 | 0.004 | 26 | 0.013 | 0.008 | 0.006 | 1.596 | 0.538 | 1.694 |
| first30d | strict_candidates | nightmare_60bps | aggressive | 0.003 | 8 | 0.010 | 26 | -0.017 | 0.029 | 0.025 | 0.641 | 0.462 | -0.589 |
| first30d | strict_candidates | nightmare_60bps | base | 0.002 | 6 | 0.005 | 25 | -0.008 | 0.016 | 0.013 | 0.715 | 0.480 | -0.504 |
| first30d | strict_candidates | nightmare_60bps | micro_risk_tight | 0.001 | 3 | 0.003 | 24 | -0.005 | 0.009 | 0.007 | 0.672 | 0.458 | -0.539 |
| first30d | strict_candidates | nightmare_60bps | prop_strict | 0.003 | 4 | 0.004 | 24 | -0.007 | 0.017 | 0.013 | 0.785 | 0.500 | -0.411 |
| first30d | strict_candidates | punitive_40bps | aggressive | 0.003 | 8 | 0.010 | 26 | -0.006 | 0.020 | 0.016 | 0.847 | 0.462 | -0.310 |
| first30d | strict_candidates | punitive_40bps | base | 0.002 | 6 | 0.005 | 26 | -0.004 | 0.013 | 0.011 | 0.847 | 0.462 | -0.310 |
| first30d | strict_candidates | punitive_40bps | micro_risk_tight | 0.001 | 3 | 0.003 | 25 | -0.003 | 0.007 | 0.006 | 0.786 | 0.440 | -0.385 |
| first30d | strict_candidates | punitive_40bps | prop_strict | 0.003 | 4 | 0.004 | 25 | -0.001 | 0.013 | 0.012 | 0.951 | 0.480 | -0.113 |

## Rolling Validation Summary
| window_days | rule | scenario | config | windows | pass_rate | negative_windows | median_return_pct | worst_return_pct | worst_dd_pct | median_pf | min_accepted | median_events_per_day |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 14 | late_us_fade | baseline | base | 7 | 0.286 | 2 | 0.008 | -0.005 | 0.009 | 2.299 | 6 | 0.571 |
| 14 | late_us_fade | baseline | conservative | 7 | 0.286 | 2 | 0.006 | -0.004 | 0.006 | 2.222 | 6 | 0.571 |
| 14 | late_us_fade | baseline | micro_risk_tight | 7 | 0.286 | 2 | 0.004 | -0.003 | 0.004 | 2.222 | 5 | 0.571 |
| 14 | late_us_fade | baseline | prop_strict | 7 | 0.143 | 2 | 0.010 | -0.007 | 0.011 | 2.222 | 6 | 0.571 |
| 14 | late_us_fade | nightmare_60bps | base | 7 | 0.286 | 3 | 0.003 | -0.009 | 0.021 | 1.506 | 6 | 0.571 |
| 14 | late_us_fade | nightmare_60bps | conservative | 7 | 0.143 | 3 | 0.003 | -0.009 | 0.017 | 1.556 | 6 | 0.571 |
| 14 | late_us_fade | nightmare_60bps | micro_risk_tight | 7 | 0.143 | 3 | 0.002 | -0.008 | 0.012 | 1.556 | 5 | 0.571 |
| 14 | late_us_fade | nightmare_60bps | prop_strict | 7 | 0.143 | 3 | 0.005 | -0.017 | 0.022 | 1.556 | 6 | 0.571 |
| 14 | late_us_fade | punitive_40bps | base | 7 | 0.286 | 2 | 0.005 | -0.008 | 0.014 | 1.737 | 6 | 0.571 |
| 14 | late_us_fade | punitive_40bps | conservative | 7 | 0.143 | 2 | 0.003 | -0.006 | 0.011 | 1.737 | 6 | 0.571 |
| 14 | late_us_fade | punitive_40bps | micro_risk_tight | 7 | 0.143 | 3 | 0.002 | -0.004 | 0.008 | 1.737 | 5 | 0.571 |
| 14 | late_us_fade | punitive_40bps | prop_strict | 7 | 0.143 | 2 | 0.006 | -0.010 | 0.017 | 1.737 | 6 | 0.571 |
| 14 | ny_13_range_reversal | baseline | base | 7 | 0.286 | 2 | 0.010 | -0.001 | 0.003 | 4.878 | 1 | 0.500 |
| 14 | ny_13_range_reversal | baseline | conservative | 7 | 0.286 | 2 | 0.007 | -0.001 | 0.003 | 4.878 | 1 | 0.500 |
| 14 | ny_13_range_reversal | baseline | micro_risk_tight | 7 | 0.286 | 2 | 0.005 | -0.001 | 0.002 | 4.696 | 1 | 0.500 |
| 14 | ny_13_range_reversal | baseline | prop_strict | 7 | 0.286 | 2 | 0.012 | -0.002 | 0.004 | 4.878 | 1 | 0.500 |
| 14 | ny_13_range_reversal | nightmare_60bps | base | 7 | 0.000 | 3 | 0.002 | -0.007 | 0.008 | 1.271 | 1 | 0.500 |
| 14 | ny_13_range_reversal | nightmare_60bps | conservative | 7 | 0.286 | 3 | 0.001 | -0.006 | 0.006 | 1.119 | 1 | 0.500 |
| 14 | ny_13_range_reversal | nightmare_60bps | micro_risk_tight | 7 | 0.286 | 3 | 0.001 | -0.004 | 0.004 | 1.262 | 1 | 0.500 |
| 14 | ny_13_range_reversal | nightmare_60bps | prop_strict | 7 | 0.286 | 3 | 0.002 | -0.009 | 0.009 | 1.271 | 1 | 0.500 |
| 14 | ny_13_range_reversal | punitive_40bps | base | 7 | 0.286 | 3 | 0.004 | -0.005 | 0.005 | 1.884 | 1 | 0.500 |
| 14 | ny_13_range_reversal | punitive_40bps | conservative | 7 | 0.286 | 3 | 0.003 | -0.004 | 0.004 | 1.873 | 1 | 0.500 |
| 14 | ny_13_range_reversal | punitive_40bps | micro_risk_tight | 7 | 0.286 | 3 | 0.002 | -0.003 | 0.003 | 1.846 | 1 | 0.500 |
| 14 | ny_13_range_reversal | punitive_40bps | prop_strict | 7 | 0.286 | 3 | 0.005 | -0.007 | 0.007 | 1.873 | 1 | 0.500 |
| 14 | strict_candidates | baseline | base | 7 | 0.857 | 0 | 0.028 | 0.000 | 0.008 | 3.329 | 10 | 1.429 |
| 14 | strict_candidates | baseline | conservative | 7 | 0.857 | 0 | 0.022 | 0.000 | 0.006 | 3.096 | 10 | 1.429 |
| 14 | strict_candidates | baseline | micro_risk_tight | 7 | 0.857 | 1 | 0.014 | -0.000 | 0.004 | 2.894 | 10 | 1.429 |
| 14 | strict_candidates | baseline | prop_strict | 7 | 0.857 | 0 | 0.037 | 0.000 | 0.009 | 3.411 | 10 | 1.429 |
| 14 | strict_candidates | nightmare_60bps | base | 7 | 0.143 | 3 | 0.007 | -0.013 | 0.017 | 1.160 | 10 | 1.429 |
| 14 | strict_candidates | nightmare_60bps | conservative | 7 | 0.286 | 3 | 0.002 | -0.009 | 0.012 | 1.085 | 10 | 1.429 |
| 14 | strict_candidates | nightmare_60bps | micro_risk_tight | 7 | 0.429 | 4 | -0.000 | -0.006 | 0.009 | 0.997 | 10 | 1.429 |
| 14 | strict_candidates | nightmare_60bps | prop_strict | 7 | 0.143 | 3 | 0.010 | -0.013 | 0.016 | 1.239 | 9 | 1.429 |
| 14 | strict_candidates | punitive_40bps | base | 7 | 0.571 | 3 | 0.019 | -0.011 | 0.011 | 1.709 | 10 | 1.429 |
| 14 | strict_candidates | punitive_40bps | conservative | 7 | 0.571 | 3 | 0.013 | -0.006 | 0.008 | 1.618 | 10 | 1.429 |
| 14 | strict_candidates | punitive_40bps | micro_risk_tight | 7 | 0.571 | 3 | 0.007 | -0.005 | 0.007 | 1.498 | 10 | 1.429 |
| 14 | strict_candidates | punitive_40bps | prop_strict | 7 | 0.286 | 3 | 0.017 | -0.010 | 0.013 | 1.846 | 10 | 1.429 |
| 30 | late_us_fade | baseline | base | 5 | 0.600 | 0 | 0.015 | 0.003 | 0.009 | 2.157 | 16 | 0.600 |
| 30 | late_us_fade | baseline | conservative | 5 | 0.800 | 0 | 0.012 | 0.002 | 0.006 | 2.299 | 14 | 0.600 |
| 30 | late_us_fade | baseline | micro_risk_tight | 5 | 0.800 | 0 | 0.007 | 0.001 | 0.004 | 2.179 | 13 | 0.600 |
| 30 | late_us_fade | baseline | prop_strict | 5 | 0.400 | 0 | 0.020 | 0.003 | 0.011 | 2.469 | 14 | 0.600 |
| 30 | late_us_fade | nightmare_60bps | base | 5 | 0.400 | 2 | 0.001 | -0.006 | 0.024 | 1.070 | 16 | 0.600 |
| 30 | late_us_fade | nightmare_60bps | conservative | 5 | 0.200 | 2 | 0.003 | -0.004 | 0.015 | 1.231 | 14 | 0.600 |
| 30 | late_us_fade | nightmare_60bps | micro_risk_tight | 5 | 0.400 | 2 | 0.001 | -0.004 | 0.010 | 1.129 | 13 | 0.600 |
| 30 | late_us_fade | nightmare_60bps | prop_strict | 5 | 0.000 | 2 | 0.005 | -0.007 | 0.019 | 1.231 | 14 | 0.600 |
| 30 | late_us_fade | punitive_40bps | base | 5 | 0.400 | 1 | 0.007 | -0.003 | 0.013 | 1.290 | 16 | 0.600 |
| 30 | late_us_fade | punitive_40bps | conservative | 5 | 0.200 | 1 | 0.006 | -0.002 | 0.010 | 1.500 | 14 | 0.600 |
| 30 | late_us_fade | punitive_40bps | micro_risk_tight | 5 | 0.400 | 1 | 0.002 | -0.001 | 0.007 | 1.358 | 13 | 0.600 |
| 30 | late_us_fade | punitive_40bps | prop_strict | 5 | 0.200 | 1 | 0.011 | -0.004 | 0.016 | 1.500 | 14 | 0.600 |
| 30 | ny_13_range_reversal | baseline | base | 5 | 0.400 | 0 | 0.021 | 0.008 | 0.003 | 4.537 | 9 | 0.467 |
| 30 | ny_13_range_reversal | baseline | conservative | 5 | 0.400 | 0 | 0.013 | 0.006 | 0.003 | 3.874 | 9 | 0.467 |
| 30 | ny_13_range_reversal | baseline | micro_risk_tight | 5 | 0.400 | 0 | 0.008 | 0.004 | 0.002 | 3.850 | 8 | 0.467 |
| 30 | ny_13_range_reversal | baseline | prop_strict | 5 | 0.400 | 0 | 0.021 | 0.010 | 0.004 | 3.874 | 9 | 0.467 |
| 30 | ny_13_range_reversal | nightmare_60bps | base | 5 | 0.000 | 2 | 0.002 | -0.006 | 0.009 | 1.176 | 9 | 0.467 |
| 30 | ny_13_range_reversal | nightmare_60bps | conservative | 5 | 0.400 | 3 | -0.000 | -0.005 | 0.007 | 0.974 | 9 | 0.467 |
| 30 | ny_13_range_reversal | nightmare_60bps | micro_risk_tight | 5 | 0.400 | 3 | -0.000 | -0.003 | 0.004 | 0.955 | 8 | 0.467 |
| 30 | ny_13_range_reversal | nightmare_60bps | prop_strict | 5 | 0.400 | 3 | -0.000 | -0.007 | 0.011 | 0.974 | 9 | 0.467 |
| 30 | ny_13_range_reversal | punitive_40bps | base | 5 | 0.400 | 1 | 0.008 | -0.001 | 0.005 | 1.826 | 9 | 0.467 |
| 30 | ny_13_range_reversal | punitive_40bps | conservative | 5 | 0.400 | 2 | 0.004 | -0.001 | 0.004 | 1.523 | 9 | 0.467 |
| 30 | ny_13_range_reversal | punitive_40bps | micro_risk_tight | 5 | 0.400 | 1 | 0.002 | -0.001 | 0.003 | 1.465 | 8 | 0.467 |
| 30 | ny_13_range_reversal | punitive_40bps | prop_strict | 5 | 0.400 | 2 | 0.007 | -0.001 | 0.007 | 1.523 | 9 | 0.467 |
| 30 | strict_candidates | baseline | base | 5 | 1.000 | 0 | 0.044 | 0.011 | 0.008 | 3.237 | 26 | 1.300 |
| 30 | strict_candidates | baseline | conservative | 5 | 1.000 | 0 | 0.031 | 0.008 | 0.006 | 3.365 | 26 | 1.300 |
| 30 | strict_candidates | baseline | micro_risk_tight | 5 | 1.000 | 0 | 0.019 | 0.004 | 0.004 | 3.368 | 25 | 1.300 |
| 30 | strict_candidates | baseline | prop_strict | 5 | 1.000 | 0 | 0.052 | 0.013 | 0.009 | 3.365 | 26 | 1.300 |
| 30 | strict_candidates | nightmare_60bps | base | 5 | 0.000 | 1 | 0.013 | -0.008 | 0.017 | 1.239 | 25 | 1.300 |
| 30 | strict_candidates | nightmare_60bps | conservative | 5 | 0.000 | 1 | 0.009 | -0.006 | 0.014 | 1.210 | 25 | 1.300 |
| 30 | strict_candidates | nightmare_60bps | micro_risk_tight | 5 | 0.800 | 1 | 0.004 | -0.005 | 0.010 | 1.221 | 24 | 1.300 |
| 30 | strict_candidates | nightmare_60bps | prop_strict | 5 | 0.000 | 1 | 0.015 | -0.007 | 0.018 | 1.434 | 24 | 1.300 |
| 30 | strict_candidates | punitive_40bps | base | 5 | 0.400 | 1 | 0.021 | -0.004 | 0.013 | 1.744 | 26 | 1.300 |
| 30 | strict_candidates | punitive_40bps | conservative | 5 | 0.800 | 1 | 0.017 | -0.001 | 0.008 | 1.886 | 25 | 1.300 |
| 30 | strict_candidates | punitive_40bps | micro_risk_tight | 5 | 0.800 | 1 | 0.009 | -0.003 | 0.007 | 1.742 | 25 | 1.300 |
| 30 | strict_candidates | punitive_40bps | prop_strict | 5 | 0.000 | 1 | 0.029 | -0.001 | 0.013 | 1.989 | 25 | 1.300 |
| 45 | late_us_fade | baseline | base | 3 | 0.333 | 0 | 0.016 | 0.010 | 0.009 | 1.668 | 27 | 0.756 |
| 45 | late_us_fade | baseline | conservative | 3 | 1.000 | 0 | 0.014 | 0.008 | 0.007 | 1.909 | 25 | 0.756 |
| 45 | late_us_fade | baseline | micro_risk_tight | 3 | 1.000 | 0 | 0.008 | 0.004 | 0.005 | 1.729 | 24 | 0.756 |
| 45 | late_us_fade | baseline | prop_strict | 3 | 0.333 | 0 | 0.024 | 0.014 | 0.012 | 1.909 | 25 | 0.756 |
| 45 | late_us_fade | nightmare_60bps | base | 3 | 0.000 | 3 | -0.005 | -0.012 | 0.024 | 0.809 | 27 | 0.756 |
| 45 | late_us_fade | nightmare_60bps | conservative | 3 | 0.000 | 3 | -0.003 | -0.004 | 0.017 | 0.886 | 25 | 0.756 |
| 45 | late_us_fade | nightmare_60bps | micro_risk_tight | 3 | 0.000 | 3 | -0.002 | -0.003 | 0.010 | 0.818 | 24 | 0.756 |
| 45 | late_us_fade | nightmare_60bps | prop_strict | 3 | 0.000 | 2 | -0.004 | -0.006 | 0.021 | 0.886 | 25 | 0.756 |
| 45 | late_us_fade | punitive_40bps | base | 3 | 0.000 | 2 | -0.000 | -0.003 | 0.014 | 0.987 | 27 | 0.756 |
| 45 | late_us_fade | punitive_40bps | conservative | 3 | 0.000 | 0 | 0.002 | 0.001 | 0.011 | 1.108 | 25 | 0.756 |
| 45 | late_us_fade | punitive_40bps | micro_risk_tight | 3 | 0.000 | 1 | 0.000 | -0.000 | 0.008 | 1.016 | 24 | 0.756 |
| 45 | late_us_fade | punitive_40bps | prop_strict | 3 | 0.000 | 0 | 0.004 | 0.002 | 0.017 | 1.108 | 25 | 0.756 |
| 45 | ny_13_range_reversal | baseline | base | 3 | 1.000 | 0 | 0.041 | 0.025 | 0.003 | 5.364 | 20 | 0.511 |
| 45 | ny_13_range_reversal | baseline | conservative | 3 | 0.667 | 0 | 0.028 | 0.016 | 0.003 | 4.971 | 19 | 0.511 |
| 45 | ny_13_range_reversal | baseline | micro_risk_tight | 3 | 0.667 | 0 | 0.018 | 0.009 | 0.002 | 5.803 | 16 | 0.511 |
| 45 | ny_13_range_reversal | baseline | prop_strict | 3 | 0.667 | 0 | 0.046 | 0.026 | 0.004 | 4.971 | 19 | 0.511 |
| 45 | ny_13_range_reversal | nightmare_60bps | base | 3 | 0.000 | 1 | 0.004 | -0.002 | 0.009 | 1.201 | 20 | 0.511 |
| 45 | ny_13_range_reversal | nightmare_60bps | conservative | 3 | 0.667 | 1 | 0.002 | -0.004 | 0.007 | 1.104 | 19 | 0.511 |
| 45 | ny_13_range_reversal | nightmare_60bps | micro_risk_tight | 3 | 0.667 | 1 | 0.001 | -0.002 | 0.004 | 1.143 | 16 | 0.511 |
| 45 | ny_13_range_reversal | nightmare_60bps | prop_strict | 3 | 0.333 | 1 | 0.007 | -0.003 | 0.011 | 1.292 | 18 | 0.511 |
| 45 | ny_13_range_reversal | punitive_40bps | base | 3 | 1.000 | 0 | 0.017 | 0.007 | 0.005 | 2.021 | 20 | 0.511 |
| 45 | ny_13_range_reversal | punitive_40bps | conservative | 3 | 0.667 | 0 | 0.011 | 0.002 | 0.004 | 1.859 | 19 | 0.511 |
| 45 | ny_13_range_reversal | punitive_40bps | micro_risk_tight | 3 | 0.667 | 0 | 0.007 | 0.002 | 0.003 | 2.003 | 16 | 0.511 |
| 45 | ny_13_range_reversal | punitive_40bps | prop_strict | 3 | 0.667 | 0 | 0.018 | 0.004 | 0.007 | 1.859 | 19 | 0.511 |
| 45 | strict_candidates | baseline | base | 3 | 1.000 | 0 | 0.076 | 0.046 | 0.008 | 3.035 | 56 | 1.600 |
| 45 | strict_candidates | baseline | conservative | 3 | 1.000 | 0 | 0.056 | 0.032 | 0.006 | 3.199 | 53 | 1.600 |
| 45 | strict_candidates | baseline | micro_risk_tight | 3 | 1.000 | 0 | 0.034 | 0.018 | 0.004 | 3.161 | 49 | 1.600 |
| 45 | strict_candidates | baseline | prop_strict | 3 | 1.000 | 0 | 0.093 | 0.054 | 0.009 | 3.199 | 53 | 1.600 |
| 45 | strict_candidates | nightmare_60bps | base | 3 | 0.000 | 1 | 0.002 | -0.003 | 0.018 | 1.026 | 54 | 1.600 |
| 45 | strict_candidates | nightmare_60bps | conservative | 3 | 0.000 | 1 | 0.004 | -0.003 | 0.014 | 1.105 | 51 | 1.600 |
| 45 | strict_candidates | nightmare_60bps | micro_risk_tight | 3 | 0.667 | 1 | 0.004 | -0.002 | 0.010 | 1.114 | 48 | 1.600 |
| 45 | strict_candidates | nightmare_60bps | prop_strict | 3 | 0.000 | 0 | 0.013 | 0.002 | 0.018 | 1.180 | 49 | 1.600 |
| 45 | strict_candidates | punitive_40bps | base | 3 | 0.000 | 0 | 0.026 | 0.013 | 0.013 | 1.470 | 56 | 1.600 |
| 45 | strict_candidates | punitive_40bps | conservative | 3 | 1.000 | 0 | 0.024 | 0.011 | 0.008 | 1.681 | 52 | 1.600 |
| 45 | strict_candidates | punitive_40bps | micro_risk_tight | 3 | 1.000 | 0 | 0.013 | 0.004 | 0.007 | 1.551 | 49 | 1.600 |
| 45 | strict_candidates | punitive_40bps | prop_strict | 3 | 0.000 | 0 | 0.035 | 0.014 | 0.013 | 1.615 | 51 | 1.600 |

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
| punitive_40bps | 30 | shock_alignment | aligned_shock | 48 | 25 | 0.521 | -0.110 | 0.408 | 0.793 | 2.398 | 0.600 |
| punitive_40bps | 30 | entry_hour_utc | 22 | 25 | 13 | 0.520 | -0.773 | -0.065 | 0.024 | 0.885 | 0.154 |
| punitive_40bps | 30 | global_ema_state | bearish | 33 | 17 | 0.515 | 0.149 | 0.853 | 1.413 | 18.282 | 0.647 |
| punitive_40bps | 30 | entry_hour_utc | 21 | 37 | 19 | 0.514 | 0.105 | 0.176 | 1.320 | 1.506 | 0.526 |
| punitive_40bps | 30 | local_ema_state | mixed | 127 | 65 | 0.512 | 0.096 | 0.216 | 1.243 | 1.621 | 0.538 |
| punitive_40bps | 30 | rsi_bucket | bearish_mid | 59 | 30 | 0.508 | -0.026 | 0.334 | 0.937 | 2.021 | 0.533 |
| punitive_40bps | 30 | compression_state | expanded | 44 | 22 | 0.500 | 0.234 | 0.605 | 1.442 | 2.786 | 0.636 |
| punitive_40bps | 30 | symbol | DOGEUSDT | 22 | 11 | 0.500 | -0.341 | 0.856 | 0.420 | 287.034 | 0.364 |
| punitive_40bps | 30 | local_ema_state | bearish | 16 | 8 | 0.500 | -0.092 | 0.734 | 0.860 | 8.439 | 0.625 |
| punitive_40bps | 30 | symbol | SUIUSDT | 10 | 5 | 0.500 | 0.137 | 0.075 | 1.281 | 1.137 | 0.400 |
| punitive_40bps | 30 | entry_hour_utc | 7 | 8 | 4 | 0.500 | 0.231 | 0.231 | inf | inf | 1.000 |

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
- Concentration is measured on strict candidates with conservative risk under punitive costs.
