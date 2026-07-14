# Simple Crypto Setup Lab

Scope: one setup family at a time, existing 240m/30m structure+EMA direction context, 15m entry, structural SL/TP, explicit cost-per-R.

## Summary

| setup          | symbol   | trades | win_rate | gross_avg_r | base_avg_r | base_pf | stress_avg_r | stress_pf | median_stop_pct | median_planned_rr | median_base_cost_r | median_stress_cost_r | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r | top_trend_strength | top_consolidation_state | top_shock_alignment | top_dmi_alignment | top_vwap_alignment | top_ema_alignment |
| -------------- | -------- | ------ | -------- | ----------- | ---------- | ------- | ------------ | --------- | --------------- | ----------------- | ------------------ | -------------------- | ----------- | --------- | ----------- | ------------ | ------------ | ------------------ | ----------------------- | ------------------- | ----------------- | ------------------ | ----------------- |
| context_change | BNBUSDT  | 46     | 0.4348   | 0.3199      | 0.2397     | 1.3907  | 0.0791       | 1.1115    | 0.6087          | 2.0000            | 0.0617             | 0.1851               | 0.4348      | 0.5652    | 0.0000      | 1.6813       | -1.0516      | strong_trend       | directional             | no_shock            | aligned           | flat               | aligned           |
| context_change | BTCUSDT  | 40     | 0.4750   | 0.5274      | 0.4534     | 1.9773  | 0.3055       | 1.5639    | 0.5352          | 2.0000            | 0.0708             | 0.2124               | 0.4750      | 0.4250    | 0.1000      | 1.9093       | -0.7473      | trend              | directional             | no_shock            | aligned           | flat               | aligned           |
| context_change | DOGEUSDT | 49     | 0.4694   | 0.4501      | 0.3495     | 1.6378  | 0.1484       | 1.2234    | 0.6056          | 2.0000            | 0.0756             | 0.2267               | 0.4694      | 0.4898    | 0.0408      | 2.0000       | -0.9808      | trend              | directional             | no_shock            | aligned           | flat               | flat              |
| context_change | ETHUSDT  | 51     | 0.3922   | 0.2941      | 0.1875     | 1.2916  | -0.0257      | 0.9676    | 0.6472          | 2.0000            | 0.0683             | 0.2050               | 0.3922      | 0.5686    | 0.0392      | 1.6368       | -1.0135      | strong_trend       | directional             | no_shock            | aligned           | flat               | aligned           |
| context_change | SOLUSDT  | 45     | 0.4889   | 0.6175      | 0.5492     | 2.1788  | 0.4126       | 1.7458    | 0.9410          | 2.0000            | 0.0467             | 0.1401               | 0.4889      | 0.4222    | 0.0889      | 2.0159       | -0.8384      | strong_trend       | directional             | no_shock            | aligned           | aligned            | aligned           |
| context_change | XRPUSDT  | 50     | 0.5000   | 0.5621      | 0.4731     | 1.9329  | 0.2952       | 1.4908    | 0.6879          | 2.0000            | 0.0742             | 0.2227               | 0.5000      | 0.4600    | 0.0400      | 2.0049       | -0.9735      | trend              | directional             | no_shock            | aligned           | flat               | aligned           |
| ALL            | ALL      | 281    | 0.4591   | 0.4582      | 0.3709     | 1.6823  | 0.1963       | 1.3026    | 0.6472          | 2.0000            | 0.0677             | 0.2031               | 0.4591      | 0.4911    | 0.0498      | 1.8850       | -0.9880      | trend              | directional             | no_shock            | aligned           | flat               | aligned           |

## Session Split

| setup          | session_utc | trades | base_avg_r | base_pf | median_stop_pct |
| -------------- | ----------- | ------ | ---------- | ------- | --------------- |
| context_change | asia        | 281    | 0.3709     | 1.6823  | 0.6472          |

## Context Split

