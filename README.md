# Trading Journal Bot 📊

A trading journal platform combining a Telegram bot, web dashboard, automated charting, market data, backtesting, and performance analytics.

## Demo

[![Trading Journal Bot Demo](https://img.youtube.com/vi/nYDuefVCTns/maxresdefault.jpg)](https://youtu.be/nYDuefVCTns)

**Watch the demo:** [YouTube](https://youtu.be/nYDuefVCTns)

## Features

* **Telegram trade logging** with a guided conversational flow
* **Web dashboard** for trades, goals, reviews, and analytics
* **Automatic charts** with entry, stop-loss, and take-profit markers
* **TradeLocker integration** for forex and commodity market data
* **Performance analytics** including win rate, expectancy, Sharpe ratio, and Monte Carlo simulation
* **Trading psychology tracking** for mood, stress, and confidence
* **Multi-account support** for personal and prop-firm accounts
* **Backtesting tools** for ICT/SMC and systematic strategies
* **Weekly goals and reviews** for process adherence

## Quick Start

### 1. Install

```bash
git clone https://github.com/YOUR_USERNAME/trading-journal.git
cd trading-journal

python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
```

Add the required credentials to `.env`:

```env
TELEGRAM_JOURAL=your_bot_token
TELEGRAM_JOURNAL_CHAT=your_chat_id
WEBAPP_URL=https://your-public-url
```

TradeLocker credentials and additional options are documented in `.env.example`.

> Verify whether `TELEGRAM_JOURAL` is intentionally named this way. If not, rename it to `TELEGRAM_JOURNAL` throughout the project.

### 3. Run

```bash
make bot       # Start Telegram bot
make webapp    # Start web dashboard
make test      # Run tests
```

Run the bot and web application in separate terminals.

## Telegram Commands

| Command               | Description                                 |
| --------------------- | ------------------------------------------- |
| `/start`              | Initialize the bot and configure an account |
| `/journal`            | Log a new trade                             |
| `/open`               | View open trades                            |
| `/close [id] [price]` | Close a trade                               |
| `/stats`              | View performance statistics                 |
| `/report`             | Open the web dashboard                      |
| `/mini`               | Open the Telegram Mini App                  |
| `/accounts`           | List trading accounts                       |
| `/useaccount [id]`    | Switch the active account                   |
| `/newaccount`         | Create an account                           |
| `/setgoal`            | Set a weekly goal                           |

## Telegram Mini App

Telegram Mini Apps require a public HTTPS URL.

### ngrok

```bash
brew install ngrok
ngrok http 5000
```

Add the generated URL to `.env`:

```env
WEBAPP_URL=https://your-url.ngrok.io
```

### Cloudflare Tunnel

```bash
brew install cloudflare/cloudflare/cloudflared
cloudflared tunnel --url http://localhost:5000
```

For production, deploy the web application behind your own HTTPS domain.

## Market Data

| Source        | Markets               | Role                        |
| ------------- | --------------------- | --------------------------- |
| TradeLocker   | Forex and commodities | Primary live source         |
| Broker CSV    | NAS100                | Broker-specific data        |
| yFinance      | Stocks and crypto     | Fallback source             |
| CSV / Parquet | All supported markets | Local cache and backtesting |

TradeLocker support includes:

* Live OHLC data
* Bid and ask quotes
* Broker symbol resolution
* Local market-data caching

## Backtesting

### Forex ICT/SMC

`backtesting/forex_v1.py` implements a multi-timeframe strategy using:

* 4H, 1H, 15m, and 1m structure
* Liquidity sweeps
* Market structure shifts
* Fair-value-gap retests

### NAS100

`backtesting/nas100_test.py` tests multiple strategy families across different timeframes and risk-to-reward settings:

* EMA crossover
* RSI mean reversion
* SMA pullback
* Breakout strategies

```bash
make nas100          # Run a 30-day test
make nas100-sweep    # Test multiple configurations
make nas100-monthly  # Run rolling monthly validation
```

## Architecture

| Component         | Port | Purpose                                              |
| ----------------- | ---: | ---------------------------------------------------- |
| `trading-journal` | 5000 | Trade logging, dashboard, analytics, and backtesting |
| `pine-review`     | 8000 | Market-structure analysis and trade review           |
| `vibe-trading`    |  CLI | Exchange connectivity and trade execution            |

## Project Structure

```text
trading-journal/
├── backtesting/             # Strategy testing and walk-forward analysis
│   ├── forex_v1.py
│   ├── nas100_test.py
│   ├── rolling_analysis.py
│   ├── visualize.py
│   └── structure_lib/
├── bot/                     # Telegram bot and journal database
│   ├── journal_daemon.py
│   ├── journal_db.py
│   ├── mean_reversion_bot.py
│   └── session_detector.py
├── webapp/                  # Flask dashboard and API
│   ├── app.py
│   ├── templates/
│   └── static/js/
├── infra/                   # Market data and external integrations
│   ├── tradelocker_client.py
│   ├── market_data.py
│   └── pine_bridge.py
├── core/                    # Analytics and data export
│   ├── exporter.py
│   └── monte_carlo.py
├── backtesting_config/      # Account and prop-firm rules
├── scripts/                 # Setup and maintenance scripts
├── docs/                    # Additional documentation
├── data/                    # Database, cache, and market data
└── pine-review/             # Market-structure review application
```

## Database

The journal stores:

* Trading accounts and account rules
* Open and closed trades
* Psychology metrics
* Process-review notes
* Weekly reviews and goals
* Chart drawings and annotations

The database is initialized and migrated automatically from:

```text
bot/journal_db.py:init_db()
```

## API Overview

### Accounts

```text
GET  /api/accounts
POST /api/accounts
POST /api/accounts/:id/rules
```

### Trades

```text
GET  /api/trades
GET  /api/trades/open
POST /api/trades/:id/close
POST /api/trades/:id/review
GET  /api/trades/:id/events
```

### Analytics

```text
GET /api/dashboard
GET /api/analytics/monte-carlo
GET /api/replay/:id
```

### Weekly Reviews

```text
GET  /api/review/week
POST /api/review/week
GET  /api/goals/week
POST /api/goals/week
```

## Development

```bash
pytest tests/
black .
flake8 .
```

## Deployment

### GitHub

```bash
make git-init
make deploy
```

### Linux VM

```bash
ssh ubuntu@YOUR_VM_IP

git clone https://github.com/YOUR_USERNAME/trading-journal.git
cd trading-journal

./scripts/setup_daily_reminder.sh
```

## Troubleshooting

### Bot does not respond

* Confirm the Telegram token and chat ID in `.env`
* Verify the bot process is running
* Review application logs for errors

```bash
ps aux | grep journal_daemon
```

### Charts are not generated

* Verify market-data credentials
* Check permissions for `data/cache/`
* Confirm that a fallback data source is available

### TradeLocker data does not load

* Verify the `TL_*` credentials
* Confirm the TradeLocker API is accessible
* Check broker-specific symbol names

### Mini App does not open

* Confirm `WEBAPP_URL` uses public HTTPS
* Verify the web application is running
* Confirm the URL is accessible outside your local network

```bash
curl "$WEBAPP_URL"
```

## Roadmap

* [x] Chart-first trade entry with drawing tools
* [x] BOS, CHoCH, and liquidity-sweep annotations
* [x] Market-structure analysis with swings, FVGs, order blocks, and liquidity
* [x] Multi-timeframe market-data fetching
* [x] Backtesting and Monte Carlo simulation
* [ ] Connect Pine Review analysis to the main journal
* [ ] Automatically overlay HH, HL, BOS, CHoCH, and FVG structures
* [ ] Add real-time WebSocket streaming for scalping
* [ ] Expand TradeLocker forex-data support
* [ ] Add execution through Binance Futures and Bybit connectors

## Contributing

1. Fork the repository.
2. Create a feature branch.
3. Commit your changes.
4. Push the branch.
5. Open a pull request.

```bash
git checkout -b feature/my-feature
git commit -am "Add my feature"
git push origin feature/my-feature
```

## Built With

* [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
* [Flask](https://flask.palletsprojects.com/)
* [pandas](https://pandas.pydata.org/)
* [matplotlib](https://matplotlib.org/)
* [yfinance](https://github.com/ranaroussi/yfinance)
* [TradeLocker](https://tradelocker.com/)

## License

Distributed under the MIT License. See `LICENSE` for details.
