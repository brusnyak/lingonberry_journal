# Simple Crypto Setup Lab

Scope: one setup family at a time, existing 240m/30m structure+EMA direction context, 15m entry, structural SL/TP, explicit cost-per-R.

## Summary

| setup          | symbol   | trades | win_rate | gross_avg_r | base_avg_r | base_pf | stress_avg_r | stress_pf | median_stop_pct | median_planned_rr | median_base_cost_r | median_stress_cost_r | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r | top_trend_strength | top_consolidation_state | top_shock_alignment | top_dmi_alignment | top_vwap_alignment | top_ema_alignment |
| -------------- | -------- | ------ | -------- | ----------- | ---------- | ------- | ------------ | --------- | --------------- | ----------------- | ------------------ | -------------------- | ----------- | --------- | ----------- | ------------ | ------------ | ------------------ | ----------------------- | ------------------- | ----------------- | ------------------ | ----------------- |
| context_change | BNBUSDT  | 16     | 0.5625   | 0.7323      | 0.6603     | 2.4118  | 0.5163       | 1.9777    | 0.5004          | 2.0000            | 0.0650             | 0.1949               | 0.5625      | 0.4375    | 0.0000      | 2.0388       | -0.5308      | weak_or_range      | directional             | no_shock            | aligned           | flat               | aligned           |
| context_change | BTCUSDT  | 12     | 0.7500   | 1.3333      | 1.2650     | 7.9828  | 1.1282       | 6.3693    | 0.4840          | 2.0000            | 0.0699             | 0.2098               | 0.7500      | 0.1667    | 0.0833      | 2.1136       | -0.2977      | trend              | directional             | no_shock            | aligned           | aligned            | aligned           |
| context_change | DOGEUSDT | 14     | 0.6429   | 0.9286      | 0.8292     | 3.0934  | 0.6303       | 2.3299    | 0.6787          | 2.0000            | 0.0747             | 0.2242               | 0.6429      | 0.3571    | 0.0000      | 2.1828       | -0.5132      | strong_trend       | directional             | no_shock            | aligned           | flat               | flat              |
| context_change | ETHUSDT  | 14     | 0.5000   | 0.5000      | 0.4276     | 1.7952  | 0.2828       | 1.4612    | 0.5215          | 2.0000            | 0.0665             | 0.1996               | 0.5000      | 0.5000    | 0.0000      | 1.9031       | -0.9029      | strong_trend       | directional             | no_shock            | aligned           | aligned            | aligned           |
| context_change | SOLUSDT  | 19     | 0.5789   | 0.9361      | 0.8561     | 3.0607  | 0.6959       | 2.3660    | 0.9890          | 2.0000            | 0.0592             | 0.1777               | 0.5789      | 0.3684    | 0.0526      | 2.1500       | -0.8095      | strong_trend       | directional             | no_shock            | aligned           | aligned            | aligned           |
| context_change | XRPUSDT  | 12     | 0.8333   | 1.5921      | 1.4869     | 8.4181  | 1.2764       | 5.7630    | 0.5834          | 2.0000            | 0.0934             | 0.2802               | 0.8333      | 0.1667    | 0.0000      | 2.3304       | -0.5110      | trend              | directional             | no_shock            | aligned           | flat               | flat              |
| ALL            | ALL      | 87     | 0.6322   | 0.9725      | 0.8902     | 3.3448  | 0.7256       | 2.6149    | 0.6134          | 2.0000            | 0.0700             | 0.2100               | 0.6322      | 0.3448    | 0.0230      | 2.1268       | -0.5437      | trend              | directional             | no_shock            | aligned           | flat               | aligned           |

## Session Split

| setup          | session_utc | trades | base_avg_r | base_pf | median_stop_pct |
| -------------- | ----------- | ------ | ---------- | ------- | --------------- |
| context_change | asia        | 87     | 0.8902     | 3.3448  | 0.6134          |

## Context Split

