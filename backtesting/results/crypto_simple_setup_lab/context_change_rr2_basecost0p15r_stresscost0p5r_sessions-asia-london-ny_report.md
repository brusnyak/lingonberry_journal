# Simple Crypto Setup Lab

Scope: one setup family at a time, existing 240m/30m structure+EMA direction context, 15m entry, structural SL/TP, explicit cost-per-R.

## Summary

| setup          | symbol   | trades | win_rate | gross_avg_r | base_avg_r | base_pf | stress_avg_r | stress_pf | median_stop_pct | median_planned_rr | median_base_cost_r | median_stress_cost_r | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r |
| -------------- | -------- | ------ | -------- | ----------- | ---------- | ------- | ------------ | --------- | --------------- | ----------------- | ------------------ | -------------------- | ----------- | --------- | ----------- | ------------ | ------------ |
| context_change | BNBUSDT  | 194    | 0.418    | 0.339       | 0.259      | 1.473   | 0.073        | 1.113     | 0.783           | 2.000             | 0.077              | 0.255                | 0.418       | 0.505     | 0.077       | 1.570        | -1.002       |
| context_change | BTCUSDT  | 177    | 0.418    | 0.334       | 0.250      | 1.454   | 0.055        | 1.082     | 0.702           | 2.000             | 0.086              | 0.285                | 0.418       | 0.503     | 0.079       | 1.392        | -1.005       |
| context_change | DOGEUSDT | 277    | 0.419    | 0.362       | 0.298      | 1.563   | 0.148        | 1.244     | 1.091           | 2.000             | 0.055              | 0.183                | 0.419       | 0.495     | 0.087       | 1.482        | -0.982       |
| context_change | ETHUSDT  | 221    | 0.434    | 0.385       | 0.311      | 1.591   | 0.137        | 1.220     | 0.842           | 2.000             | 0.071              | 0.237                | 0.434       | 0.484     | 0.081       | 1.704        | -0.918       |
| context_change | SOLUSDT  | 259    | 0.456    | 0.449       | 0.382      | 1.746   | 0.227        | 1.384     | 0.988           | 2.000             | 0.061              | 0.202                | 0.456       | 0.479     | 0.066       | 1.728        | -0.950       |
| context_change | XRPUSDT  | 266    | 0.429    | 0.356       | 0.277      | 1.495   | 0.094        | 1.141     | 0.799           | 2.000             | 0.075              | 0.250                | 0.429       | 0.515     | 0.056       | 1.419        | -1.008       |
| ALL            | ALL      | 1394   | 0.430    | 0.374       | 0.300      | 1.559   | 0.128        | 1.204     | 0.864           | 2.000             | 0.069              | 0.232                | 0.430       | 0.496     | 0.074       | 1.583        | -0.982       |

## Session Split

| setup          | session_utc | trades | base_avg_r | base_pf | median_stop_pct |
| -------------- | ----------- | ------ | ---------- | ------- | --------------- |
| context_change | asia        | 537    | 0.324      | 1.611   | 0.877           |
| context_change | london      | 328    | 0.272      | 1.480   | 0.790           |
| context_change | ny          | 529    | 0.294      | 1.559   | 0.913           |

## Rolling Windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | median_stress_pf | worst_stress_return_r |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ---------------- | --------------------- |
| 52      | 106.000       | 0.846                 | 0.615                   | 1.502          | -23.410             | 1.168            | -40.700               |

## Read

- Base cost uses 6bps round-trip, roughly taker entry plus maker target exit.
- Stress cost uses 20bps round-trip. If a setup dies there, it has weak execution margin.
- This lab is not a promotion tool. It exists to falsify simple setup ideas before they reach the engine.
