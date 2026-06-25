#!/usr/bin/env python
"""
Data updater script to fill gaps in existing parquet files.
"""
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data import DataManager, BinanceSource, YFinanceSource
from src.data.tradelocker_source import TradeLockerSource

from src.utils.logger import setup_logger

logger = setup_logger(__name__)

# Timeframe mapping
TIMEFRAME_MAP = {
    '1': '1m',
    '5': '5m',
    '15': '15m',
    '30': '30m',
    '60': '1h',
    '240': '4h',
    '1440': '1d'
}

# Symbol mapping for different sources
SYMBOL_MAP = {
    # Crypto (Binance format)
    'BTCUSD': 'BTC/USDT',
    'ETHUSD': 'ETH/USDT',
    'ADAUSDT': 'ADA/USDT',
    'XRPUSDT': 'XRP/USDT',
    
    # Forex (Yahoo Finance format)
    'EURUSD': 'EURUSD',
    'GBPUSD': 'GBPUSD',
    'GBPJPY': 'GBPJPY',
    'USDCAD': 'USDCAD',
    
    # Metals (Yahoo Finance format)
    'XAUUSD': 'XAUUSD',
    'XAGUSD': 'XAGUSD',
    
    # Indices (Yahoo Finance format)
    'USA30IDXUSD': 'US30',
    'USA500IDXUSD': 'SPX500',
    'USATECHIDXUSD': 'NAS100'
}


def parse_filename(filename: str) -> tuple:
    """
    Parse parquet filename to extract symbol and timeframe.
    
    Example: BTCUSD1.parquet -> ('BTCUSD', '1m')
    """
    name = filename.replace('.parquet', '')
    
    # Find where numbers start
    for i, char in enumerate(name):
        if char.isdigit():
            symbol = name[:i]
            tf_code = name[i:]
            timeframe = TIMEFRAME_MAP.get(tf_code, '1d')
            return symbol, timeframe
    
    return name, '1d'


def load_existing_data(file_path: Path) -> pd.DataFrame:
    """Load existing parquet file."""
    try:
        df = pd.read_parquet(file_path)
        logger.info(f"Loaded {len(df)} existing candles from {file_path.name}")
        return df
    except Exception as e:
        logger.error(f"Error loading {file_path}: {e}")
        return pd.DataFrame()


def fetch_new_data(symbol: str, timeframe: str, since: datetime, manager: DataManager) -> pd.DataFrame:
    """Fetch new data from appropriate source."""
    try:
        # Map symbol to source format
        source_symbol = SYMBOL_MAP.get(symbol, symbol)
        
        # Determine source
        if source_symbol in ("GBPUSD", "EURUSD"):
            source = 'tradelocker'
        elif '/' in source_symbol:
            source = 'binance'
        else:
            source = 'yfinance'

        
        logger.info(f"Fetching {source_symbol} {timeframe} from {source} since {since}")
        
        # Fetch data
        df = manager.fetch_ohlcv(
            source_symbol,
            timeframe,
            source=source,
            limit=1000,
            since=since
        )
        
        logger.info(f"Fetched {len(df)} new candles")
        return df
        
    except Exception as e:
        logger.error(f"Error fetching {symbol} {timeframe}: {e}")
        return pd.DataFrame()


