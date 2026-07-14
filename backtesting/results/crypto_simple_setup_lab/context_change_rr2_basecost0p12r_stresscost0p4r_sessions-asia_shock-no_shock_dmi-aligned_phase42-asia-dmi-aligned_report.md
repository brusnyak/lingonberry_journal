# Simple Crypto Setup Lab

Scope: one setup family at a time, existing 240m/30m structure+EMA direction context, 15m entry, structural SL/TP, explicit cost-per-R.

## Summary

| setup          | symbol   | trades | win_rate | gross_avg_r | base_avg_r | base_pf | stress_avg_r | stress_pf | median_stop_pct | median_planned_rr | median_base_cost_r | median_stress_cost_r | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r | top_trend_strength | top_consolidation_state | top_shock_alignment | top_dmi_alignment |
| -------------- | -------- | ------ | -------- | ----------- | ---------- | ------- | ------------ | --------- | --------------- | ----------------- | ------------------ | -------------------- | ----------- | --------- | ----------- | ------------ | ------------ | ------------------ | ----------------------- | ------------------- | ----------------- |
| context_change | BNBUSDT  | 15     | 0.5333   | 0.6000      | 0.5334     | 2.0787  | 0.3780       | 1.6758    | 0.9948          | 2.0000            | 0.0603             | 0.2010               | 0.5333      | 0.4667    | 0.0000      | 2.0082       | -0.5760      | strong_trend       | directional             | no_shock            | aligned           |
| context_change | BTCUSDT  | 11     | 0.4545   | 0.4545      | 0.3740     | 1.7572  | 0.1862       | 1.3178    | 0.6862          | 2.0000            | 0.0874             | 0.2915               | 0.4545      | 0.4545    | 0.0909      | 1.8887       | -0.9888      | trend              | directional             | no_shock            | aligned           |
| context_change | DOGEUSDT | 20     | 0.5500   | 0.7500      | 0.6819     | 2.8177  | 0.5230       | 2.2056    | 0.9904          | 2.0000            | 0.0609             | 0.2029               | 0.5500      | 0.3500    | 0.1000      | 2.0376       | -0.5882      | strong_trend       | directional             | no_shock            | aligned           |
| context_change | ETHUSDT  | 15     | 0.6667   | 1.0000      | 0.9405     | 3.6701  | 0.8016       | 3.0227    | 1.0060          | 2.0000            | 0.0596             | 0.1988               | 0.6667      | 0.3333    | 0.0000      | 2.2275       | -0.5342      | trend              | directional             | no_shock            | aligned           |
| context_change | SOLUSDT  | 20     | 0.6500   | 1.1393      | 1.0796     | 4.3449  | 0.9401       | 3.5014    | 1.1069          | 2.0000            | 0.0543             | 0.1810               | 0.6500      | 0.3000    | 0.0500      | 2.1083       | -0.5844      | strong_trend       | directional             | no_shock            | aligned           |
| context_change | XRPUSDT  | 13     | 0.7692   | 1.3927      | 1.3208     | 6.3801  | 1.1531       | 5.1200    | 0.8527          | 2.0000            | 0.0704             | 0.2345               | 0.7692      | 0.2308    | 0.0000      | 2.2105       | -0.5352      | transition         | directional             | no_shock            | aligned           |
| ALL            | ALL      | 94     | 0.6064   | 0.9031      | 0.8364     | 3.2283  | 0.6808       | 2.5758    | 0.9238          | 2.0000            | 0.0649             | 0.2165               | 0.6064      | 0.3511    | 0.0426      | 2.0529       | -0.5603      | strong_trend       | directional             | no_shock            | aligned           |

## Session Split

| setup          | session_utc | trades | base_avg_r | base_pf | median_stop_pct |
| -------------- | ----------- | ------ | ---------- | ------- | --------------- |
| context_change | asia        | 94     | 0.8364     | 3.2283  | 0.9238          |

## Context Split

| trend_strength | consolidation_state       | shock_alignment | dmi_alignment | trades | stress_avg_r | stress_pf |
| -------------- | ------------------------- | --------------- | ------------- | ------ | ------------ | --------- |
| weak_or_range  | volatile_range            | no_shock        | aligned       | 1      | 1.8528       | inf       |
| strong_trend   | directional               | no_shock        | aligned       | 31     | 1.0342       | 4.3373    |
| trend          | directional               | no_shock        | aligned       | 27     | 0.7368       | 2.7924    |
| weak_or_range  | range                     | no_shock        | aligned       | 16     | 0.5008       | 2.0562    |
| transition     | transition                | no_shock        | aligned       | 17     | 0.2720       | 1.4685    |
| transition     | range_to_trend_transition | no_shock        | aligned       | 1      | -1.1301      | 0.0000    |
| transition     | coiling_transition        | no_shock        | aligned       | 1      | -1.3189      | 0.0000    |

## Rolling Windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | median_stress_pf | worst_stress_return_r |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ---------------- | --------------------- |
| 20      | 15.0000       | 1.0000                | 0.9000                  | 5.4510         | 0.1015              | 4.4123           | -2.4075               |

## Read

- Base cost uses 6bps round-trip, roughly taker entry plus maker target exit.
- Stress cost uses 20bps round-trip. If a setup dies there, it has weak execution margin.
- This lab is not a promotion tool. It exists to falsify simple setup ideas before they reach the engine.
