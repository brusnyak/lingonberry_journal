# Crypto Deployment Validation Gate

Date: 2026-07-13.

Status: research candidate only. Not deployment-ready.

## Current Candidate

- Asset class: crypto futures.
- Exchange data: Binance primary; Bybit available but not separately required for same-price-action tests.
- Signal interval: `15m`.
- Structure context: `15m / 60m / 240m`.
- Concrete execution currently tested: `fixed_2r` + `hold_target_expiry`.
- Best current validation config: `base` at `0.20%` risk, max `6` open trades, max `1` per symbol, `0.50%` daily loss cap.
- Best current return config: `prop_strict` at `0.25%` risk, max `4` open, max `1` per symbol, `0.40%` daily loss cap. It is not cleaner for deployment because rolling daily/max DD gates fail more often.

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
| Walk-forward | Partial fail | Rolling validation exists. `base` strict passes 30d baseline 5/5 and high 4/5, but punitive only 2/5 and nightmare 0/5. |
| Friction stress | Partial pass | 60d strict survives `40bps`, but first30d and rolling punitive windows are unstable. |
| Extreme config stress | Partial pass | `prop_strict` survives recent 30d and 60d stress best, but first30d still fails punitive/nightmare. |
| Worst-window control | Partial | Rolling max DD stays < `2%` in tested strict windows, but this is still backtest-only. |
| Daily loss | Partial fail | `prop_strict` fails more rolling gates because daily/max DD is higher; live fill-based enforcement still missing. |
| Concentration | Unknown | Needs contribution report after walk-forward. |
| Frequency | Partial | Latest 30d strict: `2.94/day` basket, `1.47/symbol/week`; first30d weaker. |
| UI review | Not done | No review packet loaded yet. |
| Paper run | Not done | No live/demo execution log. |
| Kill switch | Not done | Research harness only. |

## Blunt Verdict

Do not deploy yet.

The current strict crypto basket is good enough to continue. It is not stable enough yet because rolling punitive and nightmare friction fail too often. The right next work is chart review of failure windows and regime conditioning, not adding another indicator gate.

Changing risk and concurrency does not solve the weak-window problem. It only changes how much capital we lose or gain while the same signal regime works or fails.

## Next Required Work

1. Build review packet:
   - best winners,
   - worst losers,
   - target-too-short winners,
   - high-MAE winners,
   - first30d failures,
   - failing punitive/nightmare rolling windows.
2. Add regime/failure-window diagnosis:
   - trend vs range,
   - compression/expanded state,
   - shock alignment,
   - setup family contribution,
   - symbol concentration.
3. Only after rolling punitive survival improves, run paper/demo for a week.
