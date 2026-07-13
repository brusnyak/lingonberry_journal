# Crypto Foundation Validation

Date: 2026-07-13.

## Purpose

- Validate foundation layers before adding new pattern-recognition logic.
- Compare the same canonical setup filters across target and management choices.
- Surface whether failures are direction, entry, stop, target, management, or no-follow-through.

## Confidence By Setup

| setup_name | tested_variants | promote_candidates | research_candidates | best_window | best_target_model | best_management_model | best_avg_r | best_return_to_dd | best_direction_accuracy | dominant_failure | confidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| late_us_short_bull_flush_ce | 6 | 0 | 6 | 15m_60d_reindexed | fixed_2r | be_after_half_target | +0.394 | +7.050 | 52.6% | direction | low |
| ny_long_neutral_reversal_ce | 6 | 0 | 6 | 15m_60d_reindexed | fixed_2r | partial_1r_be_after_half_target | +0.192 | +5.761 | 46.0% | direction | low |
| london_long_middle_local_retest | 6 | 0 | 2 | 15m_60d_reindexed | fixed_1_5r | partial_1r_be_after_half_target | +0.302 | +3.015 | 46.0% | direction | low |
| london_long_middle_local_next_open | 6 | 0 | 3 | 15m_60d_reindexed | fixed_1_5r | partial_1r_be_after_half_target | +0.310 | +2.767 | 45.8% | direction | low |
| late_us_short_bearish_trend_ce | 6 | 0 | 0 | 15m_60d_reindexed | fixed_2r | partial_1r_be_after_half_target | +0.159 | +0.910 | 30.4% | direction | reject |

## Best Promote / Research Candidates

| window | setup_name | target_model | management_model | accepted | avg_r | profit_factor | return_to_dd | win_rate | direction_accuracy | bad_direction_rate | bad_entry_rate | target_too_far_rate | dominant_failure | foundation_grade |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 15m_60d_reindexed | late_us_short_bull_flush_ce | fixed_2r | be_after_half_target | 78 | +0.394 | +2.361 | +7.050 | 57.7% | 52.6% | 24.4% | 29.5% | 24.4% | direction | research_candidate |
| 15m_60d_reindexed | late_us_short_bull_flush_ce | fixed_1_5r | hold_target_expiry | 81 | +0.342 | +2.083 | +6.485 | 61.7% | 51.9% | 23.5% | 29.6% | 11.1% | direction | research_candidate |
| 15m_60d_reindexed | late_us_short_bull_flush_ce | fixed_2r | partial_1r_be_after_half_target | 78 | +0.319 | +2.125 | +5.837 | 65.4% | 52.6% | 24.4% | 29.5% | 24.4% | direction | research_candidate |
| 15m_60d_reindexed | ny_long_neutral_reversal_ce | fixed_2r | partial_1r_be_after_half_target | 202 | +0.192 | +1.740 | +5.761 | 57.4% | 46.0% | 29.2% | 19.8% | 13.9% | direction | research_candidate |
| 15m_60d_reindexed | ny_long_neutral_reversal_ce | fixed_2r | be_after_half_target | 199 | +0.207 | +1.783 | +5.063 | 45.2% | 46.2% | 29.1% | 19.6% | 14.1% | direction | research_candidate |
| 15m_60d_reindexed | ny_long_neutral_reversal_ce | fixed_1_5r | partial_1r_be_after_half_target | 211 | +0.160 | +1.655 | +4.736 | 52.6% | 46.0% | 29.9% | 19.4% | 10.0% | direction | research_candidate |
| 15m_60d_reindexed | late_us_short_bull_flush_ce | fixed_2r | hold_target_expiry | 78 | +0.337 | +1.973 | +4.699 | 57.7% | 52.6% | 24.4% | 29.5% | 26.9% | direction | research_candidate |
| 15m_60d_reindexed | ny_long_neutral_reversal_ce | fixed_2r | hold_target_expiry | 199 | +0.199 | +1.668 | +3.968 | 49.7% | 46.2% | 29.1% | 19.6% | 23.6% | direction | research_candidate |
| 15m_60d_reindexed | ny_long_neutral_reversal_ce | fixed_1_5r | be_after_half_target | 209 | +0.148 | +1.588 | +3.748 | 43.5% | 45.9% | 29.7% | 19.6% | 10.0% | direction | research_candidate |
| 15m_60d_reindexed | late_us_short_bull_flush_ce | fixed_1_5r | be_after_half_target | 77 | +0.288 | +2.049 | +3.587 | 55.8% | 48.1% | 24.7% | 31.2% | 10.4% | direction | research_candidate |
| 15m_60d_reindexed | ny_long_neutral_reversal_ce | fixed_1_5r | hold_target_expiry | 208 | +0.158 | +1.530 | +3.401 | 50.5% | 45.7% | 29.8% | 19.7% | 16.8% | direction | research_candidate |
| 15m_60d_reindexed | late_us_short_bull_flush_ce | fixed_1_5r | partial_1r_be_after_half_target | 77 | +0.267 | +1.985 | +3.193 | 59.7% | 48.1% | 24.7% | 31.2% | 10.4% | direction | research_candidate |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_1_5r | partial_1r_be_after_half_target | 50 | +0.302 | +2.311 | +3.015 | 70.0% | 46.0% | 24.0% | 24.0% | 8.0% | direction | research_candidate |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_1_5r | partial_1r_be_after_half_target | 48 | +0.310 | +2.423 | +2.767 | 70.8% | 45.8% | 22.9% | 22.9% | 8.3% | direction | research_candidate |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_1_5r | be_after_half_target | 48 | +0.303 | +2.307 | +2.235 | 60.4% | 45.8% | 22.9% | 22.9% | 8.3% | direction | research_candidate |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_1_5r | hold_target_expiry | 49 | +0.323 | +2.110 | +2.076 | 69.4% | 46.9% | 22.4% | 22.4% | 12.2% | direction | research_candidate |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_1_5r | hold_target_expiry | 47 | +0.270 | +1.890 | +1.590 | 68.1% | 46.8% | 21.3% | 21.3% | 12.8% | entry | research_candidate |

