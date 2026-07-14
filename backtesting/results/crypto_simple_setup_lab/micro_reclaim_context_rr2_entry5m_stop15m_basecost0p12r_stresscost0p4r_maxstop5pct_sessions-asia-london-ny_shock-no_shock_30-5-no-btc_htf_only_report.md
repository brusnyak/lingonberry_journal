# Simple Crypto Setup Lab

Scope: one setup family at a time, existing 240m/30m structure+EMA direction context, 15m entry, structural SL/TP, explicit cost-per-R.

## Summary

| setup                 | symbol   | trades | win_rate | gross_avg_r | base_avg_r | base_pf  | stress_avg_r | stress_pf | median_stop_pct | median_planned_rr | median_base_cost_r | median_stress_cost_r | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r | top_trend_strength | top_consolidation_state | top_shock_alignment | top_dmi_alignment |
| --------------------- | -------- | ------ | -------- | ----------- | ---------- | -------- | ------------ | --------- | --------------- | ----------------- | ------------------ | -------------------- | ----------- | --------- | ----------- | ------------ | ------------ | ------------------ | ----------------------- | ------------------- | ----------------- |
| micro_reclaim_context | DOGEUSDT | 4      | 0.0000   | -1.0000     | -1.0301    | 0.0000   | -1.1004      | 0.0000    | 2.0480          | 2.0000            | 0.0296             | 0.0985               | 0.0000      | 1.0000    | 0.0000      | 0.2520       | -1.0161      | trend              | directional             | no_shock            | aligned           |
| micro_reclaim_context | ETHUSDT  | 4      | 1.0000   | 2.0000      | 1.9747     | inf      | 1.9157       | inf       | 2.2122          | 2.0000            | 0.0271             | 0.0905               | 1.0000      | 0.0000    | 0.0000      | 2.1205       | -0.8677      | strong_trend       | directional             | no_shock            | aligned           |
| micro_reclaim_context | SOLUSDT  | 4      | 1.0000   | 2.0000      | 1.9794     | inf      | 1.9314       | inf       | 2.7834          | 2.0000            | 0.0218             | 0.0726               | 1.0000      | 0.0000    | 0.0000      | 2.1547       | -0.2793      | trend              | directional             | no_shock            | aligned           |
| micro_reclaim_context | XRPUSDT  | 9      | 0.4444   | 0.8889      | 0.8656     | 101.4933 | 0.8114       | 29.2589   | 2.6387          | 2.0000            | 0.0227             | 0.0758               | 0.4444      | 0.0000    | 0.5556      | 1.9075       | -0.1843      | strong_trend       | directional             | no_shock            | aligned           |
| ALL                   | ALL      | 21     | 0.5714   | 0.9524      | 0.9279     | 5.6419   | 0.8709       | 4.9246    | 2.4396          | 2.0000            | 0.0246             | 0.0820               | 0.5714      | 0.1905    | 0.2381      | 2.0576       | -0.3979      | strong_trend       | directional             | no_shock            | aligned           |

## Session Split

| setup                 | session_utc | trades | base_avg_r | base_pf  | median_stop_pct |
| --------------------- | ----------- | ------ | ---------- | -------- | --------------- |
| micro_reclaim_context | asia        | 6      | 0.9833     | 142.6900 | 4.2324          |
| micro_reclaim_context | london      | 7      | 0.8321     | 3.8214   | 2.2691          |
| micro_reclaim_context | ny          | 8      | 0.9703     | 4.7106   | 1.8776          |

## Context Split

| trend_strength | consolidation_state | shock_alignment | dmi_alignment | trades | stress_avg_r | stress_pf |
| -------------- | ------------------- | --------------- | ------------- | ------ | ------------ | --------- |
| transition     | transition          | no_shock        | opposed       | 1      | 1.9180       | inf       |
| strong_trend   | directional         | no_shock        | opposed       | 2      | 1.8837       | inf       |
| strong_trend   | directional         | no_shock        | aligned       | 8      | 1.0404       | 7.8849    |
| trend          | directional         | no_shock        | opposed       | 3      | 0.9260       | 3.5676    |
| trend          | directional         | no_shock        | aligned       | 6      | 0.4376       | 3.1063    |
| weak_or_range  | range               | no_shock        | aligned       | 1      | -1.1228      | 0.0000    |

## Rolling Windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | median_stress_pf | worst_stress_return_r |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ---------------- | --------------------- |
| 1       | 11.0000       | 1.0000                | 1.0000                  | 16.9766        | 16.7326             | 14.9141          | 16.1085               |

## Read

- Base cost uses 6bps round-trip, roughly taker entry plus maker target exit.
- Stress cost uses 20bps round-trip. If a setup dies there, it has weak execution margin.
- This lab is not a promotion tool. It exists to falsify simple setup ideas before they reach the engine.
