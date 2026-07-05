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

### Phase 3 — Engine infrastructure (DONE 2026-07-05 – 2026-07-06)

| Step | Scope | Tests | Note |
|------|-------|-------|------|
| 3A Market regime module | `backtesting/engine/regime.py` — `MarketRegime` class | 21 | ER + ATR% percentile → trend_up, trend_down, ranging, volatile, low_vol |
| 3B Funding rate signal engine | `backtesting/engine/funding_signals.py` — `FundingSignalEngine` | 17 | Rolling percentile extremes → entry triggers |
| 3C Correlation matrix | `backtesting/engine/correlation.py` — `CorrelationMatrix` + `portfolio_overlap` | 14 | Rolling 60d correlation, exposure overlap detection |
| 3D Validation framework | `backtesting/engine/validation.py` + `backtesting/crypto/validation.py` | 20 | Regime-stratified windows, calendar-based rolling validation |

All four modules exist, tested, and committed. Each was built independently — no module depends on another. This was the right call: infrastructure before signal discovery.

### Phase 4 — Strategy building (DONE 2026-07-06)

| Step | Scope | Tests | Note |
|------|-------|-------|------|
| 4A RegimeGate wrapper | `backtesting/engine/regime_gate.py` | 15 | Generic wrapper filters any strategy's entries by regime. Better than the original plan (TSMOM-only flag) — reusable across all strategies. |
| 4B CryptoFundingMeanRev | `backtesting/crypto/strategies/funding_mean_rev.py` | 14 | Funding-rate mean reversion. First crypto-native strategy built from signal engine. |
| 4C Screener integration | `backtesting/crypto/batch.py` — `--screener-top-n` flag | (in batch.py) | Tier-2 pair ranking integrated into CLI, filters pair list before sweep. |
| 4D Data expansion | deferred | — | On-chain / orderbook data only if a confirmed signal warrants deeper investigation. No confirmed signal exists yet. |

### Phase 5 — Integration layer (DONE 2026-07-06)

Wires Phase 3-4 components into the sweep pipeline so they actually run together.

| Step | Scope | Tests | Note |
|------|-------|-------|------|
| 5A RegimeGate in batch.py | `--regime-filter` + `--regime-tf` CLI args | (in batch.py) | Any strategy auto-wrapped with RegimeGate via CLI flag |
| 5B Regime data exposed | `data["regime"]` in `_run_one_crypto` + `_validate_one` | (in batch.py) | All strategies can read per-bar regime labels |
| 5C TSMOM baseline sweep | 6 core pairs, 30d, regime-filtered | — | Zero crashes. BTC/ETH/BNB correctly blocked (not trending). |
| 5D FundingMeanRev baseline sweep | 6 core pairs, 30d, regime-filtered | — | Same pattern. But 30d windows produce <10 trades per config — can't evaluate. |

**Key result from Phase 5 sweeps**: infrastructure works end-to-end (zero crashes across 144 configs). But 30-day windows with regime filters produce statistically meaningless sample sizes. The bottleneck is now data volume, not code correctness.

### Phase 6 — Signal discovery (NEXT)

Goal: find out whether any of our strategies produce real edge. If none do, we learn something. If one does, we expand it. **Do not tune engine components to improve results — that's overfitting the engine, not discovering signal.**

**Rule for this phase**: the engine is frozen. Regime thresholds, signal thresholds, validation parameters — none change during signal discovery. If a strategy fails, the strategy changes, not the engine.

| Step | Task | Method | Success criteria |
|------|------|--------|-----------------|
| 6A | **Baseline: TSMOM raw** | Sweep 6 core pairs, 90-180d, no regime filter, `{entry_len: [20,40], exit_len: [10], stop_atr_mult: [2,3], stop_mode: [atr, channel]}` | ≥500 total trades (all configs combined), PF visible above noise for ≥1 param combo on ≥3 pairs |
| 6B | **Baseline: FundingMeanRev raw** | Sweep 6 core pairs, 90-180d, no regime filter, `{stop_atr_mult: [2,3], stop_mode: [atr, channel], entry_threshold: [0.8]}` | Same. Funding extremes are crypto-native — edge should exist irrespective of regime |
| 6C | **Baseline: TrIct raw** | Sweep 6 core pairs, 90-180d, no regime filter | Same. Current TrIct is experimental (51 trades / 30d DOGE PF=2.28) — expand to core pairs |
| 6D | **Regime impact analysis** | Re-run best configs from 6A-6C with `--regime-filter` variants (trend_only, range_only, no_volatile) | Compare with/without filter. A useful regime filter improves PF without halving trade count |
| 6E | **Regime-stratified validation** | Run top configs through `--validate` with regime-stratified windows | ≤20% of windows can be negative per audit checklist |
| 6F | **Correlation check** | Top configs across strategies: compute pair correlation + strategy correlation | Combined risk: if two strategies trade same pair in same direction, check they're not correlated >0.6 |
| 6G | **Decision gate** | Review all results. If ≥2 strategies show edge on ≥3 core pairs → Phase 7 (portfolio). If none → stop adding strategies, investigate new signal sources | Stop condition: if after all 6 core pairs × 180 days no strategy shows edge, the problem is signal selection, not engine quality |

### Phase 7 — Portfolio (deferred)
Nothing here until Phase 6 produces confirmed signals. Same items as before:
- Combined risk budgeting
- Cross-exchange execution modeling
- Live crypto deployment (paper → small → scaled)

If Phase 6 produces zero confirmed edges, Phase 7 is cancelled for crypto and the engine serves as a research tool only.

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
