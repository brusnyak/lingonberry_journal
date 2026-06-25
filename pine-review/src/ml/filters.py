"""
Filters for ML signals.
Implements volatility, regime, and ADX filters to improve signal quality.
"""
import pandas as pd
import numpy as np
from typing import Optional


class VolatilityFilter:
    """
    Filter signals based on volatility regime.
    Only trade when volatility is within acceptable range.
    """
    
    def __init__(self, min_percentile: float = 20, 
                 max_percentile: float = 80,
                 lookback: int = 100):
        """
        Initialize filter.
        
        Args:
            min_percentile: Minimum volatility percentile (0-100)
            max_percentile: Maximum volatility percentile (0-100)
            lookback: Lookback period for percentile calculation
        """
        self.min_percentile = min_percentile
        self.max_percentile = max_percentile
        self.lookback = lookback
    
    def filter(self, df: pd.DataFrame) -> pd.Series:
        """
        Generate filter mask.
        
        Args:
            df: Dataframe with OHLC data
        
        Returns:
            Boolean series (True = pass filter)
        """
        # Calculate volatility (ATR or returns std)
        if 'atr' in df.columns:
            volatility = df['atr']
        else:
            returns = df['close'].pct_change()
            volatility = returns.rolling(14).std()
        
        # Calculate rolling percentiles
        min_vol = volatility.rolling(self.lookback).quantile(
            self.min_percentile / 100
        )
        max_vol = volatility.rolling(self.lookback).quantile(
            self.max_percentile / 100
        )
        
        # Pass filter if volatility is in range
        mask = (volatility >= min_vol) & (volatility <= max_vol)
        
        return mask


class RegimeFilter:
    """
    Filter signals based on market regime.
    Only trade in trending markets (avoid choppy/ranging).
    """
    
    def __init__(self, ema_fast: int = 50, 
                 ema_slow: int = 200,
                 min_separation: float = 0.01):
        """
        Initialize filter.
        
        Args:
            ema_fast: Fast EMA period
            ema_slow: Slow EMA period
            min_separation: Minimum separation between EMAs (as % of price)
        """
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.min_separation = min_separation
    
    def filter(self, df: pd.DataFrame, 
              direction: Optional[int] = None) -> pd.Series:
        """
        Generate filter mask.
        
        Args:
            df: Dataframe with OHLC data
            direction: 1 for long only, -1 for short only, None for both
        
        Returns:
            Boolean series (True = pass filter)
        """
        # Calculate EMAs
        ema_fast = df['close'].ewm(span=self.ema_fast).mean()
        ema_slow = df['close'].ewm(span=self.ema_slow).mean()
        
        # Calculate separation
        separation = abs(ema_fast - ema_slow) / df['close']
        
        # Determine regime
        is_trending = separation >= self.min_separation
        is_bullish = ema_fast > ema_slow
        is_bearish = ema_fast < ema_slow
        
        # Apply direction filter
        if direction == 1:  # Long only
            mask = is_trending & is_bullish
        elif direction == -1:  # Short only
            mask = is_trending & is_bearish
        else:  # Both directions
            mask = is_trending
        
        return mask


class ADXFilter:
    """
    Filter signals based on ADX (trend strength).
    Only trade when trend is strong enough.
    """
    
    def __init__(self, min_adx: float = 20, 
                 max_adx: float = 50):
        """
        Initialize filter.
        
        Args:
            min_adx: Minimum ADX value (trend strength)
            max_adx: Maximum ADX value (avoid overextended)
        """
        self.min_adx = min_adx
        self.max_adx = max_adx
    
    def filter(self, df: pd.DataFrame) -> pd.Series:
        """
        Generate filter mask.
        
        Args:
            df: Dataframe with ADX indicator
        
        Returns:
            Boolean series (True = pass filter)
        """
        if 'adx' not in df.columns:
            # No ADX data, pass all
            return pd.Series(True, index=df.index)
        
        adx = df['adx']
        
        # Pass filter if ADX is in range
        mask = (adx >= self.min_adx) & (adx <= self.max_adx)
        
        return mask


def combine_filters(*filters: pd.Series) -> pd.Series:
    """
    Combine multiple filter masks with AND logic.
    
    Args:
        *filters: Variable number of boolean series
    
    Returns:
        Combined boolean series (True = pass all filters)
    """
    if len(filters) == 0:
        raise ValueError("At least one filter required")
    
    result = filters[0].copy()
    
    for f in filters[1:]:
        result = result & f
    
    return result
