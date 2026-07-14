# Context Change Filter Audit

Setup: `context_change`

Basket: `BTC, ETH, SOL, XRP, DOGE, BNB`

Baseline rules:

- strict 240m/30m/15m direction context
- 15m entry
- structural stop and fixed `2R` target
- sessions: `asia,london,ny`
- shock filter: `no_shock`
- cost gates: base <= `0.12R`, stress <= `0.40R`
- portfolio risk: `0.2%` risk/trade, max `3` open, max `1` open per symbol, daily loss limit `0.5%`

## Candidate Ranking Read

Feature report:

`context_change_rr2_basecost0p12r_stresscost0p4r_sessions-asia-london-ny_shock-no_shock_liquid-no-avax-180d-ranked_feature_report.md`

Strong signals from the 180d candidate table:

- `asia` session is materially stronger than London/NY.
- `dmi=aligned` is better than opposed, but not enough by itself.
- `trend_strength=trend` is weak; `strong_trend`, `weak_or_range`, and range states were better.
- `DOGE` is the weakest remaining symbol, but not toxic like AVAX.

## Explicit Filter Tests

| Variant | Days | Candidates | Accepted | PF | Return | Max DD | Return/DD | Win | Stop |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| base | 30 | 29 | 23 | 0.745 | -0.94% | 2.29% | -0.41 | 34.8% | 65.2% |
| base | 60 | 103 | 70 | 1.566 | +4.62% | 3.36% | 1.37 | 48.6% | 47.1% |
| base | 90 | 151 | 112 | 1.561 | +7.14% | 3.36% | 2.13 | 49.1% | 45.5% |
| base | 180 | 303 | 228 | 1.437 | +11.77% | 4.11% | 2.86 | 47.4% | 47.8% |
| dmi-aligned | 30 | 24 | 21 | 0.602 | -1.37% | 2.01% | -0.68 | 28.6% | 66.7% |
| dmi-aligned | 60 | 79 | 63 | 1.828 | +5.48% | 2.82% | 1.95 | 50.8% | 42.9% |
| dmi-aligned | 90 | 115 | 95 | 1.837 | +8.11% | 2.82% | 2.88 | 51.6% | 41.1% |
| dmi-aligned | 180 | 221 | 186 | 1.480 | +10.29% | 3.81% | 2.70 | 47.3% | 46.8% |
| asia-only | 30 | 13 | 10 | 0.964 | -0.05% | 0.72% | -0.07 | 40.0% | 60.0% |
| asia-only | 60 | 48 | 33 | 2.207 | +3.87% | 1.30% | 2.98 | 54.5% | 39.4% |
| asia-only | 90 | 65 | 49 | 3.268 | +8.25% | 1.30% | 6.34 | 65.3% | 30.6% |
| asia-only | 180 | 133 | 100 | 2.291 | +11.92% | 1.30% | 9.16 | 58.0% | 38.0% |
| no-trend | 30 | 20 | 17 | 0.830 | -0.43% | 1.39% | -0.31 | 35.3% | 58.8% |
| no-trend | 60 | 71 | 50 | 2.055 | +5.24% | 1.95% | 2.69 | 54.0% | 40.0% |
| no-trend | 90 | 100 | 78 | 1.819 | +6.74% | 1.95% | 3.46 | 52.6% | 42.3% |
| no-trend | 180 | 193 | 155 | 1.669 | +11.28% | 2.57% | 4.39 | 50.3% | 43.9% |

## Decision

- `asia-only` is the best risk filter tested so far.
- It improves drawdown sharply: 180d max DD from `4.11%` to `1.30%`.
- It does not fully solve the recent 30d weakness: 30d PF is still below `1`.
- `dmi-aligned` is not worth promoting by itself.
- `no-trend` is useful but weaker than `asia-only`.

## Next

1. Do not deploy yet.
2. Treat `asia-only` as the new candidate baseline for research.
3. Step back into foundation before adding setups:
   - validate session regime logic;
   - inspect why London/NY degrade;
   - inspect whether 30d weakness is direction failure, stop/target mismatch, or hostile regime.
4. Next concrete test should be a foundation audit of direction correctness by session and recent regime, not another entry pattern.
