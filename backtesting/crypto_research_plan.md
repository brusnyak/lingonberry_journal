# Crypto Research Plan

Goal: find a small, testable crypto futures strategy that can plausibly grow a 20 USDT account toward 100 USDT without hiding behind lookahead, fees, funding, liquidation, or cherry-picked pump assets.

## Current Data State

Verified locally on 2026-06-25:

- Exchanges: Binance USDT-M, Bybit linear.
- Core symbols with 90 days: BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, DOGEUSDT, BNBUSDT.
- Aggressive symbols with 30 days: HYPEUSDT, AAVEUSDT, WLDUSDT, 1000PEPEUSDT, LINKUSDT, AVAXUSDT, SUIUSDT, NEARUSDT.
- Timeframes: 1m, 3m, 5m, 15m, 1h, 4h, 1d.
- Funding: present for all symbols.
- Instrument specs: present for 14 ids per exchange.

This is enough for first-pass technical experiments. It is not enough for machine learning or broad robustness claims.

## External Resources Worth Using

### Backtesting / Research Process

- Freqtrade: copy the workflow ideas, not the whole framework.
  - Lookahead analysis.
  - Recursive analysis.
  - Hyperopt / walk-forward style.
- VectorBT: useful for fast vectorized sweeps and parameter heatmaps.
  - Do not replace the event engine with it yet; our engine models partials, fees, funding, and liquidation more directly.
- NautilusTrader: useful reference for production-grade event modeling.
  - Too heavy for this phase.

### Exchange Data

Use exchange-specific raw storage. Same symbol is not the same instrument across Binance and Bybit.

Data we already have:

- OHLCV candles.
- Funding history.
- Instrument specs.

Data to add next, in this order:

1. Mark price candles.
   - Needed for liquidation realism.
2. Index price candles.
   - Needed to separate spot/index move from perp premium.
3. Premium index / basis.
   - Useful for crowded perp regimes.
4. Open interest.
   - Useful for leverage buildup and squeeze/fade filters.
5. Taker buy/sell volume.
   - Useful for aggressive flow confirmation/exhaustion.
6. Long/short ratios.
   - Useful as a sentiment/crowding feature, but dangerous if treated as signal alone.
7. Order book snapshots or L2.
   - Later only. Heavy storage and easy to overfit.
8. Liquidations.
   - Useful if sourced reliably; otherwise skip.

## Feature Ladder

Do not jump to ML before simple edges fail cleanly.

### Level 0: Engine/Data Sanity

Required:

- No lookahead.
- Costs included.
- Funding side-aware.
- Min notional and qty steps enforced.
- Liquidation modeled.
- Exchange-separated data.
- Report includes WR, RR/payoff, PF, net avg R, PnL, DD, final equity, duration, trade PnL sequence, target/ruin status.

### Level 1: Technical Baselines

Test small, with one idea at a time:

- Trend continuation:
  - 4h trend + 30m structure + 5m trigger.
- Pullback after structure shift:
  - First pullback only after confirmed 30m HH/HL or LL/LH.
- Liquidity sweep:
  - Prior 30m/4h high-low sweep + reclaim.
- Volatility compression then expansion:
  - Narrow range / ATR compression, then break with volume.
- BOS fade:
  - Failed breakout back into range.

### Level 2: Exchange Microstructure Features

Add one feature family at a time:

- Funding regime.
- Open interest expansion/contraction.
- Taker buy/sell imbalance.
- Premium/index basis.
- Mark/index divergence.

### Level 3: Pattern Recognition

Only after Level 1/2 creates a stable event set:

- Label events, not every candle.
- Predict trade quality, not direction.
- Features must be known before entry.
- Evaluation must be rolling out-of-sample.

### Level 4: ML

ML is last, not first.

Candidate tasks:

- Classify whether a valid setup should be skipped.
- Rank symbols/setups for the next 4-24 hours.
- Predict volatility regime for position sizing.

Reject any ML model that only improves in-sample or only works on one symbol.

## First Small Experiment Matrix

Use core only first:

- Exchanges: Binance, Bybit.
- Symbols: BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, DOGEUSDT, BNBUSDT.
- Windows: 30d, 60d, 90d.
- Entry timeframes: 3m, 5m, 15m.
- Context timeframes: 30m and 4h.
- Risk: 0.5%, 1.0%, 2.0%.
- Max trades: 1 per symbol at a time.

Initial strategies:

1. `structure_pullback_v1`
   - Confirmed 30m structure shift.
   - 4h MA direction agreement.
   - Enter first 5m pullback/reclaim only.
   - Max 1-2 trades per structure leg.

2. `sweep_reclaim_v1`
   - Sweep prior 30m or 4h swing.
   - Close back inside.
   - 5m confirmation.
   - Trade toward range midpoint or opposite liquidity.

3. `compression_breakout_v1`
   - 30m/1h ATR compression.
   - 5m expansion with volume.
   - 4h trend filter.

4. `bos_fade_v1`
   - Breakout beyond 30m level.
   - Failed continuation.
   - Re-enter prior range.

## Pass/Fail Gates

For a strategy to be worth developing:

- 30d PF >= 1.20 on at least 4 core symbol/exchange combos.
- 90d PF >= 1.10 on core symbols where 90d exists.
- Max DD <= 30% on a 20 USDT account.
- Net avg R > 0 after fees/funding.
- Fewer than 30 trades per 30 days per symbol.
- No single symbol contributes more than 50% of total PnL.
- No liquidation exits.
- No target achieved only by one lucky trade.

For a strategy to be promising:

- PF >= 1.35.
- Max DD <= 20%.
- 30d return >= 30% without exceeding DD gate.
- Stable on both Binance and Bybit for at least one major symbol.

## Current Judgment

The two cold tests already run failed:

- Prior-bar Donchian + 1h trend: overtraded and lost 48-70%.
- 30m structure + 5m/30m/4h MA alignment: better WR, still too many trades, PF < 1, lost 39-44%.

Structure helps as context. It is not an entry trigger by itself.

Next best test: first-pullback-after-structure-shift, with a strict per-leg trade cap and volatility/volume confirmation.
