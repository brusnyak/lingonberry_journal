# Simple Crypto Setup Lab

Scope: one setup family at a time, existing 240m/30m structure+EMA direction context, 15m entry, structural SL/TP, explicit cost-per-R.

## Summary

| setup          | symbol   | trades | win_rate | gross_avg_r | base_avg_r | base_pf | stress_avg_r | stress_pf | median_stop_pct | median_planned_rr | median_base_cost_r | median_stress_cost_r | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r |
| -------------- | -------- | ------ | -------- | ----------- | ---------- | ------- | ------------ | --------- | --------------- | ----------------- | ------------------ | -------------------- | ----------- | --------- | ----------- | ------------ | ------------ |
| context_change | BTCUSDT  | 177    | 0.4181   | 0.3339      | 0.2501     | 1.4541  | 0.0546       | 1.0824    | 0.7017          | 2.0000            | 0.0855             | 0.2850               | 0.4181      | 0.5028    | 0.0791      | 1.3916       | -1.0047      |
| context_change | DOGEUSDT | 277    | 0.4188   | 0.3616      | 0.2976     | 1.5629  | 0.1484       | 1.2439    | 1.0907          | 2.0000            | 0.0550             | 0.1834               | 0.4188      | 0.4946    | 0.0866      | 1.4818       | -0.9818      |
| context_change | ETHUSDT  | 221    | 0.4344   | 0.3854      | 0.3108     | 1.5914  | 0.1370       | 1.2201    | 0.8425          | 2.0000            | 0.0712             | 0.2374               | 0.4344      | 0.4842    | 0.0814      | 1.7039       | -0.9182      |
| context_change | SOLUSDT  | 259    | 0.4556   | 0.4488      | 0.3823     | 1.7457  | 0.2273       | 1.3839    | 0.9883          | 2.0000            | 0.0607             | 0.2024               | 0.4556      | 0.4788    | 0.0656      | 1.7279       | -0.9500      |
| context_change | XRPUSDT  | 266    | 0.4286   | 0.3557      | 0.2771     | 1.4950  | 0.0937       | 1.1410    | 0.7994          | 2.0000            | 0.0751             | 0.2502               | 0.4286      | 0.5150    | 0.0564      | 1.4186       | -1.0083      |
| ALL            | ALL      | 1200   | 0.4317   | 0.3794      | 0.3068     | 1.5736  | 0.1374       | 1.2188    | 0.8764          | 2.0000            | 0.0685             | 0.2282               | 0.4317      | 0.4950    | 0.0733      | 1.5826       | -0.9818      |

## Session Split

| setup          | session_utc | trades | base_avg_r | base_pf | median_stop_pct |
| -------------- | ----------- | ------ | ---------- | ------- | --------------- |
| context_change | asia        | 470    | 0.3331     | 1.6313  | 0.9017          |
| context_change | london      | 274    | 0.2673     | 1.4681  | 0.7917          |
| context_change | ny          | 456    | 0.3034     | 1.5828  | 0.9563          |

## Rolling Windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | median_stress_pf | worst_stress_return_r |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ---------------- | --------------------- |
| 52      | 91.0000       | 0.7885                | 0.6346                  | 1.5884         | -15.7641            | 1.2240           | -31.5469              |

## Read

- Base cost uses 6bps round-trip, roughly taker entry plus maker target exit.
- Stress cost uses 20bps round-trip. If a setup dies there, it has weak execution margin.
- This lab is not a promotion tool. It exists to falsify simple setup ideas before they reach the engine.
