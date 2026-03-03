# cTrader Integration Testing Guide

This guide will help you test the cTrader integration, fetch trades, and generate charts.

## Prerequisites

1. **cTrader Account** - You need a cTrader trading account
2. **API Credentials** - Register at [cTrader Open API](https://openapi.ctrader.com/)
3. **Python Environment** - Python 3.9+ with dependencies installed

## Step 1: Get cTrader API Credentials

### Register Application

1. Go to [cTrader Open API](https://openapi.ctrader.com/)
2. Sign in with your cTrader ID
3. Create a new application:
   - Name: "Lingonberry Journal"
   - Redirect URI: `http://localhost:5000/callback` (or your webapp URL)
   - Permissions: Select all trading and account permissions

4. Note down:
   - **Client ID**
   - **Client Secret**

### Get Access Token

You need to complete OAuth2 flow to get access token. Two options:

#### Option A: Use cTrader Playground (Easiest)

1. Go to [cTrader API Playground](https://openapi.ctrader.com/playground)
2. Authorize your application
3. Copy the **Access Token** and **Refresh Token**

#### Option B: Manual OAuth Flow

```bash
# 1. Get authorization code
# Open in browser:
https://openapi.ctrader.com/oauth/authorize?client_id=YOUR_CLIENT_ID&redirect_uri=http://localhost:5000/callback&scope=trading&response_type=code

# 2. After authorization, you'll be redirected with a code
# Extract the code from URL: http://localhost:5000/callback?code=AUTHORIZATION_CODE

# 3. Exchange code for tokens
curl -X POST https://openapi.ctrader.com/oauth/token \
  -u "YOUR_CLIENT_ID:YOUR_CLIENT_SECRET" \
  -d "grant_type=authorization_code" \
  -d "code=AUTHORIZATION_CODE" \
  -d "redirect_uri=http://localhost:5000/callback"

# Response will contain access_token and refresh_token
```

### Get Account ID

```bash
# Use the access token to get your account ID
curl -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  https://openapi.ctrader.com/v2/accounts
```

Look for `ctidTraderAccountId` in the response.

## Step 2: Configure Environment

Edit your `.env` file:

```bash
# cTrader API Credentials
CTRADER_CLIENT_ID=your_client_id_here
CTRADER_CLIENT_SECRET=your_client_secret_here
CTRADER_ACCESS_TOKEN=your_access_token_here
CTRADER_REFRESH_TOKEN=your_refresh_token_here
CTRADER_ACCOUNT_ID=your_account_id_here
```

## Step 3: Test Connection

```bash
# Activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Test basic connection
python infra/ctrader_client.py
```

Expected output:
```
🔌 Testing cTrader API connection...

✅ Connected to cTrader API - Found 1 account(s)

📊 Fetching account info...
  Account: 12345678 - IC Markets
  Balance: 50000.00 USD
  Account ID: 1234567

📈 Fetching open positions for account 1234567...
  Found 0 open position(s)

📜 Fetching recent closed trades...
  Found 5 recent trade(s)

  Latest trade:
    Symbol: GBPJPY
    Volume: 50000
    Entry: 191.50000
    Close: 192.00000
    P&L: 250.00

✅ Connection test completed
```

## Step 4: Fetch and Export Trades

```bash
# Run comprehensive test suite
python scripts/test_ctrader.py
```

This will:
1. Test connection
2. Fetch last 30 days of trades
3. Save to CSV and Parquet in `data/exports/`
4. Fetch market data for GBPJPY (5M, 30M, 4H)
5. Save market data to CSV and Parquet

Expected output:
```
🚀 cTrader Integration Test Suite

============================================================
TEST 1: Connection Test
============================================================

✅ Connection successful!

Found 1 account(s):
  - 12345678 (IC Markets)
    Balance: 50000.0 USD
    ID: 1234567

============================================================
TEST 2: Fetch Historical Trades
============================================================

Fetching trades from 2026-02-01 to 2026-03-02...
✅ Found 15 trade(s)

✅ Saved to CSV: data/exports/ctrader_trades_20260302_120000.csv
✅ Saved to Parquet: data/exports/ctrader_trades_20260302_120000.parquet

📊 Trade Summary:
  Total Trades: 15
  Total P&L: 1250.50
  Winning Trades: 9
  Losing Trades: 6
  Win Rate: 60.0%

📈 Top 5 Trades:
   symbolName direction     pnl           open_time
0      GBPJPY      LONG  450.00 2026-02-28 10:30:00
1      EURUSD     SHORT  320.50 2026-02-27 14:15:00
...

============================================================
TEST 3: Fetch Market Data (Trendbars)
============================================================

Fetching GBPJPY 5m data...
  ✅ Found 2016 candles
  ✅ Saved to CSV: data/exports/ctrader_GBPJPY_5m_20260302_120000.csv
  ✅ Saved to Parquet: data/exports/ctrader_GBPJPY_5m_20260302_120000.parquet

  Sample data (first 3 rows):
                 time      open      high       low     close  volume
0 2026-02-23 00:00:00  191.4500  191.4600  191.4400  191.4550   12345
1 2026-02-23 00:05:00  191.4550  191.4700  191.4500  191.4650   15678
2 2026-02-23 00:10:00  191.4650  191.4800  191.4600  191.4750   13456

...

============================================================
✅ All tests passed!
============================================================

Exported files are in: /path/to/data/exports
```

## Step 5: Visualize Trades on Charts

```bash
# Generate 3-timeframe charts for recent trades
python scripts/visualize_trades.py
```

This will:
1. Fetch your most recent trade
2. Generate 3 charts (4H, 30M, 5M)
3. Mark entry, exit, SL, TP on charts
4. Save to `data/reports/`

Expected output:
```
📈 Trade Visualization Tool

Fetching recent trades...
✅ Found 5 trade(s)

Generating charts for the most recent trade...

📊 Visualizing trade: GBPJPY BUY
   Opened: 2026-03-01 08:54:41
   Closed: 2026-03-01 10:30:15
   P&L: 250.00

  Generating 4H chart...
  ✅ Saved chart: trade_GBPJPY_4H_20260302_120000.png

  Generating 30M chart...
  ✅ Saved chart: trade_GBPJPY_30M_20260302_120000.png

  Generating 5M chart...
  ✅ Saved chart: trade_GBPJPY_5M_20260302_120000.png

============================================================
✅ Visualization complete!
============================================================

Charts saved to: /path/to/data/reports
```

## Troubleshooting

### Error: "Missing cTrader credentials"

- Check your `.env` file has all required variables
- Make sure you're in the project root directory
- Verify credentials are correct (no extra spaces)

### Error: "401 Unauthorized"

- Your access token has expired
- Run the test again - it will automatically refresh the token
- Update your `.env` with the new tokens printed in the output

### Error: "No trades found"

- Your account might not have any closed trades in the last 30 days
- Try paper trading or demo account first
- Check if you're using the correct account ID

### Error: "No data available for timeframe"

- Some symbols might not have data for all timeframes
- Try a different symbol (EURUSD, GBPUSD are usually available)
- Check if your broker provides historical data

## Next Steps

Once testing is successful:

1. **Import trades to database**:
   ```bash
   python jobs/ctrader_sync.py
   ```

2. **View in web dashboard**:
   ```bash
   make webapp
   # Open http://localhost:5000
   ```

3. **Set up automatic sync** (optional):
   - Edit `jobs/ctrader_sync.py` to run on schedule
   - Or use cron/systemd timer

## API Rate Limits

cTrader API has rate limits:
- 100 requests per minute
- 1000 requests per hour

The scripts include automatic retry and backoff logic.

## Security Notes

- Never commit your `.env` file to git
- Keep your access tokens secure
- Refresh tokens regularly (they expire after 30 days)
- Use environment variables in production

## Resources

- [cTrader Open API Docs](https://openapi.ctrader.com/docs)
- [API Reference](https://openapi.ctrader.com/api-reference)
- [OAuth2 Guide](https://openapi.ctrader.com/guides/oauth)
- [Rate Limits](https://openapi.ctrader.com/guides/rate-limits)
