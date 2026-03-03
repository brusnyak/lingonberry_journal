# cTrader Integration Setup Guide

This guide will help you set up automatic trade import from cTrader to your trading journal.

## Prerequisites

- cTrader account (demo or live)
- cTrader Open API credentials
- Python environment with dependencies installed

## Step 1: Get cTrader API Credentials

### Option A: Using cTrader Open API Portal

1. Go to [cTrader Open API Portal](https://openapi.ctrader.com/)
2. Sign in with your cTrader ID
3. Create a new application:
   - Click "Create Application"
   - Name: "Trading Journal"
   - Redirect URI: `http://localhost:5000/callback` (for local testing)
   - Scopes: Select "trading" and "accounts"
4. Save your credentials:
   - Client ID
   - Client Secret

### Option B: Contact Your Broker

Some brokers provide direct API access. Contact your broker's support team and request:
- API Client ID
- API Client Secret
- API Documentation

## Step 2: Configure Environment Variables

Add the following to your `.env` file:

```bash
# cTrader API Credentials
CTRADER_CLIENT_ID=your_client_id_here
CTRADER_CLIENT_SECRET=your_client_secret_here
CTRADER_ACCOUNT_ID=your_account_id_here

# Optional: If you already have tokens
CTRADER_ACCESS_TOKEN=your_access_token_here
CTRADER_REFRESH_TOKEN=your_refresh_token_here
```

### Finding Your Account ID

1. Log in to cTrader
2. Go to Account Settings
3. Copy your Account ID (usually a long number)

## Step 3: Test Connection

Run the connection test:

```bash
make ctrader-test
```

Expected output:
```
INFO | Authenticating with cTrader...
INFO | Connected to account: 1234567
INFO | Fetching positions...
INFO | Found 5 positions
```

If you see errors:
- Check your credentials in `.env`
- Verify your account ID is correct
- Ensure your API application has the correct scopes

## Step 4: Initial Sync

Import your historical trades (last 90 days):

```bash
.venv/bin/python jobs/ctrader_sync.py historical 90
```

This will:
- Fetch all closed positions from the last 90 days
- Import them into your journal database
- Create a cTrader account in your journal if it doesn't exist

Expected output:
```
INFO | Starting historical sync for last 90 days
INFO | Fetched 45 historical positions from cTrader
INFO | Imported trade #123: GBPJPY long
INFO | Imported trade #124: EURUSD short
...
INFO | Historical sync complete: {'fetched': 45, 'imported': 45, 'skipped': 0, 'errors': 0}
```

## Step 5: Set Up Automatic Sync

### Option A: Manual Sync

Run sync manually whenever you want to update:

```bash
make ctrader-sync
```

### Option B: Scheduled Sync (Recommended)

Add to your crontab to sync every 5 minutes:

```bash
# Edit crontab
crontab -e

# Add this line (adjust path to your project)
*/5 * * * * cd /path/to/trading-journal && .venv/bin/python jobs/ctrader_sync.py >> data/logs/ctrader_sync.log 2>&1
```

### Option C: Background Service

Create a systemd service (Linux) or launchd service (macOS):

**macOS (launchd):**

Create `~/Library/LaunchAgents/com.tradingjournal.ctrader.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.tradingjournal.ctrader</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/trading-journal/.venv/bin/python</string>
        <string>/path/to/trading-journal/jobs/ctrader_sync.py</string>
    </array>
    <key>StartInterval</key>
    <integer>300</integer>
    <key>WorkingDirectory</key>
    <string>/path/to/trading-journal</string>
    <key>StandardOutPath</key>
    <string>/path/to/trading-journal/data/logs/ctrader_sync.log</string>
    <key>StandardErrorPath</key>
    <string>/path/to/trading-journal/data/logs/ctrader_sync_error.log</string>
</dict>
</plist>
```

Load the service:
```bash
launchctl load ~/Library/LaunchAgents/com.tradingjournal.ctrader.plist
```

## Step 6: Verify Sync

Check your journal for imported trades:

```bash
# Via web app
open http://localhost:5000

# Via Telegram bot
/stats
/open
```

You should see trades with source "ctrader_api" in the notes.

## Troubleshooting

### Authentication Errors

**Error:** `401 Unauthorized`

**Solution:**
- Verify your Client ID and Secret are correct
- Check if your API application is active
- Try regenerating your credentials

### No Trades Imported

**Error:** `Fetched 0 positions`

**Solution:**
- Verify your Account ID is correct
- Check if you have any closed positions in the time range
- Try increasing the `days_back` parameter: `python jobs/ctrader_sync.py historical 180`

### Duplicate Trades

**Error:** Trades are being imported multiple times

**Solution:**
- The sync job checks for duplicates using position ID
- If you see duplicates, check the `external_trade_id` field in the database
- Delete duplicates manually: `DELETE FROM trades WHERE source='ctrader_api' AND id > X`

### Token Expired

**Error:** `403 Forbidden` or `Token expired`

**Solution:**
- The client will automatically refresh tokens
- If refresh fails, delete `CTRADER_ACCESS_TOKEN` and `CTRADER_REFRESH_TOKEN` from `.env`
- Run `make ctrader-test` to re-authenticate

## Data Mapping

cTrader positions are mapped to journal trades as follows:

| cTrader Field | Journal Field | Notes |
|--------------|---------------|-------|
| positionId | external_trade_id | Unique identifier |
| symbolName | symbol | Trading pair |
| tradeSide | direction | BUY → long, SELL → short |
| entryPrice | entry | Entry price |
| stopLoss | sl | Stop loss price |
| takeProfit | tp | Take profit price |
| volume | lot_size | Converted to lots (÷100000) |
| openTimestamp | ts_open | ISO format |
| closeTimestamp | ts_close | ISO format (if closed) |
| grossProfit | pnl_usd | Gross P&L |
| netProfit | pnl_usd | Net P&L (after fees) |
| commission | notes | Included in notes |
| swap | notes | Included in notes |

## Advanced Configuration

### Custom Sync Interval

Edit `jobs/ctrader_sync.py` and modify the sync logic:

```python
# Sync last 7 days instead of 90
result = sync_job.sync_historical_trades(days_back=7)
```

### Multiple Accounts

To sync multiple cTrader accounts:

1. Create separate journal accounts for each cTrader account
2. Run sync with specific account ID:

```python
sync_job = CTraderSyncJob(account_id=2)  # Journal account ID
sync_job.run_once()
```

### Webhook Integration (Future)

cTrader supports webhooks for real-time trade notifications. This will be implemented in a future update.

## Support

If you encounter issues:

1. Check the logs: `data/logs/ctrader_sync.log`
2. Enable debug logging in `jobs/ctrader_sync.py`:
   ```python
   logging.basicConfig(level=logging.DEBUG)
   ```
3. Review cTrader API documentation: https://help.ctrader.com/open-api/
4. Contact your broker's API support team

## Next Steps

After successful sync:
- Review imported trades in the web dashboard
- Add notes and psychology data to trades
- Generate trade charts for analysis
- Set up weekly reviews

---

**Last Updated:** March 1, 2026
