# Simple Crypto Setup Lab

Scope: one setup family at a time, existing 240m/30m structure+EMA direction context, 15m entry, structural SL/TP, explicit cost-per-R.

## Summary

| setup          | symbol   | trades | win_rate | gross_avg_r | base_avg_r | base_pf | stress_avg_r | stress_pf | median_stop_pct | median_planned_rr | median_base_cost_r | median_stress_cost_r | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r | top_trend_strength | top_consolidation_state | top_shock_alignment | top_dmi_alignment | top_vwap_alignment | top_ema_alignment |
| -------------- | -------- | ------ | -------- | ----------- | ---------- | ------- | ------------ | --------- | --------------- | ----------------- | ------------------ | -------------------- | ----------- | --------- | ----------- | ------------ | ------------ | ------------------ | ----------------------- | ------------------- | ----------------- | ------------------ | ----------------- |
| context_change | BNBUSDT  | 12     | 0.5833   | 0.8333      | 0.7582     | 3.0987  | 0.5828       | 2.3667    | 0.8362          | 2.0000            | 0.0718             | 0.2392               | 0.5833      | 0.3333    | 0.0833      | 2.0388       | -0.2422      | strong_trend       | directional             | no_shock            | aligned           | aligned            | aligned           |
| context_change | BTCUSDT  | 9      | 0.5556   | 0.8889      | 0.8078     | 4.1349  | 0.6184       | 2.8170    | 0.6862          | 2.0000            | 0.0874             | 0.2915               | 0.5556      | 0.2222    | 0.2222      | 2.0499       | -0.2442      | trend              | directional             | no_shock            | aligned           | aligned            | aligned           |
| context_change | DOGEUSDT | 18     | 0.4444   | 0.5000      | 0.4407     | 2.0635  | 0.3024       | 1.6381    | 1.1755          | 2.0000            | 0.0510             | 0.1702               | 0.4444      | 0.3889    | 0.1667      | 1.8736       | -0.6131      | strong_trend       | directional             | no_shock            | aligned           | aligned            | flat              |
| context_change | ETHUSDT  | 13     | 0.5385   | 0.6923      | 0.6247     | 2.5116  | 0.4669       | 1.9725    | 0.8811          | 2.0000            | 0.0681             | 0.2270               | 0.5385      | 0.3846    | 0.0769      | 2.1068       | -0.5800      | trend              | directional             | no_shock            | aligned           | aligned            | aligned           |
| context_change | SOLUSDT  | 17     | 0.7059   | 1.3404      | 1.2843     | 6.0766  | 1.1536       | 4.9198    | 1.1875          | 2.0000            | 0.0505             | 0.1684               | 0.7059      | 0.2353    | 0.0588      | 2.1500       | -0.3708      | strong_trend       | directional             | no_shock            | aligned           | aligned            | aligned           |
| context_change | XRPUSDT  | 15     | 0.5333   | 0.7403      | 0.6679     | 2.5468  | 0.4988       | 1.9858    | 0.9015          | 2.0000            | 0.0666             | 0.2219               | 0.5333      | 0.4000    | 0.0667      | 2.0098       | -0.5474      | strong_trend       | directional             | no_shock            | aligned           | flat               | aligned           |
| ALL            | ALL      | 84     | 0.5595   | 0.8320      | 0.7652     | 3.1238  | 0.6091       | 2.4394    | 0.9251          | 2.0000            | 0.0649             | 0.2162               | 0.5595      | 0.3333    | 0.1071      | 2.0514       | -0.5026      | strong_trend       | directional             | no_shock            | aligned           | aligned            | aligned           |

## Session Split

| setup          | session_utc | trades | base_avg_r | base_pf | median_stop_pct |
| -------------- | ----------- | ------ | ---------- | ------- | --------------- |
| context_change | asia        | 84     | 0.7652     | 3.1238  | 0.9251          |

## Context Split

