# Crypto Deployment Validation Gate

Date: 2026-07-13.

Status: research candidate only. Not deployment-ready.

## Current Candidate

- Asset class: crypto futures.
- Exchange data: Binance primary; Bybit available but not separately required for same-price-action tests.
- Signal interval: `15m`.
- Structure context: `15m / 60m / 240m`.
- Concrete execution currently tested: `fixed_2r` + `hold_target_expiry`.
- Risk model in research report: `0.20%` per trade, max `6` open trades, max `1` open per symbol, `0.50%` daily loss cap.
- Best current stress-test candidate: `prop_strict` at `0.25%` risk, max `4` open, max `1` per symbol, `0.40%` daily loss cap.

## Deployment-Ready Definition

A strategy is deployment-ready only after it passes all gates below. Good aggregate backtest stats are not enough.

| Gate | Required Threshold |
| --- | --- |
| Data freshness | OHLCV, structure cache, market specs, funding all < `2` days stale. |
| Causal features | Every MTF feature joined by `known_after_ts <= decision_ts`; no pivot timestamp joins. |
| Physical de-duplication | One execution per symbol/direction/entry/stop; target and management variants cannot inflate frequency. |
| Walk-forward | At least `3` rolling test windows; no single test window negative after realistic costs. |
| Friction stress | Survives `high_22bps` with PF >= `1.5`; survives `punitive_40bps` with PF >= `1.2` and positive return. |
| Worst-window control | Any 30d window max DD <= `2%` at deployment risk. |
| Daily loss | Worst daily loss <= `0.75%` at deployment risk. |
| Per-symbol concentration | No one symbol contributes > `25%` of total R. |
| Setup concentration | No one setup family contributes > `60%` of total R unless explicitly deployed as a single-module strategy. |
| Frequency | Basket >= `1.5` strict physical events/day over the latest 60d; per-symbol frequency reported, not required to be high individually. |
| UI review | Manual chart review of at least `20` winners, `20` losers, all target-too-short candidates, and all worst 10 MAE trades. |
| Paper run | Minimum `1` week live-paper or demo execution with logged fills, slippage, rejected orders, and missed signals. |
| Kill switch | Live process must enforce max daily loss, max open exposure, stale-data halt, and API error halt. |

## Current Status Against Gate

| Gate | Status | Evidence |
| --- | --- | --- |
| Data freshness | Pass for crypto | Binance/Bybit OHLCV and structure are < `1` day stale. |
| Causal features | Pass in tests | Structure lookup tests cover `known_after_ts`. |
| Physical de-duplication | Pass | `foundation_trade_forensics` collapses physical entries. |
| Walk-forward | Fail / incomplete | First 30d is weak; recent 30d is strong. Need rolling validation. |
| Friction stress | Partial pass | 60d strict survives `40bps`, but first30d strict fails `40bps`. |
| Extreme config stress | Partial pass | `prop_strict` survives recent 30d and 60d stress best, but first30d still fails punitive/nightmare. |
| Worst-window control | Unknown | Need rolling windows beyond first/recent split. |
| Daily loss | Partial | Research daily loss cap simulated, but not live fill based. |
| Concentration | Unknown | Needs contribution report after walk-forward. |
| Frequency | Partial | Latest 30d strict: `2.94/day` basket, `1.47/symbol/week`; first30d weaker. |
| UI review | Not done | No review packet loaded yet. |
| Paper run | Not done | No live/demo execution log. |
| Kill switch | Not done | Research harness only. |

## Blunt Verdict

Do not deploy yet.

The current strict crypto basket is good enough to continue. It is not stable enough yet because early 30d performance is weak and fails punitive friction. The right next work is rolling walk-forward and regime conditioning, not adding another indicator gate.

Changing risk and concurrency does not solve the weak-window problem. It only changes how much capital we lose or gain while the same signal regime works or fails.

## Next Required Work

1. Build rolling validation over the de-duplicated strict candidate set:
   - windows: `14d`, `30d`, `45d`;
   - step: `7d`;
   - outputs: return, DD, PF, win rate, friction survival, frequency, symbol contribution.
2. Build review packet:
   - best winners,
   - worst losers,
   - target-too-short winners,
   - high-MAE winners,
   - first30d failures.
3. Only after walk-forward passes, run paper/demo for a week.
