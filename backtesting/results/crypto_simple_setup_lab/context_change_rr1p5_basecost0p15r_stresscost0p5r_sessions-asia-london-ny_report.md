# Simple Crypto Setup Lab

Scope: one setup family at a time, existing 240m/30m structure+EMA direction context, 15m entry, structural SL/TP, explicit cost-per-R.

## Summary

| setup          | symbol   | trades | win_rate | gross_avg_r | base_avg_r | base_pf | stress_avg_r | stress_pf | median_stop_pct | median_planned_rr | median_base_cost_r | median_stress_cost_r | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r |
| -------------- | -------- | ------ | -------- | ----------- | ---------- | ------- | ------------ | --------- | --------------- | ----------------- | ------------------ | -------------------- | ----------- | --------- | ----------- | ------------ | ------------ |
| context_change | BNBUSDT  | 194    | 0.495    | 0.314       | 0.234      | 1.481   | 0.048        | 1.083     | 0.783           | 1.500             | 0.077              | 0.255                | 0.495       | 0.448     | 0.057       | 1.511        | -0.823       |
| context_change | BTCUSDT  | 177    | 0.452    | 0.204       | 0.120      | 1.229   | -0.075       | 0.881     | 0.702           | 1.500             | 0.086              | 0.285                | 0.452       | 0.480     | 0.068       | 1.392        | -0.812       |
| context_change | DOGEUSDT | 277    | 0.484    | 0.289       | 0.225      | 1.443   | 0.076        | 1.130     | 1.091           | 1.500             | 0.055              | 0.183                | 0.484       | 0.477     | 0.040       | 1.482        | -0.862       |
| context_change | ETHUSDT  | 221    | 0.529    | 0.392       | 0.317      | 1.703   | 0.143        | 1.269     | 0.842           | 1.500             | 0.071              | 0.237                | 0.529       | 0.416     | 0.054       | 1.553        | -0.783       |
| context_change | SOLUSDT  | 259    | 0.514    | 0.374       | 0.307      | 1.670   | 0.152        | 1.288     | 0.988           | 1.500             | 0.061              | 0.202                | 0.514       | 0.429     | 0.058       | 1.523        | -0.848       |
| context_change | XRPUSDT  | 266    | 0.477    | 0.267       | 0.189      | 1.361   | 0.005        | 1.009     | 0.799           | 1.500             | 0.075              | 0.250                | 0.477       | 0.481     | 0.041       | 1.419        | -0.922       |
| ALL            | ALL      | 1394   | 0.493    | 0.310       | 0.236      | 1.480   | 0.064        | 1.111     | 0.864           | 1.500             | 0.069              | 0.232                | 0.493       | 0.456     | 0.052       | 1.502        | -0.845       |

## Session Split

| setup          | session_utc | trades | base_avg_r | base_pf | median_stop_pct |
| -------------- | ----------- | ------ | ---------- | ------- | --------------- |
| context_change | asia        | 537    | 0.263      | 1.540   | 0.877           |
| context_change | london      | 328    | 0.214      | 1.417   | 0.790           |
| context_change | ny          | 529    | 0.222      | 1.460   | 0.913           |

## Rolling Windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | median_stress_pf | worst_stress_return_r |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ---------------- | --------------------- |
| 52      | 106.000       | 0.808                 | 0.558                   | 1.461          | -22.436             | 1.114            | -39.726               |

## Read

- Base cost uses 6bps round-trip, roughly taker entry plus maker target exit.
- Stress cost uses 20bps round-trip. If a setup dies there, it has weak execution margin.
- This lab is not a promotion tool. It exists to falsify simple setup ideas before they reach the engine.
