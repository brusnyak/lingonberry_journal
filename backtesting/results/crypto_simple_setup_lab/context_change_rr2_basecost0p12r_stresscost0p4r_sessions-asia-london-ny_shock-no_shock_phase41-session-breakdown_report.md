# Simple Crypto Setup Lab

Scope: one setup family at a time, existing 240m/30m structure+EMA direction context, 15m entry, structural SL/TP, explicit cost-per-R.

## Summary

| setup          | symbol   | trades | win_rate | gross_avg_r | base_avg_r | base_pf | stress_avg_r | stress_pf | median_stop_pct | median_planned_rr | median_base_cost_r | median_stress_cost_r | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r | top_trend_strength | top_consolidation_state | top_shock_alignment | top_dmi_alignment |
| -------------- | -------- | ------ | -------- | ----------- | ---------- | ------- | ------------ | --------- | --------------- | ----------------- | ------------------ | -------------------- | ----------- | --------- | ----------- | ------------ | ------------ | ------------------ | ----------------------- | ------------------- | ----------------- |
| context_change | BNBUSDT  | 40     | 0.4750   | 0.4250      | 0.3568     | 1.6342  | 0.1977       | 1.3040    | 0.9162          | 2.0000            | 0.0655             | 0.2183               | 0.4750      | 0.5250    | 0.0000      | 1.8478       | -1.0170      | strong_trend       | directional             | no_shock            | aligned           |
| context_change | BTCUSDT  | 48     | 0.4583   | 0.4375      | 0.3599     | 1.6904  | 0.1788       | 1.2886    | 0.7167          | 2.0000            | 0.0838             | 0.2792               | 0.4583      | 0.4792    | 0.0625      | 1.8095       | -0.8667      | trend              | directional             | no_shock            | aligned           |
| context_change | DOGEUSDT | 54     | 0.4074   | 0.2963      | 0.2319     | 1.4194  | 0.0817       | 1.1290    | 0.9876          | 2.0000            | 0.0609             | 0.2030               | 0.4074      | 0.5185    | 0.0741      | 1.5409       | -1.0098      | strong_trend       | directional             | no_shock            | aligned           |
| context_change | ETHUSDT  | 60     | 0.5333   | 0.6833      | 0.6174     | 2.4891  | 0.4637       | 1.9508    | 0.9409          | 2.0000            | 0.0638             | 0.2127               | 0.5333      | 0.3833    | 0.0833      | 2.0669       | -0.7391      | trend              | directional             | no_shock            | aligned           |
| context_change | SOLUSDT  | 52     | 0.5769   | 0.8228      | 0.7600     | 2.8594  | 0.6133       | 2.3191    | 1.0061          | 2.0000            | 0.0596             | 0.1988               | 0.5769      | 0.3846    | 0.0385      | 2.0633       | -0.7923      | trend              | directional             | no_shock            | aligned           |
| context_change | XRPUSDT  | 49     | 0.4694   | 0.4715      | 0.4011     | 1.7618  | 0.2367       | 1.3867    | 0.8527          | 2.0000            | 0.0704             | 0.2345               | 0.4694      | 0.4898    | 0.0408      | 1.3931       | -0.8786      | trend              | directional             | no_shock            | aligned           |
| ALL            | ALL      | 303    | 0.4884   | 0.5310      | 0.4630     | 1.9395  | 0.3043       | 1.5318    | 0.9041          | 2.0000            | 0.0664             | 0.2212               | 0.4884      | 0.4587    | 0.0528      | 1.8887       | -0.8500      | trend              | directional             | no_shock            | aligned           |

## Session Split

| setup          | session_utc | trades | base_avg_r | base_pf | median_stop_pct |
| -------------- | ----------- | ------ | ---------- | ------- | --------------- |
| context_change | asia        | 133    | 0.6848     | 2.6372  | 0.9409          |
| context_change | london      | 57     | 0.3245     | 1.5899  | 0.7006          |
| context_change | ny          | 113    | 0.2718     | 1.4927  | 0.9407          |

## Context Split

| trend_strength | consolidation_state       | shock_alignment | dmi_alignment | trades | stress_avg_r | stress_pf |
| -------------- | ------------------------- | --------------- | ------------- | ------ | ------------ | --------- |
| weak_or_range  | volatile_range            | no_shock        | aligned       | 1      | 1.8528       | inf       |
| transition     | range_to_trend_transition | no_shock        | opposed       | 3      | 1.7860       | inf       |
| strong_trend   | directional               | no_shock        | aligned       | 68     | 0.6799       | 2.5656    |
| weak_or_range  | range                     | no_shock        | opposed       | 16     | 0.6395       | 2.3978    |
| weak_or_range  | range                     | no_shock        | aligned       | 29     | 0.5448       | 2.1583    |
| transition     | transition                | no_shock        | opposed       | 17     | 0.4646       | 2.0033    |
| trend          | transition                | no_shock        | aligned       | 2      | 0.2675       | 1.4467    |
| trend          | directional               | no_shock        | aligned       | 79     | 0.2136       | 1.3555    |
| transition     | transition                | no_shock        | aligned       | 40     | 0.1432       | 1.2310    |
| strong_trend   | directional               | no_shock        | opposed       | 17     | -0.2278      | 0.6995    |
| trend          | directional               | no_shock        | opposed       | 29     | -0.4133      | 0.5430    |
| transition     | range_to_trend_transition | no_shock        | aligned       | 1      | -1.1301      | 0.0000    |
| transition     | coiling_transition        | no_shock        | aligned       | 1      | -1.3189      | 0.0000    |

## Rolling Windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | median_stress_pf | worst_stress_return_r |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ---------------- | --------------------- |
| 20      | 51.5000       | 0.7000                | 0.6000                  | 1.6728         | -13.2799            | 1.3136           | -20.9330              |

## Read

- Base cost uses 6bps round-trip, roughly taker entry plus maker target exit.
- Stress cost uses 20bps round-trip. If a setup dies there, it has weak execution margin.
- This lab is not a promotion tool. It exists to falsify simple setup ideas before they reach the engine.