## Rejected / Weak Foundation Rows

| window | setup_name | target_model | management_model | accepted | avg_r | profit_factor | return_to_dd | win_rate | direction_accuracy | bad_direction_rate | bad_entry_rate | target_too_far_rate | dominant_failure | foundation_grade | foundation_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_2r | partial_1r_be_after_half_target | 48 | +0.297 | +2.264 | +2.842 | 75.0% | 43.8% | 22.9% | 22.9% | 10.4% | direction | reject | direction<45% |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_2r | partial_1r_be_after_half_target | 47 | +0.302 | +2.260 | +2.634 | 74.5% | 42.6% | 23.4% | 23.4% | 10.6% | direction | reject | direction<45% |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_1_5r | be_after_half_target | 49 | +0.279 | +2.092 | +2.226 | 59.2% | 44.9% | 24.5% | 24.5% | 8.2% | direction | reject | direction<45% |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_2r | be_after_half_target | 47 | +0.308 | +2.206 | +2.221 | 61.7% | 42.6% | 23.4% | 23.4% | 10.6% | direction | reject | direction<45% |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_2r | be_after_half_target | 47 | +0.272 | +2.029 | +2.081 | 59.6% | 42.6% | 23.4% | 23.4% | 10.6% | direction | reject | direction<45% |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_2r | hold_target_expiry | 47 | +0.323 | +2.063 | +1.993 | 68.1% | 44.7% | 21.3% | 21.3% | 17.0% | entry | reject | direction<45% |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_2r | hold_target_expiry | 46 | +0.280 | +1.903 | +1.612 | 67.4% | 43.5% | 21.7% | 21.7% | 17.4% | entry | reject | direction<45% |
| 15m_60d_reindexed | late_us_short_bearish_trend_ce | fixed_2r | partial_1r_be_after_half_target | 46 | +0.159 | +1.803 | +0.910 | 63.0% | 30.4% | 41.3% | 21.7% | 17.4% | direction | reject | direction<45% |
| 15m_60d_reindexed | late_us_short_bearish_trend_ce | fixed_1_5r | partial_1r_be_after_half_target | 46 | +0.150 | +1.747 | +0.845 | 58.7% | 30.4% | 41.3% | 21.7% | 15.2% | direction | reject | direction<45% |
| 15m_60d_reindexed | late_us_short_bearish_trend_ce | fixed_2r | be_after_half_target | 46 | +0.124 | +1.599 | +0.688 | 54.3% | 30.4% | 41.3% | 21.7% | 17.4% | direction | reject | direction<45% |
| 15m_60d_reindexed | late_us_short_bearish_trend_ce | fixed_1_5r | hold_target_expiry | 46 | +0.112 | +1.457 | +0.625 | 58.7% | 30.4% | 41.3% | 21.7% | 15.2% | direction | reject | direction<45% |
| 15m_60d_reindexed | late_us_short_bearish_trend_ce | fixed_1_5r | be_after_half_target | 46 | +0.113 | +1.549 | +0.617 | 54.3% | 30.4% | 41.3% | 21.7% | 15.2% | direction | reject | direction<45% |
| 15m_60d_reindexed | late_us_short_bearish_trend_ce | fixed_2r | hold_target_expiry | 46 | +0.038 | +1.129 | +0.169 | 54.3% | 30.4% | 41.3% | 21.7% | 19.6% | direction | reject | pf<1.25, direction<45% |

