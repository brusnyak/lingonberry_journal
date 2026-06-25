# XAUUSD NY Short Candidate

Status: audited research candidate, not live-approved.

## Rule

- Asset: XAUUSD
- Timeframe: 5m
- Session: NY, 13:00-16:00 UTC
- Direction: short only
- Setup: EMA20/EMA100 trend-pullback reclaim
- Entry: close crosses back below EMA20 while price is below EMA100 and EMA20 < EMA100
- Stop: highest high of prior 12 bars + XAU buffer
- Target: 2R
- Max hold: 24 bars / 2 hours
- Required filters:
  - EMA gap >= 10 XAU pips
  - vol_ratio between 1.0 and 2.0
- Costs included:
  - entry spread: 2 pips
  - TP exit spread: 1 pip
  - SL exit spread + slippage: 1.5 pips
  - commission: 1.50 USD per lot round trip

## Performance

The first lab pass understated signal count because an earlier unfiltered same-day
signal could block a later filtered valid signal. The dedicated audit runner now
rebuilds signals from raw XAUUSD 5m data and treats the later filtered valid
signal as tradeable.

Risk 0.30% per trade, dedicated audit runner:

| Window | Trades | Return | Max DD | Max Daily Loss | Win Rate | Avg R |
|---|---:|---:|---:|---:|---:|---:|
| 490d | 94 | 9.33% | 1.80% | 0.31% | 52.13% | 0.331 |
| 365d | 66 | 4.77% | 1.88% | 0.31% | 51.52% | 0.241 |
| 180d | 34 | 4.19% | 0.60% | 0.30% | 61.76% | 0.411 |
| 90d | 21 | 1.91% | 0.61% | 0.30% | 61.90% | 0.303 |

Risk 0.33% per trade, dedicated audit runner:

| Window | Trades | Return | Max DD | Max Daily Loss | Win Rate | Avg R |
|---|---:|---:|---:|---:|---:|---:|
| 490d | 94 | 10.26% | 1.96% | 0.35% | 52.13% | 0.331 |
| 365d | 66 | 5.24% | 2.06% | 0.35% | 51.52% | 0.241 |
| 180d | 34 | 4.61% | 0.66% | 0.33% | 61.76% | 0.411 |
| 90d | 21 | 2.10% | 0.67% | 0.33% | 61.90% | 0.303 |

## Mentor Verdict

- This is currently the best candidate matching the user's preferred shape on the full data: 9-10% return with sub-2% DD over 490d.
- The cleaner setting is 0.30% risk. It keeps 490d and standalone 365d DD below 2%.
- The higher setting is 0.33% risk. It keeps full 490d DD below 2%, but standalone 365d DD rises to 2.06%, so it is less clean.
- This does not pass a fast prop challenge by itself in the recent 180d window; it is slow but controlled.
- Not live-approved yet. Next gate: exact chart audit on the 94 trades, then add news/session exclusions and broker-specific spread checks.
