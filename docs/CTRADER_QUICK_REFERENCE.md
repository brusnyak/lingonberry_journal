# cTrader API - Quick Reference Card

## 🔑 Credentials (from Playground)

```bash
# Get from: https://openapi.ctrader.com/apps
CTRADER_CLIENT_ID=your_client_id
CTRADER_CLIENT_SECRET=your_client_secret
CTRADER_ACCESS_TOKEN=your_access_token      # Expires in 30 days
CTRADER_REFRESH_TOKEN=your_refresh_token    # Never expires
```

## 🚀 Installation

```bash
pip install ctrader-open-api twisted pyOpenSSL service_identity
```

## 📡 Connection

```python
from infra.ctrader_protobuf_client import CTraderProtobufClient

client = CTraderProtobufClient(host_type="demo")  # or "live"
client.connect()
```

## 📊 Fetch Historical Data

```python
from datetime import datetime, timedelta, timezone

# Get symbols first
symbols = client.get_symbols()

# Fetch candles
to_ts = datetime.now(timezone.utc)
from_ts = to_ts - timedelta(days=7)

data = client.get_trendbars(
    symbol="EURUSD",
    timeframe="H1",  # M1, M5, M15, M30, H1, H4, D1, W1, MN1
    from_ts=from_ts,
    to_ts=to_ts,
    count=100
)
```

## ⏱️ Timeframes

| Code | Period | Max Lookback |
|------|--------|--------------|
| M1 | 1 minute | ~1 week |
| M5 | 5 minutes | ~2 weeks |
| M15 | 15 minutes | ~1 month |
| M30 | 30 minutes | ~2 months |
| H1 | 1 hour | ~3 months |
| H4 | 4 hours | ~1 year |
| D1 | 1 day | ~5 years |
| W1 | 1 week | ~10 years |
| MN1 | 1 month | All history |

## 🎯 Common Symbols

| Symbol | Name | Typical ID |
|--------|------|------------|
| EURUSD | Euro/US Dollar | 1 |
| GBPUSD | British Pound/US Dollar | 2 |
| USDJPY | US Dollar/Japanese Yen | 3 |
| AUDUSD | Australian Dollar/US Dollar | 4 |
| USDCAD | US Dollar/Canadian Dollar | 5 |
| XAUUSD | Gold/US Dollar | 6 |

**Note:** IDs vary by broker - always fetch symbol list!

## 🔄 Refresh Access Token

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

tokens = response.json()
# Update .env with tokens["accessToken"] and tokens["refreshToken"]
```

## 📐 Data Structure

```python
# Each trendbar contains:
{
    'timestamp': 1709481600000,  # Unix timestamp (ms)
    'datetime': datetime(2024, 3, 3, 12, 0, 0),  # Python datetime
    'open': 1.08234,
    'high': 1.08456,
    'low': 1.08123,
    'close': 1.08345,
    'volume': 12345
}
```

## 🌐 Endpoints

| Environment | Host | Port |
|-------------|------|------|
| Demo | demo.ctraderapi.com | 5035 |
| Live | live.ctraderapi.com | 5035 |

## ⚠️ Key Points

- ❌ **NO REST API** for market data
- ✅ **Protobuf required** for all data fetching
- 🔐 **Access token** expires in 30 days
- 🔄 **Refresh token** never expires
- 💓 **Heartbeat** every 10 seconds
- 📊 **Max 1000 bars** per request

## 🐛 Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| 404 Not Found | Using REST for data | Use Protobuf client |
| 401 Unauthorized | Token expired | Refresh access token |
| Symbol not found | Wrong symbol name | Fetch symbol list first |
| Connection timeout | Firewall/port blocked | Check port 5035 access |

## 📚 Files

| File | Purpose |
|------|---------|
| `infra/ctrader_protobuf_client.py` | Main Protobuf client |
| `infra/ctrader_client.py` | Token refresh only |
| `docs/CTRADER_API_GUIDE.md` | Technical guide |
| `docs/CTRADER_SETUP_COMPLETE.md` | Full setup guide |
| `scripts/setup_ctrader.sh` | Installation script |

## 🔗 Resources

- Playground: https://openapi.ctrader.com/apps
- Docs: https://help.ctrader.com/open-api/
- Python SDK: https://github.com/spotware/OpenApiPy
