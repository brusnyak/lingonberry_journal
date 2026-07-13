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

- Execution rows: `281976`.
- Unique signals: `13336`.
- Symbols: `14`.

## Top Research-Ready Buckets

| session_utc | direction | ctx_240_regime | trend_alignment | entry_model | target_model | management_model | confirmation_model | events | symbols | events_per_symbol_day | avg_r | profit_factor | target_rate | stop_rate | expiry_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| late_us | short | bear | full_trend | fvg_edge_retest | fixed_2r | hold_target_expiry | none | 152 | 14 | 0.184 | 0.501 | 2.581 | 0.336 | 0.237 | 0.428 |
| late_us | short | bear | full_trend | fvg_ce_retest | fixed_2r | hold_target_expiry | none | 171 | 14 | 0.207 | 0.443 | 2.438 | 0.287 | 0.222 | 0.491 |
| late_us | short | bear | full_trend | fvg_edge_retest | fixed_1_5r | hold_target_expiry | none | 152 | 14 | 0.184 | 0.437 | 2.475 | 0.441 | 0.224 | 0.336 |
| late_us | short | bear | full_trend | fvg_ce_retest | fixed_1_5r | hold_target_expiry | none | 171 | 14 | 0.207 | 0.425 | 2.457 | 0.421 | 0.211 | 0.368 |
| late_us | short | bull | counter_global_or_structure | fvg_ce_retest | fixed_1_5r | hold_target_expiry | none | 61 | 14 | 0.074 | 0.416 | 2.564 | 0.311 | 0.230 | 0.459 |
| late_us | short | bull | counter_global_or_structure | fvg_ce_retest | fixed_1_5r | be_after_half_target | none | 61 | 14 | 0.074 | 0.409 | 3.072 | 0.279 | 0.164 | 0.410 |
| late_us | short | bull | counter_global_or_structure | next_open | fixed_1_5r | be_after_half_target | none | 94 | 14 | 0.114 | 0.406 | 2.977 | 0.223 | 0.160 | 0.574 |
| late_us | short | bear | full_trend | fvg_edge_retest | fixed_2r | be_after_half_target | none | 152 | 14 | 0.184 | 0.402 | 2.511 | 0.263 | 0.184 | 0.362 |
| late_us | short | bear | full_trend | fvg_ce_retest | fixed_2r | be_after_half_target | none | 171 | 14 | 0.207 | 0.393 | 2.388 | 0.257 | 0.199 | 0.427 |
| late_us | short | bull | counter_global_or_structure | next_open | fixed_1_5r | hold_target_expiry | none | 94 | 14 | 0.114 | 0.391 | 2.737 | 0.223 | 0.170 | 0.606 |
| london | short | bear | mixed | next_open | fixed_2r | hold_target_expiry | none | 65 | 14 | 0.110 | 0.388 | 1.817 | 0.400 | 0.385 | 0.215 |
| late_us | short | bear | full_trend | fvg_ce_retest | fixed_1_5r | be_after_half_target | none | 171 | 14 | 0.207 | 0.387 | 2.693 | 0.363 | 0.152 | 0.292 |
| late_us | short | bull | counter_global_or_structure | next_open | fixed_2r | be_after_half_target | none | 94 | 14 | 0.114 | 0.373 | 2.730 | 0.074 | 0.160 | 0.734 |
| late_us | short | bull | counter_global_or_structure | fvg_ce_retest | fixed_2r | be_after_half_target | none | 61 | 14 | 0.074 | 0.372 | 2.382 | 0.115 | 0.230 | 0.607 |
| late_us | short | bear | full_trend | fvg_edge_retest | fixed_2r | partial_1r_be_after_half_target | none | 152 | 14 | 0.184 | 0.371 | 2.498 | 0.263 | 0.184 | 0.362 |
| late_us | short | bull | counter_global_or_structure | fvg_ce_retest | fixed_2r | hold_target_expiry | none | 61 | 14 | 0.074 | 0.369 | 2.280 | 0.115 | 0.246 | 0.639 |
| late_us | short | bull | counter_global_or_structure | next_open | fixed_1_5r | partial_1r_be_after_half_target | none | 94 | 14 | 0.114 | 0.369 | 2.800 | 0.223 | 0.160 | 0.574 |
| late_us | short | bull | counter_global_or_structure | next_open | fixed_2r | hold_target_expiry | none | 94 | 14 | 0.114 | 0.360 | 2.520 | 0.074 | 0.181 | 0.745 |
| late_us | short | bull | counter_global_or_structure | fvg_ce_retest | fixed_1_5r | partial_1r_be_after_half_target | none | 61 | 14 | 0.074 | 0.359 | 2.820 | 0.279 | 0.164 | 0.410 |
| late_us | short | bear | full_trend | fvg_ce_retest | fixed_1_5r | partial_1r_be_after_half_target | none | 171 | 14 | 0.207 | 0.351 | 2.584 | 0.363 | 0.152 | 0.292 |
| late_us | short | bear | full_trend | fvg_edge_retest | fixed_1_5r | partial_1r_be_after_half_target | none | 152 | 14 | 0.184 | 0.349 | 2.642 | 0.316 | 0.158 | 0.243 |
| london | short | bear | mixed | next_open | fixed_2r | be_after_half_target | none | 65 | 14 | 0.110 | 0.343 | 1.732 | 0.385 | 0.385 | 0.138 |
| late_us | short | bull | counter_global_or_structure | next_open | fixed_2r | partial_1r_be_after_half_target | none | 94 | 14 | 0.114 | 0.340 | 2.593 | 0.074 | 0.160 | 0.734 |
| late_us | short | bear | full_trend | fvg_ce_retest | fixed_2r | partial_1r_be_after_half_target | none | 171 | 14 | 0.207 | 0.335 | 2.232 | 0.257 | 0.199 | 0.427 |
| late_us | short | bull | counter_global_or_structure | fvg_ce_retest | fixed_2r | partial_1r_be_after_half_target | none | 61 | 14 | 0.074 | 0.322 | 2.210 | 0.115 | 0.230 | 0.607 |

