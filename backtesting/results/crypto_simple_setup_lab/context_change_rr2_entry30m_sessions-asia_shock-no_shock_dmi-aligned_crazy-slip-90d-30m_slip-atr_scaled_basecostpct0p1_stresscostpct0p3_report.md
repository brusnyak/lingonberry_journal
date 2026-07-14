# Simple Crypto Setup Lab

Scope: one setup family at a time, existing 240m/30m structure+EMA direction context, 15m entry, structural SL/TP, explicit cost-per-R.

## Summary

| setup          | symbol   | trades | win_rate | gross_avg_r | base_avg_r | base_pf | stress_avg_r | stress_pf | median_stop_pct | median_planned_rr | median_base_cost_r | median_stress_cost_r | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r | top_trend_strength | top_consolidation_state | top_shock_alignment | top_dmi_alignment | top_vwap_alignment | top_ema_alignment |
| -------------- | -------- | ------ | -------- | ----------- | ---------- | ------- | ------------ | --------- | --------------- | ----------------- | ------------------ | -------------------- | ----------- | --------- | ----------- | ------------ | ------------ | ------------------ | ----------------------- | ------------------- | ----------------- | ------------------ | ----------------- |
| context_change | BNBUSDT  | 15     | 0.4667   | 0.5514      | 0.4590     | 1.8920  | 0.2741       | 1.4491    | 0.6161          | 2.0000            | 0.0741             | 0.2224               | 0.4667      | 0.4667    | 0.0667      | 1.3133       | -0.8540      | strong_trend       | directional             | no_shock            | aligned           | flat               | aligned           |
| context_change | BTCUSDT  | 9      | 0.4444   | 0.3333      | 0.2522     | 1.4155  | 0.0900       | 1.1268    | 0.5776          | 2.0000            | 0.0718             | 0.2155               | 0.4444      | 0.5556    | 0.0000      | 0.4232       | -1.1355      | trend              | directional             | no_shock            | aligned           | flat               | aligned           |
| context_change | DOGEUSDT | 11     | 0.3636   | 0.2727      | 0.2143     | 1.4445  | 0.0973       | 1.1812    | 1.1912          | 2.0000            | 0.0463             | 0.1390               | 0.3636      | 0.4545    | 0.1818      | 1.1667       | -0.8172      | strong_trend       | directional             | no_shock            | aligned           | aligned            | flat              |
| context_change | ETHUSDT  | 10     | 0.4000   | 0.3227      | 0.1462     | 1.2277  | -0.2069      | 0.7766    | 0.6102          | 2.0000            | 0.0855             | 0.2565               | 0.4000      | 0.5000    | 0.1000      | 1.6431       | -0.8886      | trend              | directional             | no_shock            | aligned           | flat               | aligned           |
| context_change | SOLUSDT  | 13     | 0.3846   | 0.3077      | 0.2415     | 1.4878  | 0.1091       | 1.1941    | 0.8828          | 2.0000            | 0.0569             | 0.1708               | 0.3846      | 0.4615    | 0.1538      | 1.1765       | -0.7619      | trend              | directional             | no_shock            | aligned           | aligned            | aligned           |
| context_change | XRPUSDT  | 13     | 0.6154   | 1.1172      | 1.0405     | 5.1442  | 0.8872       | 4.0416    | 0.7032          | 2.0000            | 0.0698             | 0.2095               | 0.6154      | 0.2308    | 0.1538      | 2.1347       | -0.4844      | strong_trend       | directional             | no_shock            | aligned           | aligned            | aligned           |
| ALL            | ALL      | 71     | 0.4507   | 0.5073      | 0.4174     | 1.8566  | 0.2377       | 1.4036    | 0.8101          | 2.0000            | 0.0703             | 0.2110               | 0.4507      | 0.4366    | 0.1127      | 1.3175       | -0.8036      | trend              | directional             | no_shock            | aligned           | flat               | aligned           |

## Session Split

| setup          | session_utc | trades | base_avg_r | base_pf | median_stop_pct |
| -------------- | ----------- | ------ | ---------- | ------- | --------------- |
| context_change | asia        | 71     | 0.4174     | 1.8566  | 0.8101          |

