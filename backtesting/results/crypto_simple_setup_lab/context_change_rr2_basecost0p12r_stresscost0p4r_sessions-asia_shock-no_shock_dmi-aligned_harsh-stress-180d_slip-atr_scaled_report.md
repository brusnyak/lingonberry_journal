# Simple Crypto Setup Lab

Scope: one setup family at a time, existing 240m/30m structure+EMA direction context, 15m entry, structural SL/TP, explicit cost-per-R.

## Summary

| setup          | symbol   | trades | win_rate | gross_avg_r | base_avg_r | base_pf | stress_avg_r | stress_pf | median_stop_pct | median_planned_rr | median_base_cost_r | median_stress_cost_r | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r | top_trend_strength | top_consolidation_state | top_shock_alignment | top_dmi_alignment | top_vwap_alignment | top_ema_alignment |
| -------------- | -------- | ------ | -------- | ----------- | ---------- | ------- | ------------ | --------- | --------------- | ----------------- | ------------------ | -------------------- | ----------- | --------- | ----------- | ------------ | ------------ | ------------------ | ----------------------- | ------------------- | ----------------- | ------------------ | ----------------- |
| context_change | BNBUSDT  | 25     | 0.4400   | 0.3487      | 0.3483     | 1.6217  | 0.3473       | 1.6194    | 0.6432          | 2.0000            | 0.0003             | 0.0011               | 0.4400      | 0.5600    | 0.0000      | 1.4559       | -1.0426      | weak_or_range      | directional             | no_shock            | aligned           | aligned            | aligned           |
| context_change | BTCUSDT  | 22     | 0.5455   | 0.6850      | 0.6846     | 2.6726  | 0.6836       | 2.6685    | 0.5375          | 2.0000            | 0.0004             | 0.0014               | 0.5455      | 0.4091    | 0.0455      | 2.0514       | -0.8829      | trend              | directional             | no_shock            | aligned           | flat               | aligned           |
| context_change | DOGEUSDT | 32     | 0.5312   | 0.6562      | 0.6557     | 2.6127  | 0.6543       | 2.6064    | 0.5951          | 2.0000            | 0.0004             | 0.0015               | 0.5312      | 0.4062    | 0.0625      | 2.0376       | -0.7583      | strong_trend       | directional             | no_shock            | aligned           | flat               | flat              |
| context_change | ETHUSDT  | 24     | 0.5000   | 0.5000      | 0.4994     | 1.9981  | 0.4981       | 1.9938    | 0.7394          | 2.0000            | 0.0004             | 0.0014               | 0.5000      | 0.5000    | 0.0000      | 1.9031       | -0.9291      | strong_trend       | directional             | no_shock            | aligned           | aligned            | aligned           |
| context_change | SOLUSDT  | 28     | 0.5714   | 0.8495      | 0.8490     | 3.1595  | 0.8478       | 3.1529    | 0.9027          | 2.0000            | 0.0004             | 0.0012               | 0.5714      | 0.3929    | 0.0357      | 2.1083       | -0.8214      | strong_trend       | directional             | no_shock            | aligned           | aligned            | aligned           |
| context_change | XRPUSDT  | 21     | 0.7143   | 1.1955      | 1.1950     | 5.1793  | 1.1937       | 5.1679    | 0.6304          | 2.0000            | 0.0005             | 0.0017               | 0.7143      | 0.2857    | 0.0000      | 2.2447       | -0.5752      | trend              | directional             | no_shock            | aligned           | flat               | aligned           |
| ALL            | ALL      | 152    | 0.5461   | 0.6953      | 0.6947     | 2.6236  | 0.6935       | 2.6185    | 0.6312          | 2.0000            | 0.0004             | 0.0014               | 0.5461      | 0.4276    | 0.0263      | 2.0501       | -0.7974      | trend              | directional             | no_shock            | aligned           | flat               | aligned           |

## Session Split

| setup          | session_utc | trades | base_avg_r | base_pf | median_stop_pct |
| -------------- | ----------- | ------ | ---------- | ------- | --------------- |
| context_change | asia        | 152    | 0.6947     | 2.6236  | 0.6312          |

## Context Split

