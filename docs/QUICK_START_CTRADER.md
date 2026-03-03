# cTrader Integration - Quick Start

## 🚀 5-Minute Setup

### 1. Install Dependencies
```bash
make install
```

### 2. Configure Credentials

Add to `.env`:
```bash
CTRADER_CLIENT_ID=your_client_id
CTRADER_CLIENT_SECRET=your_client_secret
CTRADER_ACCOUNT_ID=your_account_id
```

### 3. Test Connection
```bash
make ctrader-test
```

### 4. Import Trades
```bash
make ctrader-sync
```

### 5. View Results
```bash
make run-web
# Open http://localhost:5000
```

## 📋 Common Commands

| Command | Description |
|---------|-------------|
| `make ctrader-test` | Test API connection |
| `make ctrader-sync` | Sync trades (incremental) |
| `.venv/bin/python jobs/ctrader_sync.py historical 90` | Import last 90 days |
| `.venv/bin/python jobs/ctrader_sync.py open` | Sync open positions only |

## 🔄 Automatic Sync

### Option 1: Cron (Recommended)
```bash
crontab -e
# Add:
*/5 * * * * cd /path/to/trading-journal && .venv/bin/python jobs/ctrader_sync.py
```

### Option 2: Run Script
```bash
bash scripts/setup_ctrader.sh
```

## ✅ Verification Checklist

- [ ] Credentials configured in `.env`
- [ ] Connection test passes
- [ ] Historical trades imported
- [ ] Trades visible in web dashboard
- [ ] Automatic sync configured (optional)

## 🐛 Troubleshooting

### "Authentication failed"
- Check Client ID and Secret
- Verify account is active
- Try regenerating credentials

### "No trades imported"
- Verify Account ID is correct
- Check if you have closed positions
- Try longer time range: `historical 180`

### "Duplicate trades"
- Normal on first run
- Sync job prevents duplicates automatically
- Check `external_trade_id` field

## 📚 Full Documentation

See [CTRADER_SETUP.md](./CTRADER_SETUP.md) for detailed instructions.

## 🎯 What Gets Imported

✅ Entry/Exit prices  
✅ Stop Loss / Take Profit  
✅ Lot size  
✅ P&L (gross and net)  
✅ Commission and swap  
✅ Open and close timestamps  
✅ Trade direction  

## 🔜 Coming Soon

- Real-time position monitoring
- Webhook integration
- Multi-account sync
- Advanced trade analytics

---

**Need Help?** Check the logs: `data/logs/ctrader_sync.log`
