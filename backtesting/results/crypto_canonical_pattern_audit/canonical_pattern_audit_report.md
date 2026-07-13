# Crypto Canonical Pattern Audit

Date: 2026-07-13.

## Purpose

- Measure direction accuracy, best/worst trading hours, entry trigger quality, and path failure modes.
- Export review samples for best winners, clean winners, worst losers, bad-direction losers, and target-too-far cases.

## Setup Stats

| setup_name | trades | avg_r | median_r | profit_factor | win_rate | direction_accuracy | clean_path_rate | bad_direction_rate | bad_entry_rate | target_too_far_rate | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r | median_bars_to_exit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| late_us_short_bull_flush_ce | 85 | +0.493 | +0.386 | +3.226 | 60.0% | 56.5% | 35.3% | 24.7% | 23.5% | 23.5% | 20.0% | 15.3% | 52.9% | +1.287 | -0.454 | 24.0 |
| london_long_middle_local_retest | 76 | +0.320 | +0.246 | +2.158 | 55.3% | 51.3% | 36.8% | 23.7% | 26.3% | 14.5% | 21.1% | 18.4% | 44.7% | +1.042 | -0.395 | 18.5 |
| london_long_middle_local_next_open | 75 | +0.291 | +0.137 | +2.003 | 54.7% | 50.7% | 36.0% | 26.7% | 26.7% | 16.0% | 20.0% | 20.0% | 45.3% | +1.014 | -0.449 | 19.0 |
| late_us_short_bearish_trend_ce | 56 | +0.248 | +0.168 | +1.799 | 58.9% | 46.4% | 28.6% | 32.1% | 28.6% | 23.2% | 14.3% | 25.0% | 60.7% | +0.838 | -0.444 | 24.0 |
| ny_long_neutral_reversal_ce | 147 | +0.090 | -0.051 | +1.291 | 45.6% | 40.1% | 21.8% | 27.9% | 25.2% | 13.6% | 11.6% | 21.1% | 57.1% | +0.774 | -0.524 | 24.0 |

## Best Setup/Hour Buckets