## Session/Direction Aggregate

| session_utc | direction | trend_alignment | events | buckets | weighted_avg_r | weighted_stop | max_avg_r | max_pf |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ny | short | full_trend | 9672 | 36 | +0.014 | 0.124 | +0.121 | 1.511 |
| asia | short | full_trend | 9360 | 36 | +0.058 | 0.186 | +0.114 | 1.419 |
| asia | long | counter_global_or_structure | 9360 | 72 | -0.072 | 0.203 | +0.136 | 1.371 |
| ny | long | counter_global_or_structure | 8424 | 78 | -0.141 | 0.293 | +0.263 | 2.669 |
| london | long | counter_global_or_structure | 6474 | 66 | -0.341 | 0.423 | -0.140 | 0.658 |
| london | short | full_trend | 6270 | 36 | +0.009 | 0.248 | +0.168 | 1.448 |
| ny | long | full_trend | 4884 | 36 | -0.060 | 0.145 | -0.028 | 0.904 |
| late_us | short | full_trend | 4632 | 30 | +0.297 | 0.172 | +0.501 | 2.693 |
| late_us | long | counter_global_or_structure | 3846 | 42 | -0.167 | 0.376 | +0.026 | 1.069 |
| asia | short | counter_global_or_structure | 3600 | 42 | -0.054 | 0.194 | +0.117 | 1.384 |
| ny | long | middle_local_ema | 3480 | 48 | -0.090 | 0.216 | +0.217 | 1.622 |
| london | long | full_trend | 2886 | 24 | +0.104 | 0.275 | +0.206 | 1.742 |
| asia | long | full_trend | 2376 | 24 | -0.193 | 0.278 | -0.112 | 0.679 |
| ny | short | counter_global_or_structure | 2250 | 30 | +0.065 | 0.232 | +0.271 | 1.871 |
| asia | short | global_middle_ema | 2208 | 24 | +0.078 | 0.182 | +0.186 | 2.246 |
| asia | short | middle_local_ema | 1968 | 24 | +0.146 | 0.171 | +0.219 | 2.137 |
| london | long | middle_local_ema | 1956 | 24 | +0.172 | 0.217 | +0.248 | 1.778 |
| london | short | global_middle_ema | 1494 | 18 | -0.199 | 0.436 | -0.083 | 0.845 |
| asia | long | middle_local_ema | 1428 | 18 | -0.109 | 0.251 | +0.008 | 1.029 |
| london | short | mixed | 1332 | 18 | +0.205 | 0.301 | +0.388 | 1.817 |
| london | short | counter_global_or_structure | 1314 | 18 | -0.263 | 0.383 | -0.164 | 0.609 |
| london | short | middle_local_ema | 1218 | 18 | -0.051 | 0.241 | +0.054 | 1.192 |
| late_us | short | counter_global_or_structure | 930 | 12 | +0.374 | 0.183 | +0.416 | 3.072 |
| late_us | long | full_trend | 870 | 12 | -0.289 | 0.298 | -0.205 | 0.557 |
| ny | short | middle_local_ema | 822 | 12 | -0.129 | 0.136 | -0.078 | 0.748 |
| ny | long | global_middle_ema | 504 | 6 | -0.031 | 0.145 | +0.011 | 1.036 |
| ny | short | global_middle_ema | 468 | 6 | -0.108 | 0.269 | -0.080 | 0.805 |
| ny | short | mixed | 444 | 6 | -0.189 | 0.385 | -0.179 | 0.648 |
| late_us | short | global_middle_ema | 444 | 6 | +0.073 | 0.196 | +0.101 | 1.421 |
| asia | short | mixed | 438 | 6 | -0.314 | 0.340 | -0.277 | 0.380 |

## Judgment

- If daytime buckets fail here, raw event strength is not executable edge.
- If a daytime bucket survives here, the old late-US module should stop being treated as the main engine.
- Frequency target for a general intraday engine should be near daily per active symbol before portfolio throttles.
