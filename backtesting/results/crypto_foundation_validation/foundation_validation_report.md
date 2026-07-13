# Crypto Foundation Validation

Date: 2026-07-13.

## Purpose

- Validate foundation layers before adding new pattern-recognition logic.
- Compare the same canonical setup filters across target and management choices.
- Surface whether failures are direction, entry, stop, target, management, or no-follow-through.

## Confidence By Setup

| setup_name | tested_variants | promote_candidates | research_candidates | best_window | best_target_model | best_management_model | best_avg_r | best_return_to_dd | best_direction_accuracy | dominant_failure | confidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| late_us_short_bearish_trend_ce | 18 | 0 | 6 | 15m_60d | fixed_1_5r | hold_target_expiry | +0.312 | +2.225 | 46.4% | direction | low |
| ny_long_neutral_reversal_ce | 18 | 0 | 6 | 15m_30d | fixed_2r | hold_target_expiry | +0.192 | +1.478 | 51.5% | direction | low |
| london_long_middle_local_next_open | 18 | 6 | 13 | 15m_30d | fixed_2r | be_after_half_target | +0.796 | +15.324 | 64.3% | direction | medium |
| london_long_middle_local_retest | 18 | 6 | 13 | 15m_30d | fixed_2r | be_after_half_target | +0.758 | +14.934 | 62.8% | direction | medium |
| late_us_short_bull_flush_ce | 18 | 9 | 14 | 15m_60d | fixed_1_5r | partial_1r_be_after_half_target | +0.444 | +12.434 | 54.3% | direction | medium_high |

## Best Promote / Research Candidates