| setup_name | entry_hour_utc | trades | avg_r | median_r | profit_factor | win_rate | direction_accuracy | clean_path_rate | bad_direction_rate | bad_entry_rate | target_too_far_rate | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r | median_bars_to_exit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| london_long_middle_local_next_open | 10 | 10 | +0.825 | +1.067 | +5.997 | 60.0% | 70.0% | 60.0% | 20.0% | 20.0% | 0.0% | 50.0% | 10.0% | 20.0% | +1.906 | -0.159 | 8.5 |
| london_long_middle_local_retest | 10 | 11 | +0.812 | +0.702 | +6.333 | 63.6% | 63.6% | 54.5% | 18.2% | 18.2% | 0.0% | 45.5% | 9.1% | 27.3% | +1.743 | -0.125 | 12.0 |
| late_us_short_bull_flush_ce | 22 | 18 | +0.713 | +0.474 | +5.735 | 66.7% | 66.7% | 50.0% | 22.2% | 16.7% | 22.2% | 27.8% | 11.1% | 44.4% | +1.566 | -0.159 | 23.5 |
| late_us_short_bull_flush_ce | 21 | 21 | +0.648 | +0.703 | +5.305 | 61.9% | 71.4% | 47.6% | 19.0% | 23.8% | 28.6% | 23.8% | 9.5% | 47.6% | +1.684 | -0.444 | 24.0 |
| london_long_middle_local_retest | 11 | 10 | +0.597 | +0.641 | +3.591 | 60.0% | 80.0% | 80.0% | 10.0% | 20.0% | 30.0% | 30.0% | 20.0% | 30.0% | +1.462 | -0.118 | 17.0 |
| london_long_middle_local_next_open | 11 | 10 | +0.583 | +0.641 | +3.539 | 60.0% | 80.0% | 80.0% | 20.0% | 20.0% | 30.0% | 30.0% | 20.0% | 30.0% | +1.455 | -0.140 | 17.0 |
| ny_long_neutral_reversal_ce | 18 | 14 | +0.582 | +0.917 | +2.926 | 64.3% | 71.4% | 28.6% | 7.1% | 42.9% | 28.6% | 28.6% | 21.4% | 42.9% | +1.489 | -0.701 | 18.5 |
| london_long_middle_local_retest | 7 | 11 | +0.533 | +0.487 | +8.187 | 81.8% | 54.5% | 27.3% | 0.0% | 9.1% | 36.4% | 9.1% | 0.0% | 81.8% | +1.070 | -0.115 | 24.0 |
| late_us_short_bearish_trend_ce | 22 | 22 | +0.520 | +0.443 | +4.096 | 68.2% | 45.5% | 40.9% | 36.4% | 18.2% | 27.3% | 18.2% | 13.6% | 68.2% | +0.790 | -0.425 | 24.0 |
| london_long_middle_local_next_open | 7 | 11 | +0.501 | +0.487 | +7.337 | 81.8% | 54.5% | 27.3% | 0.0% | 9.1% | 45.5% | 0.0% | 0.0% | 90.9% | +1.070 | -0.273 | 24.0 |
| london_long_middle_local_next_open | 9 | 15 | +0.455 | +0.272 | +2.835 | 60.0% | 53.3% | 40.0% | 33.3% | 20.0% | 20.0% | 26.7% | 20.0% | 46.7% | +1.101 | -0.674 | 19.0 |
| ny_long_neutral_reversal_ce | 19 | 11 | +0.374 | +0.233 | +2.245 | 63.6% | 45.5% | 9.1% | 9.1% | 36.4% | 9.1% | 27.3% | 27.3% | 36.4% | +0.842 | -0.629 | 17.0 |
| ny_long_neutral_reversal_ce | 13 | 27 | +0.345 | -0.037 | +2.140 | 48.1% | 51.9% | 33.3% | 29.6% | 22.2% | 18.5% | 22.2% | 22.2% | 44.4% | +1.043 | -0.604 | 15.0 |
| london_long_middle_local_retest | 9 | 15 | +0.306 | +0.093 | +2.125 | 53.3% | 53.3% | 40.0% | 33.3% | 20.0% | 20.0% | 20.0% | 20.0% | 46.7% | +1.101 | -0.667 | 19.0 |
| late_us_short_bull_flush_ce | 20 | 28 | +0.305 | +0.105 | +1.839 | 53.6% | 46.4% | 21.4% | 28.6% | 32.1% | 21.4% | 17.9% | 25.0% | 53.6% | +0.964 | -0.690 | 24.0 |
| late_us_short_bearish_trend_ce | 21 | 17 | +0.280 | +0.039 | +1.860 | 52.9% | 47.1% | 17.6% | 29.4% | 29.4% | 11.8% | 23.5% | 23.5% | 52.9% | +0.948 | -0.587 | 24.0 |
| late_us_short_bull_flush_ce | 23 | 14 | +0.234 | +0.165 | +2.194 | 50.0% | 35.7% | 21.4% | 35.7% | 21.4% | 7.1% | 14.3% | 14.3% | 57.1% | +0.691 | -0.298 | 24.0 |
| late_us_short_bearish_trend_ce | 23 | 9 | +0.204 | +0.420 | +1.755 | 77.8% | 55.6% | 22.2% | 11.1% | 22.2% | 33.3% | 0.0% | 22.2% | 77.8% | +1.283 | -0.384 | 24.0 |
| london_long_middle_local_retest | 8 | 20 | +0.090 | -0.074 | +1.247 | 45.0% | 40.0% | 15.0% | 25.0% | 45.0% | 5.0% | 15.0% | 25.0% | 40.0% | +0.833 | -0.940 | 18.5 |
| ny_long_neutral_reversal_ce | 17 | 20 | +0.023 | -0.098 | +1.103 | 40.0% | 20.0% | 10.0% | 40.0% | 10.0% | 10.0% | 5.0% | 10.0% | 85.0% | +0.571 | -0.340 | 24.0 |
| london_long_middle_local_next_open | 8 | 20 | +0.011 | -0.074 | +1.027 | 45.0% | 35.0% | 15.0% | 30.0% | 45.0% | 5.0% | 15.0% | 30.0% | 40.0% | +0.783 | -0.940 | 18.5 |
| ny_long_neutral_reversal_ce | 15 | 9 | -0.041 | -0.027 | +0.830 | 44.4% | 22.2% | 11.1% | 44.4% | 22.2% | 11.1% | 0.0% | 11.1% | 77.8% | +0.553 | -0.493 | 24.0 |
| ny_long_neutral_reversal_ce | 16 | 35 | -0.068 | -0.066 | +0.800 | 45.7% | 51.4% | 31.4% | 20.0% | 25.7% | 14.3% | 5.7% | 25.7% | 51.4% | +1.032 | -0.386 | 24.0 |
| ny_long_neutral_reversal_ce | 14 | 24 | -0.195 | -0.118 | +0.477 | 29.2% | 25.0% | 16.7% | 41.7% | 29.2% | 8.3% | 4.2% | 25.0% | 58.3% | +0.517 | -0.595 | 24.0 |
| ny_long_neutral_reversal_ce | 20 | 7 | -0.197 | -0.198 | +0.431 | 42.9% | 0.0% | 0.0% | 28.6% | 14.3% | 0.0% | 0.0% | 14.3% | 85.7% | +0.522 | -0.745 | 24.0 |
| late_us_short_bearish_trend_ce | 20 | 5 | -0.207 | -0.410 | +0.596 | 40.0% | 60.0% | 40.0% | 20.0% | 40.0% | 40.0% | 0.0% | 40.0% | 60.0% | +1.015 | -0.580 | 24.0 |
| london_long_middle_local_retest | 12 | 6 | -0.327 | -0.799 | +0.482 | 16.7% | 33.3% | 33.3% | 66.7% | 33.3% | 0.0% | 16.7% | 33.3% | 33.3% | +0.289 | -0.941 | 15.0 |
| london_long_middle_local_next_open | 12 | 6 | -0.660 | -0.799 | +0.000 | 0.0% | 33.3% | 16.7% | 66.7% | 33.3% | 0.0% | 0.0% | 33.3% | 33.3% | +0.289 | -0.941 | 17.5 |

