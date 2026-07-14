# Simple Crypto Setup Lab

Scope: one setup family at a time, existing 240m/30m structure+EMA direction context, 15m entry, structural SL/TP, explicit cost-per-R.

## Summary

| setup          | symbol   | trades | win_rate | gross_avg_r | base_avg_r | base_pf | stress_avg_r | stress_pf | median_stop_pct | median_planned_rr | median_base_cost_r | median_stress_cost_r | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r | top_trend_strength | top_consolidation_state | top_shock_alignment | top_dmi_alignment |
| -------------- | -------- | ------ | -------- | ----------- | ---------- | ------- | ------------ | --------- | --------------- | ----------------- | ------------------ | -------------------- | ----------- | --------- | ----------- | ------------ | ------------ | ------------------ | ----------------------- | ------------------- | ----------------- |
| context_change | BNBUSDT  | 12     | 0.4167   | 0.3333      | 0.2456     | 1.4489  | 0.0410       | 1.0624    | 0.6602          | 2.0000            | 0.0912             | 0.3038               | 0.4167      | 0.5000    | 0.0833      | 1.8085       | -0.8799      | weak_or_range      | directional             | no_shock            | aligned           |
| context_change | BTCUSDT  | 13     | 0.3077   | 0.1538      | 0.0877     | 1.1760  | -0.0666      | 0.8859    | 1.0410          | 2.0000            | 0.0576             | 0.1921               | 0.3077      | 0.4615    | 0.2308      | 1.6501       | -0.6858      | transition         | directional             | aligned_shock       | aligned           |
| context_change | DOGEUSDT | 37     | 0.4324   | 0.5068      | 0.4383     | 1.8881  | 0.2783       | 1.4859    | 0.8503          | 2.0000            | 0.0706             | 0.2352               | 0.4324      | 0.4595    | 0.1081      | 1.4028       | -0.8154      | strong_trend       | directional             | no_shock            | aligned           |
| context_change | ETHUSDT  | 20     | 0.4000   | 0.3000      | 0.2330     | 1.4308  | 0.0766       | 1.1204    | 0.9148          | 2.0000            | 0.0657             | 0.2189               | 0.4000      | 0.5000    | 0.1000      | 0.9846       | -0.8852      | strong_trend       | directional             | opposing_shock      | aligned           |
| context_change | SOLUSDT  | 29     | 0.3448   | 0.1034      | 0.0347     | 1.0553  | -0.1257      | 0.8268    | 0.9055          | 2.0000            | 0.0663             | 0.2209               | 0.3448      | 0.5862    | 0.0690      | 1.4118       | -1.1017      | strong_trend       | directional             | no_shock            | aligned           |
| context_change | XRPUSDT  | 24     | 0.4167   | 0.4319      | 0.3550     | 1.7060  | 0.1755       | 1.2893    | 0.7724          | 2.0000            | 0.0777             | 0.2589               | 0.4167      | 0.4583    | 0.1250      | 1.4114       | -0.9861      | trend              | directional             | no_shock            | aligned           |
| ALL            | ALL      | 135    | 0.3926   | 0.3268      | 0.2555     | 1.4764  | 0.0891       | 1.1414    | 0.8374          | 2.0000            | 0.0716             | 0.2388               | 0.3926      | 0.4963    | 0.1111      | 1.4149       | -0.9863      | strong_trend       | directional             | no_shock            | aligned           |

## Session Split

| setup          | session_utc | trades | base_avg_r | base_pf | median_stop_pct |
| -------------- | ----------- | ------ | ---------- | ------- | --------------- |
| context_change | asia        | 135    | 0.2555     | 1.4764  | 0.8374          |

## Context Split

| trend_strength | consolidation_state       | shock_alignment | dmi_alignment | trades | stress_avg_r | stress_pf |
| -------------- | ------------------------- | --------------- | ------------- | ------ | ------------ | --------- |
| weak_or_range  | volatile_range            | aligned_shock   | aligned       | 2      | 1.6711       | inf       |
| strong_trend   | directional               | no_shock        | aligned       | 18     | 0.6659       | 2.8012    |
| trend          | directional               | opposing_shock  | aligned       | 12     | 0.6419       | 2.2505    |
| transition     | transition                | aligned_shock   | aligned       | 4      | 0.5517       | 2.7042    |
| transition     | transition                | opposing_shock  | aligned       | 5      | 0.4951       | 1.9242    |
| transition     | transition                | no_shock        | aligned       | 15     | 0.2397       | 1.4063    |
| trend          | directional               | no_shock        | aligned       | 19     | 0.1792       | 1.3199    |
| weak_or_range  | volatile_range            | opposing_shock  | aligned       | 1      | -0.1489      | 0.0000    |
| strong_trend   | directional               | opposing_shock  | aligned       | 19     | -0.1719      | 0.7618    |
| weak_or_range  | range                     | no_shock        | aligned       | 9      | -0.2075      | 0.7270    |
| weak_or_range  | range                     | opposing_shock  | aligned       | 6      | -0.2162      | 0.7377    |
| trend          | directional               | aligned_shock   | aligned       | 9      | -0.2290      | 0.7211    |
| weak_or_range  | range                     | aligned_shock   | aligned       | 3      | -0.3191      | 0.6298    |
| strong_trend   | directional               | aligned_shock   | aligned       | 10     | -0.9254      | 0.0000    |
| transition     | range_to_trend_transition | opposing_shock  | aligned       | 1      | -1.2598      | 0.0000    |
| transition     | range_to_trend_transition | no_shock        | aligned       | 2      | -1.2901      | 0.0000    |

## Rolling Windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | median_stress_pf | worst_stress_return_r |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ---------------- | --------------------- |
| 19      | 21.0000       | 0.7368                | 0.7368                  | 1.9158         | -14.6511            | 1.3924           | -18.5037              |

## Read

- Base cost uses 6bps round-trip, roughly taker entry plus maker target exit.
- Stress cost uses 20bps round-trip. If a setup dies there, it has weak execution margin.
- This lab is not a promotion tool. It exists to falsify simple setup ideas before they reach the engine.
