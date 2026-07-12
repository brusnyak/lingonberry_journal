# Crypto FVG Retest UI Review

## Portfolio Candidate Packet

New focused sample file:

- `backtesting/results/review_samples/crypto_portfolio_candidate_review_samples.csv`

Use the `/review` page, select one of the crypto symbols below, and click
`LOAD PORTFOLIO CANDIDATE REVIEW`.

This packet is the current best bucket plus rejects:

- accepted winners;
- accepted losers;
- rejected stale retests;
- rejected no-confirmation setups;
- rejected portfolio-throttle setups.

Current best bucket:

- entry: `structure_confirmed_fvg_top_retest`;
- target: `fixed_1_5r`;
- management: `partial_1r_be`.

Review goal:

1. Check if accepted winners are genuinely valid before outcome.
2. Check if accepted losers are acceptable variance or structural mistakes.
3. Check if stale retest rejects should stay rejected.
4. Check if no-confirmation rejects are truly missing structure.
5. Check if portfolio-throttle rejects are redundant clustered trades or trades
   worth overriding.

Suggested labels:

- `good`: accepted trade or rejection decision is structurally correct.
- `bad`: accepted trade should have been rejected, or rejected trade should have
  been accepted.
- `skip`: ambiguous/hindsight-contaminated.

Useful note tags:

- `[accept_valid]`
- `[accept_bad_direction]`
- `[accept_bad_entry]`
- `[reject_correct]`
- `[reject_wrong]`
- `[stale_valid]`
- `[no_confirmation_valid]`
- `[portfolio_override]`

## Older Retest Packet

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
