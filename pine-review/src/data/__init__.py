"""Data package exports.

Keep optional third-party provider imports lazy/guarded so local backtests
that only use parquet/CSV loaders do not fail when live-data deps are absent.
"""

from src.data.base import DataSource, DataManager
from src.data.cache import DataCache

try:
    from src.data.binance_source import BinanceSource
except ModuleNotFoundError:  # ccxt missing in offline/local test environments
    BinanceSource = None

try:
    from src.data.yfinance_source import YFinanceSource
except ModuleNotFoundError:  # yfinance missing in offline/local test environments
    YFinanceSource = None

__all__ = [
    'DataSource',
    'DataManager',
    'BinanceSource',
    'YFinanceSource',
    'DataCache'
]
