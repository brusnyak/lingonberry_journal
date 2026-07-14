# Simple Crypto Setup Lab

Scope: one setup family at a time, existing 240m/30m structure+EMA direction context, 15m entry, structural SL/TP, explicit cost-per-R.

## Summary

| setup          | symbol   | trades | win_rate | gross_avg_r | base_avg_r | base_pf | stress_avg_r | stress_pf | median_stop_pct | median_planned_rr | median_base_cost_r | median_stress_cost_r | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r | top_trend_strength | top_consolidation_state | top_shock_alignment | top_dmi_alignment |
| -------------- | -------- | ------ | -------- | ----------- | ---------- | ------- | ------------ | --------- | --------------- | ----------------- | ------------------ | -------------------- | ----------- | --------- | ----------- | ------------ | ------------ | ------------------ | ----------------------- | ------------------- | ----------------- |
| context_change | BNBUSDT  | 24     | 0.4583   | 0.4167      | 0.3486     | 1.6516  | 0.1897       | 1.3078    | 0.8610          | 2.0000            | 0.0697             | 0.2323               | 0.4583      | 0.5000    | 0.0417      | 1.6038       | -0.8825      | strong_trend       | directional             | no_shock            | aligned           |
| context_change | BTCUSDT  | 29     | 0.4483   | 0.4519      | 0.3708     | 1.7527  | 0.1817       | 1.3047    | 0.6862          | 2.0000            | 0.0874             | 0.2915               | 0.4483      | 0.4483    | 0.1034      | 1.8887       | -0.6801      | trend              | directional             | no_shock            | aligned           |
| context_change | DOGEUSDT | 46     | 0.3478   | 0.2174      | 0.1612     | 1.3172  | 0.0302       | 1.0522    | 1.1755          | 2.0000            | 0.0510             | 0.1702               | 0.3478      | 0.4783    | 0.1739      | 1.4726       | -0.9288      | trend              | directional             | no_shock            | aligned           |
| context_change | ETHUSDT  | 31     | 0.5806   | 0.7742      | 0.7125     | 2.7333  | 0.5685       | 2.2175    | 0.9777          | 2.0000            | 0.0614             | 0.2046               | 0.5806      | 0.3871    | 0.0323      | 2.1068       | -0.6386      | trend              | directional             | no_shock            | aligned           |
| context_change | SOLUSDT  | 42     | 0.5476   | 0.7330      | 0.6788     | 2.5072  | 0.5522       | 2.1019    | 1.1821          | 2.0000            | 0.0508             | 0.1692               | 0.5476      | 0.4286    | 0.0238      | 2.0575       | -0.8240      | transition         | directional             | no_shock            | aligned           |
| context_change | XRPUSDT  | 36     | 0.4444   | 0.4179      | 0.3487     | 1.6159  | 0.1871       | 1.2854    | 0.9103          | 2.0000            | 0.0659             | 0.2197               | 0.4444      | 0.5278    | 0.0278      | 1.3699       | -1.0077      | trend              | directional             | no_shock            | aligned           |
| ALL            | ALL      | 208    | 0.4663   | 0.4949      | 0.4312     | 1.8746  | 0.2825       | 1.4987    | 0.9925          | 2.0000            | 0.0605             | 0.2015               | 0.4663      | 0.4615    | 0.0721      | 1.8155       | -0.8240      | trend              | directional             | no_shock            | aligned           |

## Session Split

| setup          | session_utc | trades | base_avg_r | base_pf | median_stop_pct |
| -------------- | ----------- | ------ | ---------- | ------- | --------------- |
| context_change | asia        | 208    | 0.4312     | 1.8746  | 0.9925          |

## Context Split

| trend_strength | consolidation_state       | shock_alignment | dmi_alignment | trades | stress_avg_r | stress_pf |
| -------------- | ------------------------- | --------------- | ------------- | ------ | ------------ | --------- |
| weak_or_range  | volatile_range            | no_shock        | aligned       | 1      | 1.8528       | inf       |
| transition     | range_to_trend_transition | no_shock        | opposed       | 1      | 1.8167       | inf       |
| transition     | transition                | opposing_shock  | opposed       | 1      | 1.7954       | inf       |
| strong_trend   | directional               | no_shock        | aligned       | 31     | 1.0342       | 4.3373    |
| trend          | directional               | no_shock        | aligned       | 27     | 0.7368       | 2.7924    |
| transition     | transition                | no_shock        | opposed       | 11     | 0.5899       | 2.6236    |
| trend          | directional               | opposing_shock  | opposed       | 4      | 0.5471       | 1.9518    |
| weak_or_range  | range                     | no_shock        | aligned       | 16     | 0.5008       | 2.0562    |
| weak_or_range  | range                     | no_shock        | opposed       | 9      | 0.4901       | 1.9444    |
| transition     | transition                | aligned_shock   | opposed       | 2      | 0.3482       | 1.6105    |
| weak_or_range  | range                     | opposing_shock  | aligned       | 2      | 0.3429       | 1.5868    |
| transition     | transition                | no_shock        | aligned       | 17     | 0.2720       | 1.4685    |
| trend          | directional               | aligned_shock   | opposed       | 2      | 0.2394       | 1.3660    |
| transition     | transition                | opposing_shock  | aligned       | 7      | 0.0613       | 1.0884    |
| trend          | directional               | aligned_shock   | aligned       | 14     | -0.0013      | 0.9979    |
| weak_or_range  | volatile_range            | aligned_shock   | aligned       | 1      | -0.0673      | 0.0000    |
| trend          | directional               | opposing_shock  | aligned       | 15     | -0.1856      | 0.7619    |
| trend          | directional               | no_shock        | opposed       | 12     | -0.2389      | 0.7102    |
| weak_or_range  | range                     | aligned_shock   | aligned       | 4      | -0.2635      | 0.6225    |
| strong_trend   | directional               | opposing_shock  | aligned       | 9      | -0.3899      | 0.5029    |

## Rolling Windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | median_stress_pf | worst_stress_return_r |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ---------------- | --------------------- |
| 20      | 35.5000       | 0.8500                | 0.7000                  | 1.6112         | -7.3897             | 1.3004           | -12.9655              |

## Read

- Base cost uses 6bps round-trip, roughly taker entry plus maker target exit.
- Stress cost uses 20bps round-trip. If a setup dies there, it has weak execution margin.
- This lab is not a promotion tool. It exists to falsify simple setup ideas before they reach the engine.
