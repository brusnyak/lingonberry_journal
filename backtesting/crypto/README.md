# Crypto Engine — Data & Structure Audit

## Data Inventory (2026-06-26)

### 16 Pairs Available

| Pair | 30m | Bars (30m) | Date Range | Structure Quality |
|---|---|---|---|---|
| ADAUSDT | YES | 100K | Apr 25 – Jun 25 | HIGH (496 pivots, 52 sigs) |
| ALGOUSDT | YES | 100K | May 17 – Jun 23 | untested |
| ATOMUSDT | YES | 100K | May 25 – Jun 23 | untested |
| AVAXUSDT | YES | 93K | Apr 26 – Jun 23 | HIGH (398 pivots, 31 sigs) |
| SOLUSDT | YES | 100K | Apr 15 – Jun 25 | HIGH (524 pivots, 31 sigs) |
| TRXUSDT | YES | 100K | May 16 – Jun 23 | untested |
| XRPUSDT | YES | 100K | Apr 15 – Jun 25 | HIGH (517 pivots, 34 sigs) |
| BTCUSDT | RESAMPLE | 26K(5m) | Mar 27 – Jun 25 | LOW (50 pivots, 5 sigs) |
| ETHUSDT | RESAMPLE | 26K(5m) | Mar 27 – Jun 25 | LOW (56 pivots, 6 sigs) |
| DOGEUSDT | RESAMPLE | 115K(5m) | May 20 – May 25 | LOW (49 pivots, 2 sigs) |
| ARBUSDT | RESAMPLE | 26K(5m) | Mar 26 – Jun 24 | untested |
| ENAUSDT | RESAMPLE | 115K(5m) | May 20 – May 25 | untested |
| INJUSDT | RESAMPLE | 26K(5m) | Mar 26 – Jun 24 | untested |
| SUIUSDT | RESAMPLE | 26K(5m) | Mar 26 – Jun 24 | untested (has files) |
| TIAUSDT | RESAMPLE | 26K(5m) | Mar 26 – Jun 24 | untested |
| WLDUSDT | RESAMPLE | 26K(5m) | Mar 26 – Jun 24 | untested |

### Missing (No Data At All)
- LINKUSDT
- NEARUSDT
- BNBUSDT (DEFAULT_SYMBOLS)
- HYPEUSDT (DEFAULT_SYMBOLS)
- AAVEUSDT (DEFAULT_SYMBOLS)

### 30m vs Resample
Only 7 pairs have native 30m parquet files. The rest are resampled from 5m or 1m by the loader. This affects structure quality — BTC/ETH/DOGE show 10x fewer structure events than ADA/SOL/XRP/AVAX even in the same window. This could be real (more efficient markets = less noise) or an artifact of resampled data (fewer candles).

## Structure Pipeline Performance

All 8 tested pairs run in 0.1–4s total (30-day window).

| Asset | Pipeline | Sweeps | Sweep Time | Signal Gen | Total |
|---|---|---|---|---|---|
| ADA | 0.1s | 25K | 0.4s | 0.5s | 1.1s |
| XRP | 0.1s | 108K | 1.8s | 1.5s | 3.7s |
| SOL | 0.1s | 105K | 1.7s | 1.5s | 3.6s |
| AVAX | 0.1s | 42K | 0.7s | 0.6s | 1.7s |
| BTC/ETH/DOGE | 0.02s | 2K | 0.03s | 0.04s | 0.1s |

## Data Layout

```
data/market_data/crypto/
  ADAUSDT1.parquet         # flat files (all TFs)
  ADAUSDT5.parquet
  ADAUSDT30.parquet        # 30m direct
  ...
  binance/                 # exchange-scoped (used by loader when exchange="binance")
    BTCUSDT1.parquet
    DOGEUSDT5.parquet
    ...
  bybit/                   # exchange-scoped
    BTCUSDT1.parquet
    ...
  _backup_before_20260625_pull/   # stale — remove
  _aborted_365_pull_20260625T132304Z/  # stale — remove
```

Flat files have deeper history (100K bars) than exchange-scoped files (~25K).
Loader fallback: exchange dir → flat → pine-review.

## Gaps & Next Actions

1. **Missing pairs**: Fetch LINK, NEAR, BNB, HYPE, AAVE from Binance/Bybit
2. **30m resampling**: Generate native 30m for BTC, ETH, DOGE, ARB, ENA, INJ, SUI, TIA, WLD
3. **Compaction**: Flatten backup dirs, deduplicate exchange vs flat, consolidate to exchange dirs
4. **Visual verify**: Open http://localhost:5000/review — select TrFvg on crypto pairs — confirm structure overlays (pivots, BOS, ChoCH, FVG, OB)
