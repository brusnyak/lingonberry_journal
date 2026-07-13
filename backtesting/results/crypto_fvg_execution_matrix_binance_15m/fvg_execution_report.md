# Crypto FVG Execution Matrix

Date: 2026-07-13.

## Scope

- Timeframe: `15m`.
- Days: `60`.
- Exchange scope: intended for first-pass single-exchange price-action research.
- Entry models: FVG CE retest, FVG edge retest, next open.
- Confirmation models: raw and causal structure-confirmed.
- Targets: fixed `1.5R`, fixed `2R`.
- Management: hold, BE after half target, partial `1R` + BE after half target.

## Frequency

- Execution rows: `226356`.
- Unique signals: `10311`.
- Symbols: `11`.

## Top Research-Ready Buckets

| session_utc | direction | ctx_240_regime | trend_alignment | entry_model | target_model | management_model | confirmation_model | events | symbols | events_per_symbol_day | avg_r | profit_factor | target_rate | stop_rate | expiry_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| late_us | short | neutral | global_middle_ema | fvg_edge_retest | fixed_2r | hold_target_expiry | none | 65 | 11 | 0.128 | 0.533 | 2.950 | 0.292 | 0.215 | 0.492 |
| late_us | short | neutral | global_middle_ema | fvg_ce_retest | fixed_2r | hold_target_expiry | none | 74 | 11 | 0.146 | 0.515 | 3.038 | 0.270 | 0.189 | 0.541 |
| late_us | short | bull | counter_global_or_structure | fvg_ce_retest | fixed_2r | hold_target_expiry | none | 65 | 11 | 0.100 | 0.473 | 3.160 | 0.123 | 0.169 | 0.708 |
| late_us | short | neutral | global_middle_ema | fvg_ce_retest | fixed_1_5r | hold_target_expiry | none | 74 | 11 | 0.146 | 0.469 | 2.857 | 0.405 | 0.189 | 0.405 |
| late_us | short | bull | counter_global_or_structure | fvg_ce_retest | fixed_1_5r | hold_target_expiry | none | 65 | 11 | 0.100 | 0.468 | 3.171 | 0.292 | 0.169 | 0.538 |
| late_us | short | bull | counter_global_or_structure | fvg_ce_retest | fixed_2r | be_after_half_target | none | 65 | 11 | 0.100 | 0.461 | 3.126 | 0.123 | 0.169 | 0.677 |
| late_us | short | neutral | global_middle_ema | fvg_ce_retest | fixed_2r | be_after_half_target | none | 74 | 11 | 0.146 | 0.452 | 2.775 | 0.243 | 0.189 | 0.514 |
| late_us | short | neutral | global_middle_ema | fvg_edge_retest | fixed_1_5r | hold_target_expiry | none | 65 | 11 | 0.128 | 0.438 | 2.603 | 0.400 | 0.215 | 0.385 |
| late_us | short | neutral | global_middle_ema | fvg_ce_retest | fixed_1_5r | be_after_half_target | none | 74 | 11 | 0.146 | 0.436 | 2.868 | 0.378 | 0.176 | 0.351 |
| late_us | short | bull | counter_global_or_structure | next_open | fixed_1_5r | hold_target_expiry | none | 107 | 11 | 0.165 | 0.432 | 3.478 | 0.206 | 0.103 | 0.692 |
| late_us | short | bull | counter_global_or_structure | next_open | fixed_1_5r | be_after_half_target | none | 107 | 11 | 0.165 | 0.427 | 3.665 | 0.196 | 0.103 | 0.636 |
| late_us | short | bull | counter_global_or_structure | next_open | fixed_2r | hold_target_expiry | none | 107 | 11 | 0.165 | 0.418 | 3.263 | 0.084 | 0.112 | 0.804 |
| late_us | short | bull | counter_global_or_structure | fvg_ce_retest | fixed_1_5r | be_after_half_target | none | 65 | 11 | 0.100 | 0.405 | 3.032 | 0.262 | 0.154 | 0.462 |
| late_us | short | neutral | global_middle_ema | fvg_edge_retest | fixed_2r | be_after_half_target | none | 65 | 11 | 0.128 | 0.405 | 2.532 | 0.231 | 0.200 | 0.446 |
| late_us | short | bull | counter_global_or_structure | next_open | fixed_2r | be_after_half_target | none | 107 | 11 | 0.165 | 0.404 | 3.322 | 0.075 | 0.103 | 0.785 |
| late_us | short | bull | counter_global_or_structure | fvg_ce_retest | fixed_2r | partial_1r_be_after_half_target | none | 65 | 11 | 0.100 | 0.399 | 2.848 | 0.123 | 0.169 | 0.677 |
| late_us | short | bull | counter_global_or_structure | next_open | fixed_1_5r | partial_1r_be_after_half_target | none | 107 | 11 | 0.165 | 0.396 | 3.494 | 0.196 | 0.103 | 0.636 |
| late_us | short | neutral | global_middle_ema | fvg_ce_retest | fixed_2r | partial_1r_be_after_half_target | none | 74 | 11 | 0.146 | 0.384 | 2.518 | 0.243 | 0.189 | 0.514 |
| late_us | short | bull | counter_global_or_structure | next_open | fixed_2r | partial_1r_be_after_half_target | none | 107 | 11 | 0.165 | 0.375 | 3.189 | 0.075 | 0.103 | 0.785 |
| late_us | short | neutral | global_middle_ema | fvg_ce_retest | fixed_1_5r | partial_1r_be_after_half_target | none | 74 | 11 | 0.146 | 0.373 | 2.601 | 0.378 | 0.176 | 0.351 |
| late_us | short | neutral | global_middle_ema | fvg_edge_retest | fixed_2r | partial_1r_be_after_half_target | none | 65 | 11 | 0.128 | 0.362 | 2.415 | 0.231 | 0.200 | 0.446 |
| late_us | short | bull | counter_global_or_structure | fvg_ce_retest | fixed_1_5r | partial_1r_be_after_half_target | none | 65 | 11 | 0.100 | 0.350 | 2.764 | 0.262 | 0.154 | 0.462 |
| late_us | short | neutral | global_middle_ema | next_open | fixed_1_5r | hold_target_expiry | none | 97 | 11 | 0.191 | 0.313 | 2.411 | 0.216 | 0.155 | 0.629 |
| late_us | short | neutral | global_middle_ema | next_open | fixed_2r | partial_1r_be_after_half_target | none | 97 | 11 | 0.191 | 0.304 | 2.446 | 0.093 | 0.144 | 0.701 |
| ny | short | bull | counter_global_or_structure | next_open | fixed_2r | hold_target_expiry | none | 67 | 11 | 0.105 | 0.304 | 1.756 | 0.224 | 0.358 | 0.418 |

