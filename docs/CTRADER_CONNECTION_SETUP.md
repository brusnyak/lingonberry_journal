# cTrader Historical + Live Data Setup

This project is wired to use cTrader Open API Protobuf for market data.

## 1) Install dependencies

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

## 2) Configure environment

Required keys in `.env`:

- `CTRADER_CLIENT_ID`
- `CTRADER_CLIENT_SECRET`
- `CTRADER_ACCESS_TOKEN`
- `CTRADER_REFRESH_TOKEN`

Optional:

- `CTRADER_ACCOUNT_ID` (if not set, first account from token is used)
- `CTRADER_HOST_TYPE=demo` (`demo` or `live`)

## 3) Connection test

```bash
python infra/ctrader_client.py
```

Expected:

- account list loaded
- symbols loaded
- sample `EURUSD` live quote attempt

## 4) Historical data usage

Use `infra/market_data.py` (already integrated) with source `ctrader`.
It calls `CTraderClient.get_trendbars()` under the hood.

## 5) Live quote usage

Use:

```python
from infra.ctrader_client import CTraderClient

client = CTraderClient()
client.connect()
quote = client.get_live_quote("EURUSD")
print(quote)
client.disconnect()
```

## Notes

- cTrader Open API market data is Protobuf/TCP based, not REST `v1/v2` endpoints.
- Token refresh is done via `https://openapi.ctrader.com/apps/token`.
- Python SDK package: `ctrader-open-api` (import path: `ctrader_open_api`).
