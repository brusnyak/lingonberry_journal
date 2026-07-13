# Crypto Session Candidate Promotion

Date: 2026-07-13.

## Filters

- `session_utc` = `late_us`
- `direction` = `short`
- `ctx_240_regime` = `neutral`
- `trend_alignment` = `global_middle_ema`
- `global_ema_state` = `bearish`
- `middle_ema_state` = `bearish`
- `local_ema_state` = `bearish`
- `entry_model` = `fvg_ce_retest`
- `target_model` = `fixed_2r`
- `management_model` = `hold_target_expiry`
- `confirmation_model` = `none`

## Portfolio

- Candidate trades: `74`.
- Accepted trades: `53`.
- Symbols: `11`.
- Return: `+3.76%`.
- Max DD: `1.84%`.
- Return/DD: `2.05`.
- PF: `2.14`.
- Avg R: `+0.355`.
- Win rate: `56.6%`.
- Stop rate: `22.6%`.
- Expiry rate: `54.7%`.

## Forensics

| failure_layer | count | share | avg_r |
| --- | --- | --- | --- |
| working | 30 | 56.6% | +1.177 |
| direction_or_entry | 13 | 24.5% | -0.756 |
| target_or_time_exit | 6 | 11.3% | -0.321 |
| management_or_target | 3 | 5.7% | -1.209 |
| entry_or_stop | 1 | 1.9% | -1.123 |

Path split:

| path_tag | count | share | avg_r |
| --- | --- | --- | --- |
| no_followthrough | 26 | 49.1% | -0.431 |
| clean_target_path | 13 | 24.5% | +1.675 |
| expiry_after_progress | 12 | 22.6% | +0.864 |
| gave_back_after_1r | 2 | 3.8% | -1.054 |

By symbol:

| symbol | trades | avg_r | stop_rate | expiry_rate |
| --- | --- | --- | --- | --- |
| AAVEUSDT | 1 | -1.128 | 1.000 | 0.000 |
| XRPUSDT | 7 | -0.215 | 0.429 | 0.429 |
| LINKUSDT | 4 | 0.037 | 0.250 | 0.500 |
| DOGEUSDT | 8 | 0.134 | 0.375 | 0.500 |
| AVAXUSDT | 3 | 0.183 | 0.000 | 1.000 |
| ETHUSDT | 8 | 0.245 | 0.125 | 0.750 |
| 1000PEPEUSDT | 7 | 0.250 | 0.143 | 0.857 |
| NEARUSDT | 4 | 0.898 | 0.250 | 0.250 |
| SOLUSDT | 6 | 0.958 | 0.167 | 0.333 |
| SUIUSDT | 1 | 1.169 | 0.000 | 1.000 |
| WLDUSDT | 4 | 1.366 | 0.000 | 0.250 |

## Judgment

- This is still in-sample over the same `60d` window.
- Promote only after holdout/window validation and manual UI review of forensic losers.
