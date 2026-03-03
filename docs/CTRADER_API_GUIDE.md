# cTrader Open API Integration Guide

## Overview

cTrader Open API uses **Protocol Buffers (Protobuf)** over **TCP/WebSocket**, NOT traditional REST APIs.

## Authentication Flow

### What You Need from Sandbox

From https://openapi.ctrader.com/apps (Playground):

1. **Access Token** - Used for all API authentication (30-day expiry)
2. **Refresh Token** - Used to get new access token (no expiry)
3. **Client ID** - Your application identifier
4. **Client Secret** - Used with refresh token

### Token Usage

| Purpose | Access Token | Refresh Token | Client ID | Client Secret |
|---------|--------------|---------------|-----------|---------------|
| Protobuf messages | ✅ | ❌ | ✅ | ✅ |
| Refreshing tokens | ❌ | ✅ | ✅ | ✅ |

## Connection Methods

### Option 1: Protocol Buffers (Official Method)

**Pros:**
- Full API access (historical + live data, trading, positions)
- Real-time streaming
- Official support

**Cons:**
- Requires Protobuf library
- More complex setup
- TCP/WebSocket connection management

**Endpoints:**
- Demo: `demo.ctraderapi.com:5035`
- Live: `live.ctraderapi.com:5035`

### Option 2: REST API (Limited)

**Available REST Endpoints:**
- `POST /apps/token` - OAuth token exchange/refresh only
- No market data endpoints
- No trading endpoints

**Conclusion:** REST is only for authentication, not data fetching.

## Recommended Approach

### For Historical Data

Use **Python OpenAPI library** with Protobuf:

```bash
pip install ctrader-open-api
```

### For Live Data

Use **WebSocket** with Protobuf messages for real-time streaming.

## Symbol IDs

Every instrument has a numeric ID. Common examples:

| Symbol | Typical ID |
|--------|------------|
| EURUSD | 1 |
| GBPUSD | 2 |
| USDJPY | 3 |
| XAUUSD | 6 |

Get exact IDs by sending `ProtoOASymbolsListReq` message.

## Message Flow for Historical Data

1. Connect to TCP/WebSocket endpoint
2. Send `ProtoOAApplicationAuthReq` (with client_id, client_secret)
3. Send `ProtoOAGetAccountListByAccessTokenReq` (with access_token)
4. Send `ProtoOAAccountAuthReq` (with account_id, access_token)
5. Send `ProtoOAGetTrendbarsReq` (with symbol_id, period, timestamps)
6. Receive `ProtoOAGetTrendbarsRes` with trendbar data

## Data Format

Trendbars use **relative pricing** (divide by 100,000):

```python
low_price = trendbar.low / 100000.0
high_price = (trendbar.low + trendbar.deltaHigh) / 100000.0
open_price = (trendbar.low + trendbar.deltaOpen) / 100000.0
close_price = (trendbar.low + trendbar.deltaClose) / 100000.0
```

## Timeframes

- M1, M5, M15, M30 (minutes)
- H1, H4 (hours)
- D1 (daily)
- W1 (weekly)
- MN1 (monthly)

## Resources

- [Official Docs](https://help.ctrader.com/open-api/)
- [Python SDK](https://github.com/spotware/OpenApiPy)
- [.NET SDK](https://github.com/spotware/OpenAPI.Net)
- [Protobuf Messages](https://help.ctrader.com/open-api/messages/)
