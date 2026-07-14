# Simple Crypto Setup Lab

Scope: one setup family at a time, existing 240m/30m structure+EMA direction context, 15m entry, structural SL/TP, explicit cost-per-R.

## Summary

| setup          | symbol   | trades | win_rate | gross_avg_r | base_avg_r | base_pf | stress_avg_r | stress_pf | median_stop_pct | median_planned_rr | median_base_cost_r | median_stress_cost_r | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r | top_trend_strength | top_consolidation_state | top_shock_alignment | top_dmi_alignment |
| -------------- | -------- | ------ | -------- | ----------- | ---------- | ------- | ------------ | --------- | --------------- | ----------------- | ------------------ | -------------------- | ----------- | --------- | ----------- | ------------ | ------------ | ------------------ | ----------------------- | ------------------- | ----------------- |
| context_change | BNBUSDT  | 16     | 0.5000   | 0.5625      | 0.4970     | 2.0706  | 0.3440       | 1.6535    | 0.8996          | 2.0000            | 0.0669             | 0.2230               | 0.5000      | 0.4375    | 0.0625      | 1.8917       | -0.3217      | strong_trend       | directional             | no_shock            | aligned           |
| context_change | BTCUSDT  | 12     | 0.5000   | 0.6667      | 0.5912     | 2.6129  | 0.4151       | 1.9349    | 0.7231          | 2.0000            | 0.0832             | 0.2773               | 0.5000      | 0.3333    | 0.1667      | 1.9693       | -0.3035      | trend              | directional             | no_shock            | aligned           |
| context_change | DOGEUSDT | 24     | 0.4167   | 0.6389      | 0.5839     | 2.6381  | 0.4556       | 2.1102    | 1.2200          | 2.0000            | 0.0492             | 0.1639               | 0.4167      | 0.3333    | 0.2500      | 1.6536       | -0.4804      | strong_trend       | directional             | no_shock            | aligned           |
| context_change | ETHUSDT  | 13     | 0.5385   | 0.6948      | 0.6315     | 2.5429  | 0.4839       | 2.0362    | 0.9758          | 2.0000            | 0.0615             | 0.2050               | 0.5385      | 0.3846    | 0.0769      | 2.1268       | -0.6892      | strong_trend       | directional             | no_shock            | aligned           |
| context_change | SOLUSDT  | 15     | 0.5333   | 1.0719      | 1.0051     | 3.3300  | 0.8494       | 2.6832    | 0.9890          | 2.0000            | 0.0607             | 0.2022               | 0.5333      | 0.4000    | 0.0667      | 2.0667       | -0.6250      | transition         | directional             | no_shock            | aligned           |
| context_change | XRPUSDT  | 17     | 0.5294   | 0.6821      | 0.6119     | 2.3724  | 0.4479       | 1.8527    | 0.9244          | 2.0000            | 0.0649             | 0.2164               | 0.5294      | 0.4118    | 0.0588      | 2.0098       | -0.7063      | strong_trend       | directional             | aligned_shock       | aligned           |
| ALL            | ALL      | 97     | 0.4948   | 0.7118      | 0.6469     | 2.5785  | 0.4955       | 2.0411    | 0.9735          | 2.0000            | 0.0616             | 0.2054               | 0.4948      | 0.3814    | 0.1237      | 1.9217       | -0.5352      | strong_trend       | directional             | no_shock            | aligned           |

## Session Split

| setup          | session_utc | trades | base_avg_r | base_pf | median_stop_pct |
| -------------- | ----------- | ------ | ---------- | ------- | --------------- |
| context_change | asia        | 97     | 0.6469     | 2.5785  | 0.9735          |

## Context Split

| trend_strength | consolidation_state | shock_alignment | dmi_alignment | trades | stress_avg_r | stress_pf |
| -------------- | ------------------- | --------------- | ------------- | ------ | ------------ | --------- |
| weak_or_range  | volatile_range      | no_shock        | aligned       | 1      | 1.8528       | inf       |
| strong_trend   | directional         | no_shock        | aligned       | 23     | 1.4720       | 10.3027   |
| trend          | directional         | no_shock        | aligned       | 16     | 0.9231       | 3.9729    |
| transition     | transition          | opposing_shock  | aligned       | 4      | 0.7443       | 2.2323    |
| weak_or_range  | range               | no_shock        | aligned       | 11     | 0.4975       | 2.0855    |
| strong_trend   | directional         | opposing_shock  | aligned       | 7      | 0.2222       | 1.3111    |
| trend          | directional         | aligned_shock   | aligned       | 10     | -0.0723      | 0.8838    |
| transition     | transition          | aligned_shock   | aligned       | 5      | -0.2159      | 0.6251    |
| transition     | transition          | no_shock        | aligned       | 8      | -0.3069      | 0.5927    |
| trend          | directional         | opposing_shock  | aligned       | 4      | -0.4239      | 0.5173    |
| weak_or_range  | volatile_range      | aligned_shock   | aligned       | 2      | -0.6459      | 0.0000    |
| weak_or_range  | range               | aligned_shock   | aligned       | 2      | -0.7208      | 0.0000    |
| strong_trend   | directional         | aligned_shock   | aligned       | 4      | -0.9330      | 0.0000    |

## Rolling Windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | median_stress_pf | worst_stress_return_r |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ---------------- | --------------------- |
| 20      | 16.5000       | 1.0000                | 1.0000                  | 2.7337         | 4.4208              | 1.9741           | 3.0298                |

## Read

- Base cost uses 6bps round-trip, roughly taker entry plus maker target exit.
- Stress cost uses 20bps round-trip. If a setup dies there, it has weak execution margin.
- This lab is not a promotion tool. It exists to falsify simple setup ideas before they reach the engine.
