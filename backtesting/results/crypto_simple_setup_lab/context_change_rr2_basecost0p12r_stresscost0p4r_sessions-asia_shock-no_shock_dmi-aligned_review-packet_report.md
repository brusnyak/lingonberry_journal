# Simple Crypto Setup Lab

Scope: one setup family at a time, existing 240m/30m structure+EMA direction context, 15m entry, structural SL/TP, explicit cost-per-R.

## Summary

| setup          | symbol   | trades | win_rate | gross_avg_r | base_avg_r | base_pf | stress_avg_r | stress_pf | median_stop_pct | median_planned_rr | median_base_cost_r | median_stress_cost_r | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r | top_trend_strength | top_consolidation_state | top_shock_alignment | top_dmi_alignment | top_vwap_alignment | top_ema_alignment |
| -------------- | -------- | ------ | -------- | ----------- | ---------- | ------- | ------------ | --------- | --------------- | ----------------- | ------------------ | -------------------- | ----------- | --------- | ----------- | ------------ | ------------ | ------------------ | ----------------------- | ------------------- | ----------------- | ------------------ | ----------------- |
| context_change | BNBUSDT  | 15     | 0.5333   | 0.6000      | 0.5334     | 2.0787  | 0.3780       | 1.6758    | 0.9948          | 2.0000            | 0.0603             | 0.2010               | 0.5333      | 0.4667    | 0.0000      | 2.0082       | -0.5760      | strong_trend       | directional             | no_shock            | aligned           | aligned            | aligned           |
| context_change | BTCUSDT  | 11     | 0.4545   | 0.4545      | 0.3740     | 1.7572  | 0.1862       | 1.3178    | 0.6862          | 2.0000            | 0.0874             | 0.2915               | 0.4545      | 0.4545    | 0.0909      | 1.8887       | -0.9888      | trend              | directional             | no_shock            | aligned           | aligned            | aligned           |
| context_change | DOGEUSDT | 20     | 0.5500   | 0.7500      | 0.6819     | 2.8177  | 0.5230       | 2.2056    | 0.9904          | 2.0000            | 0.0609             | 0.2029               | 0.5500      | 0.3500    | 0.1000      | 2.0376       | -0.5882      | strong_trend       | directional             | no_shock            | aligned           | aligned            | flat              |
| context_change | ETHUSDT  | 15     | 0.6667   | 1.0000      | 0.9405     | 3.6701  | 0.8016       | 3.0227    | 1.0060          | 2.0000            | 0.0596             | 0.1988               | 0.6667      | 0.3333    | 0.0000      | 2.2275       | -0.5342      | trend              | directional             | no_shock            | aligned           | aligned            | aligned           |
| context_change | SOLUSDT  | 20     | 0.6500   | 1.1393      | 1.0796     | 4.3449  | 0.9401       | 3.5014    | 1.1069          | 2.0000            | 0.0543             | 0.1810               | 0.6500      | 0.3000    | 0.0500      | 2.1083       | -0.5844      | strong_trend       | directional             | no_shock            | aligned           | aligned            | aligned           |
| context_change | XRPUSDT  | 13     | 0.7692   | 1.3927      | 1.3208     | 6.3801  | 1.1531       | 5.1200    | 0.8527          | 2.0000            | 0.0704             | 0.2345               | 0.7692      | 0.2308    | 0.0000      | 2.2105       | -0.5352      | transition         | directional             | no_shock            | aligned           | aligned            | aligned           |
| ALL            | ALL      | 94     | 0.6064   | 0.9031      | 0.8364     | 3.2283  | 0.6808       | 2.5758    | 0.9238          | 2.0000            | 0.0649             | 0.2165               | 0.6064      | 0.3511    | 0.0426      | 2.0529       | -0.5603      | strong_trend       | directional             | no_shock            | aligned           | aligned            | aligned           |

## Session Split

| setup          | session_utc | trades | base_avg_r | base_pf | median_stop_pct |
| -------------- | ----------- | ------ | ---------- | ------- | --------------- |
| context_change | asia        | 94     | 0.8364     | 3.2283  | 0.9238          |

## Context Split

