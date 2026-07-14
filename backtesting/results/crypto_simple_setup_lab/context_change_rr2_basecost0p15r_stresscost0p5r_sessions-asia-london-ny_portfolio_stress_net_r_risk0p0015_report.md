# Simple Crypto Setup Portfolio Validation

Scope: portfolio/risk throttle applied to one already-filtered simple setup candidate set.

## Summary

| candidates | accepted | acceptance_rate | symbols | exchanges | total_r  | avg_r  | median_r | profit_factor | gross_return_pct | max_dd_pct | daily_max_dd_pct | return_to_dd | win_rate | stop_rate | expiry_rate | risk_per_trade_pct | max_open_trades | max_open_per_symbol | daily_loss_limit_pct |
| ---------- | -------- | --------------- | ------- | --------- | -------- | ------ | -------- | ------------- | ---------------- | ---------- | ---------------- | ------------ | -------- | --------- | ----------- | ------------------ | --------------- | ------------------- | -------------------- |
| 1200       | 745      | 0.6208          | 5       | 1         | 151.7636 | 0.2037 | -0.1116  | 1.3495        | 0.2276           | 0.0440     | 0.0440           | 5.1746       | 0.4416   | 0.4617    | 0.0966      | 0.0015             | 3               | 1                   | 0.0050               |

## Symbol Split

| symbol   | trades | avg_r  | pf     | pnl_pct |
| -------- | ------ | ------ | ------ | ------- |
| BTCUSDT  | 123    | 0.0376 | 1.0586 | 0.0069  |
| DOGEUSDT | 174    | 0.1942 | 1.3382 | 0.0507  |
| ETHUSDT  | 142    | 0.0856 | 1.1371 | 0.0182  |
| SOLUSDT  | 148    | 0.3917 | 1.7548 | 0.0870  |
| XRPUSDT  | 158    | 0.2735 | 1.4809 | 0.0648  |

## Read

- This is still research validation, not live approval.
- Stress-mode validation should be treated as the primary deployment-risk read.
