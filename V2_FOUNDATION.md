# V2 Strategy Foundation — Direction ML Engine for Prop Firm Trading

> Based on 365 days of data across 5 major forex pairs (GBPAUD, EURUSD, GBPUSD, GBPJPY, EURJPY)
> at 60m timeframe, 84-column feature matrix, walk-forward validated ensemble.

## Core Finding: ML Direction Prediction Works at ~62%

| Metric | Structure Alone | ML Ensemble | Improvement |
|--------|:-:|:-:|:-:|
| 1h direction accuracy | ~53% | **~62%** | +9% |
| 4h direction accuracy | ~54% | ~59% | +5% |
| 8h+ direction accuracy | ~55% | ~53% | degrades |
| Best pair (GBPJPY) | — | **63.1%** | — |
| Worst pair (EURUSD) | — | 61.5% | — |

Consistent across all pairs tested. The edge is real and generalizes.

### What Drives the Prediction (Feature Importance)

| Category | Total Importance | Key Features |
|----------|:-:|-----------|
| **Structure swings** | 190 | pool_dist_atr (59), ll/hh/lh/hl_dist_atr |
| **Window context** | 180 | displacement_5/10/20, bull_bar_ratio |
| **FVG/Sweep** | 170 | range_atr, sweep_dir, fvg_gap_atr |
| **Price action per-bar** | 147 | upper/lower_wick, body_pct, pin/inside bars |
| **Volatility** | 112 | atr_pctile, atr, rel_volume |
| **Session** | 54 | hour_sin/cos, ny_open |
| **Candle patterns** | 25 | negligible — 22 TA-Lib patterns combined |
| **Raw prices** | 52 | minor |

Drop candle patterns from V2 — they contribute nothing.

## Strategy Architecture

```
60m bar closes
    │
    ├── Feature Engine ──► 62-column feature vector (no candle patterns)
    │                        (structure swings + displacement + volatility
    │                         + price action + FVG/sweep + session)
    │
    ├── ML Direction Model ──► P(UP) / P(DOWN) for next 1h
    │    ├── LightGBM + XGBoost + CatBoost ensemble
    │    ├── Retrained weekly, walk-forward validated
    │    └── Output: UP probability (0-1)
    │
    ├── Structure Filter ──► Regime alignment check
    │    ├── 4H regime (highest confidence): bias direction
    │    ├── 1H regime (confluence): strengthen
    │    ├── 15m structure: entry timing
    │    └── Only trade when 4H + ML agree
    │
    └── Risk Gate ──► Position sizing based on P(UP) confidence
         ├── P > 0.65: full size (0.5% risk)
         ├── 0.55 < P < 0.65: half size (0.25% risk)
         └── P < 0.55: no trade
```

### Entry Rules (5 mandatory)

1. **ML confidence ≥ 0.55** for the predicted direction at 1h horizon
2. **4H regime same direction** as ML prediction
3. **1H regime same direction** (confluence) — optional but preferred
4. **Enter at next 60m bar open** after confirmation (no FVG retrace needed)
5. **No entry within 30m of high-impact news** (NFP, FOMC, CPI)

### Exit Rules

- **SL**: 1.5× ATR(14) below entry for longs, above for shorts (structural)
- **TP1** (50% position): 1.5R
- **TP2** (50% position): 2.5R, trailed after 2h if no TP hit
- **Max hold**: 4 bars (4h) — if neither SL/TP hit, close at market
- **Time-based exit**: 15:30 UTC daily (before London close)

## Risk Management for Prop Firm

### 25k 2-Step Account
| Parameter | Value |
|-----------|:-----:|
| Daily DD limit | $1,233 (5%) |
| Max DD | $2,466 (10%) |
| Target 8% | $2,000 |
| Risk per trade | 0.5% ($125) |
| Max concurrent | 2 positions |

### 100k 1-Step Account
| Parameter | Value |
|-----------|:-----:|
| Daily DD limit | $3,992 (4%) |
| Max DD | $5,988 (6%) |
| Target 10% | $10,000 |
| Risk per trade | 0.3% ($300) |
| Max concurrent | 2 positions |

### Position Sizing Formula
```
lot_size = (account_balance × risk_pct) / (SL_pips × pip_value)
```

## Expected Performance (Theoretical)

With 62% accuracy and 1.5:1 RR:
```
Per 100 trades:
  Wins:   62 × 1.5R =  93R
  Losses: 38 × 1.0R = -38R
  Net:              =  55R

On 25k account (R = $125):
  Net = 55 × $125 = $6,875 per 100 trades

At 2 trades/day, 22 trading days/month:
  44 trades/month → $3,025/month = 12.1% return
```

### Drawdown Estimate
```
Worst expected run at 62% accuracy:
  Expected max losing streak ≈ ln(100) / -ln(0.62) ≈ 8 trades
  Max DD = 8 × $125 = $1,000 (4% of 25k account)

  Within 5% daily limit. Acceptable.
```

## Implementation Path

### Phase 1: ML Pipeline (this session) ✅
- [x] Feature matrix: 84 columns → 62 useful (dropping candle patterns)
- [x] Direction ML: ensemble, walk-forward, ~62% accuracy
- [x] Multi-pair validation: consistent across 5 pairs
- [x] Feature importance analysis: structure + displacement dominate

### Phase 2: VBT-Native Strategy Engine
- [ ] Rewrite entry logic as signal-mask generator (boolean arrays)
- [ ] Integrate ML model inference as pre-computed feature column
- [ ] Single `from_signals` call per session batch
- [ ] Target: < 1s for full parameter sweep (486 combos)

### Phase 3: Live Validation
- [ ] Paper trade for 2 weeks minimum (60+ trades)
- [ ] Verify: actual accuracy vs predicted, slippage, fill rates
- [ ] Adjust confidence threshold if needed (P > 0.6, P > 0.7)

### Phase 4: Prop Firm Challenge
- [ ] Start with 25k 2-step (lower capital, same rules)
- [ ] Target: 8% ($2,000) in 30 days
- [ ] Max risk per trade: 0.5%
- [ ] No trading after 3 consecutive losses (cool-down 1 day)

## Open Questions

1. **Retrain frequency**: weekly vs monthly. Weekly captures regime changes but risks overfitting to recent noise. Test both.
2. **News filter**: how close to news events do we skip? Current: 30min before major releases. Test with 15min buffer.
3. **Pair correlation**: GBPJPY and EURJPY likely correlated (both JPY pairs). Max 1 JPY pair at a time.
4. **ML confidence threshold**: 0.55 was assumed. Test 0.50-0.70 range to find optimal Sharpe ratio.

## Files

- `backtesting/scripts/train_direction_ml.py` — Direction ML training + reporting
- `backtesting/scripts/direction_accuracy_v2.py` — Multi-TF structure accuracy analysis
- `backtesting/ml/features.py` — 84-column feature matrix builder
- `backtesting/results/direction_ml_gbpaud_report.csv` — GBPAUD results
- `backtesting/results/direction_ml_5pairs_report.csv` — Multi-pair results