| trend_strength | consolidation_state | shock_alignment | dmi_alignment | vwap_alignment | ema_alignment | trades | stress_avg_r | stress_pf |
| -------------- | ------------------- | --------------- | ------------- | -------------- | ------------- | ------ | ------------ | --------- |
| weak_or_range  | volatile_range      | no_shock        | aligned       | flat           | aligned       | 1      | 1.9015       | inf       |
| trend          | directional         | no_shock        | aligned       | aligned        | opposed       | 1      | 1.8252       | inf       |
| transition     | transition          | no_shock        | aligned       | flat           | opposed       | 3      | 1.7840       | inf       |
| weak_or_range  | range               | no_shock        | aligned       | opposed        | aligned       | 2      | 1.7568       | inf       |
| strong_trend   | directional         | no_shock        | aligned       | opposed        | opposed       | 4      | 1.7241       | 6.5731    |
| strong_trend   | directional         | no_shock        | aligned       | aligned        | opposed       | 1      | 1.7161       | inf       |
| trend          | directional         | no_shock        | aligned       | flat           | flat          | 5      | 1.7079       | inf       |
| weak_or_range  | range               | no_shock        | aligned       | aligned        | flat          | 1      | 1.6626       | inf       |
| trend          | directional         | no_shock        | aligned       | flat           | opposed       | 5      | 1.3325       | 5.7747    |
| strong_trend   | directional         | no_shock        | aligned       | flat           | flat          | 5      | 1.0980       | 5.4333    |
| trend          | directional         | no_shock        | aligned       | aligned        | aligned       | 7      | 1.0112       | 4.1885    |
| strong_trend   | directional         | no_shock        | aligned       | aligned        | aligned       | 10     | 0.8004       | 2.7101    |
| transition     | transition          | no_shock        | aligned       | flat           | aligned       | 3      | 0.7843       | 2.8848    |
| transition     | transition          | no_shock        | aligned       | flat           | flat          | 3      | 0.5489       | 1.8316    |
| transition     | transition          | no_shock        | aligned       | aligned        | aligned       | 6      | 0.5423       | 2.4100    |
| trend          | directional         | no_shock        | aligned       | flat           | aligned       | 6      | 0.4809       | 2.0022    |
| strong_trend   | directional         | no_shock        | aligned       | aligned        | flat          | 2      | 0.3553       | 1.6520    |
| weak_or_range  | range               | no_shock        | aligned       | aligned        | aligned       | 4      | 0.3520       | 1.6261    |
| trend          | directional         | no_shock        | aligned       | aligned        | flat          | 4      | 0.3032       | 1.5211    |
| weak_or_range  | range               | no_shock        | aligned       | flat           | aligned       | 4      | 0.2714       | 1.4380    |

## Rolling Windows

### 30-day windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | worst_base_dd_pct | median_stress_pf | worst_stress_return_r | worst_stress_dd_pct | base_sharpe | stress_sharpe |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ----------------- | ---------------- | --------------------- | ------------------- | ----------- | ------------- |
| 8       | 35.5000       | 1.0000                | 1.0000                  | 3.7583         | 16.8314             | 16.8314           | 2.9169           | 11.3190               | 11.3190             | 130.0933    | 115.9086      |

### 60-day windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | worst_base_dd_pct | median_stress_pf | worst_stress_return_r | worst_stress_dd_pct | base_sharpe | stress_sharpe |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ----------------- | ---------------- | --------------------- | ------------------- | ----------- | ------------- |
| 2       | 68.0000       | 1.0000                | 1.0000                  | 4.2262         | 66.7327             | 66.7327           | 3.2466           | 54.9808               | 54.9808             | 2298.5367   | 1785.4800     |

## Read

- Base cost uses 6bps round-trip, roughly taker entry plus maker target exit.
- Stress cost uses 20bps round-trip. If a setup dies there, it has weak execution margin.
- This lab is not a promotion tool. It exists to falsify simple setup ideas before they reach the engine.
