# Crypto Deployment Validation Gate

Date: 2026-07-13.

Status: research candidate only. Not deployment-ready.

## Current Candidate

- Asset class: crypto futures.
- Exchange data: Binance primary; Bybit available but not separately required for same-price-action tests.
- Signal interval: `15m`.
- Structure context: `15m / 60m / 240m`.
- Concrete execution currently tested: `fixed_2r` + `hold_target_expiry`.
- Best current validation config: `conservative` at `0.15%` risk, max `4` open trades, max `1` per symbol, `0.35%` daily loss cap.
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
| Walk-forward | Partial pass | `conservative` strict passes 30d baseline 5/5, high 4/5, punitive 4/5; 45d punitive 3/3. Nightmare still fails at useful return levels. |
| Friction stress | Partial pass | Conservative risk fixes most `40bps` rolling failures; `60bps` remains too harsh for deployment sizing. |
| Extreme config stress | Partial pass | `prop_strict` survives recent 30d and 60d stress best, but first30d still fails punitive/nightmare. |
| Worst-window control | Partial | Rolling max DD stays < `2%` in tested strict windows, but this is still backtest-only. |
| Daily loss | Partial pass | `conservative` lowers rolling DD materially; live fill-based enforcement still missing. |
| Concentration | Unknown | Needs contribution report after walk-forward. |
| Frequency | Partial | Latest 30d strict: `2.94/day` basket, `1.47/symbol/week`; first30d weaker. |
| UI review | Ready / not reviewed | De-duplicated packet exists at `foundation_review_packet.csv`; manual review not done. |
| Paper run | Not done | No live/demo execution log. |
| Kill switch | Not done | Research harness only. |

## Blunt Verdict

Do not deploy yet.

The current strict crypto basket is good enough to continue. Conservative risk gives decent rolling results under baseline, high, and punitive friction. It is still not deployment-ready because nightmare execution fails and the failure-window review has not been done.

Changing risk did solve part of the gate problem. It did not solve signal quality under awful execution.

## Next Required Work

1. Review `foundation_review_packet.csv` in the UI:
   - punitive failed losers,
   - nightmare failed losers,
   - low-return baseline windows,
   - high-MAE winners,
   - target-too-short winners,
   - clean winners.
2. Use the failure diagnostics to test one small gate only if chart review agrees:
   - trend vs range,
   - compression/expanded state,
   - shock alignment,
   - setup family contribution,
   - symbol concentration.
3. Only after review confirms trade quality, run paper/demo at conservative risk for a week.
