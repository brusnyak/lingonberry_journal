# Crypto Trade Forensics Audit

Date: 2026-07-13.

## Scope

- Entry: `structure_confirmed_fvg_top_retest`.
- Target: `fixed_1_5r`.
- Management: `partial_1r_be_after_half_target`.
- Accepted trades inspected: `101`.
- Risk proxy: `0.20%` per trade.
- Portfolio return: `+7.51%`.
- Portfolio max DD: `0.90%`.
- Portfolio PF: `2.82`.

## Layer Verdicts

- Data: `101/101` accepted trades had candle windows reconstructed.
- Direction: winners `67.3%`; avg R `+0.372`.
- Entry: median bars to entry `2.0`; median MAE `-0.448R`.
- Stop: stop exits `14.9%`; median path MAE `-0.448R`.
- Target: target exits `27.7%`; reached `1R` `61.4%`; reached half-target `68.3%`.
- Expiry: expiry exits `40.6%`.

Failure-layer split:

| failure_layer | count | share | avg_r |
| --- | --- | --- | --- |
| working | 68 | 67.3% | +0.856 |
| direction_or_entry | 18 | 17.8% | -0.684 |
| management_or_target | 5 | 5.0% | -0.687 |
| unknown | 4 | 4.0% | -0.071 |
| entry_or_stop | 3 | 3.0% | -1.055 |
| target_or_time_exit | 3 | 3.0% | -0.480 |

Path split:

| path_tag | count | share | avg_r |
| --- | --- | --- | --- |
| no_followthrough | 32 | 31.7% | -0.427 |
| clean_target_path | 31 | 30.7% | +1.043 |
| expiry_after_progress | 20 | 19.8% | +0.840 |
| partial_followthrough | 8 | 7.9% | +0.374 |
| gave_back_after_1r | 6 | 5.9% | +0.068 |
| gave_back_after_half_target | 4 | 4.0% | -0.321 |

Pre-entry tape split:

| pre_structure_tape | count | share | avg_r |
| --- | --- | --- | --- |
| orderly_bearish | 93 | 92.1% | +0.370 |
| bullish_reversal_pressure | 5 | 5.0% | +0.108 |
| bearish_continuation | 3 | 3.0% | +0.888 |

Management variants for same entry/target:

| management_model | events | avg_r | median_r | profit_factor | target_rate | stop_rate | expiry_rate | hit_1r_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| partial_1r_be_after_half_target | 192 | 0.371 | 0.466 | 2.993 | 0.276 | 0.130 | 0.396 | 0.526 |
| be_after_half_target | 192 | 0.360 | 0.126 | 2.865 | 0.276 | 0.130 | 0.396 | 0.526 |
| partial_1r_be | 192 | 0.358 | 0.485 | 2.558 | 0.297 | 0.177 | 0.406 | 0.557 |
| partial_1r_hold | 192 | 0.352 | 0.588 | 2.508 | 0.302 | 0.214 | 0.484 | 0.557 |
| be_after_1r | 192 | 0.347 | 0.338 | 2.462 | 0.297 | 0.177 | 0.406 | 0.557 |
| hold_target_expiry | 192 | 0.335 | 0.427 | 2.220 | 0.302 | 0.214 | 0.484 | 0.557 |
| market_expiry_haircut | 192 | 0.287 | 0.327 | 1.985 | 0.302 | 0.214 | 0.484 | 0.557 |
| time_stop | 192 | 0.239 | 0.218 | 2.073 | 0.141 | 0.125 | 0.734 | 0.385 |

## Judgment

- Proven: shock-aware half-target management reduces stop damage without needing EMA as a hard filter.
- Assumed: the 11-symbol reviewed basket is representative enough for the next UI sample.
- Unknown: whether the same bucket survives discovery/holdout and symbol promotion without curve-fit leakage.
- Next test: UI review only the forensic edge cases, not random winners.