| window | setup_name | target_model | management_model | accepted | avg_r | profit_factor | return_to_dd | win_rate | direction_accuracy | bad_direction_rate | bad_entry_rate | target_too_far_rate | dominant_failure | foundation_grade |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 15m_30d | london_long_middle_local_next_open | fixed_2r | be_after_half_target | 42 | +0.796 | +5.991 | +15.324 | 76.2% | 64.3% | 16.7% | 11.9% | 21.4% | direction | promote_candidate |
| 15m_30d | london_long_middle_local_retest | fixed_2r | be_after_half_target | 43 | +0.758 | +5.582 | +14.934 | 74.4% | 62.8% | 14.0% | 11.6% | 18.6% | direction | promote_candidate |
| 15m_30d | london_long_middle_local_retest | fixed_1_5r | hold_target_expiry | 46 | +0.681 | +5.004 | +14.350 | 80.4% | 65.2% | 15.2% | 13.0% | 19.6% | direction | promote_candidate |
| 15m_30d | london_long_middle_local_retest | fixed_2r | partial_1r_be_after_half_target | 44 | +0.691 | +5.725 | +13.931 | 84.1% | 63.6% | 13.6% | 11.4% | 18.2% | direction | promote_candidate |
| 15m_30d | london_long_middle_local_next_open | fixed_1_5r | be_after_half_target | 44 | +0.684 | +5.493 | +13.794 | 77.3% | 68.2% | 15.9% | 11.4% | 15.9% | direction | promote_candidate |
| 15m_30d | london_long_middle_local_next_open | fixed_2r | partial_1r_be_after_half_target | 42 | +0.706 | +5.608 | +13.586 | 83.3% | 64.3% | 16.7% | 11.9% | 21.4% | direction | promote_candidate |
| 15m_30d | london_long_middle_local_next_open | fixed_1_5r | partial_1r_be_after_half_target | 44 | +0.664 | +5.537 | +13.377 | 84.1% | 68.2% | 15.9% | 11.4% | 15.9% | direction | promote_candidate |
| 15m_30d | london_long_middle_local_retest | fixed_1_5r | partial_1r_be_after_half_target | 46 | +0.620 | +4.810 | +13.071 | 82.6% | 65.2% | 15.2% | 13.0% | 15.2% | direction | promote_candidate |
| 15m_30d | london_long_middle_local_retest | fixed_1_5r | be_after_half_target | 45 | +0.624 | +4.478 | +12.870 | 75.6% | 64.4% | 15.6% | 13.3% | 15.6% | direction | promote_candidate |
| 15m_30d | late_us_short_bull_flush_ce | fixed_1_5r | partial_1r_be_after_half_target | 69 | +0.431 | +3.332 | +11.986 | 68.1% | 58.0% | 21.7% | 24.6% | 5.8% | direction | promote_candidate |
| 15m_30d | london_long_middle_local_retest | fixed_2r | hold_target_expiry | 44 | +0.814 | +5.560 | +11.898 | 79.5% | 63.6% | 13.6% | 11.4% | 22.7% | direction | promote_candidate |
| 15m_30d | late_us_short_bull_flush_ce | fixed_1_5r | be_after_half_target | 68 | +0.474 | +3.434 | +11.342 | 60.3% | 57.4% | 22.1% | 25.0% | 5.9% | direction | promote_candidate |
| 15m_30d | london_long_middle_local_next_open | fixed_2r | hold_target_expiry | 42 | +0.778 | +5.168 | +10.898 | 78.6% | 64.3% | 16.7% | 11.9% | 26.2% | direction | promote_candidate |
| 15m_30d | london_long_middle_local_next_open | fixed_1_5r | hold_target_expiry | 44 | +0.667 | +4.742 | +9.784 | 79.5% | 68.2% | 15.9% | 11.4% | 20.5% | direction | promote_candidate |
| 15m_60d | late_us_short_bull_flush_ce | fixed_2r | partial_1r_be_after_half_target | 85 | +0.424 | +2.983 | +9.385 | 71.8% | 56.5% | 24.7% | 23.5% | 23.5% | direction | promote_candidate |
| 15m_60d | late_us_short_bull_flush_ce | fixed_2r | be_after_half_target | 85 | +0.493 | +3.226 | +9.080 | 60.0% | 56.5% | 24.7% | 23.5% | 23.5% | direction | promote_candidate |
| 15m_30d | late_us_short_bull_flush_ce | fixed_1_5r | hold_target_expiry | 66 | +0.514 | +3.069 | +7.895 | 68.2% | 57.6% | 21.2% | 24.2% | 10.6% | direction | promote_candidate |
| 15m_30d | late_us_short_bull_flush_ce | fixed_2r | be_after_half_target | 63 | +0.510 | +3.068 | +7.260 | 61.9% | 58.7% | 22.2% | 25.4% | 27.0% | direction | promote_candidate |
| 15m_60d | late_us_short_bull_flush_ce | fixed_2r | hold_target_expiry | 85 | +0.456 | +2.623 | +7.186 | 61.2% | 56.5% | 24.7% | 23.5% | 29.4% | direction | promote_candidate |
| 15m_30d | late_us_short_bull_flush_ce | fixed_2r | partial_1r_be_after_half_target | 63 | +0.415 | +2.736 | +6.812 | 71.4% | 58.7% | 22.2% | 25.4% | 27.0% | direction | promote_candidate |
| 15m_30d | late_us_short_bull_flush_ce | fixed_2r | hold_target_expiry | 63 | +0.502 | +2.758 | +5.866 | 63.5% | 58.7% | 22.2% | 25.4% | 31.7% | direction | promote_candidate |
| 15m_60d | late_us_short_bull_flush_ce | fixed_1_5r | partial_1r_be_after_half_target | 92 | +0.444 | +3.570 | +12.434 | 68.5% | 54.3% | 25.0% | 22.8% | 5.4% | direction | research_candidate |
| 15m_60d | late_us_short_bull_flush_ce | fixed_1_5r | be_after_half_target | 91 | +0.482 | +3.671 | +10.860 | 61.5% | 53.8% | 25.3% | 23.1% | 5.5% | direction | research_candidate |
| 15m_60d | late_us_short_bull_flush_ce | fixed_1_5r | hold_target_expiry | 89 | +0.500 | +3.164 | +10.365 | 67.4% | 53.9% | 24.7% | 22.5% | 9.0% | direction | research_candidate |
| 15m_60d | london_long_middle_local_retest | fixed_1_5r | partial_1r_be_after_half_target | 80 | +0.321 | +2.347 | +5.043 | 71.2% | 51.2% | 25.0% | 26.2% | 11.2% | direction | research_candidate |
| 15m_60d | london_long_middle_local_retest | fixed_2r | partial_1r_be_after_half_target | 78 | +0.335 | +2.343 | +4.148 | 71.8% | 51.3% | 24.4% | 25.6% | 14.1% | direction | research_candidate |
| 15m_60d | london_long_middle_local_retest | fixed_2r | hold_target_expiry | 72 | +0.413 | +2.336 | +3.437 | 65.3% | 52.8% | 20.8% | 22.2% | 22.2% | direction | research_candidate |
| 15m_60d | london_long_middle_local_retest | fixed_1_5r | be_after_half_target | 78 | +0.280 | +2.069 | +3.119 | 57.7% | 51.3% | 24.4% | 26.9% | 11.5% | direction | research_candidate |
| 15m_60d | london_long_middle_local_retest | fixed_2r | be_after_half_target | 76 | +0.320 | +2.158 | +3.051 | 55.3% | 51.3% | 23.7% | 26.3% | 14.5% | direction | research_candidate |
| 15m_60d | london_long_middle_local_next_open | fixed_1_5r | partial_1r_be_after_half_target | 78 | +0.298 | +2.177 | +2.982 | 69.2% | 52.6% | 26.9% | 25.6% | 11.5% | direction | research_candidate |
| 15m_60d | london_long_middle_local_retest | fixed_1_5r | hold_target_expiry | 74 | +0.349 | +2.165 | +2.828 | 66.2% | 52.7% | 21.6% | 23.0% | 14.9% | direction | research_candidate |
| 15m_60d | london_long_middle_local_next_open | fixed_2r | partial_1r_be_after_half_target | 76 | +0.298 | +2.094 | +2.575 | 69.7% | 50.0% | 27.6% | 26.3% | 15.8% | direction | research_candidate |
| 15m_60d | london_long_middle_local_next_open | fixed_2r | hold_target_expiry | 70 | +0.345 | +2.084 | +2.291 | 62.9% | 51.4% | 24.3% | 22.9% | 25.7% | direction | research_candidate |
| 15m_60d | late_us_short_bearish_trend_ce | fixed_1_5r | hold_target_expiry | 56 | +0.312 | +2.150 | +2.225 | 62.5% | 46.4% | 32.1% | 28.6% | 12.5% | direction | research_candidate |
| 15m_60d | london_long_middle_local_next_open | fixed_1_5r | hold_target_expiry | 72 | +0.308 | +1.996 | +2.105 | 63.9% | 54.2% | 23.6% | 22.2% | 19.4% | direction | research_candidate |
| 15m_60d | london_long_middle_local_next_open | fixed_1_5r | be_after_half_target | 77 | +0.267 | +1.991 | +2.053 | 55.8% | 53.2% | 26.0% | 26.0% | 11.7% | direction | research_candidate |
| 15m_60d | london_long_middle_local_next_open | fixed_2r | be_after_half_target | 75 | +0.291 | +2.003 | +1.982 | 54.7% | 50.7% | 26.7% | 26.7% | 16.0% | direction | research_candidate |
| 15m_60d | late_us_short_bearish_trend_ce | fixed_2r | hold_target_expiry | 56 | +0.248 | +1.799 | +1.764 | 58.9% | 46.4% | 32.1% | 28.6% | 23.2% | direction | research_candidate |
| 15m_60d | late_us_short_bearish_trend_ce | fixed_2r | partial_1r_be_after_half_target | 56 | +0.236 | +1.936 | +1.684 | 64.3% | 46.4% | 32.1% | 28.6% | 21.4% | direction | research_candidate |
| 15m_60d | late_us_short_bearish_trend_ce | fixed_2r | be_after_half_target | 56 | +0.228 | +1.882 | +1.624 | 53.6% | 46.4% | 32.1% | 28.6% | 21.4% | direction | research_candidate |

## Rejected / Weak Foundation Rows

