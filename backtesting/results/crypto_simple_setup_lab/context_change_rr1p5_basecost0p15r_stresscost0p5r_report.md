# Simple Crypto Setup Lab

Scope: one setup family at a time, existing 240m/30m structure+EMA direction context, 15m entry, structural SL/TP, explicit cost-per-R.

## Summary

| setup          | symbol   | trades | win_rate | gross_avg_r | base_avg_r | base_pf | stress_avg_r | stress_pf | median_stop_pct | median_planned_rr | median_base_cost_r | median_stress_cost_r | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r |
| -------------- | -------- | ------ | -------- | ----------- | ---------- | ------- | ------------ | --------- | --------------- | ----------------- | ------------------ | -------------------- | ----------- | --------- | ----------- | ------------ | ------------ |
| context_change | BNBUSDT  | 257    | 0.494    | 0.311       | 0.230      | 1.465   | 0.040        | 1.069     | 0.746           | 1.500             | 0.080              | 0.268                | 0.494       | 0.455     | 0.051       | 1.508        | -0.829       |
| context_change | BTCUSDT  | 267    | 0.427    | 0.146       | 0.062      | 1.111   | -0.132       | 0.803     | 0.706           | 1.500             | 0.085              | 0.283                | 0.427       | 0.513     | 0.060       | 1.223        | -1.002       |
| context_change | DOGEUSDT | 410    | 0.439    | 0.172       | 0.110      | 1.199   | -0.036       | 0.943     | 1.114           | 1.500             | 0.054              | 0.180                | 0.439       | 0.517     | 0.044       | 1.280        | -1.000       |
| context_change | ETHUSDT  | 326    | 0.506    | 0.332       | 0.256      | 1.521   | 0.078        | 1.134     | 0.807           | 1.500             | 0.074              | 0.248                | 0.506       | 0.454     | 0.040       | 1.524        | -0.883       |
| context_change | SOLUSDT  | 404    | 0.500    | 0.338       | 0.270      | 1.555   | 0.111        | 1.196     | 0.946           | 1.500             | 0.063              | 0.211                | 0.500       | 0.453     | 0.047       | 1.507        | -0.907       |
| context_change | XRPUSDT  | 349    | 0.470    | 0.242       | 0.165      | 1.305   | -0.016       | 0.975     | 0.824           | 1.500             | 0.073              | 0.243                | 0.470       | 0.499     | 0.032       | 1.393        | -0.994       |
| ALL            | ALL      | 2013   | 0.473    | 0.258       | 0.184      | 1.354   | 0.012        | 1.020     | 0.863           | 1.500             | 0.070              | 0.232                | 0.473       | 0.482     | 0.045       | 1.426        | -0.938       |

## Session Split

| setup          | session_utc | trades | base_avg_r | base_pf | median_stop_pct |
| -------------- | ----------- | ------ | ---------- | ------- | --------------- |
| context_change | asia        | 537    | 0.263      | 1.540   | 0.877           |
| context_change | late_us     | 619    | 0.067      | 1.115   | 0.857           |
| context_change | london      | 328    | 0.214      | 1.417   | 0.790           |
| context_change | ny          | 529    | 0.222      | 1.460   | 0.913           |

## Rolling Windows

| windows | median_trades | positive_base_windows | positive_stress_windows | median_base_pf | worst_base_return_r | median_stress_pf | worst_stress_return_r |
| ------- | ------------- | --------------------- | ----------------------- | -------------- | ------------------- | ---------------- | --------------------- |
| 52      | 151.500       | 0.827                 | 0.481                   | 1.261          | -37.244             | 0.958            | -62.697               |

## Read

- Base cost uses 6bps round-trip, roughly taker entry plus maker target exit.
- Stress cost uses 20bps round-trip. If a setup dies there, it has weak execution margin.
- This lab is not a promotion tool. It exists to falsify simple setup ideas before they reach the engine.
