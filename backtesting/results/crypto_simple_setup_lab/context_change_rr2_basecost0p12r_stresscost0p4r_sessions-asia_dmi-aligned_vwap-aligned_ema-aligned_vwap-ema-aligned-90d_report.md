# Simple Crypto Setup Lab

Scope: one setup family at a time, existing 240m/30m structure+EMA direction context, 15m entry, structural SL/TP, explicit cost-per-R.

## Summary

| setup          | symbol  | trades | win_rate | gross_avg_r | base_avg_r | base_pf | stress_avg_r | stress_pf | median_stop_pct | median_planned_rr | median_base_cost_r | median_stress_cost_r | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r | top_trend_strength | top_consolidation_state | top_shock_alignment | top_dmi_alignment | top_vwap_alignment | top_ema_alignment |
| -------------- | ------- | ------ | -------- | ----------- | ---------- | ------- | ------------ | --------- | --------------- | ----------------- | ------------------ | -------------------- | ----------- | --------- | ----------- | ------------ | ------------ | ------------------ | ----------------------- | ------------------- | ----------------- | ------------------ | ----------------- |
| context_change | BNBUSDT | 8      | 0.5000   | 0.6250      | 0.5496     | 2.3595  | 0.3738       | 1.7908    | 0.7695          | 2.0000            | 0.0794             | 0.2647               | 0.5000      | 0.3750    | 0.1250      | 1.8917       | -0.2865      | strong_trend       | directional             | no_shock            | aligned           | aligned            | aligned           |
| context_change | BTCUSDT | 6      | 0.5000   | 0.6667      | 0.5745     | 2.5162  | 0.3595       | 1.7408    | 0.6303          | 2.0000            | 0.0952             | 0.3174               | 0.5000      | 0.3333    | 0.1667      | 1.7579       | -0.6165      | trend              | directional             | no_shock            | aligned           | aligned            | aligned           |
| context_change | ETHUSDT | 9      | 0.5556   | 0.7778      | 0.7122     | 2.9883  | 0.5593       | 2.3437    | 0.8811          | 2.0000            | 0.0681             | 0.2270               | 0.5556      | 0.3333    | 0.1111      | 2.1068       | -0.5800      | trend              | directional             | no_shock            | aligned           | aligned            | aligned           |
| context_change | SOLUSDT | 6      | 0.5000   | 0.6667      | 0.6202     | 2.7154  | 0.5118       | 2.1975    | 1.1423          | 2.0000            | 0.0528             | 0.1759               | 0.5000      | 0.3333    | 0.1667      | 1.7059       | -0.8240      | transition         | transition              | no_shock            | aligned           | aligned            | aligned           |
| context_change | XRPUSDT | 3      | 0.0000   | -0.6667     | -0.7223    | 0.0000  | -0.8522      | 0.0000    | 1.1644          | 2.0000            | 0.0515             | 0.1718               | 0.0000      | 0.6667    | 0.3333      | 1.1548       | -1.0370      | strong_trend       | directional             | aligned_shock       | aligned           | aligned            | aligned           |
| ALL            | ALL     | 32     | 0.4688   | 0.5625      | 0.4940     | 2.2097  | 0.3342       | 1.6874    | 0.9328          | 2.0000            | 0.0643             | 0.2144               | 0.4688      | 0.3750    | 0.1562      | 1.5943       | -0.6346      | strong_trend       | directional             | no_shock            | aligned           | aligned            | aligned           |

## Session Split

| setup          | session_utc | trades | base_avg_r | base_pf | median_stop_pct |
| -------------- | ----------- | ------ | ---------- | ------- | --------------- |
| context_change | asia        | 32     | 0.4940     | 2.2097  | 0.9328          |

## Context Split

| trend_strength | consolidation_state | shock_alignment | dmi_alignment | vwap_alignment | ema_alignment | trades | stress_avg_r | stress_pf |
| -------------- | ------------------- | --------------- | ------------- | -------------- | ------------- | ------ | ------------ | --------- |
| strong_trend   | directional         | no_shock        | aligned       | aligned        | aligned       | 6      | 1.7429       | inf       |
| trend          | directional         | no_shock        | aligned       | aligned        | aligned       | 5      | 1.1704       | 6.5578    |
| transition     | transition          | no_shock        | aligned       | aligned        | aligned       | 5      | 0.2575       | 1.5261    |
| weak_or_range  | range               | no_shock        | aligned       | aligned        | aligned       | 4      | 0.2361       | 1.3867    |
| trend          | directional         | aligned_shock   | aligned       | aligned        | aligned       | 3      | 0.0938       | 1.1887    |
| weak_or_range  | volatile_range      | aligned_shock   | aligned       | aligned        | aligned       | 1      | -0.0673      | 0.0000    |
| transition     | transition          | aligned_shock   | aligned       | aligned        | aligned       | 3      | -0.5504      | 0.0000    |
| strong_trend   | directional         | aligned_shock   | aligned       | aligned        | aligned       | 2      | -1.1940      | 0.0000    |
| strong_trend   | directional         | opposing_shock  | aligned       | aligned        | aligned       | 1      | -1.3210      | 0.0000    |
| transition     | transition          | opposing_shock  | aligned       | aligned        | aligned       | 1      | -1.3488      | 0.0000    |
| weak_or_range  | range               | aligned_shock   | aligned       | aligned        | aligned       | 1      | -1.3507      | 0.0000    |

## Rolling Windows

### 30-day windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | worst_base_dd_pct | median_stress_pf | worst_stress_return_r | worst_stress_dd_pct | base_sharpe | stress_sharpe |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ----------------- | ---------------- | --------------------- | ------------------- | ----------- | ------------- |
| 7       | 14.0000       | 1.0000                | 1.0000                  | 2.5299         | 4.5640              | 4.5640            | 1.9400           | 1.2132                | 1.2132              | 209.0827    | 133.3479      |

### 60-day windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | worst_base_dd_pct | median_stress_pf | worst_stress_return_r | worst_stress_dd_pct | base_sharpe | stress_sharpe |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ----------------- | ---------------- | --------------------- | ------------------- | ----------- | ------------- |
| 2       | 26.5000       | 1.0000                | 1.0000                  | 2.5327         | 13.2710             | 13.2710           | 1.9063           | 9.2367                | 9.2367              | 1068.2066   | 901.2689      |

## Read

- Base cost uses 6bps round-trip, roughly taker entry plus maker target exit.
- Stress cost uses 20bps round-trip. If a setup dies there, it has weak execution margin.
- This lab is not a promotion tool. It exists to falsify simple setup ideas before they reach the engine.
