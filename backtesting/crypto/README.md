# Crypto Engine — TrFvg Strategy ($70 Account)

## Account
- **Single personal account**: $70 on Binance/Bybit USDT-M futures
- **Leverage**: 50x
- **Risk per trade**: 0.5% ($0.35)
- **Stop**: $50 floor (29% DD hard limit)

## TrFvg Strategy
FVG-based mean reversion: enters when price fills a FVG in the bias direction. Uses structural stop loss (below swing point) with trailing on confirmed swing levels.

### Key Params (from sweep)
| Param | Best | Range Tested |
|-------|------|-------------|
| direction | bull | both, bull, bear |
| sl_buffer_pips | 20 | 10, 20 |
| tp1_r | 2.0 | 1.5, 2.0 |
| entry_tf | 15m | 5m, 15m |
| sl_mode | structure | fixed, structure |
| structure_sl_lookback | 20 | - |
| structure_sl_swing_n | 3 | - |

## Backtest Results — 30 Day Window (May 26 – Jun 25 2026)

### Summary
- **216 configs** across 9 pairs × 2 TFs × 3 directions × 2 SL × 2 TP
- **Bull direction is the only edge**: avg PF=1.25, WR=58%
- **Bear direction loses on every pair**: avg PF=0.65, WR=45%
- **Both direction: diluted**: avg PF=0.89, WR=52%
- **15m beats 5m**: less noise, higher PF (1.01 vs 0.84)
- **SL=20 beats SL=10**: avg PF 1.04 vs 0.81

### Top Configs (Bull Only, SL=20, TP=2.0)

| Pair | TF | Trades | WR | PF | RR | Ret% | DD% |
|------|----|--------|----|----|----|------|-----|
| DOGEUSDT | 15m | 22 | 68% | 4.52 | 2.11 | 6% | 0.7% |
| XRPUSDT | 15m | 32 | 72% | 2.61 | 1.02 | 7% | 1.6% |
| SUIUSDT | 15m | 42 | 52% | 2.19 | 1.99 | 6% | 1.5% |
| AVAXUSDT | 15m | 78 | 59% | 1.50 | 1.04 | 9% | 5.2% |
| ADAUSDT | 15m | 85 | 61% | 1.51 | 0.96 | 9% | 4.4% |
| DOGEUSDT | 5m | 43 | 67% | 3.00 | 1.45 | 9% | 1.2% |
| SUIUSDT | 5m | 78 | 56% | 2.14 | 1.66 | 12% | 2.0% |
| XRPUSDT | 5m | 54 | 63% | 1.88 | 1.11 | 8% | 2.0% |

### Why Bull Direction Wins
The 30-day window (May-Jun 2026) was a structurally bullish period across altcoins. TrFvg is a mean-reversion strategy that fades moves back to FVG — in an uptrend, bullish FVG fills buy dips that get carried higher, while bearish FVG fills catch falling knives.

Key insight: **TrFvg is not symmetric**. The signal quality differs by direction because:
1. Uptrends have clean FVG retests that bounce
2. Downtrend FVG fills often get swept through (trend continuation)
3. The structural SL on bear trades gets hit more often (SL above swing high, but price keeps making new highs)

### Why Losers Fail
1. **Bear direction** — every pair, every config. 45% WR, PF=0.65. The structure-based SL is systematically too close for shorts in a bull trend. This isn't random — it's a trend bias.

2. **SL=10 on volatile pairs** — ADA, AAVE, LINK have high ATR relative to pip_size. SL=10 gets eaten by noise. SL=20 survives.

3. **5m entry over-trades** — more signals, lower quality. WR drops 4-8% vs 15m, DD doubles.

4. **Both direction drags** — the bear trades cancel the bull edge. Running both gives avg PF near 1.0.

## Data Inventory (2026-06-26)

### 9 Pairs Available

| Pair | 30m | Structure Quality | Backtest Quality |
|------|-----|-------------------|------------------|
| ADAUSDT | YES | HIGH (496 pivots) | GOOD (PF 1.5) |
| XRPUSDT | YES | HIGH (517 pivots) | GOOD (PF 1.9-2.6) |
| SOLUSDT | YES | HIGH (524 pivots) | MEDIUM (PF 1.2) |
| DOGEUSDT | RESAMPLE | LOW (49 pivots) | GOOD (PF 3.0-4.5) |
| AVAXUSDT | YES | HIGH (398 pivots) | GOOD (PF 1.5) |
| NEARUSDT | DATA | 30+ days | FAIR (PF 1.3) |
| LINKUSDT | DATA | 30+ days | FAIR (PF 1.2) |
| AAVEUSDT | DATA | 30+ days | FAIR (PF 1.1) |
| SUIUSDT | RESAMPLE | untested | GOOD (PF 2.2) |

### Missing or Deprecated
- ALGO, ATOM, TRX, ARB, ENA, INJ, TIA, WLD — not in primary universe
- BTC, ETH — 10x fewer structure events, not suitable for this strategy

## Structure Pipeline Performance

All 9 tested pairs run in 0.1–4s total (30-day window).

| Asset | Pipeline | Sweeps | Sweep Time | Signal Gen | Total |
|-------|----------|--------|------------|------------|-------|
| XRP | 0.1s | 108K | 1.8s | 1.5s | 3.7s |
| SOL | 0.1s | 105K | 1.7s | 1.5s | 3.6s |
| ADA | 0.1s | 25K | 0.4s | 0.5s | 1.1s |
| AVAX | 0.1s | 42K | 0.7s | 0.6s | 1.7s |
| DOGE | 0.02s | 2K | 0.03s | 0.04s | 0.1s |

## Next Actions

1. **OOS validation**: Run on non-overlapping window (Apr 26 – May 25) to confirm edge
2. **Filter bear trades**: Hard rule — only bull signals. Or add HTF trend filter (4H structure)
3. **Test SL=30**: Higher buffer might improve bear direction too
4. **Examine top winners on review page**: Visual check of DOGE/XRP bull 15m trades
5. **Add ATR-based pip_size**: SL buffer proportional to ATR instead of fixed pips
6. **Live paper trading**: Deploy best config (XRP/DOGE/AVAX 15m bull) on demo
7. **Clean deprecated branches**: feature/ob-structure-sl, feature/prop-firm-engine

## Run Commands

```bash
# Full backtest sweep
python -m backtesting.crypto.scripts.run_trfvg_backtest

# Data fetch
python -m backtesting.data_pipeline.crypto --days 90 --exchange both --tfs 1,3,5,15,30,60,240,1440

# Structure audit
python -m backtesting.crypto.scripts.audit_structure

# Review webapp
cd ../../ && make webapp  # then open http://localhost:5000/review
```
