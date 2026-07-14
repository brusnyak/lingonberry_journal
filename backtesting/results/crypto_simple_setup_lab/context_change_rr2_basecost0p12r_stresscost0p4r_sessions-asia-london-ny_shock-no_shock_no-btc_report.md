# Simple Crypto Setup Lab

Scope: one setup family at a time, existing 240m/30m structure+EMA direction context, 15m entry, structural SL/TP, explicit cost-per-R.

## Summary

| setup          | symbol   | trades | win_rate | gross_avg_r | base_avg_r | base_pf | stress_avg_r | stress_pf | median_stop_pct | median_planned_rr | median_base_cost_r | median_stress_cost_r | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r | top_trend_strength | top_consolidation_state | top_shock_alignment | top_dmi_alignment |
| -------------- | -------- | ------ | -------- | ----------- | ---------- | ------- | ------------ | --------- | --------------- | ----------------- | ------------------ | -------------------- | ----------- | --------- | ----------- | ------------ | ------------ | ------------------ | ----------------------- | ------------------- | ----------------- |
| context_change | DOGEUSDT | 121    | 0.4298   | 0.4088      | 0.3467     | 1.6889  | 0.2018       | 1.3490    | 1.0833          | 2.0000            | 0.0554             | 0.1846               | 0.4298      | 0.4711    | 0.0992      | 1.6786       | -0.8462      | trend              | directional             | no_shock            | aligned           |
| context_change | ETHUSDT  | 107    | 0.4579   | 0.4579      | 0.3897     | 1.7869  | 0.2305       | 1.3959    | 0.8500          | 2.0000            | 0.0706             | 0.2353               | 0.4579      | 0.4579    | 0.0841      | 1.8399       | -0.8983      | trend              | directional             | no_shock            | aligned           |
| context_change | SOLUSDT  | 129    | 0.5116   | 0.6321      | 0.5698     | 2.2737  | 0.4245       | 1.8250    | 0.9900          | 2.0000            | 0.0606             | 0.2020               | 0.5116      | 0.4186    | 0.0698      | 2.0145       | -0.8560      | trend              | directional             | no_shock            | aligned           |
| context_change | XRPUSDT  | 122    | 0.4836   | 0.5208      | 0.4503     | 1.8941  | 0.2859       | 1.4857    | 0.8547          | 2.0000            | 0.0702             | 0.2340               | 0.4836      | 0.4672    | 0.0492      | 1.9628       | -0.8884      | trend              | directional             | no_shock            | aligned           |
| ALL            | ALL      | 479    | 0.4718   | 0.5084      | 0.4428     | 1.9101  | 0.2896       | 1.5129    | 0.9377          | 2.0000            | 0.0640             | 0.2133               | 0.4718      | 0.4530    | 0.0752      | 1.8491       | -0.8750      | trend              | directional             | no_shock            | aligned           |

## Session Split

| setup          | session_utc | trades | base_avg_r | base_pf | median_stop_pct |
| -------------- | ----------- | ------ | ---------- | ------- | --------------- |
| context_change | asia        | 209    | 0.4768     | 1.9904  | 1.0183          |
| context_change | london      | 108    | 0.5382     | 2.1506  | 0.8438          |
| context_change | ny          | 162    | 0.3353     | 1.6632  | 0.9545          |

## Context Split

| trend_strength | consolidation_state       | shock_alignment | dmi_alignment | trades | stress_avg_r | stress_pf |
| -------------- | ------------------------- | --------------- | ------------- | ------ | ------------ | --------- |
| weak_or_range  | volatile_range            | no_shock        | opposed       | 2      | 0.9028       | 2.3949    |
| transition     | range_to_trend_transition | no_shock        | opposed       | 3      | 0.7507       | 2.7468    |
| weak_or_range  | volatile_range            | no_shock        | aligned       | 8      | 0.7056       | 2.5730    |
| weak_or_range  | range                     | no_shock        | aligned       | 40     | 0.6682       | 2.7514    |
| strong_trend   | directional               | no_shock        | aligned       | 108    | 0.4846       | 1.9817    |
| weak_or_range  | range                     | no_shock        | opposed       | 31     | 0.4173       | 1.7592    |
| transition     | transition                | no_shock        | opposed       | 25     | 0.4016       | 1.7985    |
| trend          | directional               | no_shock        | aligned       | 110    | 0.1971       | 1.3418    |
| transition     | transition                | no_shock        | aligned       | 50     | 0.1545       | 1.2580    |
| strong_trend   | directional               | no_shock        | opposed       | 29     | 0.1349       | 1.2210    |
| trend          | directional               | no_shock        | opposed       | 63     | 0.0457       | 1.0654    |
| transition     | range_to_trend_transition | no_shock        | aligned       | 4      | -0.4668      | 0.4862    |
| trend          | transition                | no_shock        | aligned       | 1      | -1.1979      | 0.0000    |
| transition     | coiling_transition        | no_shock        | aligned       | 4      | -1.2275      | 0.0000    |
| weak_or_range  | tight_range               | no_shock        | opposed       | 1      | -1.2561      | 0.0000    |

## Rolling Windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | median_stress_pf | worst_stress_return_r |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ---------------- | --------------------- |
| 52      | 35.0000       | 0.8846                | 0.7308                  | 1.9615         | -10.7102            | 1.5293           | -14.7006              |

## Read

- Base cost uses 6bps round-trip, roughly taker entry plus maker target exit.
- Stress cost uses 20bps round-trip. If a setup dies there, it has weak execution margin.
- This lab is not a promotion tool. It exists to falsify simple setup ideas before they reach the engine.
