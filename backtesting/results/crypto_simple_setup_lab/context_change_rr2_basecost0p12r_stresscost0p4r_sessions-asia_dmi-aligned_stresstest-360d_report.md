# Simple Crypto Setup Lab

Scope: one setup family at a time, existing 240m/30m structure+EMA direction context, 15m entry, structural SL/TP, explicit cost-per-R.

## Summary

| setup          | symbol   | trades | win_rate | gross_avg_r | base_avg_r | base_pf | stress_avg_r | stress_pf | median_stop_pct | median_planned_rr | median_base_cost_r | median_stress_cost_r | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r | top_trend_strength | top_consolidation_state | top_shock_alignment | top_dmi_alignment |
| -------------- | -------- | ------ | -------- | ----------- | ---------- | ------- | ------------ | --------- | --------------- | ----------------- | ------------------ | -------------------- | ----------- | --------- | ----------- | ------------ | ------------ | ------------------ | ----------------------- | ------------------- | ----------------- |
| context_change | BNBUSDT  | 43     | 0.3953   | 0.2791      | 0.2151     | 1.3934  | 0.0660       | 1.1049    | 0.8730          | 2.0000            | 0.0687             | 0.2291               | 0.3953      | 0.5116    | 0.0930      | 1.7504       | -1.0294      | strong_trend       | directional             | no_shock            | aligned           |
| context_change | BTCUSDT  | 37     | 0.4595   | 0.5164      | 0.4441     | 2.0048  | 0.2754       | 1.5223    | 0.7709          | 2.0000            | 0.0778             | 0.2594               | 0.4595      | 0.4054    | 0.1351      | 1.8001       | -0.6535      | trend              | directional             | no_shock            | aligned           |
| context_change | DOGEUSDT | 63     | 0.4286   | 0.4177      | 0.3634     | 1.7715  | 0.2368       | 1.4440    | 1.2092          | 2.0000            | 0.0496             | 0.1654               | 0.4286      | 0.4444    | 0.1270      | 1.4818       | -0.6636      | trend              | directional             | no_shock            | aligned           |
| context_change | ETHUSDT  | 50     | 0.4200   | 0.3200      | 0.2530     | 1.4537  | 0.0966       | 1.1496    | 0.8367          | 2.0000            | 0.0717             | 0.2391               | 0.4200      | 0.5200    | 0.0600      | 1.6382       | -1.0023      | trend              | directional             | no_shock            | aligned           |
| context_change | SOLUSDT  | 58     | 0.4655   | 0.5308      | 0.4787     | 2.0077  | 0.3570       | 1.6643    | 1.2047          | 2.0000            | 0.0498             | 0.1661               | 0.4655      | 0.4483    | 0.0862      | 1.8042       | -0.8716      | trend              | directional             | no_shock            | aligned           |
| context_change | XRPUSDT  | 64     | 0.3906   | 0.2829      | 0.2162     | 1.3911  | 0.0607       | 1.0949    | 0.9215          | 2.0000            | 0.0651             | 0.2170               | 0.3906      | 0.5156    | 0.0938      | 1.5027       | -1.0000      | strong_trend       | directional             | no_shock            | aligned           |
| ALL            | ALL      | 315    | 0.4254   | 0.3883      | 0.3264     | 1.6412  | 0.1821       | 1.3109    | 0.9758          | 2.0000            | 0.0615             | 0.2050               | 0.4254      | 0.4762    | 0.0984      | 1.6605       | -0.9048      | trend              | directional             | no_shock            | aligned           |

## Session Split

| setup          | session_utc | trades | base_avg_r | base_pf | median_stop_pct |
| -------------- | ----------- | ------ | ---------- | ------- | --------------- |
| context_change | asia        | 315    | 0.3264     | 1.6412  | 0.9758          |

## Context Split

| trend_strength | consolidation_state       | shock_alignment | dmi_alignment | trades | stress_avg_r | stress_pf |
| -------------- | ------------------------- | --------------- | ------------- | ------ | ------------ | --------- |
| weak_or_range  | volatile_range            | no_shock        | aligned       | 2      | 1.8383       | inf       |
| weak_or_range  | tight_range               | opposing_shock  | aligned       | 1      | 1.6897       | inf       |
| weak_or_range  | range                     | no_shock        | aligned       | 28     | 0.6097       | 2.3511    |
| weak_or_range  | range                     | aligned_shock   | aligned       | 9      | 0.5345       | 2.1844    |
| strong_trend   | directional               | no_shock        | aligned       | 60     | 0.5151       | 2.1433    |
| trend          | directional               | no_shock        | aligned       | 49     | 0.5063       | 2.1131    |
| weak_or_range  | range                     | opposing_shock  | aligned       | 4      | 0.2616       | 1.4178    |
| transition     | transition                | no_shock        | aligned       | 27     | 0.1624       | 1.2543    |
| weak_or_range  | volatile_range            | aligned_shock   | aligned       | 1      | -0.0673      | 0.0000    |
| transition     | transition                | opposing_shock  | aligned       | 13     | -0.0817      | 0.8919    |
| strong_trend   | directional               | aligned_shock   | aligned       | 17     | -0.0902      | 0.8211    |
| trend          | directional               | aligned_shock   | aligned       | 35     | -0.1487      | 0.7912    |
| strong_trend   | directional               | opposing_shock  | aligned       | 17     | -0.1709      | 0.7587    |
| trend          | directional               | opposing_shock  | aligned       | 24     | -0.1929      | 0.7520    |
| transition     | transition                | aligned_shock   | aligned       | 20     | -0.2898      | 0.6100    |
| transition     | range_to_trend_transition | aligned_shock   | aligned       | 1      | -1.1161      | 0.0000    |
| transition     | coiling_transition        | no_shock        | aligned       | 4      | -1.2275      | 0.0000    |
| transition     | range_to_trend_transition | no_shock        | aligned       | 3      | -1.2655      | 0.0000    |

## Rolling Windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | median_stress_pf | worst_stress_return_r |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ---------------- | --------------------- |
| 47      | 25.0000       | 0.6170                | 0.5532                  | 1.3329         | -11.0281            | 1.0701           | -13.4270              |

## Read

- Base cost uses 6bps round-trip, roughly taker entry plus maker target exit.
- Stress cost uses 20bps round-trip. If a setup dies there, it has weak execution margin.
- This lab is not a promotion tool. It exists to falsify simple setup ideas before they reach the engine.
