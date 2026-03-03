# cTrader API Setup - Complete Guide

## 🎯 Summary

I've analyzed the cTrader Open API documentation and set up proper integration for your trading journal. Here's what you need to know:

## ⚠️ Important Discovery

**cTrader Open API does NOT use traditional REST APIs!**

It uses **Protocol Buffers (Protobuf)** over **TCP/WebSocket** connections. The only REST endpoint is for OAuth token exchange.

## 📋 What You Need from cTrader Sandbox

Go to: https://openapi.ctrader.com/apps (click "Playground")

Copy these 4 values:

1. **Access Token** - For authentication (expires in 30 days)
2. **Refresh Token** - To renew access token (never expires)
3. **Client ID** - Your app identifier
4. **Client Secret** - For token refresh

## ✅ What I've Done

### 1. Fixed Your .env File

Updated variable names to match standard format:
```bash
CTRADER_CLIENT_ID=19103_504eATsGZ5s57offfwCL88DhVBP0Cq3QZsZCiv8fHZeTReMz1C
CTRADER_CLIENT_SECRET=Zvn4n9Ksmwv8pzzBE8lfusXtcp2MzzCTqgDaWlF2c9wJpHHGiK
CTRADER_ACCESS_TOKEN=23_94-Twwh6hxuZH7xdBXQKmnv4TVapIuUQ6rNtmTGI
CTRADER_REFRESH_TOKEN=-KfKAL88cHYCE3S__3CSz_QSgwfJ3pg59Msv9OcVZg8
```

### 2. Created Proper Protobuf Client

**File:** `infra/ctrader_protobuf_client.py`

This is the official way to connect to cTrader API using Protocol Buffers.

### 3. Updated REST Client (Limited Use)

**File:** `infra/ctrader_client.py`

Note: This can only refresh tokens, NOT fetch market data.

### 4. Created Documentation

- `docs/CTRADER_API_GUIDE.md` - Technical overview
- `docs/CTRADER_SETUP_COMPLETE.md` - This file

### 5. Added Setup Script

**File:** `scripts/setup_ctrader.sh`

Installs required Python packages.

## 🚀 Quick Start

### Step 1: Install Dependencies

```bash
# Activate your virtual environment
source .venv/bin/activate

# Run setup script
./scripts/setup_ctrader.sh

# Or install manually
pip install ctrader-open-api twisted pyOpenSSL service_identity
```

### Step 2: Verify Credentials

Your credentials are already in `.env`. Make sure they're current:

```bash
# Check if access token is still valid (30-day expiry)
# If expired, get new tokens from Playground
```

### Step 3: Test Connection

```bash
python infra/ctrader_protobuf_client.py
```

## 📊 How to Fetch Data

### Historical Candlestick Data

```python
from infra.ctrader_protobuf_client import CTraderProtobufClient
from datetime import datetime, timedelta, timezone

# Create client
client = CTraderProtobufClient(host_type="demo")  # or "live"
client.connect()

# Fetch symbols first
symbols = client.get_symbols()

# Fetch historical data
to_ts = datetime.now(timezone.utc)
from_ts = to_ts - timedelta(days=7)

trendbars = client.get_trendbars(
    symbol="EURUSD",
    timeframe="H1",  # M1, M5, M15, M30, H1, H4, D1, W1, MN1
    from_ts=from_ts,
    to_ts=to_ts,
    count=100
)

# Each trendbar contains:
# - timestamp (milliseconds)
# - datetime (Python datetime object)
# - open, high, low, close (actual prices)
# - volume
```

### Live Streaming Data

For real-time data, you'll need to:

1. Subscribe to spot events (`ProtoOASubscribeSpotsReq`)
2. Subscribe to live trendbars (`ProtoOASubscribeLiveTrendbarReq`)
3. Handle incoming `ProtoOASpotEvent` messages

## 🔑 Symbol IDs

Every instrument has a numeric ID. Common examples:

| Symbol | Typical ID |
|--------|------------|
| EURUSD | 1 |
| GBPUSD | 2 |
| USDJPY | 3 |
| AUDUSD | 4 |
| USDCAD | 5 |
| XAUUSD | 6 |

