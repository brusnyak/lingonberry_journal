# Crypto Futures Research Universe

Goal: test whether a very small futures account can scale from 20 USDT to 100 USDT without pretending fees, funding, liquidation, and exchange constraints do not exist.

## Core Validation

Use these first:

- BTCUSDT
- ETHUSDT
- SOLUSDT
- XRPUSDT
- DOGEUSDT
- BNBUSDT

These are not automatically the highest-return assets. They are the cleanest instruments for proving the engine, cost model, and walk-forward process.

## Aggressive But Tradable

Use after the core set passes:

- HYPEUSDT
- AAVEUSDT
- WLDUSDT
- 1000PEPEUSDT
- LINKUSDT
- AVAXUSDT
- SUIUSDT
- NEARUSDT

These can move enough for a tiny 50x account, but the failure mode is obvious: funding spikes, wider spreads, noisy liquidations, and strategy overfit.

## Research Only

- ZECUSDT
- ADAUSDT
- exchange-specific hot listings

Do not promote these to core unless they pass rolling out-of-sample tests.

## Reject As Primary Universe

Avoid random current pump symbols such as MUSDT, SYNUSDT, SLXUSDT, REUSDT, OUSDT, HUSDT, and LABUSDT as primary research assets.

High 24h turnover from a fresh listing or one-day event is not a system. It is an overfit trap.

## Data Requirements

- OHLCV: 1m raw data, 2 years for core, 1 year for aggressive alts.
- Strategy bars: derive 3m, 5m, and 15m from 1m where possible.
- Regime bars: 1h, 4h, and 1d.
- Funding: full lookback at native funding timestamps.
- Specs: exchange instrument metadata on every fetch run.
- Store Binance and Bybit separately. Same symbol is not the same instrument.

## First Pass Gate

- Fees, funding, stop slippage, min notional, qty step, tick size, and liquidation must be modeled.
- Use 30-day rolling windows.
- No forced daily trades.
- Reject anything that only works on pump listings.
