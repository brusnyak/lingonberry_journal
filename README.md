# Trading Journal

Automated trading system for prop firm challenges. Runs three microservices
on Oracle Cloud Free Tier — strategy execution, position mirroring, and
trailing stop management — via cTrader OpenAPI.

```
ctrader-strategy ──▶ ctrader-mirror ──▶ position-manager
(MA cross, 15s)       (copy 25K→100K)    (trailing SL, 5s)
```

Full architecture: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

## Components

- **ctrader-strategy** — EMA crossover on BTCUSD M5, places orders on master account
- **ctrader-mirror** — Copies master positions to slave with risk-based sizing (0.5%)
- **position-manager** — Trailing stop loss via swing points, breakeven at 1.0R
- **ctrader-client** — Shared cTrader OpenAPI protobuf WebSocket client
- **trade-logger** — JSONL trade journal (signals, opens, closes, errors)
- **Web Dashboard** — Flask webapp with analytics, charts, performance tracking
- **Backtesting** — Multi-strategy engine with Parquet data (EMA, RSI, ICT structure)
- **Telegram Bot** — Trade logging, account management, reporting

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
# - TL_* credentials (see .env.example)
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

## TradeLocker Integration

Live forex data via TradeLocker (Goat Funded Trader).

**What you get:**
- ✅ Live OHLC data for forex and commodities
- ✅ Real-time bid/ask quotes
- ✅ Symbol resolution (.X suffix)
- ✅ Local market data caching

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

## Data Sources

| Source | Asset Class | Status |
|--------|-------------|--------|
| cTrader OpenAPI | Crypto (BTCUSD), Forex, Commodities | ✅ Live |
| TradeLocker | Forex, Commodities | ⏸️ Legacy (disabled) |
| Broker CSV | NAS100 (USATECHIDXUSD) | ✅ Live |
| yFinance | Stocks, Crypto | ✅ Fallback |
| Local CSV/Parquet | All | ✅ Cached |

## Backtesting

### Forex V1 (ICT/SMC)
Multi-timeframe structure strategy using 4H/1H/15m/1m with sweep + MSS + FVG retest. See `backtesting/forex_v1.py`.

### NAS100 Test
Multi-strategy backtest for NAS100 index data. Tests EMA crossover, RSI mean reversion, SMA pullback, and breakout strategies across timeframes and RR settings. See `backtesting/nas100_test.py`.

```bash
make nas100         # 30-day single run
make nas100-sweep   # full config sweep
make nas100-monthly # rolling monthly validation
```

## Architecture

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the complete system
design, service descriptions, and environment variable reference.

| Service | Port | Role |
|---------|------|------|
| **trading-journal** (this) | 5000 | Trade logging, dashboard, backtesting |
| **pine review** (`pine-review/`) | 8000 | Market structure analysis, trade review |
| **vibe-trading** (`../vibe-trading/`) | CLI | Exchange connectors, execution |

## Project Structure

```
trading-journal/
├── backtesting/            # Strategy backtesting
│   ├── forex_v1.py        # ICT/SMC structure strategy
│   ├── nas100_test.py     # NAS100 multi-strategy test
│   ├── rolling_analysis.py# Walk-forward analysis
│   ├── visualize.py       # Interactive structure viz
│   └── structure_lib/     # Shared ICT/SMC engine
├── bot/                    # Telegram bot
│   ├── journal_daemon.py  # Main bot logic
│   ├── journal_db.py      # Database operations
│   ├── mean_reversion_bot.py # V1 MR bot
│   └── session_detector.py # Session detection
├── webapp/                 # Flask web app
│   ├── app.py             # Main app (30+ API routes)
│   ├── templates/         # HTML templates
│   └── static/js/         # Frontend JS
├── infra/                  # Infrastructure
│   ├── tradelocker_client.py  # TradeLocker client
│   ├── market_data.py         # Market data fetching
│   └── pine_bridge.py         # TradingView webhook
├── core/                   # Core logic
│   ├── exporter.py         # ML dataset export
│   └── monte_carlo.py      # Monte Carlo simulation
├── backtesting_config/     # GFT account rules
├── scripts/                # Utility scripts
├── docs/                   # Documentation
├── data/                   # Database and market data
└── pine-review/            # Structure analysis app
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
./scripts/setup_daily_reminder.sh
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

### TradeLocker data not loading
- Check TL credentials in `.env`
- Verify TradeLocker API is reachable

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

- [x] Chart-first trade entry with drawing tools (BOS, CHoCH, Sweep)
- [x] Pine review app with market structure analysis (swings, FVGs, OBs, liquidity)
- [x] Backtesting engine with Monte Carlo simulation
- [x] Multi-timeframe data fetching (TradeLocker, yFinance, Binance)
- [ ] Connect structure analysis API from pine to trading journal UI
- [ ] Auto-detect HH/HL/BOS/CHOCH/FVG overlays on the chart
- [ ] Real-time WebSocket streaming for 1m scalping
- [ ] TradeLocker data source for forex
- [ ] Execution via vibe-trading connectors (Binance Futures + Bybit copy)

## Credits

Built with:
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- [Flask](https://flask.palletsprojects.com/)
- [matplotlib](https://matplotlib.org/)
- [yfinance](https://github.com/ranaroussi/yfinance)
- [TradeLocker](https://tradelocker.com/)
- [pandas](https://pandas.pydata.org/)

---

Made with ❤️ for traders by traders