## Concentration Warning

| window | setup_name | target_model | management_model | top_symbol | top_symbol_positive_return_share | symbols | net_return_pct | positive_return_pct | warning |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_2r | be_after_half_target | ETHUSDT | 52.4% | 14 | 2.56% | 3.11% | concentrated |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_2r | hold_target_expiry | ETHUSDT | 47.8% | 14 | 2.58% | 3.42% | ok |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_2r | be_after_half_target | ETHUSDT | 47.3% | 14 | 2.90% | 3.46% | ok |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_2r | partial_1r_be_after_half_target | ETHUSDT | 43.5% | 14 | 2.84% | 3.29% | ok |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_1_5r | be_after_half_target | ETHUSDT | 42.4% | 14 | 2.73% | 3.25% | ok |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_2r | hold_target_expiry | ETHUSDT | 42.2% | 14 | 3.04% | 3.86% | ok |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_1_5r | hold_target_expiry | ETHUSDT | 41.9% | 14 | 2.54% | 3.31% | ok |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_2r | partial_1r_be_after_half_target | ETHUSDT | 40.6% | 14 | 2.85% | 3.25% | ok |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_1_5r | be_after_half_target | ETHUSDT | 40.0% | 14 | 2.91% | 3.46% | ok |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_1_5r | partial_1r_be_after_half_target | ETHUSDT | 38.9% | 14 | 2.98% | 3.36% | ok |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_1_5r | partial_1r_be_after_half_target | ETHUSDT | 36.8% | 14 | 3.02% | 3.38% | ok |
| 15m_60d_reindexed | late_us_short_bearish_trend_ce | fixed_2r | hold_target_expiry | BTCUSDT | 36.5% | 13 | 0.35% | 1.65% | ok |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_1_5r | hold_target_expiry | ETHUSDT | 35.1% | 14 | 3.16% | 3.93% | ok |
| 15m_60d_reindexed | late_us_short_bearish_trend_ce | fixed_2r | be_after_half_target | BTCUSDT | 32.7% | 13 | 1.14% | 1.84% | ok |
| 15m_60d_reindexed | late_us_short_bearish_trend_ce | fixed_1_5r | be_after_half_target | AAVEUSDT | 31.9% | 13 | 1.04% | 1.58% | ok |
| 15m_60d_reindexed | late_us_short_bearish_trend_ce | fixed_1_5r | partial_1r_be_after_half_target | AAVEUSDT | 29.9% | 13 | 1.38% | 1.75% | ok |
| 15m_60d_reindexed | late_us_short_bearish_trend_ce | fixed_2r | partial_1r_be_after_half_target | AAVEUSDT | 27.7% | 13 | 1.46% | 1.89% | ok |
| 15m_60d_reindexed | late_us_short_bearish_trend_ce | fixed_1_5r | hold_target_expiry | AAVEUSDT | 26.7% | 13 | 1.03% | 1.89% | ok |
| 15m_60d_reindexed | ny_long_neutral_reversal_ce | fixed_2r | partial_1r_be_after_half_target | XRPUSDT | 24.6% | 14 | 7.76% | 8.12% | ok |
| 15m_60d_reindexed | ny_long_neutral_reversal_ce | fixed_1_5r | hold_target_expiry | XRPUSDT | 23.6% | 14 | 6.58% | 7.46% | ok |
| 15m_60d_reindexed | ny_long_neutral_reversal_ce | fixed_2r | be_after_half_target | XRPUSDT | 23.2% | 14 | 8.25% | 8.64% | ok |
| 15m_60d_reindexed | ny_long_neutral_reversal_ce | fixed_2r | hold_target_expiry | XRPUSDT | 22.4% | 14 | 7.94% | 8.42% | ok |
| 15m_60d_reindexed | ny_long_neutral_reversal_ce | fixed_1_5r | be_after_half_target | ETHUSDT | 20.4% | 14 | 6.18% | 7.08% | ok |
| 15m_60d_reindexed | ny_long_neutral_reversal_ce | fixed_1_5r | partial_1r_be_after_half_target | ETHUSDT | 20.3% | 14 | 6.76% | 7.34% | ok |
| 15m_60d_reindexed | late_us_short_bull_flush_ce | fixed_2r | hold_target_expiry | WLDUSDT | 18.2% | 14 | 5.26% | 6.34% | ok |
| 15m_60d_reindexed | late_us_short_bull_flush_ce | fixed_1_5r | be_after_half_target | NEARUSDT | 18.0% | 14 | 4.43% | 6.01% | ok |
| 15m_60d_reindexed | late_us_short_bull_flush_ce | fixed_1_5r | partial_1r_be_after_half_target | NEARUSDT | 17.7% | 14 | 4.11% | 5.54% | ok |
| 15m_60d_reindexed | late_us_short_bull_flush_ce | fixed_2r | partial_1r_be_after_half_target | WLDUSDT | 16.9% | 14 | 4.98% | 5.63% | ok |
| 15m_60d_reindexed | late_us_short_bull_flush_ce | fixed_2r | be_after_half_target | WLDUSDT | 16.4% | 14 | 6.15% | 7.03% | ok |
| 15m_60d_reindexed | late_us_short_bull_flush_ce | fixed_1_5r | hold_target_expiry | NEARUSDT | 15.9% | 14 | 5.54% | 6.82% | ok |