| trend_strength | consolidation_state | shock_alignment | dmi_alignment | vwap_alignment | ema_alignment | trades | stress_avg_r | stress_pf |
| -------------- | ------------------- | --------------- | ------------- | -------------- | ------------- | ------ | ------------ | --------- |
| weak_or_range  | volatile_range      | no_shock        | aligned       | flat           | aligned       | 1      | 1.8528       | inf       |
| trend          | directional         | no_shock        | aligned       | aligned        | opposed       | 1      | 1.7875       | inf       |
| strong_trend   | directional         | no_shock        | aligned       | aligned        | opposed       | 1      | 1.7687       | inf       |
| weak_or_range  | range               | no_shock        | aligned       | flat           | aligned       | 1      | 1.7571       | inf       |
| transition     | transition          | no_shock        | aligned       | aligned        | flat          | 1      | 1.7529       | inf       |
| transition     | transition          | no_shock        | aligned       | flat           | flat          | 2      | 1.7362       | inf       |
| weak_or_range  | range               | no_shock        | aligned       | flat           | flat          | 2      | 1.6438       | inf       |
| strong_trend   | directional         | no_shock        | aligned       | aligned        | aligned       | 14     | 1.4260       | 17.8175   |
| trend          | directional         | no_shock        | aligned       | flat           | opposed       | 4      | 1.2858       | 5.1186    |
| strong_trend   | directional         | no_shock        | aligned       | opposed        | opposed       | 5      | 1.1606       | 3.3194    |
| trend          | directional         | no_shock        | aligned       | aligned        | aligned       | 8      | 1.0328       | 4.7986    |
| strong_trend   | directional         | no_shock        | aligned       | flat           | flat          | 4      | 1.0262       | 4.6015    |
| weak_or_range  | range               | no_shock        | aligned       | aligned        | flat          | 2      | 0.8738       | 21.0653   |
| weak_or_range  | range               | no_shock        | aligned       | opposed        | aligned       | 3      | 0.7686       | 2.7515    |
| strong_trend   | directional         | no_shock        | aligned       | flat           | aligned       | 3      | 0.7669       | 2.8213    |
| trend          | directional         | no_shock        | aligned       | flat           | flat          | 3      | 0.7590       | 2.9389    |
| trend          | directional         | no_shock        | aligned       | aligned        | flat          | 4      | 0.2548       | 1.4073    |
| transition     | transition          | no_shock        | aligned       | flat           | opposed       | 2      | 0.2188       | 1.3250    |
| trend          | directional         | no_shock        | aligned       | flat           | aligned       | 7      | 0.2006       | 1.3512    |
| transition     | transition          | no_shock        | aligned       | aligned        | aligned       | 8      | 0.1133       | 1.1929    |

## Rolling Windows

### 30-day windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | worst_base_dd_pct | median_stress_pf | worst_stress_return_r | worst_stress_dd_pct | base_sharpe | stress_sharpe |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ----------------- | ---------------- | --------------------- | ------------------- | ----------- | ------------- |
| 20      | 15.0000       | 1.0000                | 0.9000                  | 5.4510         | 0.1015              | 0.1015            | 4.4123           | -2.4075               | -2.4075             | 46.0424     | 40.4912       |

### 60-day windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | worst_base_dd_pct | median_stress_pf | worst_stress_return_r | worst_stress_dd_pct | base_sharpe | stress_sharpe |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ----------------- | ---------------- | --------------------- | ------------------- | ----------- | ------------- |
| 8       | 27.5000       | 1.0000                | 1.0000                  | 2.6757         | 7.0396              | 7.0396            | 2.0751           | 2.4655                | 2.4655              | 80.3147     | 67.6931       |

### 90-day windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | worst_base_dd_pct | median_stress_pf | worst_stress_return_r | worst_stress_dd_pct | base_sharpe | stress_sharpe |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ----------------- | ---------------- | --------------------- | ------------------- | ----------- | ------------- |
| 4       | 41.0000       | 1.0000                | 1.0000                  | 2.7703         | 15.3163             | 15.3163           | 2.1157           | 9.0545                | 9.0545              | 158.6030    | 129.2916      |

## Read

- Base cost uses 6bps round-trip, roughly taker entry plus maker target exit.
- Stress cost uses 20bps round-trip. If a setup dies there, it has weak execution margin.
- This lab is not a promotion tool. It exists to falsify simple setup ideas before they reach the engine.
