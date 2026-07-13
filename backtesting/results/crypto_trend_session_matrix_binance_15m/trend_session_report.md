# Crypto Trend/Session Matrix

Date: 2026-07-13.

## Scope

- Days: `60`.
- Signal timeframes: `5m`, `15m` unless CLI overrides.
- Global trend helper: `240m EMA 21/55` plus structure regime.
- Middle trend helper: `60m EMA 21/55`.
- Local trend helper: signal-timeframe EMA 21/55.
- Event family in summary: bullish/bearish FVG formation.

## Frequency

- Total event rows: `278770`.
- FVG event rows: `134850`.
- Span days: `59.5`.

## Top Research-Ready Buckets

| tf | session_utc | direction | ctx_240_regime | trend_alignment | stop_model | target_model | events | symbols | exchanges | events_per_symbol_exchange_day | avg_r | profit_factor | hit_target_rate | stop_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 15 | late_us | short | bull | counter_global_or_structure | atr | fixed_2r | 131 | 11 | 1 | 0.202 | 0.602 | 2.313 | 0.580 | 0.405 |
| 15 | late_us | short | bull | counter_global_or_structure | event_extreme | fixed_2r | 131 | 11 | 1 | 0.202 | 0.598 | 2.402 | 0.504 | 0.366 |
| 15 | late_us | short | bull | counter_global_or_structure | atr | round_number | 131 | 11 | 1 | 0.202 | 0.507 | 2.462 | 0.702 | 0.298 |
| 15 | late_us | short | bull | counter_global_or_structure | prior_swing | fixed_2r | 131 | 11 | 1 | 0.202 | 0.425 | 3.215 | 0.099 | 0.122 |
| 15 | late_us | short | bull | counter_global_or_structure | event_extreme | round_number | 131 | 11 | 1 | 0.202 | 0.413 | 2.237 | 0.687 | 0.282 |
| 15 | asia | short | bull | middle_local_ema | event_extreme | fixed_2r | 117 | 11 | 1 | 0.184 | 0.387 | 1.855 | 0.410 | 0.376 |
| 15 | late_us | short | bull | counter_global_or_structure | prior_swing | fixed_1r | 131 | 11 | 1 | 0.202 | 0.371 | 3.217 | 0.435 | 0.107 |
| 15 | asia | short | bull | middle_local_ema | prior_swing | fixed_2r | 117 | 11 | 1 | 0.184 | 0.320 | 2.334 | 0.179 | 0.171 |
| 15 | asia | short | bull | middle_local_ema | event_extreme | round_number | 114 | 11 | 1 | 0.179 | 0.307 | 1.899 | 0.632 | 0.281 |
| 15 | late_us | short | neutral | global_middle_ema | prior_swing | fixed_1r | 116 | 11 | 1 | 0.202 | 0.284 | 2.284 | 0.448 | 0.147 |
| 15 | london | long | bull | middle_local_ema | event_extreme | fixed_2r | 181 | 10 | 1 | 0.354 | 0.254 | 1.443 | 0.436 | 0.470 |
| 15 | asia | short | bull | middle_local_ema | event_extreme | fixed_1r | 117 | 11 | 1 | 0.184 | 0.247 | 1.765 | 0.641 | 0.265 |
| 15 | london | long | bull | middle_local_ema | prior_swing | fixed_2r | 181 | 10 | 1 | 0.354 | 0.240 | 1.822 | 0.149 | 0.227 |
| 15 | late_us | short | neutral | global_middle_ema | prior_swing | fixed_2r | 116 | 11 | 1 | 0.202 | 0.234 | 1.900 | 0.095 | 0.181 |
| 15 | asia | short | bull | middle_local_ema | atr | fixed_2r | 117 | 11 | 1 | 0.184 | 0.234 | 1.387 | 0.462 | 0.513 |
| 15 | late_us | short | bull | counter_global_or_structure | event_extreme | fixed_1r | 131 | 11 | 1 | 0.202 | 0.225 | 1.652 | 0.664 | 0.298 |
| 15 | late_us | short | bull | counter_global_or_structure | prior_swing | round_number | 131 | 11 | 1 | 0.202 | 0.224 | 3.003 | 0.649 | 0.084 |
| 15 | asia | short | bull | middle_local_ema | prior_swing | fixed_1r | 117 | 11 | 1 | 0.184 | 0.219 | 2.041 | 0.393 | 0.154 |
| 15 | london | long | bull | middle_local_ema | atr | fixed_2r | 181 | 10 | 1 | 0.354 | 0.219 | 1.347 | 0.475 | 0.525 |
| 15 | late_us | short | neutral | global_middle_ema | prior_swing | prior_opposite | 108 | 11 | 1 | 0.188 | 0.216 | 2.214 | 0.750 | 0.157 |

## Alignment Summary

| tf | trend_alignment | events | symbols | avg_r | pf | stop_rate |
| --- | --- | --- | --- | --- | --- | --- |
| 15 | counter_global_or_structure | 73568 | 11 | -0.156 | 0.718 | 0.453 |
| 15 | global_middle_ema | 22192 | 11 | -0.061 | 0.876 | 0.402 |
| 15 | middle_local_ema | 14229 | 11 | -0.146 | 0.719 | 0.420 |
| 15 | mixed | 14166 | 11 | -0.130 | 0.771 | 0.468 |
| 15 | full_trend | 10695 | 11 | -0.109 | 0.784 | 0.416 |

## Session Summary

| tf | session_utc | events | symbols | avg_r | pf | stop_rate |
| --- | --- | --- | --- | --- | --- | --- |
| 15 | asia | 40760 | 11 | -0.086 | 0.831 | 0.411 |
| 15 | ny | 38351 | 11 | -0.145 | 0.719 | 0.418 |
| 15 | london | 33057 | 11 | -0.209 | 0.657 | 0.504 |
| 15 | late_us | 22682 | 11 | -0.088 | 0.833 | 0.435 |

## Judgment

- This matrix is event-level research, not final execution-path validation.
- If trend-following buckets beat countertrend buckets, the current night countertrend engine should be demoted.
- If no session outside late-US works, the engine is a niche overnight crypto strategy, not a general intraday engine.
- If frequency remains below about `0.10` events per symbol/exchange/day after broadening sessions and trend modes, the setup is intrinsically rare.
