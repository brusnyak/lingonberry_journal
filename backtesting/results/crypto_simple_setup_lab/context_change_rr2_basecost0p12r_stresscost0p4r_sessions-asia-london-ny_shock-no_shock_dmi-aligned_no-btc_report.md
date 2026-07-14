# Simple Crypto Setup Lab

Scope: one setup family at a time, existing 240m/30m structure+EMA direction context, 15m entry, structural SL/TP, explicit cost-per-R.

## Summary

| setup          | symbol   | trades | win_rate | gross_avg_r | base_avg_r | base_pf | stress_avg_r | stress_pf | median_stop_pct | median_planned_rr | median_base_cost_r | median_stress_cost_r | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r | top_trend_strength | top_consolidation_state | top_shock_alignment | top_dmi_alignment |
| -------------- | -------- | ------ | -------- | ----------- | ---------- | ------- | ------------ | --------- | --------------- | ----------------- | ------------------ | -------------------- | ----------- | --------- | ----------- | ------------ | ------------ | ------------------ | ----------------------- | ------------------- | ----------------- |
| context_change | DOGEUSDT | 79     | 0.4430   | 0.4366      | 0.3761     | 1.7761  | 0.2349       | 1.4256    | 1.1016          | 2.0000            | 0.0545             | 0.1816               | 0.4430      | 0.4557    | 0.1013      | 1.6951       | -0.7625      | strong_trend       | directional             | no_shock            | aligned           |
| context_change | ETHUSDT  | 73     | 0.4658   | 0.5068      | 0.4423     | 1.9627  | 0.2916       | 1.5395    | 0.9219          | 2.0000            | 0.0651             | 0.2169               | 0.4658      | 0.4247    | 0.1096      | 1.8850       | -0.8306      | trend              | directional             | no_shock            | aligned           |
| context_change | SOLUSDT  | 82     | 0.5122   | 0.6559      | 0.5965     | 2.3856  | 0.4579       | 1.9232    | 1.0767          | 2.0000            | 0.0557             | 0.1858               | 0.5122      | 0.4024    | 0.0854      | 2.0152       | -0.8572      | strong_trend       | directional             | no_shock            | aligned           |
| context_change | XRPUSDT  | 91     | 0.4835   | 0.5443      | 0.4758     | 1.9802  | 0.3160       | 1.5575    | 0.8589          | 2.0000            | 0.0699             | 0.2329               | 0.4835      | 0.4505    | 0.0659      | 1.9403       | -0.8621      | strong_trend       | directional             | no_shock            | aligned           |
| ALL            | ALL      | 325    | 0.4769   | 0.5379      | 0.4745     | 2.0193  | 0.3266       | 1.6055    | 0.9607          | 2.0000            | 0.0625             | 0.2082               | 0.4769      | 0.4338    | 0.0892      | 1.8850       | -0.8500      | trend              | directional             | no_shock            | aligned           |

## Session Split

| setup          | session_utc | trades | base_avg_r | base_pf | median_stop_pct |
| -------------- | ----------- | ------ | ---------- | ------- | --------------- |
| context_change | asia        | 140    | 0.6346     | 2.5341  | 1.0155          |
| context_change | london      | 69     | 0.4412     | 1.8613  | 0.8500          |
| context_change | ny          | 116    | 0.3011     | 1.6018  | 0.9972          |

## Context Split

| trend_strength | consolidation_state       | shock_alignment | dmi_alignment | trades | stress_avg_r | stress_pf |
| -------------- | ------------------------- | --------------- | ------------- | ------ | ------------ | --------- |
| weak_or_range  | volatile_range            | no_shock        | aligned       | 8      | 0.7056       | 2.5730    |
| weak_or_range  | range                     | no_shock        | aligned       | 40     | 0.6682       | 2.7514    |
| strong_trend   | directional               | no_shock        | aligned       | 108    | 0.4846       | 1.9817    |
| trend          | directional               | no_shock        | aligned       | 110    | 0.1971       | 1.3418    |
| transition     | transition                | no_shock        | aligned       | 50     | 0.1545       | 1.2580    |
| transition     | range_to_trend_transition | no_shock        | aligned       | 4      | -0.4668      | 0.4862    |
| trend          | transition                | no_shock        | aligned       | 1      | -1.1979      | 0.0000    |
| transition     | coiling_transition        | no_shock        | aligned       | 4      | -1.2275      | 0.0000    |

## Rolling Windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | median_stress_pf | worst_stress_return_r |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ---------------- | --------------------- |
| 52      | 23.5000       | 0.8077                | 0.6923                  | 2.0620         | -10.7283            | 1.6421           | -14.7610              |

## Read

- Base cost uses 6bps round-trip, roughly taker entry plus maker target exit.
- Stress cost uses 20bps round-trip. If a setup dies there, it has weak execution margin.
- This lab is not a promotion tool. It exists to falsify simple setup ideas before they reach the engine.
