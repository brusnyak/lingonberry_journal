# Trading Journal Bot 📊

A comprehensive trading journal system with Telegram bot integration, web dashboard, and cTrader API support.

## Features

- 📱 **Telegram Bot** - Conversational trade logging with guided flow
- 🌐 **Web Dashboard** - Analytics, charts, and performance tracking
- 📈 **Chart Generation** - Automatic candlestick charts with entry/SL/TP markers
- 🔄 **cTrader Integration** - Automatic trade import from cTrader accounts
- 📊 **Advanced Analytics** - Win rate, expectancy, Sharpe ratio, Monte Carlo simulation
- 🎯 **Weekly Goals** - Track adherence to trading plans
- 🧠 **Psychology Tracking** - Mood, stress, confidence metrics
- 💼 **Multi-Account Support** - Manage multiple prop firm accounts

## Quick Start

### 1. Installation

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/trading-journal.git
cd trading-journal

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env and add your credentials:
# - TELEGRAM_JOURAL (bot token from @BotFather)
# - TELEGRAM_JOURNAL_CHAT (your chat ID)
# - WEBAPP_URL (public URL for mini app)
# - CTRADER_* credentials (optional - see QUICKSTART_CTRADER.md)
```

### 3. Run

```bash
# Start Telegram bot
make bot

# Start web app (in another terminal)
make webapp

# Run tests
make test
```

## cTrader Integration (NEW!)

Automatically fetch trades and generate charts from your cTrader account.

**Quick Start:**
```bash
# 1. Get API credentials (5 min) - see QUICKSTART_CTRADER.md
# 2. Add to .env
# 3. Test connection
make ctrader-test

# 4. Fetch trades to CSV/Parquet
make ctrader-fetch

# 5. Generate 3-timeframe charts
make ctrader-viz
```

**What you get:**
- ✅ Historical trades exported to CSV/Parquet
- ✅ Multi-timeframe charts (4H, 30M, 5M)
- ✅ Long/Short position markers
- ✅ Entry, Exit, SL, TP visualization
- ✅ Automatic data caching

**Documentation:**
- [Quick Start Guide](QUICKSTART_CTRADER.md) - 5-minute setup
- [Detailed Testing Guide](docs/CTRADER_TESTING.md) - Complete reference
- [Implementation Summary](CTRADER_INTEGRATION_SUMMARY.md) - Technical details

## Telegram Bot Commands

- `/start` - Initialize bot and setup account
- `/journal` - Log a new trade
- `/open` - View open trades
- `/close [id] [exit_price]` - Close a trade
- `/stats` - View performance statistics
- `/report` - Open web dashboard
- `/mini` - Open Telegram Mini App
- `/accounts` - List all accounts
- `/useaccount [id]` - Switch active account
- `/newaccount` - Create new account
- `/setgoal` - Set weekly goal

## Telegram Mini App Setup

To use the Telegram Mini App feature, you need a public HTTPS URL:

### Option 1: ngrok (Quick Testing)
```bash
# Install ngrok
brew install ngrok  # macOS
# or download from ngrok.com

# Start tunnel
ngrok http 5000

# Copy HTTPS URL to .env
WEBAPP_URL=https://your-ngrok-url.ngrok.io
```

### Option 2: Cloudflare Tunnel (Recommended)
```bash
# Install cloudflared
brew install cloudflare/cloudflare/cloudflared

# Start tunnel
cloudflared tunnel --url http://localhost:5000

# Copy HTTPS URL to .env
```

### Option 3: Deploy to Server
```bash
# Set your server IP/domain in .env
WEBAPP_URL=https://your-domain.com