## Best Setup/Symbol Buckets

| setup_name | symbol | trades | avg_r | median_r | profit_factor | win_rate | direction_accuracy | clean_path_rate | bad_direction_rate | bad_entry_rate | target_too_far_rate | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r | median_bars_to_exit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| late_us_short_bull_flush_ce | LINKUSDT | 7 | +1.031 | +1.471 | +7.012 | 85.7% | 71.4% | 71.4% | 14.3% | 14.3% | 28.6% | 42.9% | 14.3% | 42.9% | +1.534 | -0.143 | 24.0 |
| london_long_middle_local_retest | 1000PEPEUSDT | 5 | +0.910 | +1.114 | +5.216 | 80.0% | 80.0% | 60.0% | 20.0% | 20.0% | 40.0% | 40.0% | 20.0% | 40.0% | +1.712 | -0.178 | 22.0 |
| late_us_short_bearish_trend_ce | NEARUSDT | 4 | +0.902 | +1.329 | +4.508 | 75.0% | 50.0% | 25.0% | 0.0% | 50.0% | 0.0% | 50.0% | 25.0% | 25.0% | +1.475 | -0.883 | 19.0 |
| london_long_middle_local_next_open | 1000PEPEUSDT | 5 | +0.850 | +0.956 | +4.940 | 80.0% | 80.0% | 60.0% | 20.0% | 20.0% | 40.0% | 40.0% | 20.0% | 40.0% | +1.508 | -0.178 | 22.0 |
| late_us_short_bearish_trend_ce | SOLUSDT | 7 | +0.736 | +0.504 | +5.827 | 85.7% | 71.4% | 71.4% | 28.6% | 14.3% | 42.9% | 28.6% | 14.3% | 57.1% | +1.085 | -0.282 | 24.0 |
| late_us_short_bull_flush_ce | DOGEUSDT | 5 | +0.715 | +1.240 | +3.828 | 60.0% | 60.0% | 60.0% | 40.0% | 20.0% | 40.0% | 20.0% | 20.0% | 60.0% | +1.537 | -0.411 | 24.0 |
| london_long_middle_local_retest | ETHUSDT | 10 | +0.626 | +0.372 | +3.857 | 60.0% | 50.0% | 50.0% | 20.0% | 10.0% | 0.0% | 40.0% | 10.0% | 40.0% | +1.365 | -0.171 | 12.5 |
| london_long_middle_local_next_open | ETHUSDT | 10 | +0.621 | +0.353 | +3.775 | 60.0% | 50.0% | 50.0% | 20.0% | 10.0% | 0.0% | 40.0% | 10.0% | 40.0% | +1.214 | -0.214 | 12.5 |
| late_us_short_bearish_trend_ce | WLDUSDT | 4 | +0.614 | +0.770 | +2.668 | 50.0% | 75.0% | 0.0% | 25.0% | 25.0% | 0.0% | 50.0% | 25.0% | 25.0% | +1.980 | -0.772 | 22.5 |
| london_long_middle_local_next_open | LINKUSDT | 8 | +0.590 | +0.441 | +6.619 | 75.0% | 50.0% | 25.0% | 12.5% | 12.5% | 12.5% | 25.0% | 0.0% | 62.5% | +0.944 | -0.190 | 24.0 |
| london_long_middle_local_retest | LINKUSDT | 8 | +0.590 | +0.441 | +6.619 | 75.0% | 50.0% | 25.0% | 12.5% | 12.5% | 12.5% | 25.0% | 0.0% | 62.5% | +0.944 | -0.190 | 24.0 |
| late_us_short_bull_flush_ce | AVAXUSDT | 7 | +0.562 | +0.589 | +4.445 | 71.4% | 85.7% | 57.1% | 0.0% | 14.3% | 42.9% | 14.3% | 14.3% | 57.1% | +1.571 | -0.233 | 24.0 |
| late_us_short_bull_flush_ce | ETHUSDT | 10 | +0.538 | +0.557 | +2.951 | 60.0% | 60.0% | 40.0% | 10.0% | 40.0% | 30.0% | 20.0% | 20.0% | 50.0% | +1.421 | -0.602 | 20.5 |
| late_us_short_bull_flush_ce | WLDUSDT | 11 | +0.527 | -0.002 | +3.721 | 45.5% | 54.5% | 27.3% | 45.5% | 9.1% | 18.2% | 27.3% | 9.1% | 54.5% | +1.068 | -0.535 | 24.0 |
| late_us_short_bull_flush_ce | XRPUSDT | 6 | +0.521 | +0.725 | +3.020 | 66.7% | 50.0% | 50.0% | 33.3% | 16.7% | 33.3% | 16.7% | 16.7% | 66.7% | +0.979 | -0.218 | 24.0 |
| london_long_middle_local_next_open | DOGEUSDT | 10 | +0.486 | +0.548 | +2.568 | 60.0% | 50.0% | 40.0% | 10.0% | 20.0% | 10.0% | 30.0% | 20.0% | 40.0% | +1.248 | -0.312 | 20.5 |
| london_long_middle_local_retest | SUIUSDT | 7 | +0.485 | +0.446 | +7.307 | 71.4% | 57.1% | 42.9% | 28.6% | 14.3% | 28.6% | 14.3% | 0.0% | 71.4% | +1.070 | -0.354 | 24.0 |
| late_us_short_bull_flush_ce | AAVEUSDT | 9 | +0.462 | +0.332 | +2.718 | 55.6% | 33.3% | 11.1% | 44.4% | 11.1% | 0.0% | 33.3% | 11.1% | 55.6% | +0.563 | -0.454 | 24.0 |
| london_long_middle_local_next_open | SUIUSDT | 7 | +0.457 | +0.446 | +6.951 | 71.4% | 57.1% | 42.9% | 28.6% | 14.3% | 28.6% | 14.3% | 0.0% | 71.4% | +1.070 | -0.449 | 24.0 |
| late_us_short_bull_flush_ce | 1000PEPEUSDT | 7 | +0.435 | +0.482 | +3.903 | 85.7% | 42.9% | 28.6% | 42.9% | 14.3% | 42.9% | 0.0% | 14.3% | 85.7% | +0.638 | -0.162 | 24.0 |
| london_long_middle_local_retest | XRPUSDT | 10 | +0.364 | +0.326 | +2.548 | 60.0% | 50.0% | 50.0% | 30.0% | 20.0% | 20.0% | 20.0% | 20.0% | 50.0% | +1.044 | -0.285 | 21.5 |
| london_long_middle_local_next_open | XRPUSDT | 10 | +0.354 | +0.292 | +2.481 | 60.0% | 50.0% | 50.0% | 30.0% | 20.0% | 20.0% | 20.0% | 20.0% | 50.0% | +1.003 | -0.299 | 21.5 |
| late_us_short_bull_flush_ce | NEARUSDT | 10 | +0.351 | +0.208 | +21.767 | 60.0% | 60.0% | 20.0% | 10.0% | 20.0% | 20.0% | 0.0% | 0.0% | 60.0% | +1.228 | -0.625 | 24.0 |
| late_us_short_bearish_trend_ce | 1000PEPEUSDT | 7 | +0.346 | +0.389 | +3.215 | 71.4% | 42.9% | 42.9% | 28.6% | 14.3% | 42.9% | 0.0% | 14.3% | 85.7% | +0.844 | -0.420 | 24.0 |
| ny_long_neutral_reversal_ce | AAVEUSDT | 11 | +0.344 | +0.236 | +2.020 | 63.6% | 54.5% | 27.3% | 27.3% | 27.3% | 27.3% | 18.2% | 27.3% | 54.5% | +1.101 | -0.711 | 24.0 |
| london_long_middle_local_retest | DOGEUSDT | 10 | +0.262 | +0.077 | +1.749 | 50.0% | 50.0% | 40.0% | 10.0% | 20.0% | 10.0% | 20.0% | 20.0% | 40.0% | +1.248 | -0.312 | 20.5 |
| late_us_short_bearish_trend_ce | ETHUSDT | 8 | +0.229 | -0.000 | +1.987 | 50.0% | 37.5% | 25.0% | 37.5% | 12.5% | 12.5% | 12.5% | 12.5% | 75.0% | +0.649 | -0.271 | 24.0 |
| ny_long_neutral_reversal_ce | SOLUSDT | 15 | +0.217 | +0.069 | +2.149 | 60.0% | 40.0% | 26.7% | 20.0% | 13.3% | 20.0% | 6.7% | 13.3% | 73.3% | +0.686 | -0.266 | 24.0 |
| late_us_short_bull_flush_ce | SOLUSDT | 9 | +0.216 | -0.092 | +1.572 | 44.4% | 55.6% | 22.2% | 11.1% | 66.7% | 11.1% | 22.2% | 33.3% | 22.2% | +1.042 | -1.233 | 16.0 |
| ny_long_neutral_reversal_ce | ETHUSDT | 13 | +0.168 | +0.163 | +1.509 | 53.8% | 38.5% | 23.1% | 15.4% | 30.8% | 15.4% | 15.4% | 23.1% | 53.8% | +0.875 | -0.333 | 24.0 |

