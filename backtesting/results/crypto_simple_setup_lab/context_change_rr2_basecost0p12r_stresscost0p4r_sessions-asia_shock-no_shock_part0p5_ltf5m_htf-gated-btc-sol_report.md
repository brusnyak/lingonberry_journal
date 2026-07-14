# Simple Crypto Setup Lab

Scope: one setup family at a time, existing 240m/30m structure+EMA direction context, 15m entry, structural SL/TP, explicit cost-per-R.

## Summary

| setup          | symbol  | trades | win_rate | gross_avg_r | base_avg_r | base_pf | stress_avg_r | stress_pf | median_stop_pct | median_planned_rr | median_base_cost_r | median_stress_cost_r | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r | top_trend_strength | top_consolidation_state | top_shock_alignment | top_dmi_alignment | top_vwap_alignment | top_ema_alignment |
| -------------- | ------- | ------ | -------- | ----------- | ---------- | ------- | ------------ | --------- | --------------- | ----------------- | ------------------ | -------------------- | ----------- | --------- | ----------- | ------------ | ------------ | ------------------ | ----------------------- | ------------------- | ----------------- | ------------------ | ----------------- |
| context_change | BTCUSDT | 12     | 0.7500   | 0.6250      | 0.5442     | 2.9926  | 0.3558       | 2.0877    | 0.7124          | 2.0000            | 0.0843             | 0.2811               | 0.7500      | 0.2500    | 0.0000      | 2.0540       | -0.6786      | trend              | directional             | no_shock            | aligned           | flat               | aligned           |
| context_change | SOLUSDT | 18     | 0.7222   | 0.5236      | 0.4659     | 2.5575  | 0.3312       | 1.9763    | 1.1069          | 2.0000            | 0.0543             | 0.1810               | 0.7222      | 0.2778    | 0.0000      | 1.4295       | -0.5031      | strong_trend       | directional             | no_shock            | aligned           | aligned            | aligned           |
| ALL            | ALL     | 30     | 0.7333   | 0.5642      | 0.4972     | 2.7221  | 0.3410       | 2.0199    | 0.9650          | 2.0000            | 0.0622             | 0.2074               | 0.7333      | 0.2667    | 0.0000      | 1.9693       | -0.5338      | strong_trend       | directional             | no_shock            | aligned           | aligned            | aligned           |

## Session Split

| setup          | session_utc | trades | base_avg_r | base_pf | median_stop_pct |
| -------------- | ----------- | ------ | ---------- | ------- | --------------- |
| context_change | asia        | 30     | 0.4972     | 2.7221  | 0.9650          |

## Context Split

| trend_strength | consolidation_state | shock_alignment | dmi_alignment | vwap_alignment | ema_alignment | trades | stress_avg_r | stress_pf |
| -------------- | ------------------- | --------------- | ------------- | -------------- | ------------- | ------ | ------------ | --------- |
| transition     | transition          | no_shock        | aligned       | flat           | aligned       | 1      | 1.3792       | inf       |
| weak_or_range  | volatile_range      | no_shock        | aligned       | flat           | aligned       | 1      | 1.3528       | inf       |
| trend          | directional         | no_shock        | opposed       | opposed        | opposed       | 1      | 1.3426       | inf       |
| trend          | directional         | no_shock        | aligned       | aligned        | opposed       | 1      | 1.2875       | inf       |
| trend          | directional         | no_shock        | aligned       | flat           | opposed       | 1      | 1.2431       | inf       |
| trend          | directional         | no_shock        | aligned       | aligned        | aligned       | 2      | 1.1912       | inf       |
| transition     | transition          | no_shock        | opposed       | flat           | aligned       | 1      | 1.1210       | inf       |
| strong_trend   | directional         | no_shock        | aligned       | aligned        | aligned       | 2      | 0.8597       | inf       |
| trend          | directional         | no_shock        | aligned       | flat           | aligned       | 2      | 0.7505       | inf       |
| weak_or_range  | range               | no_shock        | aligned       | aligned        | aligned       | 2      | 0.7368       | inf       |
| strong_trend   | directional         | no_shock        | opposed       | opposed        | opposed       | 1      | 0.3411       | inf       |
| strong_trend   | directional         | no_shock        | aligned       | opposed        | opposed       | 1      | 0.3408       | inf       |
| transition     | transition          | no_shock        | opposed       | opposed        | opposed       | 1      | 0.2292       | inf       |
| transition     | transition          | no_shock        | aligned       | aligned        | aligned       | 3      | 0.1631       | 1.3952    |
| trend          | directional         | no_shock        | opposed       | aligned        | aligned       | 1      | 0.1569       | inf       |
| strong_trend   | directional         | no_shock        | aligned       | flat           | aligned       | 2      | 0.0316       | 1.0500    |
| weak_or_range  | range               | no_shock        | aligned       | opposed        | aligned       | 2      | 0.0109       | 1.0166    |
| strong_trend   | directional         | no_shock        | aligned       | flat           | opposed       | 1      | -1.1091      | 0.0000    |
| strong_trend   | directional         | no_shock        | opposed       | aligned        | opposed       | 1      | -1.1985      | 0.0000    |
| strong_trend   | directional         | no_shock        | aligned       | aligned        | opposed       | 1      | -1.2313      | 0.0000    |

## Rolling Windows

### 30-day windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | worst_base_dd_pct | median_stress_pf | worst_stress_return_r | worst_stress_dd_pct | base_sharpe | stress_sharpe |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ----------------- | ---------------- | --------------------- | ------------------- | ----------- | ------------- |
| 7       | 15.0000       | 1.0000                | 1.0000                  | 5.9891         | 4.9860              | 4.9860            | 4.6641           | 3.9613                | 3.9613              | 196.6909    | 176.5330      |

### 60-day windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | worst_base_dd_pct | median_stress_pf | worst_stress_return_r | worst_stress_dd_pct | base_sharpe | stress_sharpe |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ----------------- | ---------------- | --------------------- | ------------------- | ----------- | ------------- |
| 4       | 18.0000       | 1.0000                | 1.0000                  | 4.7962         | 4.6571              | 4.6571            | 3.6856           | 2.8648                | 2.8648              | 251.8008    | 218.9623      |

### 90-day windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | worst_base_dd_pct | median_stress_pf | worst_stress_return_r | worst_stress_dd_pct | base_sharpe | stress_sharpe |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ----------------- | ---------------- | --------------------- | ------------------- | ----------- | ------------- |
| 1       | 25.0000       | 1.0000                | 1.0000                  | 4.0198         | 16.3066             | 16.3066           | 3.0345           | 12.5297               | 12.5297             |             |               |

## Read

- Base cost uses 6bps round-trip, roughly taker entry plus maker target exit.
- Stress cost uses 20bps round-trip. If a setup dies there, it has weak execution margin.
- This lab is not a promotion tool. It exists to falsify simple setup ideas before they reach the engine.
