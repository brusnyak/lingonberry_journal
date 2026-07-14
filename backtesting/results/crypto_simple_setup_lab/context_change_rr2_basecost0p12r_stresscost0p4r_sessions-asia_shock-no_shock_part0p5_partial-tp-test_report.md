# Simple Crypto Setup Lab

Scope: one setup family at a time, existing 240m/30m structure+EMA direction context, 15m entry, structural SL/TP, explicit cost-per-R.

## Summary

| setup          | symbol  | trades | win_rate | gross_avg_r | base_avg_r | base_pf | stress_avg_r | stress_pf | median_stop_pct | median_planned_rr | median_base_cost_r | median_stress_cost_r | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r | top_trend_strength | top_consolidation_state | top_shock_alignment | top_dmi_alignment | top_vwap_alignment | top_ema_alignment |
| -------------- | ------- | ------ | -------- | ----------- | ---------- | ------- | ------------ | --------- | --------------- | ----------------- | ------------------ | -------------------- | ----------- | --------- | ----------- | ------------ | ------------ | ------------------ | ----------------------- | ------------------- | ----------------- | ------------------ | ----------------- |
| context_change | SOLUSDT | 16     | 0.6250   | 1.1117      | 1.0564     | 4.1532  | 0.9275       | 3.3930    | 1.1423          | 2.0000            | 0.0528             | 0.1759               | 0.6250      | 0.3125    | 0.0625      | 2.1050       | -0.6766      | strong_trend       | directional             | no_shock            | aligned           | aligned            | aligned           |
| ALL            | ALL     | 16     | 0.6250   | 1.1117      | 1.0564     | 4.1532  | 0.9275       | 3.3930    | 1.1423          | 2.0000            | 0.0528             | 0.1759               | 0.6250      | 0.3125    | 0.0625      | 2.1050       | -0.6766      | strong_trend       | directional             | no_shock            | aligned           | aligned            | aligned           |

## Session Split

| setup          | session_utc | trades | base_avg_r | base_pf | median_stop_pct |
| -------------- | ----------- | ------ | ---------- | ------- | --------------- |
| context_change | asia        | 16     | 1.0564     | 4.1532  | 1.1423          |

## Context Split

| trend_strength | consolidation_state | shock_alignment | dmi_alignment | vwap_alignment | ema_alignment | trades | stress_avg_r | stress_pf |
| -------------- | ------------------- | --------------- | ------------- | -------------- | ------------- | ------ | ------------ | --------- |
| strong_trend   | directional         | no_shock        | aligned       | opposed        | opposed       | 1      | 4.6273       | inf       |
| transition     | transition          | no_shock        | aligned       | flat           | aligned       | 1      | 1.8792       | inf       |
| strong_trend   | directional         | no_shock        | aligned       | aligned        | aligned       | 2      | 1.8597       | inf       |
| weak_or_range  | volatile_range      | no_shock        | aligned       | flat           | aligned       | 1      | 1.8528       | inf       |
| weak_or_range  | range               | no_shock        | aligned       | opposed        | aligned       | 1      | 1.8384       | inf       |
| trend          | directional         | no_shock        | aligned       | aligned        | opposed       | 1      | 1.7875       | inf       |
| strong_trend   | directional         | no_shock        | aligned       | aligned        | opposed       | 1      | 1.7687       | inf       |
| trend          | directional         | no_shock        | aligned       | flat           | aligned       | 1      | 1.6526       | inf       |
| transition     | transition          | no_shock        | aligned       | aligned        | aligned       | 3      | 0.1881       | 1.4173    |
| strong_trend   | directional         | no_shock        | aligned       | flat           | opposed       | 1      | -1.1091      | 0.0000    |
| strong_trend   | directional         | no_shock        | opposed       | aligned        | opposed       | 1      | -1.1985      | 0.0000    |
| weak_or_range  | range               | no_shock        | aligned       | aligned        | aligned       | 1      | -1.2126      | 0.0000    |
| transition     | transition          | no_shock        | aligned       | aligned        | opposed       | 1      | -1.3296      | 0.0000    |

## Rolling Windows

### 30-day windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | worst_base_dd_pct | median_stress_pf | worst_stress_return_r | worst_stress_dd_pct | base_sharpe | stress_sharpe |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ----------------- | ---------------- | --------------------- | ------------------- | ----------- | ------------- |
| 5       | 8.0000        | 1.0000                | 1.0000                  | 15.9532        | 12.4454             | 12.4454           | 14.2001          | 11.6495               | 11.6495             | 948.8355    | 822.3884      |

### 60-day windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | worst_base_dd_pct | median_stress_pf | worst_stress_return_r | worst_stress_dd_pct | base_sharpe | stress_sharpe |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ----------------- | ---------------- | --------------------- | ------------------- | ----------- | ------------- |
| 1       | 12.0000       | 1.0000                | 1.0000                  | 9.5062         | 18.1886             | 18.1886           | 7.8240           | 16.7934               | 16.7934             |             |               |

## Read

- Base cost uses 6bps round-trip, roughly taker entry plus maker target exit.
- Stress cost uses 20bps round-trip. If a setup dies there, it has weak execution margin.
- This lab is not a promotion tool. It exists to falsify simple setup ideas before they reach the engine.
