# Local Testing Guide

Quick guide to test everything works before deploying to Oracle.

## Setup

```bash
# 1. Install dependencies
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
```

Edit `.env`:
```bash
TELEGRAM_JOURAL=your_bot_token_from_botfather
TELEGRAM_JOURNAL_CHAT=your_telegram_user_id
WEBAPP_URL=http://localhost:5000/mini
WEBAPP_PORT=5000
```

## Test 1: Database

```bash
python3 -c "from bot import journal_db; journal_db.init_db(); print('✅ Database initialized')"
```

Should create `data/journal.db`

## Test 2: Create Test Account

```bash
python3 << 'EOF'
from bot import journal_db
journal_db.init_db()
account_id = journal_db.create_account(
    name="Test Account",
    currency="USD",
    initial_balance=10000,
    max_daily_loss_pct=5.0,
    max_total_loss_pct=10.0,
    profit_target_pct=10.0,
    risk_per_trade_pct=1.0
)
print(f"✅ Account created with ID: {account_id}")
EOF
```

## Test 3: Webapp

```bash
# Start webapp
make webapp
# Or: python3 webapp/app.py
```

Open browser:
- Main dashboard: http://localhost:5000
- Mini App: http://localhost:5000/mini
- API test: http://localhost:5000/api/dashboard

Should see dashboard with your test account.

## Test 4: Telegram Bot

In a new terminal:

```bash
source .venv/bin/activate
make bot
# Or: python3 bot/journal_daemon.py
```

On Telegram:
1. Send `/start` to your bot
2. Should get welcome message
3. Send `/stats` - should show your test account
4. Send `/mini` - should get button to open Mini App

## Test 5: Log a Test Trade

On Telegram, send `/journal` and follow the prompts:

```
Bot: 💱 Asset symbol?
You: EURUSD

Bot: 🧭 Direction?
You: long

Bot: 💰 Entry price?
You: 1.0850

Bot: 🛑 Stop Loss price?
You: 1.0800

Bot: 🎯 Take Profit price?
You: 1.0950

Bot: ⏰ Entry time?
You: now

Bot: 📝 Setup notes/tags?
You: Test trade

Bot: 🧠 Mental state?
You: skip

Bot: 🌦 Market condition?
You: skip

Bot: 📦 Lot size?
You: 1.0
```

Should get confirmation with trade ID and charts.

## Test 6: View Trade in Dashboard

Refresh http://localhost:5000/mini

Should see:
- Updated stats (1 trade)
- Trade in "Recent Trades" list
- Equity curve updated

## Test 7: API Endpoints

```bash
# Get dashboard data
curl http://localhost:5000/api/dashboard | jq

# Get all trades
curl http://localhost:5000/api/trades | jq

# Get open trades
curl http://localhost:5000/api/trades/open | jq

# Get accounts
curl http://localhost:5000/api/accounts | jq
```

All should return JSON data.

## Test 8: Chart Generation

Check if charts were generated:

```bash
ls -lh data/reports/
```

Should see PNG files like:
- `trade_EURUSD_LONG_H4_20260303_123456.png`
- `trade_EURUSD_LONG_M30_20260303_123456.png`
- `trade_EURUSD_LONG_M5_20260303_123456.png`

## Test 9: Close Trade

```bash
# Get trade ID from dashboard or:
python3 << 'EOF'
from bot import journal_db
trades = journal_db.get_open_trades()
if trades:
    trade_id = trades[0]['id']
    closed = journal_db.close_trade(
        trade_id=trade_id,
        exit_price=1.0900,
        outcome="TP",
        event_type="manual_close",
        provider="test"
    )
    print(f"✅ Trade {trade_id} closed")
    print(f"P&L: {closed['pnl_usd']:.2f}")
else:
    print("No open trades")
EOF
```

Refresh dashboard - should see updated P&L.

## Test 10: Mini App in Telegram

1. On Telegram, send `/mini` to your bot
2. Tap the "Open Mini App" button
3. Should open the dashboard inside Telegram
4. Should see all your trades and stats

**Note**: Mini App might not work perfectly in local development because Telegram requires HTTPS. This will work properly after deployment.

## Common Issues

### Bot not responding
- Check `TELEGRAM_JOURAL` token is correct
- Check `TELEGRAM_JOURNAL_CHAT` matches your user ID
- Check bot is running: `ps aux | grep journal_daemon`

### Webapp shows error
- Check Flask is running on port 5000
- Check database exists: `ls data/journal.db`
- Check logs for errors

### Charts not generating
- Check market data is available
- Check `data/reports/` directory exists and is writable
- Charts might fail for some symbols - this is normal

### Mini App not loading in Telegram
- This is expected in local development
- Telegram Mini Apps require HTTPS
- Will work after deployment with proper domain

## Clean Up

To start fresh:

```bash
# Stop services
pkill -f journal_daemon
pkill -f "python3 webapp/app.py"

# Remove database
rm data/journal.db

# Remove charts
rm data/reports/*.png

# Reinitialize
python3 -c "from bot import journal_db; journal_db.init_db()"
```

## Next Steps

Once everything works locally:
1. Commit your changes (but NOT `.env`!)
2. Push to GitHub
3. Follow [DEPLOYMENT.md](DEPLOYMENT.md) to deploy to Oracle

## Quick Commands Reference

```bash
# Start bot
make bot

# Start webapp
make webapp

# Run both (in background)
make bot &
make webapp

# Stop all
pkill -f journal_daemon
pkill -f "python3 webapp/app.py"

# View logs
tail -f data/logs/bot.log
tail -f data/logs/webapp.log

# Test database
python3 -c "from bot import journal_db; print(journal_db.get_stats())"
```

---

Everything working? Great! Time to deploy to Oracle. See [DEPLOYMENT.md](DEPLOYMENT.md).
