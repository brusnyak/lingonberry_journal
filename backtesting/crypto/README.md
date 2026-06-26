# Crypto Engine - 10x Research State

## Current Verdict

Not deployment-ready.

The previous 50x/0.5% results were misleading for three reasons:

1. They used unrealistic leverage for EU-regulated execution.
2. They allowed far or stale structural stops, creating multi-day holds.
3. Some structure stops collapsed to entry/tick-noise, creating bogus R-multiples.

The current branch fixes those issues for research:

- Development account: `$70`
- Development leverage: `10x`
- Research risk: `2%` per trade
- `CryptoCosts` uses exchange-scoped market specs and funding
- `TrFvg` rejects stops that are too tight or too far:
  - `min_stop_pct=0.001`
  - `min_stop_atr_mult=0.25`
  - `max_stop_pct=0.012`
  - `max_stop_atr_mult=2.5`
- `tp1_frac=1.0` closes full position at TP1 for intraday review

## Strategy Tested

`TrFvg` remains a fair-value-gap fill reversal:

- `bull` direction = short bullish FVG fills
- `bear` direction = long bearish FVG fills
- `both` direction = both sides
- Structural SL = nearest confirmed swing, plus buffer
- Structure updates now include the latest confirmed pivot up to `i - swing_n`

## 30D Sweep - 10x / Intraday-Capped

Command:

```bash
python -m backtesting.crypto.scripts.run_trfvg_backtest
```

Core settings:

- Account: `$70`
- Leverage: `10x`
- Exchange: `binance`
- Window: latest 30D local data
- Symbols: `ADA, XRP, SOL, AVAX, NEAR, DOGE, LINK, AAVE, SUI`
- Timeframes: `5m`, `15m`
- Directions: `both`, `bull`, `bear`
- SL buffers: `10`, `20`
- TP: `1.5R`, `2.0R`

Top 30D rows after stop fixes:

| Pair | TF | Dir | Trades | WR | PF | Return | DD |
|---|---:|---|---:|---:|---:|---:|---:|
| DOGEUSDT | 5m | bull | 5 | 40% | 5.79 | 6.4% | 0.9% |
| SUIUSDT | 15m | bull | 7 | 43% | 2.46 | 5.0% | 3.1% |
| AAVEUSDT | 15m | bull | 39 | 49% | 2.01 | 31.0% | 8.9% |
| AVAXUSDT | 15m | bull | 39 | 44% | 1.98 | 37.3% | 9.2% |
| XRPUSDT | 15m | bull | 8 | 25% | 1.75 | 3.2% | 2.8% |

Important: DOGE looks good in a single 30D window, but fails rolling validation. Do not promote it.

## Rolling 30D Validation

Command:

```bash
python -m backtesting.crypto.scripts.run_rolling_trfvg
```

Test:

- 8 rolling 30D windows
- 7D step
- Pairs: `XRP, DOGE, AVAX, ADA, SUI`
- Config: `SL=20`, `TP=2R`, capped structure stops, `10x`, `2% risk`

Rolling results:

| Pair | Dir | Valid Windows | Mean PF | PF Std | Min PF | WR | Mean DD | Mean Trades |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| XRPUSDT | bull | 8/8 | 5.70 | 3.94 | 1.89 | 38% | 1.7% | 6 |
| AVAXUSDT | bull | 5/8 | 3.79 | 2.70 | 2.01 | 53% | 5.6% | 24 |
| XRPUSDT | both | 8/8 | 2.15 | 0.91 | 1.07 | 27% | 3.5% | 13 |
| AVAXUSDT | both | 5/8 | 1.56 | 0.09 | 1.46 | 43% | 6.4% | 41 |
| SUIUSDT | both | 8/8 | 1.05 | 0.47 | 0.55 | 25% | 22.4% | 51 |
| DOGEUSDT | bull | 6/8 | 0.30 | 0.32 | 0.00 | 8% | 4.2% | 7 |

Decision:

- `AVAXUSDT 15m bull` is the best current candidate because it has usable trade count.
- `XRPUSDT 15m bull` has strong PF but too few trades; treat as promising but under-sampled.
- `DOGEUSDT` is rejected despite the top single-window row.
- `SUIUSDT` is not stable enough.
- `bear` direction remains bad.

## Trade Geometry Review

Generated locally:

```bash
backtesting/results/trfvg_10x_trade_review_summary.csv
backtesting/results/trfvg_10x_trade_review.csv
```

Reviewed candidates:

| Pair | TF | Dir | Trades | Median Hold | Avg Stop | Median Stop | Max Stop | Avg TP | EOD |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| XRPUSDT | 15m | bull | 8 | 37.5m | 0.76% | 0.74% | 1.13% | 1.52% | 0 |
| AVAXUSDT | 15m | bull | 39 | 60.0m | 0.77% | 0.79% | 1.16% | 1.53% | 0 |
| DOGEUSDT | 5m | bull | 5 | 10.0m | 0.83% | 0.88% | 1.07% | 1.67% | 0 |
| SUIUSDT | 15m | bull | 7 | 30.0m | 0.91% | 0.97% | 1.18% | 1.37% | 0 |

This fixes the original SL/TP problem:

- Stops are no longer multi-percent structure guesses.
- TPs are no longer multi-day targets.
- No reviewed candidate exits at EOD.

Remaining problem:

- Trade counts are low for DOGE/XRP/SUI.
- AVAX has better count but still needs OOS and exchange-feature filters.

## Data Resources

Core data:

- `data/market_data/crypto/{exchange}/{SYMBOL}{TF}.parquet`
- `data/market_data/crypto/{exchange}/{SYMBOL}_funding.parquet`
- `data/market_data/crypto/{exchange}/market_specs.parquet`

Exchange-derived resources:

- `data/market_data/crypto/{exchange}/resources/{SYMBOL}_mark{TF}.parquet`
- `data/market_data/crypto/{exchange}/resources/{SYMBOL}_index{TF}.parquet`
- `data/market_data/crypto/{exchange}/resources/{SYMBOL}_open_interest.parquet`

Fetch command:

```bash
python -m backtesting.data_pipeline.crypto \
  --days 90 \
  --exchange both \
  --symbols DOGEUSDT,XRPUSDT,SUIUSDT,AVAXUSDT \
  --tfs 1,15,60 \
  --resources mark,index,open_interest
```

## Review UI

Run:

```bash
make run-web
```

Open:

```text
http://127.0.0.1:5000/review
```

Crypto defaults:

- Symbol: `DOGEUSDT`
- TF: `15m`
- Exchange: `binance`
- Account: `$70`
- Leverage: `10x`
- Strategy: `TrFvg`
- Direction: `bull`
- Risk: `2%`

Use the UI for visual inspection, not proof. Rolling metrics decide whether a setup is worth keeping.

## Next Crypto Work

1. Promote `AVAXUSDT 15m bull` to deeper review.
2. Add mark/index basis and open-interest filters.
3. Run Binance vs Bybit comparison with the same config.
4. Add lookahead/recursive-analysis checks inspired by Freqtrade.
5. Reject configs that pass only one 30D window.
