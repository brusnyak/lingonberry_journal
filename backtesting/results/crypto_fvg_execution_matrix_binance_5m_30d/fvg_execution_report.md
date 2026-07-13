# Crypto FVG Execution Matrix

Date: 2026-07-13.

## Scope

- Timeframe: `5m`.
- Days: `30`.
- Exchange scope: intended for first-pass single-exchange price-action research.
- Entry models: FVG CE retest, FVG edge retest, next open.
- Confirmation models: raw and causal structure-confirmed.
- Targets: fixed `1.5R`, fixed `2R`.
- Management: hold, BE after half target, partial `1R` + BE after half target.

## Frequency

- Execution rows: `340362`.
- Unique signals: `15873`.
- Symbols: `11`.

## Top Research-Ready Buckets

| session_utc | direction | ctx_240_regime | trend_alignment | entry_model | target_model | management_model | confirmation_model | events | symbols | events_per_symbol_day | avg_r | profit_factor | target_rate | stop_rate | expiry_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| late_us | short | bull | counter_global_or_structure | fvg_ce_retest | fixed_2r | be_after_half_target | none | 60 | 11 | 0.194 | 0.527 | 3.581 | 0.167 | 0.150 | 0.617 |
| late_us | short | bull | counter_global_or_structure | fvg_ce_retest | fixed_1_5r | be_after_half_target | none | 60 | 11 | 0.194 | 0.505 | 3.955 | 0.317 | 0.117 | 0.467 |
| late_us | short | bull | counter_global_or_structure | fvg_ce_retest | fixed_2r | hold_target_expiry | none | 60 | 11 | 0.194 | 0.478 | 2.890 | 0.167 | 0.200 | 0.633 |
| late_us | short | bull | counter_global_or_structure | fvg_ce_retest | fixed_1_5r | partial_1r_be_after_half_target | none | 60 | 11 | 0.194 | 0.474 | 3.975 | 0.317 | 0.117 | 0.467 |
| london | long | bull | middle_local_ema | structure_confirmed_fvg_edge_retest | fixed_2r | hold_target_expiry | latest_bull_regime | 75 | 11 | 0.236 | 0.450 | 3.850 | 0.213 | 0.093 | 0.693 |
| late_us | short | bull | counter_global_or_structure | fvg_ce_retest | fixed_2r | partial_1r_be_after_half_target | none | 60 | 11 | 0.194 | 0.449 | 3.330 | 0.167 | 0.150 | 0.617 |
| late_us | short | bull | counter_global_or_structure | fvg_ce_retest | fixed_1_5r | hold_target_expiry | none | 60 | 11 | 0.194 | 0.423 | 2.671 | 0.317 | 0.200 | 0.483 |
| london | long | bull | middle_local_ema | structure_confirmed_fvg_edge_retest | fixed_2r | be_after_half_target | latest_bull_regime | 75 | 11 | 0.236 | 0.416 | 3.955 | 0.200 | 0.067 | 0.613 |
| london | long | bull | middle_local_ema | structure_confirmed_fvg_edge_retest | fixed_2r | partial_1r_be_after_half_target | latest_bull_regime | 75 | 11 | 0.236 | 0.393 | 4.245 | 0.200 | 0.067 | 0.613 |
| ny | long | neutral | counter_global_or_structure | fvg_ce_retest | fixed_2r | be_after_half_target | none | 70 | 9 | 0.324 | 0.384 | 2.376 | 0.200 | 0.214 | 0.514 |
| london | long | bull | middle_local_ema | structure_confirmed_fvg_edge_retest | fixed_1_5r | hold_target_expiry | latest_bull_regime | 75 | 11 | 0.236 | 0.384 | 3.449 | 0.280 | 0.093 | 0.627 |
| ny | long | neutral | counter_global_or_structure | fvg_edge_retest | fixed_2r | be_after_half_target | none | 60 | 9 | 0.278 | 0.381 | 2.289 | 0.217 | 0.233 | 0.467 |
| ny | long | neutral | counter_global_or_structure | fvg_edge_retest | fixed_2r | hold_target_expiry | none | 60 | 9 | 0.278 | 0.368 | 2.078 | 0.233 | 0.267 | 0.500 |
| london | long | bull | middle_local_ema | next_open | fixed_2r | hold_target_expiry | none | 211 | 11 | 0.660 | 0.367 | 3.549 | 0.109 | 0.071 | 0.820 |
| london | long | bull | middle_local_ema | fvg_ce_retest | fixed_2r | hold_target_expiry | none | 130 | 11 | 0.407 | 0.352 | 2.886 | 0.169 | 0.115 | 0.715 |
| ny | long | neutral | counter_global_or_structure | fvg_ce_retest | fixed_2r | hold_target_expiry | none | 70 | 9 | 0.324 | 0.351 | 2.116 | 0.200 | 0.229 | 0.571 |
| london | long | bull | middle_local_ema | next_open | fixed_1_5r | hold_target_expiry | none | 211 | 11 | 0.660 | 0.350 | 3.434 | 0.199 | 0.071 | 0.730 |
| london | long | bull | middle_local_ema | structure_confirmed_next_open | fixed_2r | hold_target_expiry | latest_bull_regime | 184 | 11 | 0.576 | 0.348 | 3.447 | 0.098 | 0.071 | 0.832 |
| ny | long | neutral | counter_global_or_structure | fvg_edge_retest | fixed_1_5r | hold_target_expiry | none | 60 | 9 | 0.278 | 0.346 | 2.084 | 0.350 | 0.267 | 0.383 |
| late_us | short | bull | counter_global_or_structure | next_open | fixed_2r | hold_target_expiry | none | 111 | 11 | 0.359 | 0.345 | 2.806 | 0.072 | 0.108 | 0.820 |
| late_us | short | bull | counter_global_or_structure | next_open | fixed_2r | be_after_half_target | none | 111 | 11 | 0.359 | 0.344 | 2.801 | 0.072 | 0.108 | 0.793 |
| london | long | bull | middle_local_ema | fvg_edge_retest | fixed_2r | hold_target_expiry | none | 110 | 11 | 0.346 | 0.343 | 2.651 | 0.182 | 0.136 | 0.682 |
| london | long | bull | middle_local_ema | structure_confirmed_next_open | fixed_1_5r | hold_target_expiry | latest_bull_regime | 184 | 11 | 0.576 | 0.340 | 3.392 | 0.190 | 0.071 | 0.739 |
| london | long | bull | middle_local_ema | structure_confirmed_fvg_ce_retest | fixed_2r | hold_target_expiry | latest_bull_regime | 97 | 11 | 0.304 | 0.340 | 2.822 | 0.175 | 0.113 | 0.711 |
| london | long | bull | middle_local_ema | fvg_ce_retest | fixed_1_5r | hold_target_expiry | none | 130 | 11 | 0.407 | 0.339 | 2.921 | 0.269 | 0.108 | 0.623 |