| trend_strength | consolidation_state | shock_alignment | dmi_alignment | vwap_alignment | ema_alignment | trades | stress_avg_r | stress_pf |
| -------------- | ------------------- | --------------- | ------------- | -------------- | ------------- | ------ | ------------ | --------- |
| weak_or_range  | volatile_range      | no_shock        | aligned       | flat           | aligned       | 1      | 1.9993       | inf       |
| transition     | transition          | no_shock        | aligned       | aligned        | flat          | 1      | 1.9990       | inf       |
| trend          | directional         | no_shock        | aligned       | aligned        | opposed       | 1      | 1.9988       | inf       |
| strong_trend   | directional         | no_shock        | aligned       | aligned        | opposed       | 1      | 1.9981       | inf       |
| strong_trend   | directional         | no_shock        | aligned       | flat           | flat          | 5      | 1.3980       | 7.9788    |
| trend          | directional         | no_shock        | aligned       | flat           | flat          | 10     | 1.3979       | 7.9804    |
| strong_trend   | directional         | no_shock        | aligned       | opposed        | opposed       | 5      | 1.3559       | 4.3854    |
| strong_trend   | directional         | no_shock        | aligned       | aligned        | aligned       | 19     | 1.2617       | 6.9745    |
| trend          | directional         | no_shock        | aligned       | flat           | opposed       | 6      | 1.2103       | 4.6226    |
| trend          | directional         | no_shock        | aligned       | aligned        | flat          | 6      | 0.9988       | 3.9931    |
| weak_or_range  | range               | no_shock        | aligned       | opposed        | aligned       | 3      | 0.9985       | 3.9913    |
| transition     | transition          | no_shock        | aligned       | flat           | flat          | 3      | 0.9970       | 3.9716    |
| weak_or_range  | range               | no_shock        | aligned       | flat           | aligned       | 5      | 0.7982       | 2.9924    |
| transition     | transition          | no_shock        | aligned       | flat           | opposed       | 5      | 0.7980       | 2.9892    |
| trend          | directional         | no_shock        | aligned       | aligned        | aligned       | 12     | 0.7491       | 2.7960    |
| weak_or_range  | range               | no_shock        | aligned       | aligned        | flat          | 4      | 0.7477       | 3.9723    |
| trend          | directional         | no_shock        | aligned       | flat           | aligned       | 14     | 0.6131       | 2.4256    |
| weak_or_range  | range               | no_shock        | aligned       | flat           | flat          | 4      | 0.4976       | 1.9916    |
| transition     | transition          | no_shock        | aligned       | aligned        | aligned       | 9      | 0.4437       | 1.9974    |
| strong_trend   | directional         | no_shock        | aligned       | flat           | aligned       | 9      | 0.3307       | 1.5937    |

## Rolling Windows

### 30-day windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | worst_base_dd_pct | median_stress_pf | worst_stress_return_r | worst_stress_dd_pct | base_sharpe | stress_sharpe |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ----------------- | ---------------- | --------------------- | ------------------- | ----------- | ------------- |
| 21      | 24.0000       | 0.8571                | 0.8571                  | 2.2211         | -7.0140             | -7.0140           | 2.2186           | -7.0466               | -7.0466             | 35.3044     | 35.2507       |

### 60-day windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | worst_base_dd_pct | median_stress_pf | worst_stress_return_r | worst_stress_dd_pct | base_sharpe | stress_sharpe |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ----------------- | ---------------- | --------------------- | ------------------- | ----------- | ------------- |
| 9       | 50.0000       | 1.0000                | 1.0000                  | 2.3786         | 5.9724              | 5.9724            | 2.3730           | 5.9079                | 5.9079              | 75.5172     | 75.3857       |

### 90-day windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | worst_base_dd_pct | median_stress_pf | worst_stress_return_r | worst_stress_dd_pct | base_sharpe | stress_sharpe |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ----------------- | ---------------- | --------------------- | ------------------- | ----------- | ------------- |
| 4       | 75.0000       | 1.0000                | 1.0000                  | 1.7399         | 19.0321             | 19.0321           | 1.7361           | 18.9447               | 18.9447             | 163.9488    | 163.5851      |

## Read

- Base cost uses 6bps round-trip, roughly taker entry plus maker target exit.
- Stress cost uses 20bps round-trip. If a setup dies there, it has weak execution margin.
- This lab is not a promotion tool. It exists to falsify simple setup ideas before they reach the engine.
