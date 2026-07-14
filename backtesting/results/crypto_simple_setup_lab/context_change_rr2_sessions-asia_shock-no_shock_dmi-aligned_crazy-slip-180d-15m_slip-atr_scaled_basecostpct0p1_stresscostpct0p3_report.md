# Simple Crypto Setup Lab

Scope: one setup family at a time, existing 240m/30m structure+EMA direction context, 15m entry, structural SL/TP, explicit cost-per-R.

## Summary

| setup          | symbol   | trades | win_rate | gross_avg_r | base_avg_r | base_pf | stress_avg_r | stress_pf | median_stop_pct | median_planned_rr | median_base_cost_r | median_stress_cost_r | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r | top_trend_strength | top_consolidation_state | top_shock_alignment | top_dmi_alignment | top_vwap_alignment | top_ema_alignment |
| -------------- | -------- | ------ | -------- | ----------- | ---------- | ------- | ------------ | --------- | --------------- | ----------------- | ------------------ | -------------------- | ----------- | --------- | ----------- | ------------ | ------------ | ------------------ | ----------------------- | ------------------- | ----------------- | ------------------ | ----------------- |
| context_change | BNBUSDT  | 25     | 0.4400   | 0.3487      | 0.2812     | 1.4702  | 0.1463       | 1.2169    | 0.6432          | 2.0000            | 0.0535             | 0.1605               | 0.4400      | 0.5600    | 0.0000      | 1.4559       | -1.0426      | weak_or_range      | directional             | no_shock            | aligned           | aligned            | aligned           |
| context_change | BTCUSDT  | 22     | 0.5455   | 0.6850      | 0.6143     | 2.3980  | 0.4729       | 1.9457    | 0.5375          | 2.0000            | 0.0708             | 0.2124               | 0.5455      | 0.4091    | 0.0455      | 2.0514       | -0.8829      | trend              | directional             | no_shock            | aligned           | flat               | aligned           |
| context_change | DOGEUSDT | 32     | 0.5312   | 0.6562      | 0.5568     | 2.2166  | 0.3579       | 1.6386    | 0.5951          | 2.0000            | 0.0747             | 0.2242               | 0.5312      | 0.4062    | 0.0625      | 2.0376       | -0.7583      | strong_trend       | directional             | no_shock            | aligned           | flat               | flat              |
| context_change | ETHUSDT  | 24     | 0.5000   | 0.5000      | 0.4052     | 1.7221  | 0.2155       | 1.3154    | 0.7394          | 2.0000            | 0.0676             | 0.2028               | 0.5000      | 0.5000    | 0.0000      | 1.9031       | -0.9291      | strong_trend       | directional             | no_shock            | aligned           | aligned            | aligned           |
| context_change | SOLUSDT  | 28     | 0.5714   | 0.8495      | 0.7621     | 2.7347  | 0.5871       | 2.1032    | 0.9027          | 2.0000            | 0.0597             | 0.1791               | 0.5714      | 0.3929    | 0.0357      | 2.1083       | -0.8214      | strong_trend       | directional             | no_shock            | aligned           | aligned            | aligned           |
| context_change | XRPUSDT  | 21     | 0.7143   | 1.1955      | 1.1071     | 4.4570  | 0.9305       | 3.3897    | 0.6304          | 2.0000            | 0.0850             | 0.2551               | 0.7143      | 0.2857    | 0.0000      | 2.2447       | -0.5752      | trend              | directional             | no_shock            | aligned           | flat               | aligned           |
| ALL            | ALL      | 152    | 0.5461   | 0.6953      | 0.6097     | 2.2915  | 0.4386       | 1.7818    | 0.6312          | 2.0000            | 0.0682             | 0.2047               | 0.5461      | 0.4276    | 0.0263      | 2.0501       | -0.7974      | trend              | directional             | no_shock            | aligned           | flat               | aligned           |

## Session Split

| setup          | session_utc | trades | base_avg_r | base_pf | median_stop_pct |
| -------------- | ----------- | ------ | ---------- | ------- | --------------- |
| context_change | asia        | 152    | 0.6097     | 2.2915  | 0.6312          |

## Context Split

