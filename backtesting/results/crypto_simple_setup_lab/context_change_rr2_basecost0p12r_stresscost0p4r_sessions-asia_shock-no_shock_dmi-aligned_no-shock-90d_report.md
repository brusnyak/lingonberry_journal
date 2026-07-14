# Simple Crypto Setup Lab

Scope: one setup family at a time, existing 240m/30m structure+EMA direction context, 15m entry, structural SL/TP, explicit cost-per-R.

## Summary

| setup          | symbol   | trades | win_rate | gross_avg_r | base_avg_r | base_pf  | stress_avg_r | stress_pf | median_stop_pct | median_planned_rr | median_base_cost_r | median_stress_cost_r | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r | top_trend_strength | top_consolidation_state | top_shock_alignment | top_dmi_alignment | top_vwap_alignment | top_ema_alignment |
| -------------- | -------- | ------ | -------- | ----------- | ---------- | -------- | ------------ | --------- | --------------- | ----------------- | ------------------ | -------------------- | ----------- | --------- | ----------- | ------------ | ------------ | ------------------ | ----------------------- | ------------------- | ----------------- | ------------------ | ----------------- |
| context_change | BNBUSDT  | 8      | 0.7500   | 1.2500      | 1.1758     | 5.4852   | 1.0028       | 4.4516    | 0.8483          | 2.0000            | 0.0708             | 0.2360               | 0.7500      | 0.2500    | 0.0000      | 2.1289       | -0.2422      | strong_trend       | directional             | no_shock            | aligned           | aligned            | aligned           |
| context_change | BTCUSDT  | 5      | 0.8000   | 1.6000      | 1.5196     | 168.0196 | 1.3320       | 44.9208   | 0.6862          | 2.0000            | 0.0874             | 0.2915               | 0.8000      | 0.0000    | 0.2000      | 2.0994       | -0.2442      | trend              | directional             | no_shock            | aligned           | aligned            | aligned           |
| context_change | DOGEUSDT | 11     | 0.6364   | 0.9091      | 0.8367     | 3.1659   | 0.6677       | 2.5205    | 0.7632          | 2.0000            | 0.0786             | 0.2620               | 0.6364      | 0.3636    | 0.0000      | 2.1932       | -0.6310      | strong_trend       | directional             | no_shock            | aligned           | flat               | flat              |
| context_change | ETHUSDT  | 7      | 0.7143   | 1.1429      | 1.0827     | 4.6421   | 0.9424       | 3.9062    | 1.0060          | 2.0000            | 0.0596             | 0.1988               | 0.7143      | 0.2857    | 0.0000      | 2.1268       | -0.3613      | strong_trend       | directional             | no_shock            | aligned           | aligned            | aligned           |
| context_change | SOLUSDT  | 15     | 0.6667   | 1.2524      | 1.1975     | 5.1764   | 1.0692       | 4.2058    | 1.2219          | 2.0000            | 0.0491             | 0.1637               | 0.6667      | 0.2667    | 0.0667      | 2.1500       | -0.5437      | strong_trend       | directional             | no_shock            | aligned           | aligned            | aligned           |
| context_change | XRPUSDT  | 7      | 0.8571   | 1.7293      | 1.6510     | 11.7543  | 1.4682       | 9.2302    | 0.8527          | 2.0000            | 0.0704             | 0.2345               | 0.8571      | 0.1429    | 0.0000      | 2.2105       | -0.4868      | trend              | directional             | no_shock            | aligned           | flat               | opposed           |
| ALL            | ALL      | 53     | 0.7170   | 1.2621      | 1.1945     | 5.5714   | 1.0366       | 4.4710    | 0.9244          | 2.0000            | 0.0649             | 0.2164               | 0.7170      | 0.2453    | 0.0377      | 2.1500       | -0.3613      | strong_trend       | directional             | no_shock            | aligned           | aligned            | aligned           |

## Session Split

| setup          | session_utc | trades | base_avg_r | base_pf | median_stop_pct |
| -------------- | ----------- | ------ | ---------- | ------- | --------------- |
| context_change | asia        | 53     | 1.1945     | 5.5714  | 0.9244          |

