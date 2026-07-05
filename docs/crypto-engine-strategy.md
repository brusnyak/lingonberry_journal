# Crypto Engine — Strategy Plan

## Architecture Principle

The engine is a collection of small, independent pieces — not a monolithic file.

Each piece has one job:
- **Regime classification** — trend_up, trend_down, ranging, volatile, low_vol per pair
- **Direction identification** — HTF state, regime filter, structure labels
- **Entry logic** — pattern detection, sweep/FVG/OB matching, funding-rate extremes
- **Stop loss** — ATR multiple, channel bound, structure level
- **Targets** — fixed RR, opposite liquidity, trailing mechanism
- **Position management** — partial closes, breakeven, trail activation
- **Correlation** — rolling pair correlation matrix, portfolio overlap detection
- **Monitoring** — trade logging, metric tracking, challenge rule enforcement

Strategies compose these pieces. A strategy file defines the arrangement, not the implementation. This is already the design (`structure_lib/` has separate modules for sweeps, FVGs, order blocks, structure labels, trade signals; `engine/` has separate modules for orders, costs, data loading, metrics, runner).

The engine should never need a rewrite — only new pieces added or old pieces replaced.

## Lesson Learned (2026-07-05)

The original plan treated crypto like forex with more pairs. Phase 1 and 2 delivered good hygiene (look-ahead detection, screener) but the Phase 3 signal-expansion plan would have been building on sand. Here's why:

1. **Crypto edge sources are different from forex.** Session-based patterns (ORB, OvernightDrift), structural SMC on 24h boundaries, and short-interval mean reversion work in forex. In crypto, edge comes from funding-rate extremes, medium-term momentum, liquidation cascades, and cross-exchange signals. We had zero crypto-native signals.
2. **No regime layer means results are meaningless across time.** The TrBosFade DOGE investigation proved this: PF=1.31 on 60d, PF=1.00 on 180d — not because the strategy changed but because the market regime changed. Testing without regime classification averages across incompatible environments.
3. **Calendar-based validation windows don't fit crypto.** Crypto regimes flip in days, not months. A 90-day window that spans a liquidity crisis + recovery + consolidation produces a blended result that predicts none of them.
4. **Adding strategies to a missing foundation compounds bad data.** Every new strategy tested without regime awareness adds noise, not signal.

The revised plan below fixes the foundation before adding more strategies.

## Problem

The forex engine works with a fixed universe of ~21 pairs. You know each pair's behavior. Strategy fires when the setup appears.

Crypto is different:
- New pairs launch weekly. Old pairs lose liquidity.
- Liquidity shifts between coins based on news, development, hype cycles.
- Crypto is heavily correlated (when BTC sneezes, everything catches a cold).
- The profitable pair today may be dead next month (LATUSDT, HYPEUSDT, etc.)

This means: **a fixed pair list is the wrong approach for crypto.**

## Solution

Two-tier pair selection:

### Tier 1 — Static Core (majors)
Pairs that will be liquid for the foreseeable future. Strategy-agnostic holdouts for initial validation.

| Pair | Why |
|------|-----|
| BTCUSDT | Largest by volume, market leader |
| ETHUSDT | Second largest, DeFi hub |
| SOLUSDT | High vol, retail favorite |
| XRPUSDT | Legal clarity, institutional |
| DOGEUSDT | Meme/retail proxy |
| BNBUSDT | Exchange coin, stable vol |

These are the "forex majors" of crypto. Every strategy gets tested against these first. If it can't show edge across ≥3 of them, it's not ready.

### Tier 2 — Dynamic Alt Tier (everything else)
A screening/ranking process, not a fixed list:

```
For each listed perpetual on Binance:
  1. Passes liquidity filter (volume, open interest, spread)
  2. Passes volatility filter (enough movement to matter)
  3. Strategy-specific: matches the regime/pattern the strategy exploits
  4. Correlation check: not too correlated with existing positions
```

This means the engine needs a **screener** that scans all available pairs, ranks them, and feeds the top N to each strategy. The screener runs periodically (daily? weekly?), not per-bar.

### Tier 3 — Event-driven
News monitors for:
- New pair listings (initial volatility)
- Major upgrades (increased interest)
- Regulatory changes
- Hype cycles

These are manual/alert-based, not automated for now.

## Priority

### Phase 1 — Foundation cleanup (both forex and crypto)
| Step | Status | Scope | Why |
|------|--------|-------|-----|
| 1.1 Fix ICT look-ahead bias | DONE 2026-07-04 | structure_lib rewrite + causal incremental strategy | Blocks an entire strategy family |
| 1.2 Look-ahead detector in base Strategy | DONE 2026-07-04 | engine/base.py | Catch future bugs before they contaminate results |
| 1.3 Default risk to 2% for development | DONE 2026-07-04 | batch.py, configs | 5% destroys equity too fast to measure signal quality |