**Important:** IDs may vary by broker. Always fetch the symbol list first!

## 🔄 Message Flow

```
1. Connect to TCP/WebSocket
   ↓
2. ProtoOAApplicationAuthReq (client_id, client_secret)
   ↓
3. ProtoOAGetAccountListByAccessTokenReq (access_token)
   ↓
4. ProtoOAAccountAuthReq (account_id, access_token)
   ↓
5. ProtoOASymbolsListReq (get symbol IDs)
   ↓
6. ProtoOAGetTrendbarsReq (fetch historical data)
   ↓
7. ProtoOAGetTrendbarsRes (receive data)
```

## 📐 Data Format

Trendbars use **relative pricing** to save bandwidth:

```python
# Convert relative to actual prices
low = trendbar.low / 100000.0
high = (trendbar.low + trendbar.deltaHigh) / 100000.0
open = (trendbar.low + trendbar.deltaOpen) / 100000.0
close = (trendbar.low + trendbar.deltaClose) / 100000.0

# Round to symbol digits (usually 5 for forex)
low = round(low, 5)
```

## ⏱️ Timeframe Constraints

Maximum lookback periods vary by timeframe:

| Timeframe | Max Period |
|-----------|------------|
| M1 | ~1 week |
| M5 | ~2 weeks |
| M15 | ~1 month |
| H1 | ~3 months |
| H4 | ~1 year |
| D1 | ~5 years |

## 🔐 Token Management

### Access Token
- Expires in 30 days (2,628,000 seconds)
- Used for all API calls
- Refresh before expiry

### Refresh Token
- Never expires
- Used to get new access token
- Keep it secret!

### Refresh Example

```python
import requests
from requests.auth import HTTPBasicAuth

response = requests.post(
    "https://openapi.ctrader.com/apps/token",
    auth=HTTPBasicAuth(client_id, client_secret),
    params={
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }
)

data = response.json()
new_access_token = data["accessToken"]
new_refresh_token = data["refreshToken"]

# Update your .env file with new tokens
```

## 🌐 Connection Endpoints

### Demo (Sandbox)
- Host: `demo.ctraderapi.com`
- Port: `5035`
- Use for testing

### Live (Production)
- Host: `live.ctraderapi.com`
- Port: `5035`
- Use for real trading

## 📚 Resources

- [Official Documentation](https://help.ctrader.com/open-api/)
- [Python SDK GitHub](https://github.com/spotware/OpenApiPy)
- [.NET SDK GitHub](https://github.com/spotware/OpenAPI.Net)
- [Protobuf Messages Reference](https://help.ctrader.com/open-api/messages/)
- [Symbol Data Guide](https://help.ctrader.com/open-api/symbol-data/)

## 🐛 Troubleshooting

### "404 Not Found" Error
- You're trying to use REST endpoints that don't exist
- Use Protobuf client instead

### "401 Unauthorized" Error
- Access token expired (30-day limit)
- Get new token from Playground or use refresh token

### "No accounts found"
- Access token not linked to any trading accounts
- Re-authorize in Playground

### Connection Timeout
- Check firewall settings (port 5035)
- Verify host (demo vs live)
- Ensure SSL/TLS is enabled

### Symbol Not Found
- Fetch symbol list first with `get_symbols()`
- Symbol names are case-sensitive
- Some symbols may not be available on your broker

## 💡 Next Steps

1. **Install dependencies**: `./scripts/setup_ctrader.sh`
2. **Test connection**: `python infra/ctrader_protobuf_client.py`
3. **Integrate with your journal**: Update `infra/ctrader_ingest.py` to use Protobuf client
4. **Set up auto-refresh**: Create cron job to refresh access token every 25 days

## ⚠️ Important Notes

- **REST API is NOT for market data** - Only for OAuth
- **Protobuf is required** - No way around it
- **Async/callbacks** - API uses event-driven architecture
- **Rate limits** - Be mindful of request frequency
- **Heartbeats** - Send every 10 seconds to keep connection alive

---

**Questions?** Check the official docs or the code comments in `ctrader_protobuf_client.py`.
