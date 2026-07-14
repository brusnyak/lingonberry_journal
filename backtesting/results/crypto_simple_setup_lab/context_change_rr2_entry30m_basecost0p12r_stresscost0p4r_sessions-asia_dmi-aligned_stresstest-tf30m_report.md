# Simple Crypto Setup Lab

Scope: one setup family at a time, existing 240m/30m structure+EMA direction context, 15m entry, structural SL/TP, explicit cost-per-R.

## Summary

| setup          | symbol   | trades | win_rate | gross_avg_r | base_avg_r | base_pf | stress_avg_r | stress_pf | median_stop_pct | median_planned_rr | median_base_cost_r | median_stress_cost_r | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r | top_trend_strength | top_consolidation_state | top_shock_alignment | top_dmi_alignment |
| -------------- | -------- | ------ | -------- | ----------- | ---------- | ------- | ------------ | --------- | --------------- | ----------------- | ------------------ | -------------------- | ----------- | --------- | ----------- | ------------ | ------------ | ------------------ | ----------------------- | ------------------- | ----------------- |
| context_change | BNBUSDT  | 28     | 0.4286   | 0.3923      | 0.3237     | 1.5974  | 0.1636       | 1.2559    | 0.9073          | 2.0000            | 0.0661             | 0.2204               | 0.4286      | 0.5000    | 0.0714      | 1.3648       | -0.9415      | trend              | directional             | no_shock            | aligned           |
| context_change | BTCUSDT  | 19     | 0.4211   | 0.4211      | 0.3607     | 1.7911  | 0.2200       | 1.4092    | 1.1021          | 2.0000            | 0.0544             | 0.1815               | 0.4211      | 0.4211    | 0.1579      | 1.5103       | -0.7913      | trend              | directional             | no_shock            | aligned           |
| context_change | DOGEUSDT | 30     | 0.3333   | 0.2396      | 0.1976     | 1.4328  | 0.0996       | 1.1951    | 1.8254          | 2.0000            | 0.0330             | 0.1100               | 0.3333      | 0.4333    | 0.2333      | 1.1800       | -0.7653      | strong_trend       | directional             | no_shock            | aligned           |
| context_change | ETHUSDT  | 20     | 0.4500   | 0.6738      | 0.6134     | 2.6098  | 0.4723       | 2.0417    | 0.9464          | 2.0000            | 0.0637             | 0.2122               | 0.4500      | 0.3500    | 0.2000      | 1.9526       | -0.7857      | strong_trend       | directional             | no_shock            | aligned           |
| context_change | SOLUSDT  | 27     | 0.5185   | 0.8642      | 0.8079     | 3.2716  | 0.6764       | 2.6592    | 1.0246          | 2.0000            | 0.0586             | 0.1952               | 0.5185      | 0.3333    | 0.1481      | 2.0462       | -0.6407      | strong_trend       | directional             | no_shock            | aligned           |
| context_change | XRPUSDT  | 33     | 0.4545   | 0.5737      | 0.5178     | 2.2314  | 0.3875       | 1.8029    | 1.2245          | 2.0000            | 0.0490             | 0.1633               | 0.4545      | 0.3939    | 0.1515      | 1.8851       | -0.6576      | strong_trend       | directional             | no_shock            | aligned           |
| ALL            | ALL      | 157    | 0.4331   | 0.5218      | 0.4651     | 2.0638  | 0.3328       | 1.6577    | 1.1021          | 2.0000            | 0.0544             | 0.1815               | 0.4331      | 0.4076    | 0.1592      | 1.5103       | -0.7318      | strong_trend       | directional             | no_shock            | aligned           |

## Session Split

| setup          | session_utc | trades | base_avg_r | base_pf | median_stop_pct |
| -------------- | ----------- | ------ | ---------- | ------- | --------------- |
| context_change | asia        | 157    | 0.4651     | 2.0638  | 1.1021          |

## Context Split

| trend_strength | consolidation_state       | shock_alignment | dmi_alignment | trades | stress_avg_r | stress_pf |
| -------------- | ------------------------- | --------------- | ------------- | ------ | ------------ | --------- |
| weak_or_range  | range                     | opposing_shock  | aligned       | 3      | 1.8049       | inf       |
| strong_trend   | directional               | opposing_shock  | aligned       | 6      | 0.8527       | 3.2365    |
| transition     | transition                | aligned_shock   | aligned       | 7      | 0.7376       | 3.3083    |
| weak_or_range  | range                     | no_shock        | aligned       | 9      | 0.6032       | 2.4701    |
| transition     | transition                | no_shock        | aligned       | 17     | 0.6007       | 2.2092    |
| transition     | range_to_trend_transition | no_shock        | aligned       | 5      | 0.5863       | 2.1613    |
| strong_trend   | directional               | aligned_shock   | aligned       | 14     | 0.5858       | 2.6865    |
| weak_or_range  | range                     | aligned_shock   | aligned       | 6      | 0.4318       | 2.0605    |
| strong_trend   | directional               | no_shock        | aligned       | 36     | 0.3329       | 1.7053    |
| trend          | directional               | no_shock        | aligned       | 35     | -0.0297      | 0.9582    |
| trend          | directional               | aligned_shock   | aligned       | 13     | -0.0431      | 0.9079    |
| weak_or_range  | volatile_range            | opposing_shock  | aligned       | 1      | -0.1066      | 0.0000    |
| trend          | directional               | opposing_shock  | aligned       | 3      | -0.1742      | 0.7814    |
| transition     | transition                | opposing_shock  | aligned       | 1      | -1.2669      | 0.0000    |
| weak_or_range  | volatile_range            | no_shock        | aligned       | 1      | -1.2997      | 0.0000    |

## Rolling Windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | median_stress_pf | worst_stress_return_r |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ---------------- | --------------------- |
| 20      | 27.0000       | 0.9000                | 0.7000                  | 1.8728         | -1.3965             | 1.5150           | -6.4233               |

## Read

- Base cost uses 6bps round-trip, roughly taker entry plus maker target exit.
- Stress cost uses 20bps round-trip. If a setup dies there, it has weak execution margin.
- This lab is not a promotion tool. It exists to falsify simple setup ideas before they reach the engine.
