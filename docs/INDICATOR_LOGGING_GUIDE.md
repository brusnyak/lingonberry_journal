# Technical Indicator Logging Guide

## Overview

The trading journal now automatically captures and stores technical indicators (EMAs and VWAP) at both trade entry and exit points. This provides complete technical context for every trade.

## Captured Indicators

- **EMA 9**: 9-period Exponential Moving Average
- **EMA 21**: 21-period Exponential Moving Average  
- **EMA 50**: 50-period Exponential Moving Average
- **EMA 200**: 200-period Exponential Moving Average
- **VWAP**: Volume Weighted Average Price

## Automatic Capture

### cTrader Import

When importing trades from cTrader, indicators are automatically captured:

```python
from infra.ctrader_ingest import import_ctrader_trades

# Import trades with automatic indicator capture
result = import_ctrader_trades(
    account_id=1,
    from_ts=datetime(2026, 3, 1),
    to_ts=datetime(2026, 3, 7)
)

print(f"Imported: {result['imported']}")
print(f"Skipped: {result['skipped']}")
```

### Manual Trade Entry

For manual trades, capture indicators explicitly:

```python
from bot import journal_db

# Capture indicators at entry
entry_indicators = journal_db.capture_indicators_at_timestamp(
    symbol="EURUSD",
    asset_type="forex",
    timeframe="M30",
    timestamp="2026-03-06T08:00:00Z"
)

# Create trade with indicators
trade_id = journal_db.create_trade(
    account_id=1,
    symbol="EURUSD",
    direction="LONG",
    entry_price=1.16100,
    position_size=0.1,
    ts_open="2026-03-06T08:00:00Z",
    asset_type="forex",
    timeframe="M30",
    indicator_data={"entry": entry_indicators}
)

# Later, when closing the trade
exit_indicators = journal_db.capture_indicators_at_timestamp(
    symbol="EURUSD",
    asset_type="forex",
    timeframe="M30",
    timestamp="2026-03-06T12:00:00Z"
)

journal_db.close_trade(
    trade_id=trade_id,
    exit_price=1.16400,
    outcome="TP",
    event_type="manual_close",
    provider="manual",
    payload={},
    exit_indicators=exit_indicators
)
```

## Data Structure

Indicator data is stored as JSON in the `indicator_data` column:

```json
{
  "entry": {
    "ema_9": 1.16099,
    "ema_21": 1.16090,
    "ema_50": 1.16082,
    "ema_200": 1.16444,
    "vwap": 1.17680
  },
  "exit": {
    "ema_9": 1.15787,
    "ema_21": 1.15909,
    "ema_50": 1.15995,
    "ema_200": 1.16392,
    "vwap": 1.17651
  }
}
```

## Accessing Indicator Data

### Via API

```python
from bot import journal_db

trade = journal_db.get_trade(trade_id)

if trade.get("indicator_data"):
    entry_ema9 = trade["indicator_data"]["entry"]["ema_9"]
    exit_ema9 = trade["indicator_data"]["exit"]["ema_9"]
    
    print(f"EMA 9 at entry: {entry_ema9:.5f}")
    print(f"EMA 9 at exit: {exit_ema9:.5f}")
```

### Via Web API

```bash
curl http://localhost:5000/api/trades/123
```

Response includes:
```json
{
  "id": 123,
  "symbol": "EURUSD",
  "direction": "LONG",
  "entry_price": 1.16100,
  "exit_price": 1.16400,
  "indicator_data": {
    "entry": {
      "ema_9": 1.16099,
      "ema_21": 1.16090,
      ...
    },
    "exit": {
      "ema_9": 1.15787,
      ...
    }
  }
}
```

## Supported Assets

### Forex
- All major and minor pairs (EURUSD, GBPUSD, USDJPY, etc.)
- Timeframes: M1, M5, M15, M30, H1, H4, D

### Indices
- NAS100 (Nasdaq 100)
- US100
- USTEC
- SPX500 (S&P 500)
- US30 (Dow Jones)

### Commodities
- XAUUSD (Gold)
- XAGUSD (Silver)
- XPTUSD (Platinum)
- XPDUSD (Palladium)

## Data Sources

1. **cTrader API** (Primary)
   - Real-time data for all supported symbols
   - Requires valid API credentials
   - Connection pooling for performance

2. **Local CSV Files** (Fallback)
   - Stored in `data/market_data/{asset_type}/{symbol}/{timeframe}.csv`
   - Used when cTrader is unavailable

3. **Yahoo Finance** (Last Resort)
   - Used for stocks and some commodities
   - Limited historical data

## Performance

- Indicators are calculated once and cached
- Cache TTL: 1 hour (configurable)
- Connection pooling reduces API overhead
- Typical capture time: <1 second per timestamp

## Troubleshooting

### No indicators captured

```python
# Check if market data is available
from infra.market_data import load_ohlcv_with_cache
from datetime import datetime, timedelta

df = load_ohlcv_with_cache(
    symbol="EURUSD",
    asset_type="forex",
    timeframe="M30",
    start=datetime(2026, 3, 1),
    end=datetime(2026, 3, 7),
    ttl_seconds=0  # Force fresh fetch
)

print(f"Candles loaded: {len(df)}")
print(f"Columns: {df.columns.tolist()}")
```

### cTrader connection issues

```python
from infra.ctrader_client import test_connection

# Test connection
test_connection()
```

### Missing indicator columns

Indicators are added automatically by `_add_indicators()` in `infra/market_data.py`. If missing, check:
- Market data was fetched successfully
- DataFrame is not empty
- Volume data is available (for VWAP)

## Best Practices

1. **Always specify timeframe** - Use the same timeframe you traded on
2. **Capture at actual trade time** - Use exact entry/exit timestamps
3. **Check for None values** - Indicators may be None if data is unavailable
4. **Use appropriate asset_type** - Ensures correct data source and symbol mapping

## Example: Complete Trade Flow

```python
from bot import journal_db
from datetime import datetime

# 1. Capture entry indicators
entry_ts = "2026-03-06T08:00:00Z"
entry_indicators = journal_db.capture_indicators_at_timestamp(
    symbol="NAS100",
    asset_type="index",
    timeframe="M30",
    timestamp=entry_ts
)

# 2. Create trade
trade_id = journal_db.create_trade(
    account_id=1,
    symbol="NAS100",
    direction="SHORT",
    entry_price=5276.74,
    position_size=0.1,
    ts_open=entry_ts,
    asset_type="index",
    sl_price=5335.96,
    tp_price=5058.88,
    timeframe="M30",
    indicator_data={"entry": entry_indicators}
)

# 3. Close trade with exit indicators
exit_ts = "2026-03-06T15:30:00Z"
exit_indicators = journal_db.capture_indicators_at_timestamp(
    symbol="NAS100",
    asset_type="index",
    timeframe="M30",
    timestamp=exit_ts
)

journal_db.close_trade(
    trade_id=trade_id,
    exit_price=5058.88,
    outcome="TP",
    event_type="manual_close",
    provider="manual",
    payload={},
    ts_close=exit_ts,
    exit_indicators=exit_indicators
)

# 4. Retrieve and analyze
trade = journal_db.get_trade(trade_id)
print(f"Entry EMA 9: {trade['indicator_data']['entry']['ema_9']:.2f}")
print(f"Exit EMA 9: {trade['indicator_data']['exit']['ema_9']:.2f}")
```