| trend_strength | consolidation_state | shock_alignment | dmi_alignment | vwap_alignment | ema_alignment | trades | stress_avg_r | stress_pf |
| -------------- | ------------------- | --------------- | ------------- | -------------- | ------------- | ------ | ------------ | --------- |
| weak_or_range  | volatile_range      | no_shock        | aligned       | flat           | aligned       | 1      | 1.9015       | inf       |
| transition     | transition          | no_shock        | aligned       | aligned        | flat          | 1      | 1.8499       | inf       |
| trend          | directional         | no_shock        | aligned       | aligned        | opposed       | 1      | 1.8252       | inf       |
| strong_trend   | directional         | no_shock        | aligned       | aligned        | opposed       | 1      | 1.7161       | inf       |
| strong_trend   | directional         | no_shock        | aligned       | opposed        | opposed       | 5      | 1.1493       | 3.4075    |
| strong_trend   | directional         | no_shock        | aligned       | flat           | flat          | 5      | 1.0980       | 5.4333    |
| trend          | directional         | no_shock        | aligned       | flat           | flat          | 10     | 1.0841       | 5.5367    |
| strong_trend   | directional         | no_shock        | aligned       | aligned        | aligned       | 19     | 1.0420       | 4.3815    |
| trend          | directional         | no_shock        | aligned       | flat           | opposed       | 6      | 0.8953       | 3.0001    |
| trend          | directional         | no_shock        | aligned       | aligned        | flat          | 6      | 0.8180       | 3.1089    |
| weak_or_range  | range               | no_shock        | aligned       | opposed        | aligned       | 3      | 0.7691       | 2.9128    |
| trend          | directional         | no_shock        | aligned       | aligned        | aligned       | 12     | 0.6128       | 2.2788    |
| transition     | transition          | no_shock        | aligned       | flat           | flat          | 3      | 0.5489       | 1.8316    |
| weak_or_range  | range               | no_shock        | aligned       | flat           | aligned       | 5      | 0.5318       | 2.0731    |
| transition     | transition          | no_shock        | aligned       | flat           | opposed       | 5      | 0.4976       | 1.8689    |
| weak_or_range  | range               | no_shock        | aligned       | aligned        | flat          | 4      | 0.4055       | 1.8392    |
| transition     | transition          | no_shock        | aligned       | aligned        | aligned       | 9      | 0.3278       | 1.6512    |
| trend          | directional         | no_shock        | aligned       | flat           | aligned       | 14     | 0.2526       | 1.3876    |
| weak_or_range  | range               | no_shock        | aligned       | flat           | flat          | 4      | 0.1407       | 1.1823    |
| weak_or_range  | range               | no_shock        | aligned       | aligned        | aligned       | 8      | -0.0034      | 0.9951    |

## Rolling Windows

### 30-day windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | worst_base_dd_pct | median_stress_pf | worst_stress_return_r | worst_stress_dd_pct | base_sharpe | stress_sharpe |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ----------------- | ---------------- | --------------------- | ------------------- | ----------- | ------------- |
| 21      | 24.0000       | 0.8095                | 0.6667                  | 2.0489         | -9.3297             | -9.3297           | 1.7127           | -13.9890              | -13.9890            | 31.3965     | 22.9716       |

### 60-day windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | worst_base_dd_pct | median_stress_pf | worst_stress_return_r | worst_stress_dd_pct | base_sharpe | stress_sharpe |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ----------------- | ---------------- | --------------------- | ------------------- | ----------- | ------------- |
| 9       | 50.0000       | 1.0000                | 0.6667                  | 2.0315         | 1.3939              | 1.3939            | 1.5339           | -7.8183               | -7.8183             | 66.0076     | 45.8235       |

### 90-day windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | worst_base_dd_pct | median_stress_pf | worst_stress_return_r | worst_stress_dd_pct | base_sharpe | stress_sharpe |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ----------------- | ---------------- | --------------------- | ------------------- | ----------- | ------------- |
| 4       | 75.0000       | 1.0000                | 1.0000                  | 1.4962         | 12.8305             | 12.8305           | 1.1406           | 0.3525                | 0.3525              | 137.2779    | 77.8769       |

## Read

- Base cost uses 6bps round-trip, roughly taker entry plus maker target exit.
- Stress cost uses 20bps round-trip. If a setup dies there, it has weak execution margin.
- This lab is not a promotion tool. It exists to falsify simple setup ideas before they reach the engine.