| trend_strength | consolidation_state | shock_alignment | dmi_alignment | vwap_alignment | ema_alignment | trades | stress_avg_r | stress_pf |
| -------------- | ------------------- | --------------- | ------------- | -------------- | ------------- | ------ | ------------ | --------- |
| weak_or_range  | volatile_range      | no_shock        | aligned       | flat           | aligned       | 2      | 1.9085       | inf       |
| trend          | directional         | no_shock        | aligned       | aligned        | opposed       | 1      | 1.8252       | inf       |
| strong_trend   | directional         | no_shock        | aligned       | aligned        | opposed       | 1      | 1.7161       | inf       |
| strong_trend   | directional         | no_shock        | aligned       | opposed        | flat          | 1      | 1.5490       | inf       |
| strong_trend   | directional         | no_shock        | aligned       | opposed        | aligned       | 2      | 1.2778       | 3.1110    |
| strong_trend   | directional         | no_shock        | aligned       | opposed        | opposed       | 5      | 1.1493       | 3.4075    |
| weak_or_range  | range               | no_shock        | aligned       | opposed        | aligned       | 4      | 1.0314       | 4.4201    |
| transition     | transition          | no_shock        | aligned       | aligned        | flat          | 3      | 0.8584       | 3.1650    |
| trend          | directional         | no_shock        | aligned       | aligned        | flat          | 9      | 0.7790       | 3.0537    |
| weak_or_range  | range               | no_shock        | aligned       | aligned        | flat          | 5      | 0.6927       | 2.7920    |
| trend          | directional         | no_shock        | aligned       | flat           | flat          | 15     | 0.6600       | 2.5152    |
| transition     | transition          | no_shock        | aligned       | flat           | opposed       | 8      | 0.5945       | 2.1511    |
| weak_or_range  | range               | no_shock        | aligned       | flat           | aligned       | 11     | 0.5760       | 2.1583    |
| strong_trend   | directional         | no_shock        | aligned       | aligned        | aligned       | 38     | 0.5650       | 2.4029    |
| trend          | directional         | no_shock        | aligned       | flat           | opposed       | 12     | 0.4816       | 1.8016    |
| trend          | directional         | no_shock        | aligned       | aligned        | aligned       | 27     | 0.3633       | 1.6900    |
| weak_or_range  | range               | no_shock        | aligned       | aligned        | aligned       | 15     | 0.2694       | 1.4543    |
| weak_or_range  | range               | no_shock        | aligned       | aligned        | opposed       | 2      | 0.1822       | 1.2730    |
| transition     | transition          | no_shock        | aligned       | flat           | flat          | 4      | 0.1385       | 1.1802    |
| transition     | transition          | no_shock        | aligned       | aligned        | aligned       | 15     | 0.1315       | 1.2133    |

## Rolling Windows

### 30-day windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | worst_base_dd_pct | median_stress_pf | worst_stress_return_r | worst_stress_dd_pct | base_sharpe | stress_sharpe |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ----------------- | ---------------- | --------------------- | ------------------- | ----------- | ------------- |
| 47      | 22.0000       | 0.8085                | 0.5532                  | 1.3243         | -9.8472             | -9.8472           | 1.0705           | -15.5417              | -15.5417            | 15.7053     | 9.0141        |

### 60-day windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | worst_base_dd_pct | median_stress_pf | worst_stress_return_r | worst_stress_dd_pct | base_sharpe | stress_sharpe |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ----------------- | ---------------- | --------------------- | ------------------- | ----------- | ------------- |
| 22      | 44.5000       | 0.9091                | 0.5909                  | 1.3996         | -5.7203             | -5.7203           | 1.0769           | -13.1609              | -13.1609            | 29.9551     | 16.1654       |

### 90-day windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | worst_base_dd_pct | median_stress_pf | worst_stress_return_r | worst_stress_dd_pct | base_sharpe | stress_sharpe |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ----------------- | ---------------- | --------------------- | ------------------- | ----------- | ------------- |
| 13      | 67.0000       | 0.9231                | 0.6154                  | 1.3595         | -2.0090             | -2.0090           | 1.0523           | -12.2157              | -12.2157            | 48.3398     | 21.5073       |

## Read

- Base cost uses 6bps round-trip, roughly taker entry plus maker target exit.
- Stress cost uses 20bps round-trip. If a setup dies there, it has weak execution margin.
- This lab is not a promotion tool. It exists to falsify simple setup ideas before they reach the engine.