## Entry Model Leaders

| window | setup_name | target_model | management_model | entry_model | trades | avg_r | profit_factor | win_rate | direction_accuracy | bad_entry_rate | target_too_far_rate | median_bars_to_entry | dominant_failure |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_1_5r | hold_target_expiry | structure_confirmed_fvg_ce_retest | 7 | +0.963 | inf | 100.0% | 57.1% | 14.3% | 0.0% | 1.0 | none |
| 15m_60d_reindexed | late_us_short_bull_flush_ce | fixed_1_5r | hold_target_expiry | fvg_ce_retest | 17 | +0.832 | +5.685 | 70.6% | 76.5% | 29.4% | 5.9% | 1.0 | entry |
| 15m_60d_reindexed | late_us_short_bull_flush_ce | fixed_2r | be_after_half_target | fvg_ce_retest | 17 | +0.795 | +5.637 | 58.8% | 76.5% | 29.4% | 17.6% | 1.0 | entry |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_1_5r | be_after_half_target | structure_confirmed_fvg_ce_retest | 7 | +0.735 | +14.000 | 85.7% | 57.1% | 14.3% | 0.0% | 1.0 | management |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_1_5r | partial_1r_be_after_half_target | structure_confirmed_fvg_ce_retest | 7 | +0.726 | inf | 100.0% | 57.1% | 14.3% | 0.0% | 1.0 | none |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_2r | hold_target_expiry | structure_confirmed_fvg_ce_retest | 7 | +0.695 | +5.465 | 85.7% | 57.1% | 14.3% | 14.3% | 1.0 | entry |
| 15m_60d_reindexed | late_us_short_bull_flush_ce | fixed_2r | partial_1r_be_after_half_target | fvg_ce_retest | 17 | +0.663 | +5.254 | 76.5% | 76.5% | 29.4% | 17.6% | 1.0 | entry |
| 15m_60d_reindexed | late_us_short_bull_flush_ce | fixed_2r | hold_target_expiry | fvg_ce_retest | 17 | +0.661 | +3.164 | 58.8% | 76.5% | 29.4% | 23.5% | 1.0 | entry |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_2r | partial_1r_be_after_half_target | structure_confirmed_fvg_ce_retest | 7 | +0.588 | inf | 100.0% | 57.1% | 14.3% | 14.3% | 1.0 | none |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_2r | be_after_half_target | structure_confirmed_fvg_ce_retest | 7 | +0.538 | +8.753 | 71.4% | 57.1% | 14.3% | 14.3% | 1.0 | entry |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_2r | hold_target_expiry | structure_confirmed_next_open | 34 | +0.489 | +3.853 | 79.4% | 41.2% | 11.8% | 17.6% | 1.0 | direction |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_1_5r | hold_target_expiry | structure_confirmed_next_open | 36 | +0.486 | +4.002 | 80.6% | 44.4% | 11.1% | 11.1% | 1.0 | direction |
| 15m_60d_reindexed | late_us_short_bull_flush_ce | fixed_1_5r | be_after_half_target | fvg_ce_retest | 16 | +0.469 | +2.850 | 50.0% | 68.8% | 37.5% | 0.0% | 1.0 | entry |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_2r | hold_target_expiry | structure_confirmed_next_open | 27 | +0.452 | +3.566 | 77.8% | 37.0% | 11.1% | 18.5% | 1.0 | direction |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_2r | be_after_half_target | structure_confirmed_next_open | 35 | +0.446 | +3.537 | 71.4% | 40.0% | 14.3% | 11.4% | 1.0 | direction |
| 15m_60d_reindexed | late_us_short_bull_flush_ce | fixed_1_5r | partial_1r_be_after_half_target | structure_confirmed_fvg_ce_retest | 8 | +0.432 | +3.684 | 75.0% | 62.5% | 25.0% | 25.0% | 1.0 | other |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_1_5r | be_after_half_target | structure_confirmed_next_open | 37 | +0.426 | +3.501 | 70.3% | 43.2% | 13.5% | 8.1% | 1.0 | direction |
| 15m_60d_reindexed | late_us_short_bull_flush_ce | fixed_1_5r | partial_1r_be_after_half_target | fvg_ce_retest | 16 | +0.419 | +2.690 | 56.2% | 68.8% | 37.5% | 0.0% | 1.0 | entry |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_1_5r | hold_target_expiry | structure_confirmed_next_open | 30 | +0.417 | +3.152 | 76.7% | 40.0% | 13.3% | 13.3% | 1.0 | direction |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_2r | partial_1r_be_after_half_target | structure_confirmed_next_open | 35 | +0.410 | +3.439 | 80.0% | 40.0% | 14.3% | 11.4% | 1.0 | direction |
| 15m_60d_reindexed | late_us_short_bull_flush_ce | fixed_2r | be_after_half_target | next_open | 25 | +0.395 | +2.074 | 60.0% | 48.0% | 40.0% | 20.0% | 1.0 | direction |
| 15m_60d_reindexed | ny_long_neutral_reversal_ce | fixed_2r | hold_target_expiry | fvg_ce_retest | 39 | +0.394 | +1.926 | 56.4% | 66.7% | 38.5% | 15.4% | 1.0 | direction |
| 15m_60d_reindexed | london_long_middle_local_next_open | fixed_1_5r | partial_1r_be_after_half_target | structure_confirmed_next_open | 37 | +0.394 | +3.398 | 75.7% | 43.2% | 13.5% | 8.1% | 1.0 | direction |
| 15m_60d_reindexed | late_us_short_bull_flush_ce | fixed_1_5r | be_after_half_target | structure_confirmed_fvg_ce_retest | 8 | +0.381 | +3.188 | 62.5% | 62.5% | 25.0% | 25.0% | 1.0 | entry |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_2r | be_after_half_target | structure_confirmed_next_open | 28 | +0.364 | +2.676 | 67.9% | 35.7% | 14.3% | 10.7% | 1.0 | direction |
| 15m_60d_reindexed | ny_long_neutral_reversal_ce | fixed_2r | be_after_half_target | fvg_ce_retest | 39 | +0.361 | +1.976 | 46.2% | 66.7% | 38.5% | 5.1% | 1.0 | direction |
| 15m_60d_reindexed | ny_long_neutral_reversal_ce | fixed_1_5r | hold_target_expiry | fvg_ce_retest | 40 | +0.357 | +1.888 | 60.0% | 67.5% | 37.5% | 2.5% | 1.0 | direction |
| 15m_60d_reindexed | late_us_short_bull_flush_ce | fixed_2r | hold_target_expiry | next_open | 25 | +0.355 | +1.870 | 60.0% | 48.0% | 40.0% | 20.0% | 1.0 | direction |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_2r | partial_1r_be_after_half_target | structure_confirmed_next_open | 28 | +0.338 | +2.609 | 75.0% | 35.7% | 14.3% | 10.7% | 1.0 | direction |
| 15m_60d_reindexed | ny_long_neutral_reversal_ce | fixed_2r | be_after_half_target | structure_confirmed_fvg_ce_retest | 24 | +0.326 | +2.071 | 41.7% | 50.0% | 29.2% | 12.5% | 1.0 | direction |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_1_5r | be_after_half_target | structure_confirmed_next_open | 31 | +0.315 | +2.341 | 64.5% | 38.7% | 16.1% | 9.7% | 1.0 | direction |
| 15m_60d_reindexed | london_long_middle_local_retest | fixed_1_5r | partial_1r_be_after_half_target | structure_confirmed_next_open | 31 | +0.287 | +2.245 | 67.7% | 38.7% | 16.1% | 9.7% | 1.0 | direction |
| 15m_60d_reindexed | late_us_short_bull_flush_ce | fixed_1_5r | be_after_half_target | structure_confirmed_next_open | 30 | +0.269 | +2.093 | 60.0% | 36.7% | 20.0% | 16.7% | 1.0 | direction |
| 15m_60d_reindexed | ny_long_neutral_reversal_ce | fixed_2r | hold_target_expiry | structure_confirmed_fvg_ce_retest | 24 | +0.265 | +1.689 | 45.8% | 50.0% | 29.2% | 16.7% | 1.0 | direction |
| 15m_60d_reindexed | late_us_short_bull_flush_ce | fixed_2r | partial_1r_be_after_half_target | next_open | 25 | +0.259 | +1.709 | 64.0% | 48.0% | 40.0% | 20.0% | 1.0 | direction |
| 15m_60d_reindexed | ny_long_neutral_reversal_ce | fixed_2r | partial_1r_be_after_half_target | structure_confirmed_fvg_ce_retest | 25 | +0.253 | +1.886 | 56.0% | 52.0% | 28.0% | 12.0% | 1.0 | direction |
| 15m_60d_reindexed | late_us_short_bull_flush_ce | fixed_2r | partial_1r_be_after_half_target | structure_confirmed_fvg_ce_retest | 7 | +0.252 | +1.992 | 71.4% | 71.4% | 28.6% | 42.9% | 1.0 | no_follow_through |
| 15m_60d_reindexed | ny_long_neutral_reversal_ce | fixed_2r | partial_1r_be_after_half_target | fvg_ce_retest | 40 | +0.252 | +1.671 | 62.5% | 65.0% | 40.0% | 5.0% | 1.0 | direction |
| 15m_60d_reindexed | late_us_short_bull_flush_ce | fixed_1_5r | partial_1r_be_after_half_target | structure_confirmed_next_open | 30 | +0.241 | +1.978 | 60.0% | 36.7% | 20.0% | 16.7% | 1.0 | direction |
| 15m_60d_reindexed | late_us_short_bull_flush_ce | fixed_1_5r | hold_target_expiry | next_open | 25 | +0.238 | +1.583 | 60.0% | 48.0% | 40.0% | 4.0% | 1.0 | direction |

## Decision Rules

- Do not add a new recognition layer if direction accuracy is below 55% on the setup.
- Do not loosen frequency if `bad_entry_rate` rises above 30-35%.
- Do not lower RR globally; target choice is setup/timeframe-specific.
- Treat any setup with only one strong window as regime-dependent until holdout confirms it.