| window | setup_name | target_model | management_model | accepted | avg_r | profit_factor | return_to_dd | win_rate | direction_accuracy | bad_direction_rate | bad_entry_rate | target_too_far_rate | dominant_failure | foundation_grade | foundation_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 15m_30d | late_us_short_bearish_trend_ce | fixed_1_5r | hold_target_expiry | 18 | +0.032 | +1.064 | +0.091 | 44.4% | 44.4% | 50.0% | 61.1% | 0.0% | direction | reject | sample<30, pf<1.25, direction<45%, bad_entry>35% |
| 15m_30d | late_us_short_bearish_trend_ce | fixed_1_5r | be_after_half_target | 18 | +0.003 | +1.007 | +0.009 | 38.9% | 44.4% | 50.0% | 61.1% | 0.0% | direction | reject | sample<30, pf<1.25, direction<45%, bad_entry>35% |
| 15m_30d | late_us_short_bearish_trend_ce | fixed_1_5r | partial_1r_be_after_half_target | 18 | +0.002 | +1.005 | +0.006 | 44.4% | 44.4% | 50.0% | 61.1% | 0.0% | direction | reject | sample<30, pf<1.25, direction<45%, bad_entry>35% |
| 15m_30d | late_us_short_bearish_trend_ce | fixed_2r | partial_1r_be_after_half_target | 18 | -0.029 | +0.934 | -0.082 | 50.0% | 44.4% | 50.0% | 61.1% | 0.0% | direction | reject | sample<30, avg_r<=0, pf<1.25, direction<45%, bad_entry>35% |
| 15m_30d | late_us_short_bearish_trend_ce | fixed_2r | be_after_half_target | 18 | -0.082 | +0.819 | -0.234 | 27.8% | 44.4% | 50.0% | 61.1% | 0.0% | direction | reject | sample<30, avg_r<=0, pf<1.25, direction<45%, bad_entry>35% |
| 15m_30d | late_us_short_bearish_trend_ce | fixed_2r | hold_target_expiry | 18 | -0.244 | +0.605 | -0.698 | 33.3% | 44.4% | 50.0% | 61.1% | 5.6% | direction | reject | sample<30, avg_r<=0, pf<1.25, direction<45%, bad_entry>35% |
| 15m_60d | ny_long_neutral_reversal_ce | fixed_2r | partial_1r_be_after_half_target | 148 | +0.088 | +1.293 | +0.877 | 55.4% | 39.9% | 28.4% | 25.0% | 13.5% | direction | reject | direction<45% |
| 15m_60d | ny_long_neutral_reversal_ce | fixed_2r | be_after_half_target | 147 | +0.090 | +1.291 | +0.820 | 45.6% | 40.1% | 27.9% | 25.2% | 13.6% | direction | reject | direction<45% |
| 15m_60d | ny_long_neutral_reversal_ce | fixed_2r | hold_target_expiry | 145 | +0.098 | +1.295 | +0.814 | 52.4% | 40.0% | 28.3% | 24.8% | 21.4% | direction | reject | direction<45% |
| 15m_60d | ny_long_neutral_reversal_ce | fixed_1_5r | partial_1r_be_after_half_target | 155 | +0.075 | +1.279 | +0.766 | 48.4% | 38.7% | 29.0% | 25.2% | 7.1% | direction | reject | direction<45% |
| 15m_60d | ny_long_neutral_reversal_ce | fixed_1_5r | be_after_half_target | 154 | +0.071 | +1.258 | +0.664 | 40.9% | 39.0% | 28.6% | 25.3% | 7.1% | direction | reject | direction<45% |
| 15m_60d | ny_long_neutral_reversal_ce | fixed_1_5r | hold_target_expiry | 152 | +0.065 | +1.195 | +0.527 | 51.3% | 38.2% | 28.9% | 25.0% | 13.8% | direction | reject | pf<1.25, direction<45% |
| 5m_30d | london_long_middle_local_retest | fixed_1_5r | partial_1r_be_after_half_target | 56 | +0.198 | +1.710 | +1.670 | 58.9% | 44.6% | 30.4% | 21.4% | 7.1% | direction | reject | direction<45% |
| 5m_30d | london_long_middle_local_retest | fixed_1_5r | be_after_half_target | 55 | +0.191 | +1.639 | +1.584 | 50.9% | 43.6% | 29.1% | 21.8% | 9.1% | direction | reject | direction<45% |
| 5m_30d | london_long_middle_local_next_open | fixed_1_5r | be_after_half_target | 54 | +0.141 | +1.469 | +1.144 | 48.1% | 44.4% | 31.5% | 22.2% | 9.3% | direction | reject | direction<45% |
| 5m_30d | london_long_middle_local_next_open | fixed_2r | partial_1r_be_after_half_target | 50 | +0.111 | +1.339 | +0.839 | 58.0% | 44.0% | 36.0% | 24.0% | 14.0% | direction | reject | direction<45% |
| 5m_30d | late_us_short_bull_flush_ce | fixed_1_5r | partial_1r_be_after_half_target | 74 | +0.103 | +1.358 | +0.665 | 54.1% | 43.2% | 41.9% | 28.4% | 10.8% | direction | reject | direction<45% |
| 5m_30d | london_long_middle_local_retest | fixed_1_5r | hold_target_expiry | 48 | +0.127 | +1.340 | +0.594 | 52.1% | 39.6% | 33.3% | 25.0% | 8.3% | direction | reject | direction<45% |
| 5m_30d | late_us_short_bull_flush_ce | fixed_1_5r | be_after_half_target | 72 | +0.099 | +1.320 | +0.555 | 47.2% | 43.1% | 43.1% | 29.2% | 11.1% | direction | reject | direction<45% |
| 5m_30d | london_long_middle_local_retest | fixed_2r | hold_target_expiry | 45 | +0.111 | +1.285 | +0.517 | 51.1% | 42.2% | 35.6% | 26.7% | 22.2% | direction | reject | direction<45% |
| 5m_30d | late_us_short_bull_flush_ce | fixed_2r | partial_1r_be_after_half_target | 71 | +0.075 | +1.245 | +0.468 | 57.7% | 43.7% | 43.7% | 29.6% | 16.9% | direction | reject | pf<1.25, direction<45% |
| 5m_30d | london_long_middle_local_next_open | fixed_1_5r | hold_target_expiry | 47 | +0.085 | +1.225 | +0.386 | 51.1% | 40.4% | 36.2% | 25.5% | 12.8% | direction | reject | pf<1.25, direction<45% |
| 5m_30d | late_us_short_bull_flush_ce | fixed_2r | be_after_half_target | 70 | +0.073 | +1.220 | +0.349 | 45.7% | 44.3% | 44.3% | 30.0% | 17.1% | direction | reject | pf<1.25, direction<45% |
| 5m_30d | london_long_middle_local_next_open | fixed_2r | hold_target_expiry | 44 | +0.078 | +1.192 | +0.347 | 47.7% | 40.9% | 38.6% | 27.3% | 20.5% | direction | reject | pf<1.25, direction<45% |
| 5m_30d | london_long_middle_local_retest | fixed_2r | be_after_half_target | 45 | +0.042 | +1.109 | +0.214 | 40.0% | 42.2% | 35.6% | 26.7% | 11.1% | direction | reject | pf<1.25, direction<45% |
| 5m_30d | london_long_middle_local_next_open | fixed_2r | be_after_half_target | 44 | +0.020 | +1.051 | +0.098 | 38.6% | 40.9% | 38.6% | 27.3% | 9.1% | direction | reject | pf<1.25, direction<45% |
| 5m_30d | ny_long_neutral_reversal_ce | fixed_1_5r | hold_target_expiry | 85 | -0.008 | +0.982 | -0.112 | 45.9% | 42.4% | 32.9% | 37.6% | 5.9% | direction | reject | avg_r<=0, pf<1.25, direction<45%, bad_entry>35% |
| 5m_30d | ny_long_neutral_reversal_ce | fixed_2r | be_after_half_target | 81 | -0.023 | +0.945 | -0.199 | 37.0% | 44.4% | 35.8% | 37.0% | 9.9% | direction | reject | avg_r<=0, pf<1.25, direction<45%, bad_entry>35% |
| 5m_30d | ny_long_neutral_reversal_ce | fixed_1_5r | be_after_half_target | 82 | -0.063 | +0.853 | -0.394 | 36.6% | 39.0% | 36.6% | 39.0% | 1.2% | direction | reject | avg_r<=0, pf<1.25, direction<45%, bad_entry>35% |
| 5m_30d | ny_long_neutral_reversal_ce | fixed_2r | hold_target_expiry | 75 | -0.066 | +0.869 | -0.464 | 40.0% | 41.3% | 37.3% | 40.0% | 13.3% | direction | reject | avg_r<=0, pf<1.25, direction<45%, bad_entry>35% |
| 5m_30d | ny_long_neutral_reversal_ce | fixed_1_5r | partial_1r_be_after_half_target | 82 | -0.099 | +0.771 | -0.584 | 43.9% | 37.8% | 39.0% | 40.2% | 1.2% | direction | reject | avg_r<=0, pf<1.25, direction<45%, bad_entry>35% |
| 5m_30d | ny_long_neutral_reversal_ce | fixed_2r | partial_1r_be_after_half_target | 81 | -0.095 | +0.774 | -0.651 | 49.4% | 42.0% | 38.3% | 38.3% | 8.6% | direction | reject | avg_r<=0, pf<1.25, direction<45%, bad_entry>35% |
| 5m_30d | late_us_short_bearish_trend_ce | fixed_2r | hold_target_expiry | 19 | -0.205 | +0.562 | -0.673 | 31.6% | 15.8% | 57.9% | 31.6% | 10.5% | direction | reject | sample<30, avg_r<=0, pf<1.25, direction<45% |
| 5m_30d | late_us_short_bearish_trend_ce | fixed_2r | be_after_half_target | 19 | -0.205 | +0.562 | -0.673 | 31.6% | 15.8% | 57.9% | 31.6% | 10.5% | direction | reject | sample<30, avg_r<=0, pf<1.25, direction<45% |
| 5m_30d | late_us_short_bearish_trend_ce | fixed_2r | partial_1r_be_after_half_target | 19 | -0.217 | +0.536 | -0.690 | 31.6% | 15.8% | 57.9% | 31.6% | 10.5% | direction | reject | sample<30, avg_r<=0, pf<1.25, direction<45% |
| 5m_30d | late_us_short_bearish_trend_ce | fixed_1_5r | hold_target_expiry | 19 | -0.222 | +0.526 | -0.752 | 31.6% | 15.8% | 57.9% | 31.6% | 5.3% | direction | reject | sample<30, avg_r<=0, pf<1.25, direction<45% |
| 5m_30d | late_us_short_bearish_trend_ce | fixed_1_5r | be_after_half_target | 19 | -0.297 | +0.367 | -0.791 | 26.3% | 15.8% | 57.9% | 31.6% | 5.3% | direction | reject | sample<30, avg_r<=0, pf<1.25, direction<45% |
| 5m_30d | late_us_short_bearish_trend_ce | fixed_1_5r | partial_1r_be_after_half_target | 19 | -0.299 | +0.363 | -0.796 | 26.3% | 15.8% | 57.9% | 31.6% | 5.3% | direction | reject | sample<30, avg_r<=0, pf<1.25, direction<45% |