## Session/Direction Aggregate

| session_utc | direction | trend_alignment | events | buckets | weighted_avg_r | weighted_stop | max_avg_r | max_pf |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| asia | short | counter_global_or_structure | 17322 | 144 | -0.025 | 0.224 | +0.144 | 1.436 |
| ny | short | counter_global_or_structure | 13506 | 132 | -0.105 | 0.236 | +0.109 | 1.679 |
| london | short | counter_global_or_structure | 10284 | 120 | -0.192 | 0.353 | +0.239 | 1.934 |
| ny | long | full_trend | 9606 | 36 | -0.034 | 0.213 | +0.070 | 1.198 |
| asia | long | counter_global_or_structure | 7590 | 78 | -0.068 | 0.244 | +0.294 | 2.391 |
| asia | long | middle_local_ema | 6876 | 36 | -0.148 | 0.171 | -0.050 | 0.870 |
| london | long | full_trend | 6492 | 36 | +0.061 | 0.233 | +0.166 | 1.589 |
| ny | long | counter_global_or_structure | 6450 | 72 | +0.076 | 0.195 | +0.384 | 2.376 |
| asia | long | mixed | 6384 | 78 | -0.031 | 0.272 | +0.169 | 1.484 |
| asia | long | full_trend | 6300 | 36 | -0.251 | 0.319 | -0.185 | 0.569 |
| late_us | short | counter_global_or_structure | 6270 | 66 | +0.090 | 0.201 | +0.527 | 3.975 |
| ny | long | middle_local_ema | 5070 | 36 | +0.042 | 0.170 | +0.258 | 1.927 |
| london | long | middle_local_ema | 4842 | 36 | +0.318 | 0.081 | +0.450 | 4.245 |
| ny | short | global_middle_ema | 4686 | 36 | -0.221 | 0.296 | -0.105 | 0.724 |
| late_us | long | full_trend | 4464 | 36 | -0.072 | 0.176 | +0.026 | 1.069 |
| ny | long | mixed | 4104 | 54 | +0.012 | 0.198 | +0.321 | 2.368 |
| asia | short | global_middle_ema | 3822 | 30 | -0.147 | 0.293 | +0.229 | 1.562 |
| late_us | long | counter_global_or_structure | 2874 | 36 | +0.062 | 0.209 | +0.209 | 1.921 |
| london | long | mixed | 2784 | 36 | -0.070 | 0.291 | +0.182 | 1.578 |
| london | short | global_middle_ema | 2766 | 30 | -0.058 | 0.259 | +0.082 | 1.265 |
| london | long | counter_global_or_structure | 2226 | 30 | -0.377 | 0.426 | -0.210 | 0.564 |
| asia | long | global_middle_ema | 1722 | 24 | -0.475 | 0.486 | -0.294 | 0.427 |
| late_us | short | global_middle_ema | 1512 | 18 | -0.453 | 0.420 | -0.369 | 0.305 |
| late_us | long | middle_local_ema | 1470 | 18 | +0.004 | 0.156 | +0.050 | 1.153 |
| asia | short | middle_local_ema | 1128 | 12 | +0.118 | 0.089 | +0.187 | 2.251 |
| london | short | middle_local_ema | 948 | 12 | -0.140 | 0.226 | -0.043 | 0.847 |
| london | long | global_middle_ema | 432 | 6 | +0.217 | 0.264 | +0.248 | 1.719 |
| late_us | long | global_middle_ema | 420 | 6 | -0.259 | 0.381 | -0.230 | 0.623 |
| ny | long | global_middle_ema | 396 | 6 | +0.189 | 0.207 | +0.282 | 1.873 |
| ny | short | full_trend | 390 | 6 | +0.041 | 0.185 | +0.062 | 1.194 |

## Judgment

- If daytime buckets fail here, raw event strength is not executable edge.
- If a daytime bucket survives here, the old late-US module should stop being treated as the main engine.
- Frequency target for a general intraday engine should be near daily per active symbol before portfolio throttles.
