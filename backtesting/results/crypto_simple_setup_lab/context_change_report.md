# Simple Crypto Setup Lab

Scope: one setup family at a time, existing 240m/30m structure+EMA direction context, 15m entry, structural SL/TP, explicit cost-per-R.

## Summary

| setup          | symbol   | trades | win_rate | gross_avg_r | base_avg_r | base_pf | stress_avg_r | stress_pf | median_stop_pct | median_planned_rr | median_base_cost_r | median_stress_cost_r | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r |
| -------------- | -------- | ------ | -------- | ----------- | ---------- | ------- | ------------ | --------- | --------------- | ----------------- | ------------------ | -------------------- | ----------- | --------- | ----------- | ------------ | ------------ |
| context_change | BNBUSDT  | 453    | 0.466    | 0.250       | 0.088      | 1.147   | -0.291       | 0.643     | 0.444           | 1.500             | 0.135              | 0.450                | 0.466       | 0.506     | 0.029       | 1.421        | -1.005       |
| context_change | BTCUSDT  | 443    | 0.436    | 0.192       | 0.025      | 1.040   | -0.365       | 0.569     | 0.498           | 1.500             | 0.121              | 0.402                | 0.436       | 0.528     | 0.036       | 1.318        | -1.014       |
| context_change | DOGEUSDT | 520    | 0.427    | 0.220       | 0.118      | 1.197   | -0.120       | 0.837     | 0.874           | 1.500             | 0.069              | 0.229                | 0.427       | 0.538     | 0.035       | 1.323        | -1.000       |
| context_change | ETHUSDT  | 510    | 0.482    | 0.339       | 0.190      | 1.332   | -0.157       | 0.795     | 0.550           | 1.500             | 0.109              | 0.364                | 0.482       | 0.492     | 0.025       | 1.532        | -0.967       |
| context_change | SOLUSDT  | 527    | 0.471    | 0.289       | 0.175      | 1.313   | -0.092       | 0.870     | 0.766           | 1.500             | 0.078              | 0.261                | 0.471       | 0.493     | 0.036       | 1.500        | -0.984       |
| context_change | XRPUSDT  | 531    | 0.446    | 0.194       | 0.059      | 1.096   | -0.257       | 0.677     | 0.553           | 1.500             | 0.109              | 0.362                | 0.446       | 0.533     | 0.021       | 1.358        | -1.012       |
| ALL            | ALL      | 2984   | 0.455    | 0.248       | 0.111      | 1.188   | -0.208       | 0.732     | 0.594           | 1.500             | 0.101              | 0.336                | 0.455       | 0.515     | 0.030       | 1.419        | -1.000       |

## Session Split

| setup          | session_utc | trades | base_avg_r | base_pf | median_stop_pct |
| -------------- | ----------- | ------ | ---------- | ------- | --------------- |
| context_change | asia        | 796    | 0.132      | 1.229   | 0.616           |
| context_change | late_us     | 884    | 0.021      | 1.032   | 0.610           |
| context_change | london      | 544    | 0.126      | 1.209   | 0.486           |
| context_change | ny          | 760    | 0.185      | 1.340   | 0.654           |

## Read

- Base cost uses 6bps round-trip, roughly taker entry plus maker target exit.
- Stress cost uses 20bps round-trip. If a setup dies there, it has weak execution margin.
- This lab is not a promotion tool. It exists to falsify simple setup ideas before they reach the engine.