## Concentration Warning

| window | setup_name | target_model | management_model | top_symbol | top_symbol_positive_return_share | symbols | net_return_pct | positive_return_pct | warning |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 5m_30d | ny_long_neutral_reversal_ce | fixed_1_5r | be_after_half_target | LINKUSDT | 75.3% | 11 | -1.03% | 1.20% | concentrated |
| 5m_30d | ny_long_neutral_reversal_ce | fixed_1_5r | partial_1r_be_after_half_target | LINKUSDT | 71.8% | 11 | -1.62% | 0.86% | concentrated |
| 5m_30d | ny_long_neutral_reversal_ce | fixed_2r | partial_1r_be_after_half_target | LINKUSDT | 63.9% | 11 | -1.55% | 1.05% | concentrated |
| 15m_30d | late_us_short_bearish_trend_ce | fixed_1_5r | hold_target_expiry | WLDUSDT | 60.9% | 7 | 0.11% | 1.30% | concentrated |
| 5m_30d | late_us_short_bearish_trend_ce | fixed_2r | partial_1r_be_after_half_target | ETHUSDT | 59.2% | 8 | -0.83% | 0.63% | concentrated |
| 5m_30d | london_long_middle_local_retest | fixed_2r | hold_target_expiry | DOGEUSDT | 59.0% | 11 | 1.00% | 2.29% | concentrated |
| 5m_30d | late_us_short_bearish_trend_ce | fixed_2r | hold_target_expiry | ETHUSDT | 58.4% | 8 | -0.78% | 0.64% | concentrated |
| 5m_30d | late_us_short_bearish_trend_ce | fixed_2r | be_after_half_target | ETHUSDT | 58.4% | 8 | -0.78% | 0.64% | concentrated |
| 5m_30d | london_long_middle_local_next_open | fixed_2r | hold_target_expiry | DOGEUSDT | 58.1% | 11 | 0.69% | 2.03% | concentrated |
| 15m_30d | late_us_short_bearish_trend_ce | fixed_2r | be_after_half_target | WLDUSDT | 56.5% | 7 | -0.29% | 1.22% | concentrated |
| 5m_30d | london_long_middle_local_retest | fixed_2r | be_after_half_target | DOGEUSDT | 56.1% | 11 | 0.38% | 1.68% | concentrated |
| 5m_30d | ny_long_neutral_reversal_ce | fixed_2r | be_after_half_target | LINKUSDT | 55.4% | 11 | -0.37% | 1.97% | concentrated |
| 15m_30d | late_us_short_bearish_trend_ce | fixed_2r | partial_1r_be_after_half_target | WLDUSDT | 52.5% | 7 | -0.10% | 1.12% | concentrated |
| 5m_30d | london_long_middle_local_next_open | fixed_2r | be_after_half_target | DOGEUSDT | 52.0% | 11 | 0.18% | 1.48% | concentrated |
| 15m_30d | late_us_short_bearish_trend_ce | fixed_2r | hold_target_expiry | NEARUSDT | 52.0% | 7 | -0.88% | 1.02% | concentrated |
| 5m_30d | late_us_short_bearish_trend_ce | fixed_1_5r | be_after_half_target | WLDUSDT | 51.2% | 8 | -1.13% | 0.56% | concentrated |
| 5m_30d | late_us_short_bearish_trend_ce | fixed_1_5r | partial_1r_be_after_half_target | WLDUSDT | 50.5% | 8 | -1.14% | 0.55% | concentrated |
| 15m_30d | late_us_short_bearish_trend_ce | fixed_1_5r | be_after_half_target | WLDUSDT | 49.1% | 7 | 0.01% | 1.00% | ok |
| 15m_30d | late_us_short_bearish_trend_ce | fixed_1_5r | partial_1r_be_after_half_target | NEARUSDT | 48.0% | 7 | 0.01% | 0.90% | ok |
| 5m_30d | late_us_short_bearish_trend_ce | fixed_1_5r | hold_target_expiry | ETHUSDT | 47.9% | 8 | -0.84% | 0.57% | ok |
| 5m_30d | london_long_middle_local_next_open | fixed_1_5r | hold_target_expiry | DOGEUSDT | 46.2% | 11 | 0.80% | 2.10% | ok |
| 5m_30d | london_long_middle_local_retest | fixed_2r | partial_1r_be_after_half_target | DOGEUSDT | 44.1% | 11 | 1.30% | 2.44% | ok |
| 5m_30d | ny_long_neutral_reversal_ce | fixed_2r | hold_target_expiry | AAVEUSDT | 43.2% | 11 | -0.99% | 1.43% | ok |
| 5m_30d | london_long_middle_local_retest | fixed_1_5r | hold_target_expiry | DOGEUSDT | 42.5% | 11 | 1.22% | 2.28% | ok |
| 5m_30d | ny_long_neutral_reversal_ce | fixed_1_5r | hold_target_expiry | AAVEUSDT | 42.0% | 11 | -0.14% | 2.20% | ok |
| 5m_30d | london_long_middle_local_next_open | fixed_2r | partial_1r_be_after_half_target | DOGEUSDT | 40.0% | 11 | 1.11% | 2.25% | ok |
| 5m_30d | london_long_middle_local_next_open | fixed_1_5r | be_after_half_target | DOGEUSDT | 37.9% | 11 | 1.53% | 2.56% | ok |
| 5m_30d | london_long_middle_local_next_open | fixed_1_5r | partial_1r_be_after_half_target | DOGEUSDT | 34.3% | 11 | 1.95% | 2.92% | ok |
| 15m_60d | ny_long_neutral_reversal_ce | fixed_1_5r | hold_target_expiry | SOLUSDT | 34.0% | 11 | 1.97% | 2.92% | ok |
| 5m_30d | london_long_middle_local_retest | fixed_1_5r | be_after_half_target | DOGEUSDT | 33.2% | 11 | 2.10% | 2.92% | ok |
| 5m_30d | late_us_short_bull_flush_ce | fixed_2r | be_after_half_target | SUIUSDT | 32.8% | 10 | 1.03% | 2.20% | ok |
| 5m_30d | london_long_middle_local_retest | fixed_1_5r | partial_1r_be_after_half_target | DOGEUSDT | 32.6% | 11 | 2.21% | 3.07% | ok |
| 15m_60d | late_us_short_bearish_trend_ce | fixed_2r | be_after_half_target | SOLUSDT | 30.1% | 11 | 2.55% | 3.42% | ok |
| 5m_30d | late_us_short_bull_flush_ce | fixed_2r | partial_1r_be_after_half_target | SUIUSDT | 29.3% | 10 | 1.07% | 2.07% | ok |
| 15m_30d | ny_long_neutral_reversal_ce | fixed_1_5r | partial_1r_be_after_half_target | 1000PEPEUSDT | 29.0% | 11 | 1.53% | 2.41% | ok |
| 15m_60d | london_long_middle_local_next_open | fixed_2r | hold_target_expiry | ETHUSDT | 27.8% | 10 | 4.82% | 5.96% | ok |
| 15m_60d | ny_long_neutral_reversal_ce | fixed_2r | hold_target_expiry | SOLUSDT | 27.3% | 11 | 2.84% | 3.48% | ok |
| 15m_60d | late_us_short_bearish_trend_ce | fixed_2r | hold_target_expiry | SOLUSDT | 27.1% | 11 | 2.77% | 3.80% | ok |
| 5m_30d | late_us_short_bull_flush_ce | fixed_1_5r | be_after_half_target | SUIUSDT | 26.3% | 11 | 1.42% | 2.57% | ok |
| 15m_60d | late_us_short_bearish_trend_ce | fixed_2r | partial_1r_be_after_half_target | SOLUSDT | 25.8% | 11 | 2.65% | 3.38% | ok |
| 5m_30d | late_us_short_bull_flush_ce | fixed_2r | hold_target_expiry | ETHUSDT | 25.6% | 10 | 2.45% | 3.50% | ok |
| 15m_60d | london_long_middle_local_next_open | fixed_1_5r | hold_target_expiry | ETHUSDT | 25.3% | 10 | 4.43% | 5.55% | ok |
| 15m_60d | london_long_middle_local_retest | fixed_2r | hold_target_expiry | ETHUSDT | 25.2% | 10 | 5.94% | 6.78% | ok |
| 15m_60d | london_long_middle_local_next_open | fixed_1_5r | partial_1r_be_after_half_target | LINKUSDT | 24.9% | 10 | 4.65% | 5.08% | ok |
| 15m_30d | london_long_middle_local_retest | fixed_2r | be_after_half_target | ETHUSDT | 24.6% | 10 | 6.52% | 6.62% | ok |
| 15m_30d | london_long_middle_local_next_open | fixed_2r | be_after_half_target | ETHUSDT | 24.1% | 10 | 6.69% | 6.79% | ok |
| 15m_30d | london_long_middle_local_retest | fixed_1_5r | be_after_half_target | ETHUSDT | 24.0% | 10 | 5.62% | 5.74% | ok |
| 15m_60d | london_long_middle_local_retest | fixed_1_5r | be_after_half_target | LINKUSDT | 24.0% | 10 | 4.37% | 4.94% | ok |
| 15m_60d | london_long_middle_local_retest | fixed_2r | be_after_half_target | ETHUSDT | 23.9% | 10 | 4.86% | 5.25% | ok |
| 15m_30d | london_long_middle_local_next_open | fixed_2r | hold_target_expiry | ETHUSDT | 23.7% | 10 | 6.54% | 6.89% | ok |
| 15m_30d | london_long_middle_local_next_open | fixed_2r | partial_1r_be_after_half_target | ETHUSDT | 23.7% | 10 | 5.93% | 6.05% | ok |
| 15m_60d | london_long_middle_local_next_open | fixed_1_5r | be_after_half_target | LINKUSDT | 23.5% | 10 | 4.10% | 5.04% | ok |
| 15m_60d | ny_long_neutral_reversal_ce | fixed_1_5r | be_after_half_target | ETHUSDT | 23.4% | 11 | 2.18% | 2.97% | ok |
| 5m_30d | late_us_short_bull_flush_ce | fixed_1_5r | partial_1r_be_after_half_target | SUIUSDT | 23.4% | 11 | 1.53% | 2.51% | ok |
| 15m_60d | london_long_middle_local_next_open | fixed_2r | be_after_half_target | ETHUSDT | 23.2% | 10 | 4.36% | 5.36% | ok |
| 15m_60d | london_long_middle_local_retest | fixed_1_5r | hold_target_expiry | ETHUSDT | 23.1% | 10 | 5.17% | 5.94% | ok |
| 15m_60d | london_long_middle_local_retest | fixed_1_5r | partial_1r_be_after_half_target | LINKUSDT | 23.0% | 10 | 5.13% | 5.51% | ok |
| 15m_60d | ny_long_neutral_reversal_ce | fixed_2r | be_after_half_target | AAVEUSDT | 23.0% | 11 | 2.65% | 3.29% | ok |
| 15m_30d | london_long_middle_local_next_open | fixed_1_5r | be_after_half_target | ETHUSDT | 22.6% | 10 | 6.02% | 6.14% | ok |
| 15m_30d | ny_long_neutral_reversal_ce | fixed_1_5r | hold_target_expiry | SOLUSDT | 22.5% | 11 | 2.13% | 2.97% | ok |
| 15m_60d | london_long_middle_local_next_open | fixed_2r | partial_1r_be_after_half_target | ETHUSDT | 22.4% | 10 | 4.53% | 5.08% | ok |
| 15m_30d | london_long_middle_local_next_open | fixed_1_5r | hold_target_expiry | ETHUSDT | 22.3% | 10 | 5.87% | 6.23% | ok |
| 15m_30d | ny_long_neutral_reversal_ce | fixed_1_5r | be_after_half_target | 1000PEPEUSDT | 22.1% | 11 | 1.46% | 2.43% | ok |
| 15m_30d | london_long_middle_local_next_open | fixed_1_5r | partial_1r_be_after_half_target | ETHUSDT | 21.7% | 10 | 5.84% | 6.01% | ok |
| 15m_30d | london_long_middle_local_retest | fixed_2r | hold_target_expiry | ETHUSDT | 21.6% | 10 | 7.17% | 7.52% | ok |
| 15m_30d | london_long_middle_local_retest | fixed_1_5r | hold_target_expiry | ETHUSDT | 21.6% | 10 | 6.26% | 6.38% | ok |
| 5m_30d | late_us_short_bull_flush_ce | fixed_1_5r | hold_target_expiry | 1000PEPEUSDT | 21.5% | 11 | 2.98% | 3.72% | ok |
| 15m_30d | ny_long_neutral_reversal_ce | fixed_2r | partial_1r_be_after_half_target | 1000PEPEUSDT | 21.5% | 11 | 2.10% | 3.01% | ok |
| 15m_30d | london_long_middle_local_retest | fixed_2r | partial_1r_be_after_half_target | ETHUSDT | 21.3% | 10 | 6.08% | 6.20% | ok |
| 15m_30d | london_long_middle_local_retest | fixed_1_5r | partial_1r_be_after_half_target | ETHUSDT | 21.2% | 10 | 5.71% | 5.88% | ok |
| 15m_60d | late_us_short_bearish_trend_ce | fixed_1_5r | be_after_half_target | SOLUSDT | 21.0% | 11 | 1.98% | 2.51% | ok |
| 15m_30d | late_us_short_bull_flush_ce | fixed_1_5r | partial_1r_be_after_half_target | ETHUSDT | 20.9% | 11 | 5.95% | 5.95% | ok |
| 15m_60d | late_us_short_bearish_trend_ce | fixed_1_5r | partial_1r_be_after_half_target | SOLUSDT | 20.3% | 11 | 2.04% | 2.56% | ok |
| 15m_30d | late_us_short_bull_flush_ce | fixed_1_5r | be_after_half_target | ETHUSDT | 20.2% | 11 | 6.44% | 6.44% | ok |
| 15m_60d | late_us_short_bull_flush_ce | fixed_1_5r | partial_1r_be_after_half_target | NEARUSDT | 20.1% | 11 | 8.18% | 8.18% | ok |
| 15m_30d | ny_long_neutral_reversal_ce | fixed_2r | hold_target_expiry | SOLUSDT | 20.1% | 11 | 2.53% | 3.51% | ok |
| 15m_60d | late_us_short_bearish_trend_ce | fixed_1_5r | hold_target_expiry | SOLUSDT | 20.1% | 11 | 3.50% | 4.12% | ok |
| 15m_30d | late_us_short_bull_flush_ce | fixed_2r | hold_target_expiry | LINKUSDT | 19.7% | 11 | 6.33% | 6.44% | ok |
| 15m_30d | late_us_short_bull_flush_ce | fixed_2r | be_after_half_target | LINKUSDT | 19.6% | 11 | 6.43% | 6.49% | ok |
| 15m_30d | ny_long_neutral_reversal_ce | fixed_2r | be_after_half_target | DOGEUSDT | 19.3% | 11 | 2.09% | 3.25% | ok |
| 15m_60d | late_us_short_bull_flush_ce | fixed_1_5r | be_after_half_target | NEARUSDT | 19.3% | 11 | 8.77% | 8.77% | ok |
| 15m_60d | ny_long_neutral_reversal_ce | fixed_2r | partial_1r_be_after_half_target | SOLUSDT | 19.0% | 11 | 2.60% | 3.34% | ok |
| 15m_60d | london_long_middle_local_retest | fixed_2r | partial_1r_be_after_half_target | ETHUSDT | 18.8% | 10 | 5.23% | 5.55% | ok |
| 15m_60d | late_us_short_bull_flush_ce | fixed_2r | hold_target_expiry | LINKUSDT | 18.6% | 11 | 7.75% | 7.75% | ok |
| 15m_60d | ny_long_neutral_reversal_ce | fixed_1_5r | partial_1r_be_after_half_target | ETHUSDT | 17.8% | 11 | 2.32% | 3.16% | ok |
| 15m_30d | late_us_short_bull_flush_ce | fixed_2r | partial_1r_be_after_half_target | LINKUSDT | 17.4% | 11 | 5.23% | 5.23% | ok |
| 15m_60d | late_us_short_bull_flush_ce | fixed_2r | be_after_half_target | LINKUSDT | 17.2% | 11 | 8.38% | 8.38% | ok |
| 15m_60d | late_us_short_bull_flush_ce | fixed_1_5r | hold_target_expiry | NEARUSDT | 16.7% | 11 | 8.91% | 8.91% | ok |
| 15m_60d | late_us_short_bull_flush_ce | fixed_2r | partial_1r_be_after_half_target | NEARUSDT | 15.2% | 11 | 7.21% | 7.21% | ok |
| 15m_30d | late_us_short_bull_flush_ce | fixed_1_5r | hold_target_expiry | LINKUSDT | 14.3% | 11 | 6.78% | 6.78% | ok |

