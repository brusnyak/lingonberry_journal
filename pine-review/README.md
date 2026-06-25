# Pine Review & Market Structure Analysis

Review app, backtesting engine, and ICT/SMC market structure detection. Runs alongside the trading journal to provide structure-based analysis and trade review.

## Features

### Market Structure Analysis (`backend/src/features/market_structure.py`)
- Swing high/low detection (fractal method, configurable period)
- HH/HL/LL/LH labeling for trend identification
- BOS (Break of Structure) and CHoCH (Change of Character) detection
- Fair Value Gap (FVG) detection with ATR filtering and mitigation tracking
- Order Block detection with volume filter
- Liquidity sweep detection (breaks + reversal confirmation)
- Liquidity level tracking (extends forward until swept)
- Premium/discount zones with equilibrium (50%) levels
- Asian session detection (AMD logic — Accumulation/Manipulation/Distribution)
- Round number levels and daily/weekly/monthly open levels

### Review App (FastAPI, port 8000)
- Chart-first trade review with Lightweight Charts
- ICT overlay toggle (auto-renders FVGs, order blocks, liquidity levels)
- VWAP + EMA overlay toggle
- Drawing tools: Accum, Dist, Sweep, BOS, CHoCH, Long, Short
- Backtest session management with playback controls (play/step)
- Trade list, editor, and audit trails
- Signals and analytics pages

### Backtesting Engine (`backend/src/backtest/engine.py`)
- Long and short position support
- Stop loss and take profit
- Position sizing (fixed, risk%, Kelly)
- Commission and slippage
- Monte Carlo simulation
- Walk-forward optimization
- Full metrics: win rate, expectancy, Sharpe, profit factor, max drawdown

## Quick Start

```bash
# Install dependencies
cd backend
pip install -r requirements.txt

# Run review app (port 8000)
make review
```

Open http://localhost:8000 in a browser.

## Makefile Commands

| Command | Description |
|---------|-------------|
| `make review` | Start review app on port 8000 |
| `make back` | Alias for run-backend |
| `make front` | Alias for run-frontend |
| `make run` | Run both backend + frontend |
| `make backtest` | Run batch backtesting |
| `make clean` | Remove venv and node_modules |

## Project Structure

```
pine/
├── backend/
│   ├── src/
│   │   ├── backtest/           # Backtesting engine
│   │   │   ├── engine.py       # Core BT engine (Trade, BacktestResult, BacktestEngine)
│   │   ├── data/               # Data sources (Binance, yFinance, cache)
│   │   ├── features/           # Market structure analysis
│   │   │   ├── market_structure.py  # ICT/SMC structure detection (1088 lines)
│   │   │   ├── microstructure.py
│   │   │   └── technicals.py
│   │   ├── review_app/         # FastAPI review app
│   │   │   ├── main.py         # API endpoints
│   │   │   └── static/         # Frontend (app.js, index.html)
│   │   ├── config.py
│   │   ├── visualization/      # Chart generation
│   │   └── ml/                 # ML modules
│   └── .env                    # API keys (Binance, Telegram, TradeLocker)
├── pine_scripts/               # TradingView Pine scripts
│   ├── diy.pine                # DIY strategy (209KB)
│   ├── GainzAlgo_V3_Fixed.pine
│   ├── lorentzian_classification_v6_visualized.pine
│   ├── orig.pine
│   ├── overwhelmed.pine
│   └── turtle.pine
├── data/                       # Historical data, backtests, sessions
├── tests/                      # Test suite
└── Makefile
```

## Related Projects

- **trading-journal** (`../trading-journal/`) — Flask web UI at port 5000 with drawing engine
- **freqtrade-ict** (`../freqtrade-ict/`) — Freqtrade ICT scalper strategy (archived)
- **vibe-trading** (`../vibe-trading/`) — Trading agent CLI with exchange connectors

## License

Private project - All rights reserved
