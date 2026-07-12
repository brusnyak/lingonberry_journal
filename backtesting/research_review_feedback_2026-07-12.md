# Manual Review Feedback Checkpoint

Date: 2026-07-12.

## Scope

Reviewed packet:

- strategy: `CryptoPortfolioCandidateReview`;
- rows reviewed so far: `17`;
- symbols: `LINKUSDT`, `XRPUSDT`;
- source: `webapp/review_labels.json`;
- packet: `backtesting/results/review_samples/crypto_portfolio_candidate_review_samples.csv`.

## Label Counts

| Label | Count |
|---|---:|
| good | 9 |
| bad | 4 |
| skip | 1 |
| note-only | 3 |

By review bucket:

| Bucket | Bad | Good | Note-only | Skip |
|---|---:|---:|---:|---:|
| accepted_winner | 0 | 4 | 0 | 0 |
| accepted_loser | 1 | 1 | 1 | 0 |
| rejected_no_confirmation | 3 | 0 | 0 | 0 |
| rejected_portfolio_throttle | 0 | 2 | 0 | 1 |
| rejected_stale_retest | 0 | 2 | 2 | 0 |

## What The Review Proves

The accepted-winner bucket is visually credible so far.

The no-confirmation reject bucket also looks mostly correct:

- `3/3` reviewed no-confirmation rejects were marked bad.
- Notes repeatedly mention missing confirmation, trend/context problems, or
  wrong-side entries after large moves.

The stale-retest filter is too blunt:

- reviewed stale retests include trades marked good or note-only;
- some late retests still visually work if direction and structure remain valid.

Portfolio throttle may be too blunt:

- `2` reviewed portfolio-throttle rejects were marked good;
- one was skipped;
- this suggests the throttle is reducing risk but may reject valid trades during
  good synchronized conditions.

Accepted losers are mixed:

- one accepted loser is explicitly bad: against local trend / entry without
  confirmation;
- another accepted loser is marked good but points to missing management logic
  after price travels halfway toward target.

## Screenshot Finding

The screenshot shows a missing state class:

> large price movement / displacement changes the trade state, but the engine
> currently still treats the setup as a normal FVG retest or normal fixed-target
> trade.

This creates two opposite problems:

1. after a strong move against the intended short, the engine may still fade the
   move instead of following/standing aside;
2. after a strong move in favor, fixed `1.5R` exits too mechanically and misses
   continuation, while unmanaged reversals can give back too much.

## Next Implementation Priority

Do not jump to ML yet.

Implement a causal displacement/follow-through layer first:

1. `shock_move` detector:
   - candle range/body in ATR units;
   - close location in top/bottom fraction;
   - wick rejection;
   - direction of impulse.
2. Direction veto:
   - block shorts immediately after bullish shock/follow-through;
   - block longs immediately after bearish shock/follow-through;
   - require fresh structure confirmation after opposing shock.
3. Continuation mode:
   - if shock is in trade direction, keep setup valid but tag it as
     `impulse_continuation`;
   - compare fixed target versus runner management.
4. Management variants:
   - move stop to BE after `0.5R` or after price travels `50%` to TP;
   - partial at `1R`, BE remainder;
   - runner after fixed `1.5R` using structure/ATR trailing stop.
5. Replace the blunt stale-retest filter with:
   - stale and no confirmation = reject;
   - stale but valid continuation structure = allowed;
   - stale after opposing shock = reject.

## What To Review Next

Continue reviewing the same packet, but focus on:

- stale retests marked good: why are they still valid?
- accepted losers: was the entry wrong or only management wrong?
- portfolio-throttle rejects marked good: are they redundant clustered trades or
  valid synchronized opportunities?

## Current Verdict

The current project direction is correct:

- keep layered causal analysis;
- improve direction and management with price-action state;
- use ML later only as a meta-label/ranker after these states are explicit.