## Entry Model Quality

| setup_name | entry_model | trades | avg_r | median_r | profit_factor | win_rate | direction_accuracy | clean_path_rate | bad_direction_rate | bad_entry_rate | target_too_far_rate | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r | median_bars_to_exit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| london_long_middle_local_retest | fvg_ce_retest | 2 | +0.866 | +0.866 | +7.980 | 50.0% | 100.0% | 50.0% | 0.0% | 50.0% | 0.0% | 50.0% | 0.0% | 0.0% | +2.077 | -3.282 | 9.0 |
| late_us_short_bull_flush_ce | structure_confirmed_fvg_ce_retest | 5 | +0.621 | -0.035 | +8.767 | 40.0% | 80.0% | 40.0% | 20.0% | 20.0% | 20.0% | 20.0% | 0.0% | 40.0% | +1.758 | -0.450 | 17.0 |
| late_us_short_bull_flush_ce | next_open | 33 | +0.545 | +0.386 | +2.859 | 60.6% | 54.5% | 36.4% | 27.3% | 30.3% | 18.2% | 27.3% | 24.2% | 42.4% | +1.505 | -0.477 | 20.0 |
| late_us_short_bearish_trend_ce | structure_confirmed_next_open | 19 | +0.523 | +0.521 | +4.905 | 78.9% | 47.4% | 26.3% | 15.8% | 15.8% | 26.3% | 15.8% | 10.5% | 73.7% | +0.948 | -0.425 | 24.0 |
| late_us_short_bull_flush_ce | fvg_ce_retest | 20 | +0.456 | -0.028 | +3.060 | 45.0% | 75.0% | 25.0% | 10.0% | 35.0% | 20.0% | 25.0% | 15.0% | 30.0% | +1.560 | -0.846 | 16.0 |
| late_us_short_bull_flush_ce | structure_confirmed_next_open | 27 | +0.433 | +0.451 | +3.705 | 74.1% | 40.7% | 40.7% | 33.3% | 7.4% | 33.3% | 7.4% | 7.4% | 85.2% | +0.744 | -0.228 | 24.0 |
| late_us_short_bearish_trend_ce | structure_confirmed_fvg_ce_retest | 11 | +0.417 | +0.039 | +2.534 | 54.5% | 54.5% | 45.5% | 36.4% | 18.2% | 36.4% | 18.2% | 18.2% | 63.6% | +1.283 | -0.492 | 24.0 |
| london_long_middle_local_retest | structure_confirmed_fvg_ce_retest | 19 | +0.388 | +0.332 | +2.678 | 57.9% | 47.4% | 31.6% | 15.8% | 21.1% | 10.5% | 21.1% | 15.8% | 47.4% | +0.988 | -0.354 | 18.0 |
| ny_long_neutral_reversal_ce | fvg_ce_retest | 12 | +0.361 | +0.125 | +1.769 | 50.0% | 75.0% | 33.3% | 8.3% | 41.7% | 8.3% | 41.7% | 41.7% | 8.3% | +2.096 | -0.670 | 6.5 |
| london_long_middle_local_next_open | structure_confirmed_next_open | 69 | +0.330 | +0.270 | +2.201 | 56.5% | 52.2% | 36.2% | 26.1% | 26.1% | 15.9% | 21.7% | 18.8% | 44.9% | +1.014 | -0.449 | 18.0 |
| london_long_middle_local_retest | structure_confirmed_next_open | 51 | +0.328 | +0.272 | +2.134 | 56.9% | 52.9% | 39.2% | 25.5% | 27.5% | 17.6% | 21.6% | 19.6% | 45.1% | +1.070 | -0.371 | 19.0 |
| ny_long_neutral_reversal_ce | next_open | 21 | +0.197 | -0.092 | +1.696 | 42.9% | 47.6% | 28.6% | 23.8% | 19.0% | 19.0% | 14.3% | 19.0% | 57.1% | +0.915 | -0.573 | 24.0 |
| ny_long_neutral_reversal_ce | structure_confirmed_next_open | 86 | +0.114 | -0.032 | +1.505 | 48.8% | 34.9% | 22.1% | 30.2% | 15.1% | 15.1% | 5.8% | 12.8% | 70.9% | +0.732 | -0.405 | 24.0 |
| late_us_short_bearish_trend_ce | fvg_ce_retest | 11 | +0.030 | -0.075 | +1.071 | 45.5% | 36.4% | 18.2% | 45.5% | 45.5% | 9.1% | 18.2% | 36.4% | 45.5% | +0.732 | -0.631 | 15.0 |
| late_us_short_bearish_trend_ce | next_open | 15 | -0.066 | -0.072 | +0.863 | 46.7% | 46.7% | 26.7% | 40.0% | 40.0% | 20.0% | 6.7% | 40.0% | 53.3% | +0.844 | -0.452 | 24.0 |
| london_long_middle_local_next_open | next_open | 6 | -0.164 | -0.263 | +0.644 | 33.3% | 33.3% | 33.3% | 33.3% | 33.3% | 16.7% | 0.0% | 33.3% | 50.0% | +0.783 | -0.577 | 22.0 |
| ny_long_neutral_reversal_ce | structure_confirmed_fvg_ce_retest | 28 | -0.180 | -0.445 | +0.651 | 35.7% | 35.7% | 10.7% | 32.1% | 53.6% | 7.1% | 14.3% | 39.3% | 35.7% | +0.806 | -1.075 | 16.5 |
| london_long_middle_local_retest | next_open | 4 | -0.377 | -0.263 | +0.064 | 25.0% | 25.0% | 25.0% | 50.0% | 25.0% | 0.0% | 0.0% | 25.0% | 50.0% | +0.616 | -0.577 | 22.0 |

