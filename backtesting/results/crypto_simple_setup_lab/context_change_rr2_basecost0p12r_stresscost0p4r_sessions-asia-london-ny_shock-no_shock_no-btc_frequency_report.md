# Simple Crypto Setup Frequency Audit

Scope: day-level explanation of why the setup did or did not produce accepted trades.

## Summary

| primary_blocker    | symbol_days | active_context_bars | raw_signals | pre_portfolio_pass | portfolio_accepted |
| ------------------ | ----------- | ------------------- | ----------- | ------------------ | ------------------ |
| no_active_context  | 797         | 0                   | 0           | 0                  | 0                  |
| traded             | 318         | 11695               | 1272        | 466                | 360                |
| blocked_context    | 163         | 4359                | 332         | 0                  | 0                  |
| blocked_session    | 137         | 2719                | 345         | 0                  | 0                  |
| blocked_cost       | 101         | 3171                | 291         | 0                  | 0                  |
| invalid_stop       | 41          | 1127                | 133         | 0                  | 0                  |
| no_setup_signal    | 19          | 141                 | 0           | 0                  | 0                  |
| stop_too_tight     | 16          | 359                 | 38          | 0                  | 0                  |
| portfolio_throttle | 12          | 306                 | 33          | 13                 | 0                  |

## Symbol Split

| symbol   | primary_blocker    | days | raw_signals | pre_portfolio_pass | portfolio_accepted |
| -------- | ------------------ | ---- | ----------- | ------------------ | ------------------ |
| DOGEUSDT | no_active_context  | 195  | 0           | 0                  | 0                  |
| DOGEUSDT | traded             | 79   | 325         | 118                | 91                 |
| DOGEUSDT | blocked_context    | 52   | 104         | 0                  | 0                  |
| DOGEUSDT | blocked_session    | 35   | 87          | 0                  | 0                  |
| DOGEUSDT | blocked_cost       | 19   | 46          | 0                  | 0                  |
| DOGEUSDT | invalid_stop       | 10   | 24          | 0                  | 0                  |
| DOGEUSDT | no_setup_signal    | 4    | 0           | 0                  | 0                  |
| DOGEUSDT | stop_too_tight     | 4    | 11          | 0                  | 0                  |
| DOGEUSDT | portfolio_throttle | 3    | 6           | 3                  | 0                  |
| ETHUSDT  | no_active_context  | 208  | 0           | 0                  | 0                  |
| ETHUSDT  | traded             | 73   | 287         | 106                | 81                 |
| ETHUSDT  | blocked_cost       | 35   | 112         | 0                  | 0                  |
| ETHUSDT  | blocked_session    | 35   | 90          | 0                  | 0                  |
| ETHUSDT  | blocked_context    | 28   | 60          | 0                  | 0                  |
| ETHUSDT  | invalid_stop       | 8    | 30          | 0                  | 0                  |
| ETHUSDT  | no_setup_signal    | 7    | 0           | 0                  | 0                  |
| ETHUSDT  | stop_too_tight     | 6    | 18          | 0                  | 0                  |
| ETHUSDT  | portfolio_throttle | 1    | 4           | 1                  | 0                  |
| SOLUSDT  | no_active_context  | 198  | 0           | 0                  | 0                  |
| SOLUSDT  | traded             | 83   | 339         | 125                | 91                 |
| SOLUSDT  | blocked_context    | 39   | 78          | 0                  | 0                  |
| SOLUSDT  | blocked_session    | 39   | 95          | 0                  | 0                  |
| SOLUSDT  | blocked_cost       | 19   | 51          | 0                  | 0                  |
| SOLUSDT  | invalid_stop       | 15   | 48          | 0                  | 0                  |
| SOLUSDT  | no_setup_signal    | 3    | 0           | 0                  | 0                  |
| SOLUSDT  | portfolio_throttle | 3    | 10          | 4                  | 0                  |
| SOLUSDT  | stop_too_tight     | 2    | 2           | 0                  | 0                  |
| XRPUSDT  | no_active_context  | 196  | 0           | 0                  | 0                  |
| XRPUSDT  | traded             | 83   | 321         | 117                | 97                 |
| XRPUSDT  | blocked_context    | 44   | 90          | 0                  | 0                  |
| XRPUSDT  | blocked_cost       | 28   | 82          | 0                  | 0                  |
| XRPUSDT  | blocked_session    | 28   | 73          | 0                  | 0                  |
| XRPUSDT  | invalid_stop       | 8    | 31          | 0                  | 0                  |
| XRPUSDT  | no_setup_signal    | 5    | 0           | 0                  | 0                  |
| XRPUSDT  | portfolio_throttle | 5    | 13          | 5                  | 0                  |
| XRPUSDT  | stop_too_tight     | 4    | 7           | 0                  | 0                  |

## Read

- `no_active_context`: 240m/30m/15m direction stack did not align that day.
- `no_setup_signal`: direction context existed, but the setup trigger did not fire.
- `blocked_context`: context filters such as no-shock/DMI/consolidation blocked signals.
- `blocked_cost`: stop geometry was tradable but too expensive in R after cost gates.
- `portfolio_throttle`: signal passed setup gates but was skipped by portfolio risk rules.
