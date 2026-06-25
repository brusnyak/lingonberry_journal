"""
Configuration management for the trading system.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = PROJECT_ROOT / "reports"
DB_PATH = PROJECT_ROOT / "trading_system.db"

# API Keys
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Trading Configuration
TRADING_PAIRS = ["EURUSD", "GBPUSD", "GBPJPY", "XAUUSD", "NAS100"]
TRADING_TIMEFRAME = "5m"
MONITOR_INTERVAL = 300  # 5 minutes in seconds

# Risk Management
MAX_RISK_PER_TRADE = 0.02  # 2%
MAX_OPEN_POSITIONS = 3
MAX_DAILY_LOSS = 0.06  # 6%

# Investment Scout Configuration
MIN_VOLUME_24H = 1_000_000  # $1M
MIN_MARKET_CAP = 100_000_000  # $100M
FACTOR_WEIGHTS = {
    "value": 0.20,
    "momentum": 0.35,
    "quality": 0.25,
    "volatility": 0.20
}

# Walk-Forward Optimization
WFO_TRAIN_PERIOD = 730  # 2 years in days
WFO_TEST_PERIOD = 180   # 6 months in days
WFO_ROLL_PERIOD = 90    # 3 months in days
WFO_MIN_EFFICIENCY = 0.70  # 70% minimum WFE

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
