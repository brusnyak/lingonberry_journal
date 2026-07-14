# Simple Crypto Setup Lab

Scope: one setup family at a time, existing 240m/30m structure+EMA direction context, 15m entry, structural SL/TP, explicit cost-per-R.

## Summary

| setup          | symbol   | trades | win_rate | gross_avg_r | base_avg_r | base_pf | stress_avg_r | stress_pf | median_stop_pct | median_planned_rr | median_base_cost_r | median_stress_cost_r | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r | top_trend_strength | top_consolidation_state | top_shock_alignment | top_dmi_alignment |
| -------------- | -------- | ------ | -------- | ----------- | ---------- | ------- | ------------ | --------- | --------------- | ----------------- | ------------------ | -------------------- | ----------- | --------- | ----------- | ------------ | ------------ | ------------------ | ----------------------- | ------------------- | ----------------- |
| context_change | BNBUSDT  | 17     | 0.5882   | 0.7647      | 0.6976     | 2.5988  | 0.5409       | 2.0959    | 0.9948          | 2.0000            | 0.0603             | 0.2010               | 0.5882      | 0.4118    | 0.0000      | 2.0318       | -0.5760      | strong_trend       | directional             | no_shock            | aligned           |
| context_change | BTCUSDT  | 21     | 0.4762   | 0.5238      | 0.4406     | 1.9368  | 0.2466       | 1.4342    | 0.6816          | 2.0000            | 0.0880             | 0.2934               | 0.4762      | 0.4286    | 0.0952      | 2.0499       | -0.6801      | trend              | directional             | no_shock            | aligned           |
| context_change | DOGEUSDT | 28     | 0.4286   | 0.4286      | 0.3655     | 1.7954  | 0.2182       | 1.4105    | 1.0836          | 2.0000            | 0.0554             | 0.1846               | 0.4286      | 0.4286    | 0.1429      | 1.7368       | -0.7494      | trend              | directional             | no_shock            | aligned           |
| context_change | ETHUSDT  | 20     | 0.7000   | 1.1000      | 1.0403     | 4.2865  | 0.9009       | 3.5372    | 1.0541          | 2.0000            | 0.0570             | 0.1901               | 0.7000      | 0.3000    | 0.0000      | 2.1497       | -0.5724      | trend              | directional             | no_shock            | aligned           |
| context_change | SOLUSDT  | 29     | 0.6207   | 0.9926      | 0.9354     | 3.5642  | 0.8018       | 2.9491    | 1.0628          | 2.0000            | 0.0565             | 0.1882               | 0.6207      | 0.3448    | 0.0345      | 2.1500       | -0.7750      | transition         | directional             | no_shock            | aligned           |
| context_change | XRPUSDT  | 18     | 0.5556   | 0.7281      | 0.6557     | 2.3787  | 0.4867       | 1.8879    | 0.8310          | 2.0000            | 0.0722             | 0.2408               | 0.5556      | 0.4444    | 0.0000      | 2.0300       | -0.7019      | transition         | directional             | no_shock            | aligned           |
| ALL            | ALL      | 133    | 0.5564   | 0.7511      | 0.6848     | 2.6372  | 0.5302       | 2.1001    | 0.9409          | 2.0000            | 0.0638             | 0.2126               | 0.5564      | 0.3910    | 0.0526      | 2.0499       | -0.6771      | trend              | directional             | no_shock            | aligned           |

## Session Split

| setup          | session_utc | trades | base_avg_r | base_pf | median_stop_pct |
| -------------- | ----------- | ------ | ---------- | ------- | --------------- |
| context_change | asia        | 133    | 0.6848     | 2.6372  | 0.9409          |

## Context Split

| trend_strength | consolidation_state       | shock_alignment | dmi_alignment | trades | stress_avg_r | stress_pf |
| -------------- | ------------------------- | --------------- | ------------- | ------ | ------------ | --------- |
| weak_or_range  | volatile_range            | no_shock        | aligned       | 1      | 1.8528       | inf       |
| transition     | range_to_trend_transition | no_shock        | opposed       | 1      | 1.8167       | inf       |
| strong_trend   | directional               | no_shock        | aligned       | 31     | 1.0342       | 4.3373    |
| trend          | directional               | no_shock        | aligned       | 27     | 0.7368       | 2.7924    |
| transition     | transition                | no_shock        | opposed       | 11     | 0.5899       | 2.6236    |
| weak_or_range  | range                     | no_shock        | aligned       | 16     | 0.5008       | 2.0562    |
| weak_or_range  | range                     | no_shock        | opposed       | 9      | 0.4901       | 1.9444    |
| transition     | transition                | no_shock        | aligned       | 17     | 0.2720       | 1.4685    |
| trend          | directional               | no_shock        | opposed       | 12     | -0.2389      | 0.7102    |
| strong_trend   | directional               | no_shock        | opposed       | 6      | -0.5548      | 0.3247    |
| transition     | range_to_trend_transition | no_shock        | aligned       | 1      | -1.1301      | 0.0000    |
| transition     | coiling_transition        | no_shock        | aligned       | 1      | -1.3189      | 0.0000    |

## Rolling Windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | median_stress_pf | worst_stress_return_r |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ---------------- | --------------------- |
| 20      | 22.5000       | 0.8000                | 0.7500                  | 3.6917         | -3.8670             | 2.7636           | -8.2233               |

## Read

- Base cost uses 6bps round-trip, roughly taker entry plus maker target exit.
- Stress cost uses 20bps round-trip. If a setup dies there, it has weak execution margin.
- This lab is not a promotion tool. It exists to falsify simple setup ideas before they reach the engine.