## Context Split

| trend_strength | consolidation_state       | shock_alignment | dmi_alignment | vwap_alignment | ema_alignment | trades | stress_avg_r | stress_pf |
| -------------- | ------------------------- | --------------- | ------------- | -------------- | ------------- | ------ | ------------ | --------- |
| trend          | directional               | no_shock        | aligned       | aligned        | opposed       | 1      | 1.8462       | inf       |
| transition     | range_to_trend_transition | no_shock        | aligned       | aligned        | aligned       | 3      | 1.8252       | inf       |
| weak_or_range  | range                     | no_shock        | aligned       | flat           | aligned       | 2      | 1.7425       | inf       |
| weak_or_range  | range                     | no_shock        | aligned       | flat           | flat          | 2      | 1.6896       | inf       |
| trend          | directional               | no_shock        | aligned       | flat           | flat          | 2      | 1.6644       | inf       |
| transition     | transition                | no_shock        | aligned       | flat           | aligned       | 3      | 0.7253       | 2.7800    |
| trend          | directional               | no_shock        | aligned       | flat           | aligned       | 12     | 0.6918       | 2.7260    |
| transition     | transition                | no_shock        | aligned       | aligned        | flat          | 2      | 0.3726       | 1.6650    |
| strong_trend   | directional               | no_shock        | aligned       | aligned        | aligned       | 6      | 0.3674       | 2.5135    |
| strong_trend   | directional               | no_shock        | aligned       | flat           | aligned       | 12     | 0.3530       | 1.5561    |
| strong_trend   | directional               | no_shock        | aligned       | aligned        | flat          | 3      | 0.1438       | 1.3481    |
| transition     | transition                | no_shock        | aligned       | aligned        | aligned       | 4      | -0.1114      | 0.8087    |
| trend          | directional               | no_shock        | aligned       | aligned        | flat          | 3      | -0.1362      | 0.8222    |
| weak_or_range  | range                     | no_shock        | aligned       | aligned        | flat          | 2      | -0.6724      | 0.0000    |
| trend          | directional               | no_shock        | aligned       | aligned        | aligned       | 7      | -0.8048      | 0.2451    |
| strong_trend   | directional               | no_shock        | aligned       | opposed        | flat          | 2      | -1.1143      | 0.0000    |
| strong_trend   | directional               | no_shock        | aligned       | flat           | flat          | 1      | -1.1390      | 0.0000    |
| weak_or_range  | range                     | no_shock        | aligned       | flat           | opposed       | 1      | -1.2526      | 0.0000    |
| trend          | directional               | no_shock        | aligned       | flat           | opposed       | 1      | -1.3071      | 0.0000    |
| transition     | range_to_trend_transition | no_shock        | aligned       | flat           | aligned       | 1      | -1.3319      | 0.0000    |

## Rolling Windows

### 30-day windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | worst_base_dd_pct | median_stress_pf | worst_stress_return_r | worst_stress_dd_pct | base_sharpe | stress_sharpe |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ----------------- | ---------------- | --------------------- | ------------------- | ----------- | ------------- |
| 8       | 30.0000       | 0.7500                | 0.7500                  | 2.1084         | -1.0148             | -1.0148           | 1.5404           | -5.4982               | -5.4982             | 81.9923     | 54.8184       |

### 60-day windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | worst_base_dd_pct | median_stress_pf | worst_stress_return_r | worst_stress_dd_pct | base_sharpe | stress_sharpe |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ----------------- | ---------------- | --------------------- | ------------------- | ----------- | ------------- |
| 2       | 60.0000       | 1.0000                | 1.0000                  | 2.0202         | 27.2112             | 27.2112           | 1.5038           | 15.5907               | 15.5907             | 3480.5793   | 1495.5025     |

## Read

- Base cost uses 6bps round-trip, roughly taker entry plus maker target exit.
- Stress cost uses 20bps round-trip. If a setup dies there, it has weak execution margin.
- This lab is not a promotion tool. It exists to falsify simple setup ideas before they reach the engine.
