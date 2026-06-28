# Trading Journal — Prop Firm Trading Engine

ICT/SMC mechanical trading engine for Goat Funded Trader challenges (25k 2-Step, 100k 1-Step).
Backtest + ML pipeline on Python 3.11 / VectorBT / Numba / Polars / M1 Pro.

## Stack

| Layer | Tool |
|-------|------|
| Backtest engine | `vbt.Portfolio.from_signals` (VectorBT broadcast, Numba JIT) |
| Structure indicators | `backtesting/structure_lib/vbt_indicators.py` (Numba kernels) |
| Feature engineering | Polars LazyFrame → NumPy |
| ML ensemble | LightGBM + XGBoost + CatBoost (3-class direction, walk-forward CV) |
| Data storage | Parquet (columnar, daily refresh via TradeLocker) |
| Live execution | TradeLocker API (Oracle Cloud VM, 24/7) |
| Environment | conda `trade`, Python 3.11, Apple vecLib, Numba 0.65.1 |

## Quick Start

### Environment (M1 Pro optimized)

```bash
conda create -n trade python=3.11
conda activate trade
conda install -c conda-forge "libblas=*=*accelerate" numba ta-lib polars
conda install -c conda-forge lightgbm xgboost catboost scikit-learn
pip install "vectorbt[full,rust]"
echo "libblas=*=*accelerate" >> ~/miniconda3/envs/trade/conda-meta/pinned
```

### Backtest

```bash
conda activate trade
python -c "from backtesting.engine.vbt_runner import VbtRunner; from backtesting.strategies.tr_ict_sweep import TrIctSweep; print('Ready')"
```

### ML Pipeline

```bash
# Build feature matrix + train ensemble
python -c "from backtesting.ml import run_pipeline; result, feat, labels = run_pipeline('GBPAUD', '5', days=120)"
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
| TradeLocker | Forex, Commodities, Indices | ✅ Live |
| Broker CSV | NAS100 (USATECHIDXUSD) | ✅ Live |
| Parquet (local) | All cached daily | ✅ Active |

## Backtesting (VectorBT)

### Architecture

```
run_strategy()  →  vbt.Portfolio.from_signals(entries, exits, sl_stop, tp_stop)
                        └── Numba-compiled signal masks
                        └── Multi-column broadcast for param sweeps
                        └── Walk-forward split + metrics in one pass

ML pipeline:
build_feature_matrix() → walk_forward_train() → Mlpredictor.filter_signal()
```

### Active Strategies

| Strategy | Engine | Status |
|----------|--------|--------|
| TrIctSweep | VbtRunner (hybrid) | VectorBT signal gen working |
| SMC v1 | VbtRunner (hybrid) | On deck |
| Mean reversion | TradeLocker bot (live only) | Not migrated |

### Performance Baseline

| Test | Bars | Trades | Time |
|------|------|--------|------|
| Single backtest (30d) | 30,578 | 0-5 | 0.4s |
| Single backtest (90d) | 91,523 | 3-25 | 0.9s |
| Param sweep (486 combos) | 30,578 | — | ~5 min (target) |
| ML training (60d 5m) | ~6,300 | 264 signals | ~30s |

Target: param sweeps sub-5s via VectorBT multi-column broadcast + multiprocessing.

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
├── backtesting/
│   ├── engine/
│   │   ├── vbt_runner.py       # VectorBT hybrid runner (strategy->from_signals)
│   │   ├── sweep.py            # Multiprocessing param sweep
│   │   ├── runner.py           # Original bar-loop runner (reference)
│   │   ├── base.py             # Strategy/EngineState interfaces
│   │   ├── costs.py            # Spread/slippage/commission model
│   │   ├── data.py             # TradeLocker data load
│   │   ├── metrics.py          # Performance metrics
│   │   └── orders.py           # Signal dataclass
│   ├── structure_lib/
│   │   ├── vbt_indicators.py   # VectorBT Numba wrappers (swing, FVG, OB, sweep, labels)
│   │   ├── swing.py            # Causal swing detection
│   │   ├── fvg.py              # FVG detection
│   │   ├── sweep.py            # Liquidity sweep detection
│   │   ├── ob.py               # Order block detection
│   │   ├── labels.py           # HH/HL/LH/LL structure labels
│   │   ├── sessions.py         # Session range tracking
│   │   └── viz.py              # Structure visualization
│   ├── ml/
│   │   ├── labels.py           # Triple-barrier 3-class labels
│   │   ├── features.py         # Causal feature matrix from structure_lib
│   │   ├── train.py            # LightGBM+XGBoost+CatBoost ensemble, walk-forward
│   │   └── predict.py          # Mlpredictor inference wrapper
│   ├── strategies/
│   │   ├── tr_ict_sweep.py     # ICT sweep + FVG retest (main active)
│   │   ├── smc_v1.py           # SMC structure strategy
│   │   ├── vbt_tr_ict_sweep.py # Pure Numba signal mask version (WIP)
│   │   ├── prop_firm_structure_v1.py
│   │   └── ... (15+ strategy variants)
│   ├── features/
│   │   ├── ict_structure.py    # Strict ICT state machine
│   │   └── core.py             # Base feature builder
│   └── scripts/
│       ├── ict_direction_accuracy.py  # Triple-barrier analysis
│       └── ... (25+ analysis scripts)
├── core/                   # GFT account config, Monte Carlo
├── scripts/                # Utility scripts
└── docs/                   # Architecture docs
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
