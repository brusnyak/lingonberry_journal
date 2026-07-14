# Simple Crypto Setup Lab

Scope: one setup family at a time, existing 240m/30m structure+EMA direction context, 15m entry, structural SL/TP, explicit cost-per-R.

## Summary

| setup          | symbol  | trades | win_rate | gross_avg_r | base_avg_r | base_pf | stress_avg_r | stress_pf | median_stop_pct | median_planned_rr | median_base_cost_r | median_stress_cost_r | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r | top_trend_strength | top_consolidation_state | top_shock_alignment | top_dmi_alignment | top_vwap_alignment | top_ema_alignment |
| -------------- | ------- | ------ | -------- | ----------- | ---------- | ------- | ------------ | --------- | --------------- | ----------------- | ------------------ | -------------------- | ----------- | --------- | ----------- | ------------ | ------------ | ------------------ | ----------------------- | ------------------- | ----------------- | ------------------ | ----------------- |
| context_change | SOLUSDT | 16     | 0.6875   | 0.4334      | 0.3781     | 2.7192  | 0.2492       | 1.9526    | 1.1423          | 2.0000            | 0.0528             | 0.1759               | 0.6875      | 0.3125    | 0.0000      | 1.0780       | -0.4058      | strong_trend       | directional             | no_shock            | aligned           | aligned            | aligned           |
| ALL            | ALL     | 16     | 0.6875   | 0.4334      | 0.3781     | 2.7192  | 0.2492       | 1.9526    | 1.1423          | 2.0000            | 0.0528             | 0.1759               | 0.6875      | 0.3125    | 0.0000      | 1.0780       | -0.4058      | strong_trend       | directional             | no_shock            | aligned           | aligned            | aligned           |

## Session Split

| setup          | session_utc | trades | base_avg_r | base_pf | median_stop_pct |
| -------------- | ----------- | ------ | ---------- | ------- | --------------- |
| context_change | asia        | 16     | 0.3781     | 2.7192  | 1.1423          |

## Context Split

| trend_strength | consolidation_state | shock_alignment | dmi_alignment | vwap_alignment | ema_alignment | trades | stress_avg_r | stress_pf |
| -------------- | ------------------- | --------------- | ------------- | -------------- | ------------- | ------ | ------------ | --------- |
| transition     | transition          | no_shock        | aligned       | flat           | aligned       | 1      | 1.3792       | inf       |
| weak_or_range  | range               | no_shock        | aligned       | opposed        | aligned       | 1      | 1.3384       | inf       |
| trend          | directional         | no_shock        | aligned       | flat           | aligned       | 1      | 1.1526       | inf       |
| strong_trend   | directional         | no_shock        | aligned       | aligned        | aligned       | 2      | 0.9086       | inf       |
| weak_or_range  | volatile_range      | no_shock        | aligned       | flat           | aligned       | 1      | 0.7545       | inf       |
| trend          | directional         | no_shock        | aligned       | aligned        | opposed       | 1      | 0.6573       | inf       |
| strong_trend   | directional         | no_shock        | aligned       | opposed        | opposed       | 1      | 0.4363       | inf       |
| weak_or_range  | range               | no_shock        | aligned       | aligned        | aligned       | 1      | 0.2874       | inf       |
| transition     | transition          | no_shock        | aligned       | aligned        | aligned       | 3      | -0.0633      | 0.6483    |
| transition     | transition          | no_shock        | aligned       | aligned        | opposed       | 1      | -0.5979      | 0.0000    |
| strong_trend   | directional         | no_shock        | opposed       | aligned        | opposed       | 1      | -0.6985      | 0.0000    |
| strong_trend   | directional         | no_shock        | aligned       | flat           | opposed       | 1      | -1.1178      | 0.0000    |
| strong_trend   | directional         | no_shock        | aligned       | aligned        | opposed       | 1      | -1.2313      | 0.0000    |

## Rolling Windows

### 30-day windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | worst_base_dd_pct | median_stress_pf | worst_stress_return_r | worst_stress_dd_pct | base_sharpe | stress_sharpe |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ----------------- | ---------------- | --------------------- | ------------------- | ----------- | ------------- |
| 5       | 8.0000        | 1.0000                | 1.0000                  | 1.8345         | 1.3244              | 1.3244            | 1.4540           | 0.1449                | 0.1449              | 160.2842    | 100.4292      |

### 60-day windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | worst_base_dd_pct | median_stress_pf | worst_stress_return_r | worst_stress_dd_pct | base_sharpe | stress_sharpe |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ----------------- | ---------------- | --------------------- | ------------------- | ----------- | ------------- |
| 1       | 12.0000       | 1.0000                | 1.0000                  | 3.2120         | 5.7342              | 5.7342            | 2.5017           | 4.3390                | 4.3390              |             |               |

## Read

- Base cost uses 6bps round-trip, roughly taker entry plus maker target exit.
- Stress cost uses 20bps round-trip. If a setup dies there, it has weak execution margin.
- This lab is not a promotion tool. It exists to falsify simple setup ideas before they reach the engine.