| trend_strength | consolidation_state | shock_alignment | dmi_alignment | vwap_alignment | ema_alignment | trades | stress_avg_r | stress_pf |
| -------------- | ------------------- | --------------- | ------------- | -------------- | ------------- | ------ | ------------ | --------- |
| transition     | transition          | no_shock        | aligned       | flat           | aligned       | 1      | 1.8792       | inf       |
| weak_or_range  | volatile_range      | no_shock        | aligned       | flat           | aligned       | 1      | 1.8528       | inf       |
| trend          | directional         | opposing_shock  | aligned       | flat           | opposed       | 2      | 1.8245       | inf       |
| weak_or_range  | range               | no_shock        | aligned       | opposed        | aligned       | 2      | 1.8111       | inf       |
| transition     | transition          | aligned_shock   | aligned       | aligned        | flat          | 1      | 1.7994       | inf       |
| trend          | directional         | no_shock        | aligned       | aligned        | opposed       | 1      | 1.7875       | inf       |
| transition     | transition          | no_shock        | aligned       | flat           | opposed       | 1      | 1.7836       | inf       |
| strong_trend   | directional         | no_shock        | aligned       | opposed        | opposed       | 4      | 1.7721       | 6.8246    |
| strong_trend   | directional         | no_shock        | aligned       | aligned        | opposed       | 1      | 1.7687       | inf       |
| strong_trend   | directional         | opposing_shock  | aligned       | flat           | aligned       | 1      | 1.7644       | inf       |
| transition     | transition          | opposing_shock  | aligned       | flat           | flat          | 1      | 1.7607       | inf       |
| weak_or_range  | range               | no_shock        | aligned       | flat           | aligned       | 1      | 1.7571       | inf       |
| strong_trend   | directional         | no_shock        | aligned       | aligned        | aligned       | 6      | 1.7429       | inf       |
| trend          | directional         | opposing_shock  | aligned       | flat           | aligned       | 1      | 1.7406       | inf       |
| transition     | transition          | no_shock        | aligned       | flat           | flat          | 2      | 1.7362       | inf       |
| trend          | directional         | no_shock        | aligned       | flat           | flat          | 2      | 1.7257       | inf       |
| trend          | directional         | no_shock        | aligned       | flat           | opposed       | 4      | 1.2858       | 5.1186    |
| trend          | directional         | no_shock        | aligned       | aligned        | aligned       | 5      | 1.1704       | 6.5578    |
| strong_trend   | directional         | no_shock        | aligned       | flat           | flat          | 4      | 1.0262       | 4.6015    |
| trend          | directional         | no_shock        | aligned       | flat           | aligned       | 2      | 0.7505       | 10.8985   |

## Rolling Windows

### 30-day windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | worst_base_dd_pct | median_stress_pf | worst_stress_return_r | worst_stress_dd_pct | base_sharpe | stress_sharpe |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ----------------- | ---------------- | --------------------- | ------------------- | ----------- | ------------- |
| 7       | 39.0000       | 1.0000                | 1.0000                  | 4.1343         | 8.7715              | 8.7715            | 3.1197           | 3.5716                | 3.5716              | 155.7023    | 132.5262      |

### 60-day windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | worst_base_dd_pct | median_stress_pf | worst_stress_return_r | worst_stress_dd_pct | base_sharpe | stress_sharpe |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ----------------- | ---------------- | --------------------- | ------------------- | ----------- | ------------- |
| 2       | 69.0000       | 1.0000                | 1.0000                  | 3.7826         | 58.1071             | 58.1071           | 2.9312           | 46.9429               | 46.9429             | 3037.2348   | 2208.8318     |

## Read

- Base cost uses 6bps round-trip, roughly taker entry plus maker target exit.
- Stress cost uses 20bps round-trip. If a setup dies there, it has weak execution margin.
- This lab is not a promotion tool. It exists to falsify simple setup ideas before they reach the engine.
