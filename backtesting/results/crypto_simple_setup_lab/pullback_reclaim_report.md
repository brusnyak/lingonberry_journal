# Simple Crypto Setup Lab

Scope: one setup family at a time, existing 240m/30m structure+EMA direction context, 15m entry, structural SL/TP, explicit cost-per-R.

## Summary

| setup            | symbol   | trades | win_rate | gross_avg_r | base_avg_r | base_pf | stress_avg_r | stress_pf | median_stop_pct | median_planned_rr | median_base_cost_r | median_stress_cost_r | target_rate | stop_rate | expiry_rate | median_mfe_r | median_mae_r |
| ---------------- | -------- | ------ | -------- | ----------- | ---------- | ------- | ------------ | --------- | --------------- | ----------------- | ------------------ | -------------------- | ----------- | --------- | ----------- | ------------ | ------------ |
| pullback_reclaim | BNBUSDT  | 1927   | 0.378    | 0.060       | -0.049     | 0.918   | -0.304       | 0.598     | 0.767           | 1.500             | 0.078              | 0.261                | 0.378       | 0.533     | 0.088       | 0.991        | -1.009       |
| pullback_reclaim | BTCUSDT  | 1684   | 0.322    | -0.053      | -0.173     | 0.730   | -0.452       | 0.459     | 0.714           | 1.500             | 0.084              | 0.280                | 0.322       | 0.558     | 0.120       | 0.878        | -1.023       |
| pullback_reclaim | DOGEUSDT | 1654   | 0.333    | -0.026      | -0.096     | 0.841   | -0.259       | 0.635     | 1.360           | 1.500             | 0.044              | 0.147                | 0.333       | 0.557     | 0.110       | 0.887        | -1.013       |
| pullback_reclaim | ETHUSDT  | 1968   | 0.439    | 0.229       | 0.140      | 1.276   | -0.066       | 0.893     | 1.020           | 1.500             | 0.059              | 0.196                | 0.439       | 0.459     | 0.103       | 1.271        | -0.873       |
| pullback_reclaim | SOLUSDT  | 1847   | 0.338    | -0.012      | -0.092     | 0.847   | -0.281       | 0.617     | 1.179           | 1.500             | 0.051              | 0.170                | 0.338       | 0.550     | 0.112       | 0.919        | -1.012       |
| pullback_reclaim | XRPUSDT  | 2242   | 0.404    | 0.105       | 0.017      | 1.029   | -0.187       | 0.738     | 1.039           | 1.500             | 0.058              | 0.193                | 0.404       | 0.533     | 0.064       | 1.171        | -1.009       |
| ALL              | ALL      | 11322  | 0.372    | 0.057       | -0.035     | 0.940   | -0.251       | 0.654     | 0.985           | 1.500             | 0.061              | 0.203                | 0.372       | 0.530     | 0.098       | 1.012        | -1.008       |

## Session Split

| setup            | session_utc | trades | base_avg_r | base_pf | median_stop_pct |
| ---------------- | ----------- | ------ | ---------- | ------- | --------------- |
| pullback_reclaim | asia        | 2913   | 0.008      | 1.015   | 1.042           |
| pullback_reclaim | late_us     | 3711   | -0.121     | 0.804   | 0.984           |
| pullback_reclaim | london      | 2197   | 0.015      | 1.025   | 0.838           |
| pullback_reclaim | ny          | 2501   | -0.004     | 0.992   | 1.099           |

## Read

- Base cost uses 6bps round-trip, roughly taker entry plus maker target exit.
- Stress cost uses 20bps round-trip. If a setup dies there, it has weak execution margin.
- This lab is not a promotion tool. It exists to falsify simple setup ideas before they reach the engine.