## Path Quality

| setup_name | winner_count | loser_count | winner_median_mfe_r | winner_median_mae_r | loser_median_mfe_r | loser_median_mae_r | loser_bad_direction_rate | loser_bad_entry_rate | loser_target_too_far_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ny_long_neutral_reversal_ce | 67 | 80 | +1.171 | -0.260 | +0.523 | -0.869 | 46.2% | 43.8% | 0.0% |
| late_us_short_bull_flush_ce | 51 | 34 | +1.683 | -0.203 | +0.762 | -0.992 | 47.1% | 50.0% | 0.0% |
| london_long_middle_local_retest | 42 | 34 | +1.375 | -0.120 | +0.557 | -1.145 | 44.1% | 58.8% | 0.0% |
| london_long_middle_local_next_open | 41 | 34 | +1.401 | -0.143 | +0.542 | -1.145 | 47.1% | 58.8% | 0.0% |
| late_us_short_bearish_trend_ce | 33 | 23 | +1.130 | -0.384 | +0.312 | -1.201 | 60.9% | 60.9% | 0.0% |

## Review Packet

- UI review packet: `backtesting/results/review_samples/crypto_canonical_pattern_review_samples.csv`.
- Review `bad_direction_loser` before changing stops.
- Review `target_too_far` before reducing or increasing RR.