## Entry Model Leaders

| window | setup_name | target_model | management_model | entry_model | trades | avg_r | profit_factor | win_rate | direction_accuracy | bad_entry_rate | target_too_far_rate | median_bars_to_entry | dominant_failure |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 15m_30d | london_long_middle_local_retest | fixed_1_5r | hold_target_expiry | structure_confirmed_fvg_ce_retest | 8 | +1.183 | inf | 100.0% | 75.0% | 12.5% | 0.0% | 1.0 | none |
| 15m_30d | london_long_middle_local_retest | fixed_2r | hold_target_expiry | structure_confirmed_fvg_ce_retest | 9 | +1.032 | +9.526 | 88.9% | 66.7% | 11.1% | 11.1% | 1.0 | entry |
| 15m_60d | late_us_short_bull_flush_ce | fixed_1_5r | be_after_half_target | structure_confirmed_fvg_ce_retest | 6 | +1.001 | +23.391 | 83.3% | 66.7% | 16.7% | 0.0% | 1.0 | direction |
| 15m_60d | late_us_short_bull_flush_ce | fixed_1_5r | hold_target_expiry | structure_confirmed_fvg_ce_retest | 6 | +1.001 | +23.391 | 83.3% | 66.7% | 16.7% | 0.0% | 1.0 | direction |
| 15m_30d | london_long_middle_local_retest | fixed_1_5r | be_after_half_target | structure_confirmed_fvg_ce_retest | 8 | +0.984 | +20.881 | 87.5% | 75.0% | 12.5% | 0.0% | 1.0 | management |
| 15m_30d | london_long_middle_local_retest | fixed_1_5r | partial_1r_be_after_half_target | structure_confirmed_fvg_ce_retest | 8 | +0.942 | inf | 100.0% | 75.0% | 12.5% | 0.0% | 1.0 | none |
| 15m_30d | london_long_middle_local_retest | fixed_2r | be_after_half_target | structure_confirmed_fvg_ce_retest | 9 | +0.910 | +17.863 | 77.8% | 66.7% | 11.1% | 11.1% | 1.0 | entry |
| 15m_30d | late_us_short_bull_flush_ce | fixed_1_5r | be_after_half_target | structure_confirmed_fvg_ce_retest | 5 | +0.907 | +17.897 | 80.0% | 60.0% | 20.0% | 0.0% | 1.0 | direction |
| 15m_30d | late_us_short_bull_flush_ce | fixed_1_5r | hold_target_expiry | structure_confirmed_fvg_ce_retest | 5 | +0.907 | +17.897 | 80.0% | 60.0% | 20.0% | 0.0% | 1.0 | direction |
| 15m_60d | late_us_short_bull_flush_ce | fixed_1_5r | partial_1r_be_after_half_target | structure_confirmed_fvg_ce_retest | 6 | +0.872 | +20.496 | 83.3% | 66.7% | 16.7% | 0.0% | 1.0 | direction |
| 15m_30d | london_long_middle_local_retest | fixed_2r | partial_1r_be_after_half_target | structure_confirmed_fvg_ce_retest | 9 | +0.834 | inf | 100.0% | 66.7% | 11.1% | 11.1% | 1.0 | none |
| 15m_30d | london_long_middle_local_next_open | fixed_2r | be_after_half_target | structure_confirmed_next_open | 39 | +0.828 | +6.230 | 79.5% | 64.1% | 12.8% | 20.5% | 1.0 | direction |
| 15m_30d | london_long_middle_local_next_open | fixed_2r | hold_target_expiry | structure_confirmed_next_open | 39 | +0.816 | +5.524 | 82.1% | 64.1% | 12.8% | 23.1% | 1.0 | direction |
| 15m_30d | late_us_short_bull_flush_ce | fixed_1_5r | partial_1r_be_after_half_target | structure_confirmed_fvg_ce_retest | 5 | +0.802 | +15.951 | 80.0% | 60.0% | 20.0% | 0.0% | 1.0 | direction |
| 15m_30d | london_long_middle_local_retest | fixed_2r | hold_target_expiry | structure_confirmed_next_open | 31 | +0.757 | +4.939 | 80.6% | 61.3% | 12.9% | 25.8% | 1.0 | direction |
| 15m_30d | london_long_middle_local_retest | fixed_2r | be_after_half_target | structure_confirmed_next_open | 31 | +0.740 | +4.762 | 77.4% | 61.3% | 12.9% | 22.6% | 1.0 | direction |
| 5m_30d | late_us_short_bull_flush_ce | fixed_1_5r | be_after_half_target | structure_confirmed_fvg_ce_retest | 5 | +0.732 | +4.162 | 80.0% | 60.0% | 20.0% | 20.0% | 1.0 | direction |
| 5m_30d | late_us_short_bull_flush_ce | fixed_1_5r | hold_target_expiry | structure_confirmed_fvg_ce_retest | 5 | +0.732 | +4.162 | 80.0% | 60.0% | 20.0% | 20.0% | 1.0 | direction |
| 15m_30d | london_long_middle_local_next_open | fixed_2r | partial_1r_be_after_half_target | structure_confirmed_next_open | 39 | +0.727 | +5.760 | 84.6% | 64.1% | 12.8% | 20.5% | 1.0 | direction |
| 15m_30d | london_long_middle_local_next_open | fixed_1_5r | be_after_half_target | structure_confirmed_next_open | 41 | +0.711 | +5.721 | 80.5% | 68.3% | 12.2% | 17.1% | 1.0 | direction |
| 15m_30d | london_long_middle_local_next_open | fixed_1_5r | hold_target_expiry | structure_confirmed_next_open | 41 | +0.699 | +5.077 | 82.9% | 68.3% | 12.2% | 19.5% | 1.0 | direction |
| 15m_30d | ny_long_neutral_reversal_ce | fixed_2r | hold_target_expiry | fvg_ce_retest | 9 | +0.696 | +2.897 | 66.7% | 88.9% | 33.3% | 22.2% | 1.0 | entry |
| 15m_30d | london_long_middle_local_next_open | fixed_1_5r | partial_1r_be_after_half_target | structure_confirmed_next_open | 41 | +0.683 | +5.700 | 85.4% | 68.3% | 12.2% | 17.1% | 1.0 | direction |
| 15m_60d | late_us_short_bull_flush_ce | fixed_2r | partial_1r_be_after_half_target | structure_confirmed_fvg_ce_retest | 5 | +0.648 | +13.082 | 80.0% | 80.0% | 20.0% | 20.0% | 1.0 | direction |
| 15m_30d | london_long_middle_local_retest | fixed_2r | partial_1r_be_after_half_target | structure_confirmed_next_open | 31 | +0.648 | +4.369 | 80.6% | 61.3% | 12.9% | 22.6% | 1.0 | direction |
| 15m_30d | london_long_middle_local_retest | fixed_1_5r | hold_target_expiry | structure_confirmed_next_open | 32 | +0.636 | +4.413 | 81.2% | 65.6% | 12.5% | 25.0% | 1.0 | direction |
| 15m_60d | london_long_middle_local_retest | fixed_1_5r | hold_target_expiry | structure_confirmed_fvg_ce_retest | 17 | +0.631 | +4.864 | 76.5% | 52.9% | 17.6% | 5.9% | 1.0 | entry |
| 15m_30d | ny_long_neutral_reversal_ce | fixed_2r | hold_target_expiry | next_open | 9 | +0.625 | +4.335 | 66.7% | 77.8% | 11.1% | 44.4% | 1.0 | entry |
| 15m_60d | late_us_short_bull_flush_ce | fixed_2r | be_after_half_target | structure_confirmed_fvg_ce_retest | 5 | +0.621 | +8.767 | 40.0% | 80.0% | 20.0% | 20.0% | 1.0 | management |
| 15m_30d | london_long_middle_local_retest | fixed_1_5r | be_after_half_target | structure_confirmed_next_open | 32 | +0.619 | +4.249 | 78.1% | 65.6% | 12.5% | 21.9% | 1.0 | direction |
| 15m_30d | ny_long_neutral_reversal_ce | fixed_2r | partial_1r_be_after_half_target | next_open | 9 | +0.610 | +4.256 | 66.7% | 77.8% | 11.1% | 33.3% | 1.0 | entry |
| 15m_30d | london_long_middle_local_retest | fixed_1_5r | partial_1r_be_after_half_target | structure_confirmed_next_open | 32 | +0.601 | +4.227 | 81.2% | 65.6% | 12.5% | 21.9% | 1.0 | direction |
| 15m_60d | london_long_middle_local_retest | fixed_2r | hold_target_expiry | structure_confirmed_fvg_ce_retest | 18 | +0.598 | +3.783 | 72.2% | 50.0% | 16.7% | 16.7% | 1.0 | entry |
| 5m_30d | late_us_short_bull_flush_ce | fixed_1_5r | hold_target_expiry | next_open | 23 | +0.588 | +5.019 | 78.3% | 60.9% | 13.0% | 30.4% | 1.0 | direction |
| 15m_60d | late_us_short_bearish_trend_ce | fixed_2r | be_after_half_target | structure_confirmed_next_open | 19 | +0.575 | +8.085 | 78.9% | 47.4% | 15.8% | 26.3% | 1.0 | entry |
| 15m_30d | ny_long_neutral_reversal_ce | fixed_2r | be_after_half_target | next_open | 9 | +0.573 | +3.903 | 55.6% | 77.8% | 11.1% | 33.3% | 1.0 | entry |
| 15m_30d | late_us_short_bull_flush_ce | fixed_2r | hold_target_expiry | fvg_ce_retest | 12 | +0.573 | +2.630 | 58.3% | 75.0% | 33.3% | 25.0% | 1.0 | entry |
| 15m_30d | ny_long_neutral_reversal_ce | fixed_1_5r | hold_target_expiry | fvg_ce_retest | 9 | +0.572 | +2.557 | 66.7% | 88.9% | 33.3% | 0.0% | 1.0 | entry |
| 15m_60d | late_us_short_bearish_trend_ce | fixed_2r | partial_1r_be_after_half_target | structure_confirmed_next_open | 19 | +0.552 | +8.136 | 84.2% | 47.4% | 15.8% | 26.3% | 1.0 | entry |
| 15m_60d | late_us_short_bull_flush_ce | fixed_2r | be_after_half_target | next_open | 33 | +0.545 | +2.859 | 60.6% | 54.5% | 30.3% | 18.2% | 1.0 | direction |

## Decision Rules

- Do not add a new recognition layer if direction accuracy is below 55% on the setup.
- Do not loosen frequency if `bad_entry_rate` rises above 30-35%.
- Do not lower RR globally; target choice is setup/timeframe-specific.
- Treat any setup with only one strong window as regime-dependent until holdout confirms it.
