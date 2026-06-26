# TrFvg Crypto Strategy — Development Plan

Last updated: 2026-06-26

## Goal
Build a mechanical FVG-based mean reversion strategy for crypto USDT-M futures (Binance + Bybit) that produces positive expectancy on a $70 personal account at 50x leverage.

## Reality Check
This is not a prop firm challenge strategy. It's a $70 account that either compounds or dies. No daily DD rules except self-imposed ($3.50/day max loss). Target: 5-15% monthly return with <10% max DD.

## Key Finding — Direction Asymmetry

TrFvg is **not symmetric**. The 30-day sweep across 9 pairs × 72 param combos shows:

| Direction | Avg PF | Avg WR | Verdict |
|-----------|--------|--------|---------|
| Bull | 1.25 | 58% | **Edge confirmed** |
| Both | 0.89 | 52% | No edge (bear cancels bull) |
| Bear | 0.65 | 45% | **Anti-edge** — systematically losing |

The bear side loses on every pair, every timeframe, every buffer. This is not random — the strategy's structure-based SL is systematically wrong for shorts in a bull-trending market. Or the FVG fill pattern differs by direction.

## Best Configs (Bull-Only, SL=20, TP=2.0, 15m)

| Pair | WR | PF | DD | Trades/30d | $
|------|----|----|----|------------|---|
| DOGEUSDT | 68% | 4.52 | 0.7% | 22 | +$4.06 |
| XRPUSDT | 72% | 2.61 | 1.6% | 32 | +$4.80 |
| SUIUSDT | 52% | 2.19 | 1.5% | 42 | +$4.03 |
| AVAXUSDT | 59% | 1.50 | 5.2% | 78 | +$5.97 |
| ADAUSDT | 61% | 1.51 | 4.4% | 85 | +$6.40 |

On $70: 6-12% return/month with 0.7-5.2% DD across these configs. But this is **one 30-day window** — needs OOS.

## Current Architecture

```
15m (entry) ──► FVG detection ──► structural SL ──► trail on swing levels
1H (support) ──► structure bias (not used yet)
4H (support) ──► macro bias (not used yet)
```

### Entry
TrFvg enters on FVG fill: when price retraces into a detected FVG gap in the bias direction. SL placed below the nearest swing point (structure mode) with buffer. TP at fixed R multiple.

### Trailing
After entry, SL moves up (long) on each new confirmed swing low, with buffer. Applied on next bar for safety.

## Problem Areas

### 1. Bear direction bleeds (critical)
Bear trades lose on every pair. Possible causes:
- FVG fills in downtrends are fakeouts, not reversals
- Structure SL for shorts is too tight in momentum moves
- A market trending up means shorts face infinite resistance

**Next**: Test HTF trend filter. If 4H structure is bullish, skip shorts entirely. If bearish, allow shorts.

### 2. SL=10 too tight on volatile pairs
ADA, AAVE, LINK have high noise/signal ratio. SL=20 gives PF=1.04 vs SL=10 PF=0.81.

**Next**: Test SL=30, or better: ATR-based SL (e.g., 0.5 × ATR(14) instead of fixed pips).

### 3. 5m over-trades
5m has 2-3x more trades than 15m but WR drops 4-8% and DD doubles. The extra noise kills returns.

**Next**: Skip 5m for production. Use 15m only.

### 4. ADA avg_r display broken
The r_multiple calculation produces absurd values (13 billion) for ADA. The PnL-based metrics (PF, WR, DD) are correct. Likely a pip_size or lot calculation edge case at very low prices ($0.30). Fix if r_multiple becomes important for position sizing.

## Test Matrix — IS Window (May 26 – Jun 25 2026)

Already swept 216 configs. Next:

| Variable | Values | Purpose |
|----------|--------|---------|
| OOS window | Apr 26 – May 25 | Confirm edge exists |
| Sl_buffer | 20, 30 | Is more buffer better? |
| ATR buffer | 0.3, 0.5, 1.0 × ATR | Adaptive vs fixed pip |
| HTF filter | 4H bull only, 4H+1H both bull | Can filter fix bear? |
| Killzone | Asian/London/NY/None | Does session matter? |

## Data Sources

9 crypto pairs on Binance + Bybit via ccxt. 30-90 day windows depending on pair. Structure-rich pairs (ADA, XRP, SOL, AVAX) have native 30m parquet with 90K+ bars.

## Code Locations

| Component | Path |
|-----------|------|
| TrFvg strategy | `backtesting/strategies/tr_fvg.py` |
| Backtest runner | `backtesting/engine/runner.py` |
| Structure lib | `backtesting/structure_lib/` |
| Batch script | `backtesting/crypto/scripts/run_trfvg_backtest.py` |
| Config | `backtesting_config/settings.py` |
| Webapp | `webapp/app.py` |
| Crypto README | `backtesting/crypto/README.md` |

## Work Plan

### This Week
- [ ] OOS validation (Apr–May 2026 window)
- [ ] HTF trend filter for bear direction
- [ ] ATR-based SL buffer
- [ ] Visual verification of top winners on review page
- [ ] Live paper deployment on Oracle VM

### Next Week
- [ ] 7-day paper trading results
- [ ] Enable on all 9 pairs with pair-specific configs
- [ ] Add daily loss limit enforcement
- [ ] Telegram notification on fills/exits
