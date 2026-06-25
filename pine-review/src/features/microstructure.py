"""
Market microstructure: order flow, volume delta, absorption patterns.
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional


def calculate_volume_delta(df: pd.DataFrame) -> pd.Series:
    """
    Calculate volume delta (buy volume - sell volume).
    
    For data without tick-level buy/sell split, estimate using price action:
    - If close > open: assume volume is buying
    - If close < open: assume volume is selling
    - If close == open: split 50/50
    """
    buy_volume = np.where(
        df['close'] > df['open'],
        df['volume'],
        np.where(df['close'] == df['open'], df['volume'] * 0.5, 0)
    )
    
    sell_volume = np.where(
        df['close'] < df['open'],
        df['volume'],
        np.where(df['close'] == df['open'], df['volume'] * 0.5, 0)
    )
    
    return pd.Series(buy_volume - sell_volume, index=df.index)


def calculate_cumulative_delta(volume_delta: pd.Series, window: int = 20) -> pd.Series:
    """Calculate cumulative volume delta over rolling window."""
    return volume_delta.rolling(window=window).sum()


def calculate_delta_divergence(df: pd.DataFrame, volume_delta: pd.Series, 
                               window: int = 14) -> pd.Series:
    """
    Detect divergence between price and volume delta.
    
    Positive divergence: Price making lower lows, delta making higher lows
    Negative divergence: Price making higher highs, delta making lower highs
    """
    price_change = df['close'].diff(window)
    delta_change = volume_delta.diff(window)
    
    # Divergence score: opposite signs indicate divergence
    divergence = np.where(
        (price_change > 0) & (delta_change < 0), -1,  # Negative divergence
        np.where((price_change < 0) & (delta_change > 0), 1, 0)  # Positive divergence
    )
    
    return pd.Series(divergence, index=df.index)


def calculate_order_flow_imbalance(df: pd.DataFrame, threshold: float = 3.0) -> pd.Series:
    """
    Calculate order flow imbalance ratio.
    
    Simplified version using volume and price action:
    - Strong buying: close near high + high volume
    - Strong selling: close near low + high volume
    """
    # Calculate where close is relative to high-low range
    range_position = (df['close'] - df['low']) / (df['high'] - df['low'] + 1e-10)
    
    # Estimate buy/sell pressure
    buy_pressure = range_position * df['volume']
    sell_pressure = (1 - range_position) * df['volume']
    
    # Calculate imbalance ratio
    imbalance = buy_pressure / (sell_pressure + 1e-10)
    
    # Flag significant imbalances
    significant = np.where(
        imbalance > threshold, 1,  # Strong buying
        np.where(imbalance < (1/threshold), -1, 0)  # Strong selling
    )
    
    return pd.Series(significant, index=df.index)


def detect_absorption(df: pd.DataFrame, volume_threshold: float = 1.5, 
                     price_threshold: float = 0.3) -> pd.Series:
    """
    Detect absorption patterns: high volume + minimal price movement.
    
    Indicates institutional accumulation/distribution.
    
    Args:
        volume_threshold: Volume must be X times average
        price_threshold: Price range must be < X% of ATR
    """
    # Calculate volume ratio
    vol_ma = df['volume'].rolling(window=20).mean()
    vol_ratio = df['volume'] / vol_ma
    
    # Calculate price range relative to ATR
    price_range = df['high'] - df['low']
    atr = price_range.rolling(window=14).mean()
    range_ratio = price_range / (atr + 1e-10)
    
    # Absorption: high volume + small range
    absorption = np.where(
        (vol_ratio > volume_threshold) & (range_ratio < price_threshold),
        1, 0
    )
    
    return pd.Series(absorption, index=df.index)


def calculate_volume_profile(df: pd.DataFrame, bins: int = 20) -> Dict:
    """
    Calculate volume profile (volume at price levels).
    
    Returns dict with price levels and volume distribution.
    """
    price_min = df['low'].min()
    price_max = df['high'].max()
    
    # Create price bins
    price_bins = np.linspace(price_min, price_max, bins + 1)
    volume_at_price = np.zeros(bins)
    
    # Distribute volume across price levels
    for i in range(len(df)):
        candle_range = df['high'].iloc[i] - df['low'].iloc[i]
        if candle_range == 0:
            continue
        
        # Find which bins this candle touches
        low_bin = np.digitize(df['low'].iloc[i], price_bins) - 1
        high_bin = np.digitize(df['high'].iloc[i], price_bins) - 1
        
        # Distribute volume proportionally
        bins_touched = high_bin - low_bin + 1
        vol_per_bin = df['volume'].iloc[i] / bins_touched
        
        for b in range(max(0, low_bin), min(bins, high_bin + 1)):
            volume_at_price[b] += vol_per_bin
    
    # Find POC (Point of Control) - price level with most volume
    poc_index = np.argmax(volume_at_price)
    poc_price = (price_bins[poc_index] + price_bins[poc_index + 1]) / 2
    
    return {
        'price_levels': [(price_bins[i] + price_bins[i+1])/2 for i in range(bins)],
        'volume_distribution': volume_at_price.tolist(),
        'poc_price': poc_price,
        'poc_volume': volume_at_price[poc_index]
    }


def calculate_aggressive_volume(df: pd.DataFrame) -> Dict[str, pd.Series]:
    """
    Estimate aggressive buy/sell volume.
    
    Aggressive buying: price closes near high
    Aggressive selling: price closes near low
    """
    # Calculate where close is in the range
    range_position = (df['close'] - df['low']) / (df['high'] - df['low'] + 1e-10)
    
    # Aggressive buying: close in top 20% of range
    aggressive_buy = np.where(range_position > 0.8, df['volume'], 0)
    
    # Aggressive selling: close in bottom 20% of range
    aggressive_sell = np.where(range_position < 0.2, df['volume'], 0)
    
    return {
        'aggressive_buy': pd.Series(aggressive_buy, index=df.index),
        'aggressive_sell': pd.Series(aggressive_sell, index=df.index)
    }


def calculate_all_microstructure(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate all microstructure features.
    
    Args:
        df: DataFrame with OHLCV columns
    
    Returns:
        DataFrame with added microstructure columns
    """
    result = df.copy()
    
    # Volume delta
    result['volume_delta'] = calculate_volume_delta(df)
    result['cumulative_delta'] = calculate_cumulative_delta(result['volume_delta'])
    
    # Delta divergence
    result['delta_divergence'] = calculate_delta_divergence(df, result['volume_delta'])
    
    # Order flow imbalance
    result['order_flow_imbalance'] = calculate_order_flow_imbalance(df)
    
    # Absorption
    result['absorption'] = detect_absorption(df)
    
    # Aggressive volume
    aggressive = calculate_aggressive_volume(df)
    result['aggressive_buy'] = aggressive['aggressive_buy']
    result['aggressive_sell'] = aggressive['aggressive_sell']
    
    # Aggressive volume ratio
    result['aggressive_ratio'] = (
        result['aggressive_buy'] / (result['aggressive_sell'] + 1e-10)
    )
    
    return result
