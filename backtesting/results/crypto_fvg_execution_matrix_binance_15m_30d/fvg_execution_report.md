# Crypto FVG Execution Matrix

Date: 2026-07-13.

## Scope

- Timeframe: `15m`.
- Days: `30`.
- Exchange scope: intended for first-pass single-exchange price-action research.
- Entry models: FVG CE retest, FVG edge retest, next open.
- Confirmation models: raw and causal structure-confirmed.
- Targets: fixed `1.5R`, fixed `2R`.
- Management: hold, BE after half target, partial `1R` + BE after half target.

## Frequency

- Execution rows: `118194`.
- Unique signals: `5375`.
- Symbols: `11`.

## Top Research-Ready Buckets

| session_utc | direction | ctx_240_regime | trend_alignment | entry_model | target_model | management_model | confirmation_model | events | symbols | events_per_symbol_day | avg_r | profit_factor | target_rate | stop_rate | expiry_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| london | long | bull | middle_local_ema | structure_confirmed_next_open | fixed_2r | be_after_half_target | latest_bull_regime | 80 | 10 | 0.284 | 0.608 | 4.930 | 0.237 | 0.113 | 0.588 |
| london | long | bull | middle_local_ema | next_open | fixed_2r | be_after_half_target | none | 88 | 10 | 0.313 | 0.607 | 4.965 | 0.227 | 0.114 | 0.591 |
| london | long | bull | middle_local_ema | structure_confirmed_next_open | fixed_2r | hold_target_expiry | latest_bull_regime | 80 | 10 | 0.284 | 0.602 | 4.572 | 0.237 | 0.125 | 0.637 |
| london | long | bull | middle_local_ema | next_open | fixed_2r | hold_target_expiry | none | 88 | 10 | 0.313 | 0.599 | 4.543 | 0.227 | 0.125 | 0.648 |
| london | long | bull | middle_local_ema | structure_confirmed_next_open | fixed_2r | partial_1r_be_after_half_target | latest_bull_regime | 80 | 10 | 0.284 | 0.557 | 4.705 | 0.237 | 0.113 | 0.588 |
| london | long | bull | middle_local_ema | next_open | fixed_2r | partial_1r_be_after_half_target | none | 88 | 10 | 0.313 | 0.555 | 4.730 | 0.227 | 0.114 | 0.591 |
| london | long | bull | middle_local_ema | structure_confirmed_next_open | fixed_1_5r | be_after_half_target | latest_bull_regime | 80 | 10 | 0.284 | 0.536 | 4.486 | 0.350 | 0.113 | 0.475 |
| london | long | bull | middle_local_ema | next_open | fixed_1_5r | be_after_half_target | none | 88 | 10 | 0.313 | 0.533 | 4.505 | 0.341 | 0.114 | 0.477 |
| london | long | bull | middle_local_ema | structure_confirmed_next_open | fixed_1_5r | hold_target_expiry | latest_bull_regime | 80 | 10 | 0.284 | 0.525 | 4.114 | 0.350 | 0.125 | 0.525 |
| london | long | bull | middle_local_ema | next_open | fixed_1_5r | hold_target_expiry | none | 88 | 10 | 0.313 | 0.521 | 4.081 | 0.341 | 0.125 | 0.534 |
| london | long | bull | middle_local_ema | structure_confirmed_next_open | fixed_1_5r | partial_1r_be_after_half_target | latest_bull_regime | 80 | 10 | 0.284 | 0.516 | 4.435 | 0.350 | 0.113 | 0.475 |
| london | long | bull | middle_local_ema | next_open | fixed_1_5r | partial_1r_be_after_half_target | none | 88 | 10 | 0.313 | 0.513 | 4.455 | 0.341 | 0.114 | 0.477 |
| late_us | short | bull | counter_global_or_structure | next_open | fixed_1_5r | hold_target_expiry | none | 79 | 11 | 0.255 | 0.508 | 3.877 | 0.266 | 0.101 | 0.633 |
| late_us | short | bull | counter_global_or_structure | next_open | fixed_2r | hold_target_expiry | none | 79 | 11 | 0.255 | 0.500 | 3.615 | 0.114 | 0.114 | 0.772 |
| late_us | short | bull | counter_global_or_structure | next_open | fixed_1_5r | be_after_half_target | none | 79 | 11 | 0.255 | 0.497 | 4.064 | 0.253 | 0.101 | 0.570 |
| late_us | short | bull | counter_global_or_structure | next_open | fixed_2r | be_after_half_target | none | 79 | 11 | 0.255 | 0.490 | 3.780 | 0.101 | 0.101 | 0.759 |
| late_us | short | bull | counter_global_or_structure | next_open | fixed_1_5r | partial_1r_be_after_half_target | none | 79 | 11 | 0.255 | 0.454 | 3.828 | 0.253 | 0.101 | 0.570 |
| late_us | short | bull | counter_global_or_structure | next_open | fixed_2r | partial_1r_be_after_half_target | none | 79 | 11 | 0.255 | 0.443 | 3.562 | 0.101 | 0.101 | 0.759 |
| london | long | bull | full_trend | fvg_edge_retest | fixed_2r | hold_target_expiry | none | 82 | 11 | 0.275 | 0.303 | 1.685 | 0.341 | 0.378 | 0.280 |
| london | long | bull | full_trend | fvg_ce_retest | fixed_2r | hold_target_expiry | none | 89 | 11 | 0.298 | 0.290 | 1.673 | 0.326 | 0.371 | 0.303 |
| london | long | bull | full_trend | structure_confirmed_fvg_ce_retest | fixed_2r | hold_target_expiry | latest_bull_regime | 60 | 10 | 0.221 | 0.209 | 1.440 | 0.300 | 0.417 | 0.283 |
| london | long | bull | full_trend | fvg_ce_retest | fixed_2r | be_after_half_target | none | 89 | 11 | 0.298 | 0.205 | 1.531 | 0.258 | 0.326 | 0.258 |
| london | long | bull | full_trend | fvg_edge_retest | fixed_2r | be_after_half_target | none | 82 | 11 | 0.275 | 0.188 | 1.449 | 0.268 | 0.354 | 0.244 |
| london | long | bull | full_trend | fvg_ce_retest | fixed_1_5r | hold_target_expiry | none | 89 | 11 | 0.298 | 0.185 | 1.442 | 0.393 | 0.360 | 0.247 |
| london | long | bull | full_trend | fvg_edge_retest | fixed_1_5r | hold_target_expiry | none | 82 | 11 | 0.275 | 0.180 | 1.418 | 0.402 | 0.366 | 0.232 |

