# Crypto Engine — Strategy Plan

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
| Step | Scope | Why |
|------|-------|-----|
| 1.1 Fix ICT look-ahead bias | structure_lib rewrite | Blocks an entire strategy family |
| 1.2 Look-ahead detector in base Strategy | engine/base.py | Catch future bugs before they contaminate results |
| 1.3 Default risk to 2% for development | batch.py, configs | 5% destroys equity too fast to measure signal quality |

### Phase 2 — DOGE investigation + tier-2 screener
| Step | Scope | Why |
|------|-------|-----|
| 2.1 Why does TrBosFade work on DOGE? | analysis | Only real signal found so far |
| 2.2 Build tier-2 screener | new module | Convert fixed pair list to dynamic filter |
| 2.3 Test TrBosFade on other high-vol pairs | batch sweep | 1000PEPE, WLD, HYPE — same pattern? |

### Phase 3 — Signal expansion
| Step | Scope | Why |
|------|-------|-----|
| 3.1 OHLC pattern scan across all pairs | pipeline.py | 24 patterns × 14 pairs × 5 TFs |
| 3.2 Re-run CryptoTsmom sweep (spaces now fixed) | batch | TSMOM is most academically supported |
| 3.3 Test forex ports (TrFvg, TrAccumulation) on crypto | batch | These already work on forex |
| 3.4 Funding-rate-based signals | new strategy | Crypto-native signal (no forex analog) |

### Phase 4 — Portfolio and production
| Step | Scope | Why |
|------|-------|-----|
| 4.1 Pair correlation matrix | analysis module | Avoid doubling exposure |
| 4.2 Combined risk budgeting | engine | Portfolio sizing across strategies |
| 4.3 Prop firm challenge scaling | config | $20 → $25k/$100k scaling |
| 4.4 Walk-forward as standard | validation.py | Already built, make mandatory |

## Audit Cadence

Every time a result looks promising:

1. Single-pair, single-window → **suspicious**, do not trust
2. PF > 2 on < 500 trades → **small sample flag**
3. Run across all 6 core pairs → must show edge on ≥ 3
4. Run across 15 non-overlapping windows → ≤ 20% can be negative
5. Check look-ahead → scan `init()` for data leakage
6. Compare gross vs net PF → fee impact
7. **Only then**: consider it a real result

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
