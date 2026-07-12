# Crypto FVG Retest UI Review

Sample file:

- `backtesting/results/review_samples/crypto_fvg_retest_review_samples.csv`

Use the `/review` page and click `LOAD CRYPTO RETEST EVENTS` after selecting a
symbol.

Review symbols:

- `LINKUSDT`
- `ETHUSDT`
- `XRPUSDT`
- `SUIUSDT`
- `DOGEUSDT`
- `AVAXUSDT`
- `AAVEUSDT`
- `NEARUSDT`
- `WLDUSDT`
- `1000PEPEUSDT`
- `SOLUSDT`

Each symbol has 6 trades: 3 winners and 3 losers from the current best
hypothesis:

- bearish FVG;
- short;
- HTF bull;
- late-US session;
- high volatility;
- FVG top retest entry;
- prior-swing stop;
- partial at `+1R` plus breakeven remainder.

Judge each trade on these layers:

1. Direction: should this be short at all from the visible structure?
2. Entry: is the FVG top retest real, or is it a forced/late entry?
3. Stop: is the prior-swing stop structurally valid, too wide, or too tight?
4. Management: after `+1R`, would partial plus BE make sense visually?
5. Target: is fixed `2R` reasonable, or is there an obvious nearer/farther
   liquidity target?
6. Skip filter: should this symbol/session/context be skipped entirely?

Suggested labels:

- `good`: direction, entry, and stop are visually valid.
- `bad`: one of direction/entry/stop is structurally wrong.
- `skip`: setup is too ambiguous or only works by hindsight.

Useful note tags:

- `[direction_bad]`
- `[entry_late]`
- `[entry_good]`
- `[stop_too_wide]`
- `[stop_too_tight]`
- `[target_bad]`
- `[manage_be]`
- `[skip_symbol]`
