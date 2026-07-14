# Simple Crypto Setup Lab

Scope: one setup family at a time, existing 240m/30m structure+EMA direction context, 15m entry, structural SL/TP, explicit cost-per-R.

## Summary

| setup          | symbol   | trades | win_rate | gross_avg_r | base_avg_r | base_pf | stress_avg_r | stress_pf | median_stop_pct | median_planned_rr | median_base_cost_r | median_stress_cost_r | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r |
| -------------- | -------- | ------ | -------- | ----------- | ---------- | ------- | ------------ | --------- | --------------- | ----------------- | ------------------ | -------------------- | ----------- | --------- | ----------- | ------------ | ------------ |
| context_change | BNBUSDT  | 257    | 0.401    | 0.293       | 0.212      | 1.373   | 0.022        | 1.033     | 0.746           | 2.000             | 0.080              | 0.268                | 0.401       | 0.521     | 0.078       | 1.517        | -1.015       |
| context_change | BTCUSDT  | 267    | 0.382    | 0.231       | 0.148      | 1.251   | -0.046       | 0.935     | 0.706           | 2.000             | 0.085              | 0.283                | 0.382       | 0.539     | 0.079       | 1.223        | -1.019       |
| context_change | DOGEUSDT | 410    | 0.371    | 0.212       | 0.150      | 1.258   | 0.004        | 1.006     | 1.114           | 2.000             | 0.054              | 0.180                | 0.371       | 0.544     | 0.085       | 1.280        | -1.000       |
| context_change | ETHUSDT  | 326    | 0.414    | 0.325       | 0.248      | 1.444   | 0.070        | 1.106     | 0.807           | 2.000             | 0.074              | 0.248                | 0.414       | 0.515     | 0.071       | 1.638        | -1.009       |
| context_change | SOLUSDT  | 404    | 0.438    | 0.390       | 0.322      | 1.595   | 0.163        | 1.260     | 0.946           | 2.000             | 0.063              | 0.211                | 0.438       | 0.505     | 0.057       | 1.613        | -1.000       |
| context_change | XRPUSDT  | 349    | 0.407    | 0.292       | 0.215      | 1.368   | 0.034        | 1.050     | 0.824           | 2.000             | 0.073              | 0.243                | 0.407       | 0.539     | 0.054       | 1.393        | -1.014       |
| ALL            | ALL      | 2013   | 0.403    | 0.293       | 0.219      | 1.385   | 0.048        | 1.071     | 0.863           | 2.000             | 0.070              | 0.232                | 0.403       | 0.527     | 0.070       | 1.426        | -1.007       |

## Session Split

| setup          | session_utc | trades | base_avg_r | base_pf | median_stop_pct |
| -------------- | ----------- | ------ | ---------- | ------- | --------------- |
| context_change | asia        | 537    | 0.324      | 1.611   | 0.877           |
| context_change | late_us     | 619    | 0.037      | 1.057   | 0.857           |
| context_change | london      | 328    | 0.272      | 1.480   | 0.790           |
| context_change | ny          | 529    | 0.294      | 1.559   | 0.913           |

## Rolling Windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | median_stress_pf | worst_stress_return_r |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ---------------- | --------------------- |
| 52      | 151.500       | 0.808                 | 0.500                   | 1.331          | -38.213             | 1.012            | -63.666               |

## Read

- Base cost uses 6bps round-trip, roughly taker entry plus maker target exit.
- Stress cost uses 20bps round-trip. If a setup dies there, it has weak execution margin.
- This lab is not a promotion tool. It exists to falsify simple setup ideas before they reach the engine.
