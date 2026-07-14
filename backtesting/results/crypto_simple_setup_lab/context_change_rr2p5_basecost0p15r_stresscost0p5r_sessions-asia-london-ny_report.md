# Simple Crypto Setup Lab

Scope: one setup family at a time, existing 240m/30m structure+EMA direction context, 15m entry, structural SL/TP, explicit cost-per-R.

## Summary

| setup          | symbol   | trades | win_rate | gross_avg_r | base_avg_r | base_pf | stress_avg_r | stress_pf | median_stop_pct | median_planned_rr | median_base_cost_r | median_stress_cost_r | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r |
| -------------- | -------- | ------ | -------- | ----------- | ---------- | ------- | ------------ | --------- | --------------- | ----------------- | ------------------ | -------------------- | ----------- | --------- | ----------- | ------------ | ------------ |
| context_change | BNBUSDT  | 194    | 0.345    | 0.314       | 0.234      | 1.390   | 0.048        | 1.067     | 0.783           | 2.500             | 0.077              | 0.255                | 0.345       | 0.552     | 0.103       | 1.570        | -1.031       |
| context_change | BTCUSDT  | 177    | 0.356    | 0.347       | 0.264      | 1.443   | 0.068        | 1.095     | 0.702           | 2.500             | 0.086              | 0.285                | 0.356       | 0.542     | 0.102       | 1.392        | -1.037       |
| context_change | DOGEUSDT | 277    | 0.329    | 0.281       | 0.217      | 1.370   | 0.068        | 1.100     | 1.091           | 2.500             | 0.055              | 0.183                | 0.329       | 0.549     | 0.123       | 1.482        | -1.000       |
| context_change | ETHUSDT  | 221    | 0.398    | 0.489       | 0.414      | 1.752   | 0.240        | 1.368     | 0.842           | 2.500             | 0.071              | 0.237                | 0.398       | 0.507     | 0.095       | 1.704        | -1.004       |
| context_change | SOLUSDT  | 259    | 0.367    | 0.398       | 0.332      | 1.583   | 0.177        | 1.267     | 0.988           | 2.500             | 0.061              | 0.202                | 0.367       | 0.529     | 0.104       | 1.728        | -1.024       |
| context_change | XRPUSDT  | 266    | 0.380    | 0.410       | 0.331      | 1.558   | 0.148        | 1.209     | 0.799           | 2.500             | 0.075              | 0.250                | 0.380       | 0.545     | 0.075       | 1.419        | -1.014       |
| ALL            | ALL      | 1394   | 0.362    | 0.373       | 0.300      | 1.515   | 0.128        | 1.186     | 0.864           | 2.500             | 0.069              | 0.232                | 0.362       | 0.537     | 0.100       | 1.583        | -1.014       |

## Session Split

| setup          | session_utc | trades | base_avg_r | base_pf | median_stop_pct |
| -------------- | ----------- | ------ | ---------- | ------- | --------------- |
| context_change | asia        | 537    | 0.370      | 1.651   | 0.877           |
| context_change | london      | 328    | 0.243      | 1.390   | 0.790           |
| context_change | ny          | 529    | 0.263      | 1.461   | 0.913           |

## Rolling Windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | median_stress_pf | worst_stress_return_r |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ---------------- | --------------------- |
| 52      | 106.000       | 0.808                 | 0.577                   | 1.516          | -27.910             | 1.191            | -45.200               |

## Read

- Base cost uses 6bps round-trip, roughly taker entry plus maker target exit.
- Stress cost uses 20bps round-trip. If a setup dies there, it has weak execution margin.
- This lab is not a promotion tool. It exists to falsify simple setup ideas before they reach the engine.