### Phase 2 — DOGE investigation + tier-2 screener
| Step | Status | Scope | Why |
|------|--------|-------|-----|
| 2.1 Why does TrBosFade work on DOGE? | DONE 2026-07-04 | analysis | Edge is a 60-90 day regime artifact; PF drops to 1.00 on 180d. Not reliable. Decision: don't fix. |
| 2.2 Build tier-2 screener | DONE 2026-07-04 | backtesting/crypto/screener.py | Rank all 24 pairs by volatility, volume, and ranging behavior. Flexible scorer, plug into batch.py. |
| 2.3 Test TrBosFade on other high-vol pairs | CANCELLED | — | Strategy not reliable enough to test further. |

### Phase 3 — Engine infrastructure (revised 2026-07-05)
Before adding more strategies, build the pieces that make strategy discovery reliable.

| Step | Status | Scope | Why |
|------|--------|-------|-----|
| 3A Market regime module | **NEXT** | `backtesting/engine/regime.py` | Classify each pair as trend_up/trend_down/ranging/volatile/low_vol. Prerequisite for every valid test from here on. Uses ER, ATR%, BB width, funding rate level, BTC correlation. |
| 3B Funding rate as signal engine | pending | `backtesting/engine/funding_signals.py` | Promote funding rate from cost vector to signal vector. Rolling percentiles, extreme entry triggers. Genuinely crypto-native edge — no forex analog. |
| 3C Correlation matrix | pending | `backtesting/engine/correlation.py` | Rolling 60d correlation between active pairs. Without this, testing multiple strategies on multiple pairs doubles exposure unknowingly (crypto is >0.7 correlated across pairs). |
| 3D Fix validation framework | pending | `backtesting/crypto/validation.py` | Regime-stratified windows, not calendar-based. Default 30d window (not 60/90), 7d step (not 14). Each result shows PF by regime type. |

### Phase 4 — Signal building (revised, was Phase 3)
Only after infrastructure above is in place.

| Step | Status | Scope | Why |
|------|--------|-------|-----|
| 4A TSMOM re-run with regime filter | pending | batch | Fixed spaces, but only valid with regime-aware testing. Momentum should only fire in trending regimes — without the filter, ranging-period noise dilutes the signal. |
| 4B Funding rate standalone strategy | pending | new strategy | Extreme percentile mean-reversion. First crypto-native strategy built from the signal engine. |
| 4C Screener integration in batch.py | pending | batch.py | Replace hardcoded pair lists with dynamic ranking from tier-2 screener. Makes every subsequent run better. |
| 4D Data expansion (if viable) | pending | pipeline | On-chain metrics (exchange flows, whale tracking) or order book snapshots. Only if existing signals show edge that warrants deeper data. |

### Phase 5 — Portfolio and production (moved, was Phase 4)
Deferred until at least two reliable signal sources exist.

| Step | Scope | Why |
|------|-------|-----|
| 5.1 Combined risk budgeting | engine | Portfolio sizing across strategies |
| 5.2 Cross-exchange execution modeling | engine | Multi-exchange routing for live |
| 5.3 Prop firm challenge scaling | config | $20 → $25k/$100k scaling (forex only) |
| 5.4 Live crypto deployment | infra | Paper → small → scaled |

## Audit Cadence

Every time a result looks promising:

1. **Single-pair, single-window → suspicious**, do not trust
2. **PF > 2 on < 500 trades → small sample flag**
3. **Stratify by regime** → strategy must show edge in at least 2 regime types, not just overall. If PF=2.0 overall but 1.1 in trending and 0.4 in chop → strategy only works because it caught one trend move.
4. **Run across all 6 core pairs** → must show edge on ≥ 3
5. **Regime-stratified validation** → not calendar windows. Show PF by regime type. ≤ 20% of regime-stratified windows can be negative.
6. **Check look-ahead** → scan `init()` for data leakage and verify `_signal_source` declaration
7. **Compare gross vs net PF** → funding rate + fee impact
8. **Correlation check** → if two strategies show edge on the same pair, check they're not correlated >0.6. If they are, they're the same bet and the combined risk is wrong.
9. **Only then**: consider it a real result

The audit scripts exist (`run_audit_sweep.py`). Run them before trusting any result.

## Data

Current: 14 pairs × 2 exchanges (binance/bybit) + legacy. TFs 1m–1440m + funding rates.

| Category | Pairs |
|----------|-------|
| Core | BTC, ETH, SOL, XRP, DOGE, BNB |
| Alt | 1000PEPE, AAVE, AVAX, LINK, NEAR, SUI, WLD, HYPE |
| Legacy extras | ADA, ALGO, ARB, ATOM, ENA, INJ, MATIC, TIA, TRX, VET |

Fetch more when:
- A strategy shows cross-pair edge → extend date range for regime testing
- Need recent data → `python -m backtesting.data_pipeline.crypto --exchange binance --fresh`
- A specific pair comes up in tier-2 screening that isn't in our data yet

No urgent fetch needed. Current 14+ pairs are enough for signal discovery.
