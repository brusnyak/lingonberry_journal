# Simple Crypto Setup Lab

Scope: one setup family at a time, existing 240m/30m structure+EMA direction context, 15m entry, structural SL/TP, explicit cost-per-R.

## Summary

| setup          | symbol  | trades | win_rate | gross_avg_r | base_avg_r | base_pf | stress_avg_r | stress_pf | median_stop_pct | median_planned_rr | median_base_cost_r | median_stress_cost_r | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r | top_trend_strength | top_consolidation_state | top_shock_alignment | top_dmi_alignment | top_vwap_alignment | top_ema_alignment |
| -------------- | ------- | ------ | -------- | ----------- | ---------- | ------- | ------------ | --------- | --------------- | ----------------- | ------------------ | -------------------- | ----------- | --------- | ----------- | ------------ | ------------ | ------------------ | ----------------------- | ------------------- | ----------------- | ------------------ | ----------------- |
| context_change | BNBUSDT | 11     | 0.5455   | 0.7273      | 0.6502     | 2.6499  | 0.4705       | 2.0114    | 0.8235          | 2.0000            | 0.0729             | 0.2429               | 0.5455      | 0.3636    | 0.0909      | 2.0318       | -0.2435      | strong_trend       | directional             | no_shock            | aligned           | aligned            | aligned           |
| context_change | BTCUSDT | 7      | 0.4286   | 0.5714      | 0.4859     | 2.4669  | 0.2865       | 1.6547    | 0.6374          | 2.0000            | 0.0941             | 0.3138               | 0.4286      | 0.2857    | 0.2857      | 1.8887       | -0.2442      | trend              | directional             | no_shock            | aligned           | aligned            | aligned           |
| context_change | ETHUSDT | 11     | 0.5455   | 0.7273      | 0.6571     | 2.6781  | 0.4934       | 2.0801    | 0.7215          | 2.0000            | 0.0832             | 0.2772               | 0.5455      | 0.3636    | 0.0909      | 2.1068       | -0.5800      | trend              | directional             | aligned_shock       | aligned           | aligned            | aligned           |
| context_change | SOLUSDT | 11     | 0.7273   | 1.2727      | 1.2191     | 7.1818  | 1.0940       | 5.6929    | 1.2219          | 2.0000            | 0.0491             | 0.1637               | 0.7273      | 0.1818    | 0.0909      | 2.1290       | -0.2946      | transition         | directional             | no_shock            | aligned           | aligned            | aligned           |
| context_change | XRPUSDT | 6      | 0.1667   | -0.3333     | -0.3979    | 0.4477  | -0.5484      | 0.3516    | 1.0449          | 2.0000            | 0.0582             | 0.1939               | 0.1667      | 0.6667    | 0.1667      | 1.2539       | -1.0263      | strong_trend       | directional             | aligned_shock       | aligned           | aligned            | aligned           |
| ALL            | ALL     | 46     | 0.5217   | 0.6957      | 0.6262     | 2.6505  | 0.4642       | 2.0244    | 0.9029          | 2.0000            | 0.0665             | 0.2216               | 0.5217      | 0.3478    | 0.1304      | 2.0424       | -0.4629      | trend              | directional             | no_shock            | aligned           | aligned            | aligned           |

## Session Split

| setup          | session_utc | trades | base_avg_r | base_pf | median_stop_pct |
| -------------- | ----------- | ------ | ---------- | ------- | --------------- |
| context_change | asia        | 46     | 0.6262     | 2.6505  | 0.9029          |

## Context Split

| trend_strength | consolidation_state | shock_alignment | dmi_alignment | vwap_alignment | ema_alignment | trades | stress_avg_r | stress_pf |
| -------------- | ------------------- | --------------- | ------------- | -------------- | ------------- | ------ | ------------ | --------- |
| transition     | transition          | no_shock        | aligned       | flat           | aligned       | 1      | 1.8792       | inf       |
| weak_or_range  | volatile_range      | no_shock        | aligned       | flat           | aligned       | 1      | 1.8528       | inf       |
| weak_or_range  | range               | no_shock        | aligned       | opposed        | aligned       | 2      | 1.8111       | inf       |
| strong_trend   | directional         | opposing_shock  | aligned       | flat           | aligned       | 1      | 1.7644       | inf       |
| weak_or_range  | range               | no_shock        | aligned       | flat           | aligned       | 1      | 1.7571       | inf       |
| strong_trend   | directional         | no_shock        | aligned       | aligned        | aligned       | 6      | 1.7429       | inf       |
| trend          | directional         | opposing_shock  | aligned       | flat           | aligned       | 1      | 1.7406       | inf       |
| trend          | directional         | no_shock        | aligned       | aligned        | aligned       | 5      | 1.1704       | 6.5578    |
| trend          | directional         | no_shock        | aligned       | flat           | aligned       | 2      | 0.7505       | 10.8985   |
| transition     | transition          | no_shock        | aligned       | aligned        | aligned       | 5      | 0.2575       | 1.5261    |
| weak_or_range  | range               | no_shock        | aligned       | aligned        | aligned       | 4      | 0.2361       | 1.3867    |
| trend          | directional         | aligned_shock   | aligned       | flat           | aligned       | 2      | 0.1678       | 1.2512    |
| trend          | directional         | aligned_shock   | aligned       | aligned        | aligned       | 3      | 0.0938       | 1.1887    |
| weak_or_range  | volatile_range      | aligned_shock   | aligned       | aligned        | aligned       | 1      | -0.0673      | 0.0000    |
| transition     | transition          | aligned_shock   | aligned       | aligned        | aligned       | 3      | -0.5504      | 0.0000    |
| strong_trend   | directional         | aligned_shock   | aligned       | aligned        | aligned       | 2      | -1.1940      | 0.0000    |
| strong_trend   | directional         | aligned_shock   | aligned       | flat           | aligned       | 2      | -1.1987      | 0.0000    |
| strong_trend   | directional         | opposing_shock  | aligned       | aligned        | aligned       | 1      | -1.3210      | 0.0000    |
| transition     | transition          | opposing_shock  | aligned       | aligned        | aligned       | 1      | -1.3488      | 0.0000    |
| weak_or_range  | range               | aligned_shock   | aligned       | aligned        | aligned       | 1      | -1.3507      | 0.0000    |

## Rolling Windows

### 30-day windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | worst_base_dd_pct | median_stress_pf | worst_stress_return_r | worst_stress_dd_pct | base_sharpe | stress_sharpe |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ----------------- | ---------------- | --------------------- | ------------------- | ----------- | ------------- |
| 7       | 21.0000       | 1.0000                | 0.8571                  | 2.8176         | 3.2916              | 3.2916            | 2.1429           | -0.6946               | -0.6946             | 155.1598    | 109.3780      |

### 60-day windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | worst_base_dd_pct | median_stress_pf | worst_stress_return_r | worst_stress_dd_pct | base_sharpe | stress_sharpe |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ----------------- | ---------------- | --------------------- | ------------------- | ----------- | ------------- |
| 2       | 38.5000       | 1.0000                | 1.0000                  | 3.0598         | 25.3479             | 25.3479           | 2.2942           | 19.1598               | 19.1598             | 1894.3410   | 1641.3617     |

## Read

- Base cost uses 6bps round-trip, roughly taker entry plus maker target exit.
- Stress cost uses 20bps round-trip. If a setup dies there, it has weak execution margin.
- This lab is not a promotion tool. It exists to falsify simple setup ideas before they reach the engine.
