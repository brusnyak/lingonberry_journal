# Crypto Session Candidate Promotion

Date: 2026-07-13.

## Filters

- `session_utc` = `london`
- `direction` = `long`
- `ctx_240_regime` = `bull`
- `trend_alignment` = `middle_local_ema`
- `middle_ema_state` = `bullish`
- `local_ema_state` = `bullish`
- `entry_model` = `structure_confirmed_next_open`
- `target_model` = `fixed_2r`
- `management_model` = `be_after_half_target`
- `confirmation_model` = `latest_bull_regime`

## Portfolio

- Candidate trades: `143`.
- Accepted trades: `69`.
- Symbols: `10`.
- Return: `+4.78%`.
- Max DD: `1.75%`.
- Return/DD: `2.73`.
- PF: `2.26`.
- Avg R: `+0.347`.
- Win rate: `56.5%`.
- Stop rate: `18.8%`.
- Expiry rate: `46.4%`.

## Forensics

| failure_layer | count | share | avg_r |
| --- | --- | --- | --- |
| working | 39 | 56.5% | +1.100 |
| direction_or_entry | 15 | 21.7% | -0.865 |
| management_or_target | 10 | 14.5% | -0.098 |
| entry_or_stop | 4 | 5.8% | -1.077 |
| target_or_time_exit | 1 | 1.4% | -0.702 |

Path split:

| path_tag | count | share | avg_r |
| --- | --- | --- | --- |
| no_followthrough | 31 | 44.9% | -0.423 |
| expiry_after_progress | 14 | 20.3% | +0.780 |
| clean_target_path | 14 | 20.3% | +1.935 |
| gave_back_after_1r | 5 | 7.2% | -0.100 |
| partial_followthrough | 5 | 7.2% | -0.096 |

By symbol:

| symbol | trades | avg_r | stop_rate | expiry_rate |
| --- | --- | --- | --- | --- |
| NEARUSDT | 4 | -0.279 | 0.750 | 0.000 |
| SOLUSDT | 8 | -0.251 | 0.250 | 0.250 |
| AVAXUSDT | 5 | -0.070 | 0.200 | 0.600 |
| AAVEUSDT | 4 | 0.006 | 0.250 | 0.750 |
| XRPUSDT | 10 | 0.378 | 0.200 | 0.600 |
| DOGEUSDT | 10 | 0.486 | 0.200 | 0.400 |
| LINKUSDT | 8 | 0.590 | 0.000 | 0.625 |
| ETHUSDT | 10 | 0.621 | 0.100 | 0.400 |
| SUIUSDT | 5 | 0.709 | 0.000 | 0.600 |
| 1000PEPEUSDT | 5 | 0.850 | 0.200 | 0.400 |

## Judgment

- This is still in-sample over the same `60d` window.
- Promote only after holdout/window validation and manual UI review of forensic losers.