# Deploy using provided scripts
make deploy
```

## cTrader Integration

### Setup

1. Register at [cTrader Open API](https://openapi.ctrader.com/)
2. Create an application and get credentials
3. Add to `.env`:
   ```
   CTRADER_CLIENT_ID=your_client_id
   CTRADER_CLIENT_SECRET=your_client_secret
   CTRADER_ACCOUNT_ID=your_account_id
   CTRADER_ACCESS_TOKEN=your_access_token
   CTRADER_REFRESH_TOKEN=your_refresh_token
   ```

### Test Connection

```bash
python infra/ctrader_client.py
```

### Sync Trades

```bash
python jobs/ctrader_sync.py
```

## Project Structure

```
trading-journal/
├── bot/                    # Telegram bot
│   ├── journal_daemon.py   # Main bot logic
│   ├── journal_db.py       # Database operations
│   ├── chart_generator.py  # Chart generation
│   └── session_detector.py # Trading session detection
├── webapp/                 # Flask web app
│   ├── app.py             # Main app
│   ├── templates/         # HTML templates
│   └── static/            # CSS/JS assets
├── infra/                 # Infrastructure
│   ├── ctrader_client.py  # cTrader API client
│   ├── ctrader_ingest.py  # Trade import
│   └── market_data.py     # Market data fetching
├── core/                  # Core logic
│   ├── exporter.py        # ML dataset export
│   └── monte_carlo.py     # Monte Carlo simulation
├── jobs/                  # Background jobs
│   ├── ctrader_sync.py    # Auto-sync trades
│   └── sltp_poller.py     # SL/TP monitoring
├── scripts/               # Utility scripts
├── tests/                 # Test suite
└── data/                  # Database and cache
```

## Database Schema

- `accounts` - Trading accounts
- `account_rules` - Risk management rules
- `trades` - Trade records
- `trade_psychology` - Psychology metrics
- `trade_process` - Trade review notes
- `weekly_reviews` - Weekly performance reviews
- `weekly_goals` - Weekly trading goals
- `drawings` - Chart drawings and annotations

## API Endpoints

### Accounts
- `GET /api/accounts` - List accounts
- `POST /api/accounts` - Create account
- `POST /api/accounts/:id/rules` - Update rules

### Trades
- `GET /api/trades` - List trades
- `GET /api/trades/open` - Open trades
- `POST /api/trades/:id/close` - Close trade
- `POST /api/trades/:id/review` - Add review note
- `GET /api/trades/:id/events` - Trade events

### Analytics
- `GET /api/dashboard` - Dashboard data
- `GET /api/analytics/monte-carlo` - Monte Carlo stats
- `GET /api/replay/:id` - Trade replay data

### Reviews
- `GET /api/review/week` - Weekly review
- `POST /api/review/week` - Update review
- `GET /api/goals/week` - Weekly goals
- `POST /api/goals/week` - Set goal

## Development

### Run Tests
```bash
pytest tests/
```

### Code Style
```bash
# Format code
black .

# Lint
flake8 .
```

### Database Migrations
```bash
# Database is auto-migrated on startup
# Schema is in bot/journal_db.py:init_db()
```

## Deployment

### GitHub
```bash
# Initialize git
make git-init

# Deploy to GitHub
make deploy
```

### Oracle Cloud VM
```bash
# SSH to VM
ssh ubuntu@YOUR_VM_IP

# Clone and setup
git clone https://github.com/YOUR_USERNAME/trading-journal.git
cd trading-journal
./scripts/setup_ctrader.sh
```

## Troubleshooting

### Bot not responding
- Check `TELEGRAM_JOURAL` token is correct
- Verify bot is running: `ps aux | grep journal_daemon`
- Check logs for errors

### Charts not generating
- Verify market data API keys in `.env`
- Check `data/cache/` directory permissions
- Fallback to simple charts if data unavailable

### cTrader sync failing
- Test connection: `python infra/ctrader_client.py`
- Refresh access token if expired
- Check cTrader API status

### Mini App not loading
- Ensure `WEBAPP_URL` is public HTTPS
- Check webapp is running: `curl $WEBAPP_URL`
- Verify Telegram bot can access URL

## Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature-name`
3. Commit changes: `git commit -am 'Add feature'`
4. Push to branch: `git push origin feature-name`
5. Submit pull request

## License

MIT License - see LICENSE file for details

## Support

- 📧 Email: support@example.com
- 💬 Telegram: @your_username
- 🐛 Issues: GitHub Issues

## Roadmap

- [ ] Full cTrader Protobuf integration
- [ ] MetaTrader 4/5 integration
- [ ] Mobile app (React Native)
- [ ] AI trade analysis
- [ ] Social trading features
- [ ] Backtesting engine
- [ ] Risk calculator
- [ ] News sentiment analysis

## Credits

Built with:
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- [Flask](https://flask.palletsprojects.com/)
- [matplotlib](https://matplotlib.org/)
- [yfinance](https://github.com/ranaroussi/yfinance)
- [pandas](https://pandas.pydata.org/)

---

Made with ❤️ for traders by traders
