# Simple Crypto Setup Lab

Scope: one setup family at a time, existing 240m/30m structure+EMA direction context, 15m entry, structural SL/TP, explicit cost-per-R.

## Summary

| setup                 | symbol   | trades | win_rate | gross_avg_r | base_avg_r | base_pf | stress_avg_r | stress_pf | median_stop_pct | median_planned_rr | median_base_cost_r | median_stress_cost_r | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r | top_trend_strength | top_consolidation_state | top_shock_alignment | top_dmi_alignment |
| --------------------- | -------- | ------ | -------- | ----------- | ---------- | ------- | ------------ | --------- | --------------- | ----------------- | ------------------ | -------------------- | ----------- | --------- | ----------- | ------------ | ------------ | ------------------ | ----------------------- | ------------------- | ----------------- |
| micro_reclaim_context | DOGEUSDT | 10     | 0.2000   | -0.4000     | -0.4367    | 0.4687  | -0.5222      | 0.4019    | 2.1977          | 2.0000            | 0.0274             | 0.0912               | 0.2000      | 0.8000    | 0.0000      | 0.1714       | -1.0111      | transition         | directional             | no_shock            | aligned           |
| micro_reclaim_context | ETHUSDT  | 6      | 0.8333   | 1.5000      | 1.4783     | 9.7145  | 1.4277       | 9.0856    | 2.9918          | 2.0000            | 0.0204             | 0.0679               | 0.8333      | 0.1667    | 0.0000      | 2.0736       | -0.4943      | trend              | directional             | no_shock            | aligned           |
| micro_reclaim_context | SOLUSDT  | 22     | 0.8182   | 1.5455      | 1.5016     | 15.7980 | 1.3993       | 12.0947   | 1.7678          | 2.0000            | 0.0345             | 0.1151               | 0.8182      | 0.0909    | 0.0909      | 2.0684       | -0.4155      | strong_trend       | directional             | no_shock            | aligned           |
| micro_reclaim_context | XRPUSDT  | 16     | 0.3125   | 0.5000      | 0.4691     | 4.2255  | 0.3971       | 3.0560    | 3.2496          | 2.0000            | 0.0185             | 0.0615               | 0.3125      | 0.1250    | 0.5625      | 0.9634       | -0.3148      | trend              | directional             | no_shock            | opposed           |
| ALL                   | ALL      | 54     | 0.5556   | 0.8704      | 0.8342     | 4.2649  | 0.7497       | 3.5858    | 2.2939          | 2.0000            | 0.0262             | 0.0872               | 0.5556      | 0.2407    | 0.2037      | 2.0186       | -0.5831      | strong_trend       | directional             | no_shock            | aligned           |

## Session Split

| setup                 | session_utc | trades | base_avg_r | base_pf | median_stop_pct |
| --------------------- | ----------- | ------ | ---------- | ------- | --------------- |
| micro_reclaim_context | asia        | 18     | 1.0298     | 17.5489 | 3.2921          |
| micro_reclaim_context | london      | 15     | 0.0989     | 1.1769  | 2.4127          |
| micro_reclaim_context | ny          | 21     | 1.1916     | 6.8318  | 1.5799          |

## Context Split

| trend_strength | consolidation_state       | shock_alignment | dmi_alignment | trades | stress_avg_r | stress_pf |
| -------------- | ------------------------- | --------------- | ------------- | ------ | ------------ | --------- |
| transition     | range_to_trend_transition | no_shock        | opposed       | 1      | 1.9061       | inf       |
| weak_or_range  | range                     | no_shock        | aligned       | 2      | 1.7939       | inf       |
| transition     | transition                | no_shock        | aligned       | 5      | 1.7700       | inf       |
| trend          | directional               | no_shock        | aligned       | 11     | 0.9193       | 8.7777    |
| strong_trend   | directional               | no_shock        | aligned       | 13     | 0.8107       | 3.2944    |
| trend          | directional               | no_shock        | opposed       | 4      | 0.6598       | 3.2051    |
| weak_or_range  | range                     | no_shock        | opposed       | 8      | 0.4874       | 2.0330    |
| strong_trend   | directional               | no_shock        | opposed       | 4      | 0.1004       | 1.2797    |
| weak_or_range  | volatile_range            | no_shock        | opposed       | 1      | -0.0460      | 0.0000    |
| transition     | transition                | no_shock        | opposed       | 4      | -0.0810      | 0.8544    |
| transition     | coiling_transition        | no_shock        | aligned       | 1      | -1.0829      | 0.0000    |

## Rolling Windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | median_stress_pf | worst_stress_return_r |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ---------------- | --------------------- |
| 1       | 26.0000       | 1.0000                | 1.0000                  | 5.4544         | 28.8080             | 4.4437           | 26.0265               |

## Read

- Base cost uses 6bps round-trip, roughly taker entry plus maker target exit.
- Stress cost uses 20bps round-trip. If a setup dies there, it has weak execution margin.
- This lab is not a promotion tool. It exists to falsify simple setup ideas before they reach the engine.
