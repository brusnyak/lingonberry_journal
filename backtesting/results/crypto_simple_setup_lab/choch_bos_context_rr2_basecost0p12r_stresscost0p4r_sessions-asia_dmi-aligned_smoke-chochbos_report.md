# Simple Crypto Setup Lab

Scope: one setup family at a time, existing 240m/30m structure+EMA direction context, 15m entry, structural SL/TP, explicit cost-per-R.

## Summary

| setup             | symbol   | trades | win_rate | gross_avg_r | base_avg_r | base_pf | stress_avg_r | stress_pf | median_stop_pct | median_planned_rr | median_base_cost_r | median_stress_cost_r | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r | top_trend_strength | top_consolidation_state | top_shock_alignment | top_dmi_alignment |
| ----------------- | -------- | ------ | -------- | ----------- | ---------- | ------- | ------------ | --------- | --------------- | ----------------- | ------------------ | -------------------- | ----------- | --------- | ----------- | ------------ | ------------ | ------------------ | ----------------------- | ------------------- | ----------------- |
| choch_bos_context | BNBUSDT  | 4      | 0.2500   | 0.0000      | -0.0624    | 0.8842  | -0.2080      | 0.6696    | 1.2438          | 2.0000            | 0.0633             | 0.2110               | 0.2500      | 0.5000    | 0.2500      | 1.0574       | -0.8029      | transition         | directional             | aligned_shock       | aligned           |
| choch_bos_context | BTCUSDT  | 4      | 0.2500   | 0.0000      | -0.0715    | 0.8698  | -0.2382      | 0.6403    | 0.8732          | 2.0000            | 0.0702             | 0.2342               | 0.2500      | 0.5000    | 0.2500      | 0.6753       | -1.0820      | trend              | directional             | aligned_shock       | aligned           |
| choch_bos_context | DOGEUSDT | 7      | 0.1429   | -0.2857     | -0.3240    | 0.4597  | -0.4134      | 0.3790    | 1.8068          | 2.0000            | 0.0332             | 0.1107               | 0.1429      | 0.5714    | 0.2857      | 0.4815       | -1.0395      | strong_trend       | directional             | opposing_shock      | aligned           |
| choch_bos_context | ETHUSDT  | 4      | 0.2500   | -0.2500     | -0.3206    | 0.5986  | -0.4855      | 0.4679    | 0.7235          | 2.0000            | 0.0832             | 0.2772               | 0.2500      | 0.7500    | 0.0000      | 0.5817       | -1.0472      | strong_trend       | directional             | no_shock            | aligned           |
| choch_bos_context | SOLUSDT  | 3      | 0.3333   | 0.0000      | -0.0651    | 0.9076  | -0.2171      | 0.7268    | 0.7472          | 2.0000            | 0.0803             | 0.2677               | 0.3333      | 0.6667    | 0.0000      | 0.1479       | -1.0799      | strong_trend       | directional             | no_shock            | aligned           |
| choch_bos_context | XRPUSDT  | 2      | 0.5000   | 1.0000      | 0.9391     | 54.6490 | 0.7968       | 14.6573   | 1.2022          | 2.0000            | 0.0609             | 0.2032               | 0.5000      | 0.0000    | 0.5000      | 1.5571       | -0.6103      | transition         | transition              | aligned_shock       | aligned           |
| ALL               | ALL      | 24     | 0.2500   | -0.0417     | -0.1001    | 0.8270  | -0.2366      | 0.6446    | 1.0566          | 2.0000            | 0.0569             | 0.1898               | 0.2500      | 0.5417    | 0.2083      | 0.5817       | -1.0294      | transition         | directional             | aligned_shock       | aligned           |

## Session Split

| setup             | session_utc | trades | base_avg_r | base_pf | median_stop_pct |
| ----------------- | ----------- | ------ | ---------- | ------- | --------------- |
| choch_bos_context | asia        | 24     | -0.1001    | 0.8270  | 1.0566          |

## Context Split

| trend_strength | consolidation_state | shock_alignment | dmi_alignment | trades | stress_avg_r | stress_pf |
| -------------- | ------------------- | --------------- | ------------- | ------ | ------------ | --------- |
| transition     | transition          | no_shock        | aligned       | 2      | 1.7214       | inf       |
| weak_or_range  | range               | no_shock        | aligned       | 2      | 0.2519       | 1.3990    |
| strong_trend   | directional         | no_shock        | aligned       | 2      | 0.1801       | 1.2673    |
| transition     | transition          | opposing_shock  | aligned       | 3      | 0.1012       | 1.2196    |
| trend          | directional         | no_shock        | aligned       | 3      | -0.2483      | 0.6948    |
| strong_trend   | directional         | opposing_shock  | aligned       | 2      | -0.5837      | 0.0000    |
| trend          | directional         | aligned_shock   | aligned       | 5      | -0.7631      | 0.0000    |
| transition     | transition          | aligned_shock   | aligned       | 3      | -0.7942      | 0.0000    |
| strong_trend   | directional         | aligned_shock   | aligned       | 2      | -1.0889      | 0.0000    |

## Rolling Windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | median_stress_pf | worst_stress_return_r |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ---------------- | --------------------- |
| 6       | 8.5000        | 0.3333                | 0.3333                  | 0.1495         | -5.2241             | 0.1166           | -5.7470               |

## Read

- Base cost uses 6bps round-trip, roughly taker entry plus maker target exit.
- Stress cost uses 20bps round-trip. If a setup dies there, it has weak execution margin.
- This lab is not a promotion tool. It exists to falsify simple setup ideas before they reach the engine.
