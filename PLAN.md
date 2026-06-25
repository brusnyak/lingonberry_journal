# Forex V1 — Development Plan

Last updated: 2026-06-24

## Goal

Build a multi-timeframe, structure-based forex strategy (GBPUSD, EURUSD) that
eliminates losing trades through structural invalidation stops, scales out at
key levels, and goes long and short equally. No reliance on previous V2/V3
work or unvalidated Obsidian notes — every rule confirmed by our own tests.

## Core Philosophy

Losses happen from poor analysis, not market randomness. If structure tells
us where price is going, we exit when structure breaks against us — small
loss, immediate. No ATR stops, no fixed targets. Structure defines everything.

## Strategy Architecture

```
4H (240m) ──► HH/HL/LH/LL labels ──► macro bias (bullish/bearish)
1H (60m)   ──► HH/HL/LH/LL labels ──► intermediate bias (confluence)
15m        ──► HH/HL/LH/LL labels ──► sweep + MSS detection + structural SL
1m (or 5m) ──► HH/HL/LH/LL labels ──► FVG detection + entry + trailing SL
```

Structure (HH/HL = bullish, LH/LL = bearish) everywhere. Labels are consistent
across all timeframes using the same algorithm with different swing lengths.

### Entry Sequence (Mandatory — all 6 steps must pass)

```
1. 4H structure bullish/bearish → bias set
2. 1H structure same direction → confluence (TEST: both vs either vs 4H only)
3. 15m sweep: price wicks beyond a swing point (LL for longs, HH for shorts)
   AND body closes back inside → sweep confirmed
4. 15m MSS: after the sweep, price breaks a swing point in the bias direction
   with displacement (aggressive body close, often with FVG)
5. 1m/5m FVG forms in the bias direction during MSS displacement
6. 1m/5m price retraces into the FVG → entry on limit at FVG CE (50% level)
```

Sweep detection rules (from ICT methodology):
- **Wick-rejection**: wick extends beyond the swing, body closes inside
- **Close-reclaim**: body briefly closes beyond, next bar reverses inside
- **No sweep = no setup** — price drifting to a level without stop-hunt is
  not an ICT reversal setup
- **MSS required** (not just CHoCH) — CHoCH without sweep context is a warning,
  not a trade signal
- All signals use `close[1]` (confirmed previous bar), never `close[0]`

### Stop Loss

Structural — placed beyond the swept level with ATR buffer:

- **Long**: stop below the swept LL + 0.5× ATR(14) buffer
- **Short**: stop above the swept HH + 0.5× ATR(14) buffer

If price returns to re-sweep the level, the stop holds. If structure breaks
against us (new LL below for longs, new HH above for shorts), we exit.

### Exit System (Hybrid — Partial Scale-Out)

| Level | Allocation | Trigger | Action |
|-------|-----------|---------|--------|
| TP1 | **50%** | Nearest target | Close, move stop to BE |
| TP2 | **30%** | Further target | Close |
| Runner | **20%** | Structure trailing | Trail on 1m HL/LH until stopped |

Also testing: 50/50, 30/30/40, 100 (single exit).

**Targets evaluated** (trade hits the nearest one first):
1. Previous daily high/low
2. Previous 1H session high/low
3. 50% FVG level (consequent encroachment)
4. Fib extension: 1.0× / 1.272× / 1.618× of the MSS swing range

**Trailing method for runner (20%)**: 1m structure labels. New 1m HL = raise
trailing stop for longs. New 1m LH = lower trailing stop for shorts. Exit
when 1m CHoCH fires — structure has shifted, we're done.

### Fibonacci for TP

```
Long setup (example):
  15m MSS sweep low = L, MSS swing high = H
  Range = H - L
  TP1: H + 1.0 × Range
  TP2: H + 1.272 × Range
  TP3: H + 1.618 × Range
```

This adapts to current volatility automatically. In high-volatility periods
the swing range is wider → TPs are further apart. In low-volatility periods
TPs are tighter.

## Cost Model

- **Spread**: random uniform 1-3 pips on entry + 0.5-1.5 pips on exit
- **SL slippage**: random 0-1 pip extra on stop hits
- **Commission**: $0.75 per side ($1.50 round-trip)
- **Minimum stop rule**: stop distance must be ≥ 5× average spread

This matches the industry-standard cost model. Previously in strategy_v2.py.

## Test Matrix — First Sweep

| Variable | Values | Purpose |
|----------|--------|---------|
| Pairs | GBPUSD, EURUSD | Available 1m data |
| Bias TF | 4H only, 1H only, 4H+1H same | Test all |
| Entry TF | 1m, 5m | Compare noise vs precision |
| Sweep | Required, Not required | Test filter impact |
| Partials | 50/30/20, 50/50, 30/30/40, 100 (single) | Test all |
| Targets | Daily, Session, 50% FVG, Fib exts, ALL | Test individually |
| Data window | 30 days (latest available) | Consistent comparison |

**Estimated**: 2 × 3 × 2 × 2 × 4 × 5 = **480 configurations**

## Data Sources

| Symbol | 1m | 5m | 15m | 1H | 4H | Daily |
|--------|----|----|-----|----|----|-------|
| GBPUSD | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| EURUSD | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

All files in `data/market_data/` as parquet with columns: ts, open, high,
low, close, volume. 1m truncated to ~100k rows (~3 months) by yfinance.

## Obsidian Vault

The existing `/Trading/` directory in Obsidian contains previous V2 work
that is known to have issues (overfitting, missing spread model, flawed
rolling analysis). This data is **not relied upon** for Forex V1 decisions.

Action: archive old content, rebuild with only validated results from
our own sweep runs.

## Work Plan

### Phase A: Build — Today
- [ ] Build `backtesting/forex_v1.py` (clean, no inheritance)
- [ ] Multi-TF data loading and alignment
- [ ] Structure labels on all TFs (HH/HL/LH/LL)
- [ ] Sweep + MSS detection on 15m
- [ ] Entry on 1m/5m FVG retest
- [ ] Structural SL with ATR buffer
- [ ] Hybrid exit system (partials + trailing)
- [ ] Cost model (spread + slippage + commission)
- [ ] Run first sweep (30 days, GBPUSD)

### Phase B: Validate — This Week
- [ ] Review sweep results, fix bugs
- [ ] Run monthly rolling windows
- [ ] Test on EURUSD
- [ ] Archive deprecated Obsidian content
- [ ] Document validated configs

### Phase C: Deploy — Next Week
- [ ] Paper bot with best config
- [ ] Oracle server deployment
- [ ] Obsidian trade journal from validated data
- [ ] LLM-assisted post-trade review pipeline

## Non-Goals (Removed from Scope)

- VWAP/EMA bias (replaced with pure structure)
- ATR stops (replaced with structural stops)
- Session filters (did not improve results)
- Telegram scraper (visual content not reliably extractable)
- Fixed R:R targets (replaced with adaptive hybrid exit)
- Correlation or pair-specific analysis (losses = analysis issue, not pair issue)