def merge_data(existing: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    """Merge existing and new data, removing duplicates."""
    if existing.empty:
        # If new data has datetime as index, reset it to column
        if new.index.name == 'datetime':
            new = new.reset_index()
        return new
    
    if new.empty:
        return existing
    
    # Ensure both have datetime as column (not index)
    if 'datetime' not in existing.columns:
        if existing.index.name == 'datetime':
            existing = existing.reset_index()
        else:
            logger.error("datetime column not found in existing data")
            return existing
    
    if 'datetime' not in new.columns:
        if new.index.name == 'datetime':
            new = new.reset_index()
        else:
            logger.error("datetime column not found in new data")
            return existing
    
    # Ensure datetime columns have the same dtype
    # Convert to string first to avoid pandas internal array issues
    existing = existing.copy()
    new = new.copy()
    existing['datetime'] = existing['datetime'].astype(str)
    new['datetime'] = new['datetime'].astype(str)
    
    # Ensure all numeric columns are float64
    numeric_cols = ['open', 'high', 'low', 'close', 'volume']
    for col in numeric_cols:
        if col in existing.columns:
            existing[col] = existing[col].astype('float64')
        if col in new.columns:
            new[col] = new[col].astype('float64')
    
    logger.debug(f"Existing shape: {existing.shape}, columns: {existing.columns.tolist()}")
    logger.debug(f"New shape: {new.shape}, columns: {new.columns.tolist()}")
    
    # Combine
    combined = pd.concat([existing, new], ignore_index=True)
    
    # Convert datetime back with mixed format to handle inconsistent formats
    combined['datetime'] = pd.to_datetime(combined['datetime'], format='mixed')
    
    # Remove duplicates based on datetime (keep last)
    combined = combined.drop_duplicates(subset=['datetime'], keep='last')
    
    # Sort by datetime
    combined = combined.sort_values('datetime').reset_index(drop=True)
    
    logger.info(f"Merged data: {len(existing)} existing + {len(new)} new = {len(combined)} total")
    
    return combined


def update_file(file_path: Path, manager: DataManager, dry_run: bool = False):
    """Update a single parquet file."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Processing: {file_path.name}")
    logger.info(f"{'='*60}")
    
    try:
        # Parse filename
        symbol, timeframe = parse_filename(file_path.name)
        
        # Load existing data
        existing_df = load_existing_data(file_path)
        
        if existing_df.empty:
            logger.warning(f"No existing data found, skipping {file_path.name}")
            return
        
        # Get last date
        if 'datetime' in existing_df.columns:
            last_date = existing_df['datetime'].iloc[-1]
        else:
            last_date = existing_df.index[-1]
        
        # Ensure it's a datetime object
        if isinstance(last_date, (int, str)):
            last_date = pd.to_datetime(last_date)
        
        logger.info(f"Last candle: {last_date}")
        
        # Calculate gap
        now = datetime.now()
        gap_days = (now - last_date).days
        logger.info(f"Gap: {gap_days} days")
        
        if gap_days < 1:
            logger.info("Data is up to date, skipping")
            return
        
        # Fetch new data
        new_df = fetch_new_data(symbol, timeframe, last_date, manager)
        
        if new_df.empty:
            logger.warning("No new data fetched")
            return
        
        # Merge
        merged_df = merge_data(existing_df, new_df)
        
        # Save
        if not dry_run:
            merged_df.to_parquet(file_path)
            logger.info(f"✓ Saved {len(merged_df)} candles to {file_path.name}")
        else:
            logger.info(f"[DRY RUN] Would save {len(merged_df)} candles")
            
    except Exception as e:
        import traceback
        logger.error(f"Failed to update {file_path.name}: {e}")
        print(traceback.format_exc())


def main():
    """Main update process."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Update parquet data files')
    parser.add_argument('--market', type=str, help='Market to update (crypto, forex, metals, indeces, all)')
    parser.add_argument('--dry-run', action='store_true', help='Dry run (no actual updates)')
    parser.add_argument('--limit', type=int, help='Limit number of files to update')
    
    args = parser.parse_args()
    
    # Initialize data manager
    manager = DataManager()
    manager.register_source('binance', BinanceSource())
    manager.register_source('yfinance', YFinanceSource())
    manager.register_source('tradelocker', TradeLockerSource())

    
    # Get data directory
    data_dir = Path(__file__).parent.parent.parent / 'data' / 'parquet'
    
    # Determine which markets to update
    if args.market and args.market != 'all':
        markets = [args.market]
    else:
        markets = ['crypto', 'forex', 'metals', 'indeces']
    
    logger.info(f"\n{'#'*60}")
    logger.info(f"DATA UPDATE SCRIPT")
    logger.info(f"Markets: {', '.join(markets)}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info(f"{'#'*60}\n")
    
    # Process each market
    total_updated = 0
    
    for market in markets:
        market_dir = data_dir / market
        
        if not market_dir.exists():
            logger.warning(f"Market directory not found: {market_dir}")
            continue
        
        # Get all parquet files
        files = sorted(market_dir.glob('*.parquet'))
        
        if args.limit:
            files = files[:args.limit]
        
        logger.info(f"\n{'*'*60}")
        logger.info(f"Market: {market.upper()} ({len(files)} files)")
        logger.info(f"{'*'*60}")
        
        for file_path in files:
            try:
                update_file(file_path, manager, dry_run=args.dry_run)
                total_updated += 1
            except Exception as e:
                logger.error(f"Failed to update {file_path.name}: {e}")
                continue
    
    logger.info(f"\n{'#'*60}")
    logger.info(f"SUMMARY")
    logger.info(f"{'#'*60}")
    logger.info(f"Total files processed: {total_updated}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info(f"{'#'*60}\n")


if __name__ == '__main__':
    main()
