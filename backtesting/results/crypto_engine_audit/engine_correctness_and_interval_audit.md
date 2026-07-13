# Crypto Engine Correctness And Interval Audit

Date: 2026-07-13.

## Trigger

Manual UI review showed repeated trades at the same interval, same price area,
and same outcome under different labels. That made the setup lab look like it
had more independent entries than it really had.

## Engine Correctness Finding

- Confirmed bug: exact executions were duplicated as separate rows when the
  same trade existed as both raw and structure-confirmed variants.
- Impact:
  - review packets showed repeated trades at the same point;
  - broad setup variants inflated candidate counts;
  - portfolio summaries could select arbitrary raw/confirmed ordering when
    broad variants were passed into portfolio simulation.
- Fix:
  - portfolio preparation now canonicalizes exact executions;
  - exact execution identity is `exchange + symbol + entry_ts + entry + stop +
    target + direction + target_model + management_model`;
  - when duplicates exist, structure-confirmed rows are preferred over raw rows;
  - setup/frequency review packets also de-duplicate exact executions.

Post-fix duplicate checks:

| Artifact | Rows | Exact duplicate executions |
| --- | ---: | ---: |
| `crypto_london_setup_lab_review_samples.csv` | `122` | `0` |
| `crypto_london_frequency_audit_review_samples.csv` | `123` | `0` |
| `london_setup_enriched_trades.csv` | `3,057` | `0` |

## Corrected London Setup Numbers

| Variant | Candidates | Accepted | Avg R | PF | Return | Max DD | Stop | Accepted/symbol/day |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `middle_local_bull_any_entry_confirm` | `267` | `73` | `+0.396R` | `2.51` | `+5.79%` | `1.33%` | `17.8%` | `0.143` |
| `middle_local_bull_rejection_or_break` | `61` | `34` | `+0.660R` | `5.67` | `+4.49%` | `0.69%` | `8.8%` | `0.066` |
| `middle_local_bull_candle_confirm` | `62` | `33` | `+0.633R` | `4.61` | `+4.17%` | `0.91%` | `12.1%` | `0.065` |
| `middle_local_bull` | `355` | `78` | `+0.278R` | `1.97` | `+4.34%` | `2.21%` | `19.2%` | `0.152` |
| `all_london_long` | `3,057` | `361` | `+0.017R` | `1.04` | `+1.23%` | `5.70%` | `29.9%` | `0.564` |

Verdict: broad London-long entries are not good enough. They are slightly
positive after de-duplication, but the return/DD and stop rate are bad.

## Interval/Window Backtest

Scope:

- Exchange: `binance`.
- Symbols: `ETH`, `SOL`, `XRP`, `DOGE`, `AAVE`, `WLD`, `1000PEPE`, `AVAX`,
  `LINK`, `NEAR`, `SUI`.
- Windows tested now:
  - `15m`, `60d`;
  - `15m`, `30d`;
  - `5m`, `30d`.
- `5m`, `60d` was not run in this pass because `5m`, `30d` already generated
  `340,362` scored rows and took too long for routine iteration.

Top corrected observations:

| Window | Best recurring module | Events | Symbols | Avg R | PF | Stop | Expiry |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `15m/60d` | late-US short, bearish/mixed context | `65-107` | `11` | `+0.42R` to `+0.53R` | `2.6-3.7` | `10-22%` | `49-80%` |
| `15m/30d` | London long, `1H+15m` bullish | `80-88` | `10` | `+0.51R` to `+0.61R` | `4.1-5.0` | `11-13%` | `48-65%` |
| `5m/30d` | late-US short CE retest | `60` | `11` | `+0.42R` to `+0.53R` | `2.7-4.0` | `12-20%` | `47-63%` |
| `5m/30d` | London long FVG edge/next-open | `75-211` | `11` | `+0.33R` to `+0.45R` | `2.8-4.2` | `7-14%` | `61-83%` |

Interpretation:

- `15m/30d` London long looks very strong, but the improvement versus `60d`
  means regime dependence is likely.
- `5m` creates much more data, but it also creates too many scored variants.
  It should not be the main strategy-search layer yet.
- The stronger architecture is:
  1. find direction/session context on `15m`;
  2. use `5m` only as a confirmation/entry refinement layer;
  3. emit one canonical trade per setup;
  4. run forensics on every accepted and rejected candidate.

## Backtest Method Recommendation

Do not continue with broad matrix optimization as the main loop.

Use a layered harness:

1. `direction_context`
   - session;
   - `4H` structure regime;
   - `1H+15m` EMA state;
   - shock/displacement state;
   - consolidation/range state.

2. `setup_event`
   - one event family at a time;
   - FVG retest first;
   - later add session range breakout and compression break.

3. `entry_trigger`
   - one canonical trigger per event;
   - no raw/confirmed duplicate rows;
   - candidate triggers: CE retest, edge retest, bullish/bearish candle
     confirmation, wick rejection, micro-range break.

4. `risk_model`
   - prior swing stop;
   - reject stops below minimum distance;
   - target models: `1.5R`, `2R`, nearest prior high/low, session range
     objective.

5. `trade_forensics`
   - store pre-entry candles;
   - post-entry path;
   - MFE/MAE;
   - bars to half-target, `1R`, target, stop;
   - failure layer;
   - reject reason for skipped candidates.

6. `validation`
   - `30d` discovery, `30d` holdout;
   - rolling windows;
   - per-symbol promotion only after holdout;
   - compare `15m` signal with optional `5m` entry refinement.

## Next Implementation

- Build a thin canonical strategy harness rather than another broad matrix.
- First target:
  `15m London long direction + 5m entry refinement`.
- Required output:
  one row per setup, with explicit direction context, setup event, entry
  trigger, stop/target model, reject/accept reason, and forensic path.
