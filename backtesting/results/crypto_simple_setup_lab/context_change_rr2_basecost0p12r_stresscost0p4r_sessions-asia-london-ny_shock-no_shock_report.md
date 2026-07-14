# Simple Crypto Setup Lab

Scope: one setup family at a time, existing 240m/30m structure+EMA direction context, 15m entry, structural SL/TP, explicit cost-per-R.

## Summary

| setup          | symbol   | trades | win_rate | gross_avg_r | base_avg_r | base_pf | stress_avg_r | stress_pf | median_stop_pct | median_planned_rr | median_base_cost_r | median_stress_cost_r | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r | top_trend_strength | top_consolidation_state | top_shock_alignment |
| -------------- | -------- | ------ | -------- | ----------- | ---------- | ------- | ------------ | --------- | --------------- | ----------------- | ------------------ | -------------------- | ----------- | --------- | ----------- | ------------ | ------------ | ------------------ | ----------------------- | ------------------- |
| context_change | BTCUSDT  | 77     | 0.4545   | 0.4545      | 0.3766     | 1.7597  | 0.1948       | 1.3290    | 0.7318          | 2.0000            | 0.0820             | 0.2733               | 0.4545      | 0.4545    | 0.0909      | 1.8001       | -0.7566      | trend              | directional             | no_shock            |
| context_change | DOGEUSDT | 121    | 0.4298   | 0.4088      | 0.3467     | 1.6889  | 0.2018       | 1.3490    | 1.0833          | 2.0000            | 0.0554             | 0.1846               | 0.4298      | 0.4711    | 0.0992      | 1.6786       | -0.8462      | trend              | directional             | no_shock            |
| context_change | ETHUSDT  | 107    | 0.4579   | 0.4579      | 0.3897     | 1.7869  | 0.2305       | 1.3959    | 0.8500          | 2.0000            | 0.0706             | 0.2353               | 0.4579      | 0.4579    | 0.0841      | 1.8399       | -0.8983      | trend              | directional             | no_shock            |
| context_change | SOLUSDT  | 129    | 0.5116   | 0.6321      | 0.5698     | 2.2737  | 0.4245       | 1.8250    | 0.9900          | 2.0000            | 0.0606             | 0.2020               | 0.5116      | 0.4186    | 0.0698      | 2.0145       | -0.8560      | trend              | directional             | no_shock            |
| context_change | XRPUSDT  | 122    | 0.4836   | 0.5208      | 0.4503     | 1.8941  | 0.2859       | 1.4857    | 0.8547          | 2.0000            | 0.0702             | 0.2340               | 0.4836      | 0.4672    | 0.0492      | 1.9628       | -0.8884      | trend              | directional             | no_shock            |
| ALL            | ALL      | 556    | 0.4694   | 0.5010      | 0.4336     | 1.8890  | 0.2765       | 1.4864    | 0.9063          | 2.0000            | 0.0662             | 0.2207               | 0.4694      | 0.4532    | 0.0773      | 1.8448       | -0.8603      | trend              | directional             | no_shock            |

## Session Split

| setup          | session_utc | trades | base_avg_r | base_pf | median_stop_pct |
| -------------- | ----------- | ------ | ---------- | ------- | --------------- |
| context_change | asia        | 243    | 0.4771     | 2.0087  | 0.9624          |
| context_change | london      | 119    | 0.5147     | 2.0742  | 0.8448          |
| context_change | ny          | 194    | 0.3294     | 1.6438  | 0.9344          |

## Context Split

| trend_strength | consolidation_state       | shock_alignment | trades | stress_avg_r | stress_pf |
| -------------- | ------------------------- | --------------- | ------ | ------------ | --------- |
| weak_or_range  | volatile_range            | no_shock        | 10     | 0.7450       | 2.5258    |
| weak_or_range  | range                     | no_shock        | 81     | 0.5181       | 2.0893    |
| transition     | range_to_trend_transition | no_shock        | 9      | 0.4334       | 1.7923    |
| strong_trend   | directional               | no_shock        | 157    | 0.3504       | 1.6638    |
| trend          | transition                | no_shock        | 2      | 0.2675       | 1.4467    |
| transition     | transition                | no_shock        | 87     | 0.2290       | 1.3942    |
| trend          | directional               | no_shock        | 205    | 0.1517       | 1.2450    |
| transition     | coiling_transition        | no_shock        | 4      | -1.2275      | 0.0000    |
| weak_or_range  | tight_range               | no_shock        | 1      | -1.2561      | 0.0000    |

## Rolling Windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | median_stress_pf | worst_stress_return_r |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ---------------- | --------------------- |
| 52      | 41.0000       | 0.8462                | 0.7308                  | 1.9331         | -16.3164            | 1.5020           | -21.7212              |

## Read

- Base cost uses 6bps round-trip, roughly taker entry plus maker target exit.
- Stress cost uses 20bps round-trip. If a setup dies there, it has weak execution margin.
- This lab is not a promotion tool. It exists to falsify simple setup ideas before they reach the engine.