## Session/Direction Aggregate

| session_utc | direction | trend_alignment | events | buckets | weighted_avg_r | weighted_stop | max_avg_r | max_pf |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ny | long | full_trend | 3432 | 30 | -0.111 | 0.147 | -0.057 | 0.850 |
| london | long | full_trend | 2790 | 30 | +0.113 | 0.325 | +0.303 | 1.685 |
| asia | long | full_trend | 1998 | 24 | -0.293 | 0.326 | -0.247 | 0.529 |
| ny | short | global_middle_ema | 1392 | 18 | -0.025 | 0.145 | +0.075 | 1.269 |
| asia | long | middle_local_ema | 1368 | 18 | +0.067 | 0.156 | +0.087 | 1.335 |
| ny | long | middle_local_ema | 1314 | 18 | -0.076 | 0.196 | +0.065 | 1.171 |
| asia | short | counter_global_or_structure | 1152 | 12 | -0.071 | 0.169 | -0.028 | 0.901 |
| london | long | middle_local_ema | 1008 | 12 | +0.556 | 0.117 | +0.608 | 4.965 |
| late_us | long | full_trend | 840 | 12 | -0.126 | 0.220 | -0.059 | 0.866 |
| asia | long | counter_global_or_structure | 792 | 12 | -0.274 | 0.205 | -0.117 | 0.590 |
| ny | short | counter_global_or_structure | 558 | 6 | +0.023 | 0.231 | +0.059 | 1.188 |
| asia | short | global_middle_ema | 540 | 6 | -0.066 | 0.319 | +0.010 | 1.029 |
| late_us | short | counter_global_or_structure | 474 | 6 | +0.482 | 0.103 | +0.508 | 4.064 |
| london | short | counter_global_or_structure | 462 | 6 | -0.341 | 0.385 | -0.262 | 0.403 |
| late_us | long | counter_global_or_structure | 378 | 6 | -0.379 | 0.487 | -0.361 | 0.355 |
| london | short | global_middle_ema | 366 | 6 | -0.175 | 0.352 | -0.134 | 0.716 |

## Judgment

- If daytime buckets fail here, raw event strength is not executable edge.
- If a daytime bucket survives here, the old late-US module should stop being treated as the main engine.
- Frequency target for a general intraday engine should be near daily per active symbol before portfolio throttles.
