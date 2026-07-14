# Simple Crypto Setup Portfolio Validation

Scope: portfolio/risk throttle applied to one already-filtered simple setup candidate set.

## Summary

| candidates | accepted | acceptance_rate | symbols | exchanges | total_r | avg_r  | median_r | profit_factor | gross_return_pct | max_dd_pct | daily_max_dd_pct | return_to_dd | win_rate | stop_rate | expiry_rate | risk_per_trade_pct | max_open_trades | max_open_per_symbol | daily_loss_limit_pct |
| ---------- | -------- | --------------- | ------- | --------- | ------- | ------ | -------- | ------------- | ---------------- | ---------- | ---------------- | ------------ | -------- | --------- | ----------- | ------------------ | --------------- | ------------------- | -------------------- |
| 21         | 7        | 0.3333          | 4       | 1         | 7.3457  | 1.0494 | 1.8916   | 4.3833        | 0.0147           | 0.0022     | 0.0022           | 6.7438       | 0.7143   | 0.2857    | 0.0000      | 0.0020             | 3               | 1                   | 0.0050               |

## Symbol Split

| symbol   | trades | avg_r   | pf     | pnl_pct |
| -------- | ------ | ------- | ------ | ------- |
| DOGEUSDT | 2      | -1.0856 | 0.0000 | -0.0043 |
| ETHUSDT  | 1      | 1.8916  | inf    | 0.0038  |
| SOLUSDT  | 2      | 1.9264  | inf    | 0.0077  |
| XRPUSDT  | 2      | 1.8863  | inf    | 0.0075  |

## Read

- This is still research validation, not live approval.
- Stress-mode validation should be treated as the primary deployment-risk read.