## Context Split

| trend_strength | consolidation_state | shock_alignment | dmi_alignment | vwap_alignment | ema_alignment | trades | stress_avg_r | stress_pf |
| -------------- | ------------------- | --------------- | ------------- | -------------- | ------------- | ------ | ------------ | --------- |
| transition     | transition          | no_shock        | aligned       | flat           | aligned       | 1      | 1.8792       | inf       |
| weak_or_range  | volatile_range      | no_shock        | aligned       | flat           | aligned       | 1      | 1.8528       | inf       |
| weak_or_range  | range               | no_shock        | aligned       | opposed        | aligned       | 2      | 1.8111       | inf       |
| trend          | directional         | no_shock        | aligned       | aligned        | opposed       | 1      | 1.7875       | inf       |
| transition     | transition          | no_shock        | aligned       | flat           | opposed       | 1      | 1.7836       | inf       |
| strong_trend   | directional         | no_shock        | aligned       | opposed        | opposed       | 4      | 1.7721       | 6.8246    |
| strong_trend   | directional         | no_shock        | aligned       | aligned        | opposed       | 1      | 1.7687       | inf       |
| weak_or_range  | range               | no_shock        | aligned       | flat           | aligned       | 1      | 1.7571       | inf       |
| strong_trend   | directional         | no_shock        | aligned       | aligned        | aligned       | 6      | 1.7429       | inf       |
| transition     | transition          | no_shock        | aligned       | flat           | flat          | 2      | 1.7362       | inf       |
| trend          | directional         | no_shock        | aligned       | flat           | flat          | 2      | 1.7257       | inf       |
| trend          | directional         | no_shock        | aligned       | flat           | opposed       | 4      | 1.2858       | 5.1186    |
| trend          | directional         | no_shock        | aligned       | aligned        | aligned       | 5      | 1.1704       | 6.5578    |
| strong_trend   | directional         | no_shock        | aligned       | flat           | flat          | 4      | 1.0262       | 4.6015    |
| trend          | directional         | no_shock        | aligned       | flat           | aligned       | 2      | 0.7505       | 10.8985   |
| transition     | transition          | no_shock        | aligned       | aligned        | aligned       | 5      | 0.2575       | 1.5261    |
| weak_or_range  | range               | no_shock        | aligned       | aligned        | aligned       | 4      | 0.2361       | 1.3867    |
| strong_trend   | directional         | no_shock        | aligned       | aligned        | flat          | 2      | 0.2228       | 1.3747    |
| trend          | directional         | no_shock        | aligned       | aligned        | flat          | 3      | -0.2730      | 0.6726    |
| strong_trend   | directional         | no_shock        | aligned       | flat           | opposed       | 1      | -1.1091      | 0.0000    |

## Rolling Windows

### 30-day windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | worst_base_dd_pct | median_stress_pf | worst_stress_return_r | worst_stress_dd_pct | base_sharpe | stress_sharpe |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ----------------- | ---------------- | --------------------- | ------------------- | ----------- | ------------- |
| 7       | 29.0000       | 1.0000                | 1.0000                  | 10.6221        | 17.8701             | 17.8701           | 8.7420           | 15.2338               | 15.2338             | 225.9166    | 216.2261      |

### 60-day windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | worst_base_dd_pct | median_stress_pf | worst_stress_return_r | worst_stress_dd_pct | base_sharpe | stress_sharpe |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ----------------- | ---------------- | --------------------- | ------------------- | ----------- | ------------- |
| 2       | 44.0000       | 1.0000                | 1.0000                  | 8.7540         | 56.8549             | 56.8549           | 7.0343           | 49.7689               | 49.7689             | 1973.0348   | 1666.1990     |

## Read

- Base cost uses 6bps round-trip, roughly taker entry plus maker target exit.
- Stress cost uses 20bps round-trip. If a setup dies there, it has weak execution margin.
- This lab is not a promotion tool. It exists to falsify simple setup ideas before they reach the engine.
