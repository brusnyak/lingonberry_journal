# Quick Start: cTrader Integration

Get your cTrader data flowing in 5 minutes!

## Step 1: Get API Credentials (5 min)

1. Go to https://openapi.ctrader.com/
2. Sign in with your cTrader ID
3. Create new application:
   - Name: "Lingonberry Journal"
   - Redirect: `http://localhost:5000/callback`
   - Permissions: Select all
4. Copy **Client ID** and **Client Secret**

5. Get tokens from [API Playground](https://openapi.ctrader.com/playground):
   - Authorize your app
   - Copy **Access Token** and **Refresh Token**

6. Get your **Account ID**:
   ```bash
   curl -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
     https://openapi.ctrader.com/v2/accounts
   ```
   Look for `ctidTraderAccountId` in response.

## Step 2: Configure (1 min)

Edit `.env`:

```bash
CTRADER_CLIENT_ID=your_client_id
CTRADER_CLIENT_SECRET=your_client_secret
CTRADER_ACCESS_TOKEN=your_access_token
CTRADER_REFRESH_TOKEN=your_refresh_token
CTRADER_ACCOUNT_ID=your_account_id
```

## Step 3: Test (1 min)

```bash
# Test connection
make ctrader-test
```

Expected: ✅ Connected to cTrader API

## Step 4: Fetch Data (2 min)

```bash
# Fetch trades and save to CSV/Parquet
make ctrader-fetch
```

This will:
- Fetch last 30 days of trades
- Save to `data/exports/ctrader_trades_*.csv`
- Save to `data/exports/ctrader_trades_*.parquet`
- Fetch GBPJPY market data (5M, 30M, 4H)
- Show trade summary

## Step 5: Visualize (1 min)

```bash
# Generate charts with trade markers
make ctrader-viz
```

This will:
- Take your most recent trade
- Generate 3 charts (4H, 30M, 5M)
- Mark entry, exit, SL, TP
- Save to `data/reports/trade_*.png`

## Done! 🎉

You now have:
- ✅ Working cTrader connection
- ✅ Historical trades in CSV/Parquet
- ✅ Market data for multiple timeframes
- ✅ Beautiful charts with trade markers

## Next Steps

### Import to Database

```bash
make ctrader-sync
```

### View in Dashboard

```bash
make webapp
# Open http://localhost:5000
```

### Automate Sync

Add to cron or use the background job:
```bash
make run-all  # Starts bot, webapp, and auto-sync
```

## Troubleshooting

### "Missing cTrader credentials"
- Check your `.env` file
- Make sure all 5 variables are set

### "401 Unauthorized"
- Token expired - run `make ctrader-test` again
- It will auto-refresh and show new tokens
- Update your `.env` with new tokens

### "No trades found"
- Your account has no trades in last 30 days
- Try demo/paper trading first
- Or adjust date range in scripts

## Full Documentation

See [docs/CTRADER_TESTING.md](docs/CTRADER_TESTING.md) for detailed guide.

## Commands Reference

```bash
make ctrader-test   # Test connection
make ctrader-fetch  # Fetch trades to CSV/Parquet
make ctrader-viz    # Generate charts
make ctrader-sync   # Import to database
```