## Session/Direction Aggregate

| session_utc | direction | trend_alignment | events | buckets | weighted_avg_r | weighted_stop | max_avg_r | max_pf |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| asia | long | counter_global_or_structure | 7416 | 72 | -0.178 | 0.261 | -0.099 | 0.684 |
| asia | short | global_middle_ema | 6378 | 48 | +0.047 | 0.215 | +0.142 | 1.528 |
| ny | long | counter_global_or_structure | 6198 | 72 | -0.106 | 0.265 | +0.112 | 1.422 |
| ny | short | global_middle_ema | 5994 | 42 | +0.040 | 0.150 | +0.141 | 1.484 |
| ny | long | full_trend | 5226 | 36 | -0.059 | 0.139 | +0.001 | 1.002 |
| asia | short | counter_global_or_structure | 4554 | 54 | -0.075 | 0.244 | +0.026 | 1.065 |
| london | short | global_middle_ema | 4380 | 36 | +0.010 | 0.283 | +0.158 | 1.350 |
| london | long | counter_global_or_structure | 4374 | 60 | -0.330 | 0.458 | -0.048 | 0.877 |
| ny | long | middle_local_ema | 4134 | 36 | -0.188 | 0.285 | -0.063 | 0.839 |
| london | long | full_trend | 3990 | 36 | +0.127 | 0.321 | +0.290 | 1.651 |
| asia | long | full_trend | 3594 | 36 | -0.258 | 0.333 | -0.188 | 0.573 |
| late_us | short | global_middle_ema | 3186 | 36 | +0.262 | 0.185 | +0.533 | 3.038 |
| london | long | middle_local_ema | 3180 | 30 | +0.196 | 0.252 | +0.297 | 2.135 |
| asia | long | middle_local_ema | 2910 | 30 | -0.071 | 0.232 | -0.016 | 0.951 |
| ny | short | counter_global_or_structure | 2772 | 36 | +0.044 | 0.273 | +0.304 | 1.756 |
| london | short | counter_global_or_structure | 2172 | 30 | -0.250 | 0.424 | -0.056 | 0.868 |
| late_us | long | full_trend | 1914 | 24 | -0.187 | 0.271 | -0.083 | 0.785 |
| late_us | short | counter_global_or_structure | 1524 | 18 | +0.294 | 0.186 | +0.473 | 3.665 |
| late_us | long | counter_global_or_structure | 1446 | 18 | -0.151 | 0.394 | +0.222 | 1.686 |
| late_us | long | middle_local_ema | 1200 | 18 | -0.247 | 0.341 | -0.191 | 0.637 |
| asia | short | middle_local_ema | 960 | 12 | +0.168 | 0.211 | +0.216 | 1.824 |
| asia | short | full_trend | 450 | 6 | +0.044 | 0.182 | +0.054 | 1.184 |
| london | short | middle_local_ema | 408 | 6 | -0.106 | 0.321 | -0.053 | 0.851 |
| asia | long | mixed | 402 | 6 | -0.027 | 0.119 | -0.019 | 0.925 |
| ny | short | full_trend | 390 | 6 | -0.059 | 0.164 | -0.007 | 0.976 |

## Judgment

- If daytime buckets fail here, raw event strength is not executable edge.
- If a daytime bucket survives here, the old late-US module should stop being treated as the main engine.
- Frequency target for a general intraday engine should be near daily per active symbol before portfolio throttles.
