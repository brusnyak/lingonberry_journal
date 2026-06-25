"""
Technical indicators with normalization for cross-asset comparison.
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional


def calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Calculate RSI (Relative Strength Index)."""
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
    """Calculate MACD with histogram."""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    
    return {
        'macd': macd_line,
        'signal': signal_line,
        'histogram': histogram
    }


def calculate_stochastic(high: pd.Series, low: pd.Series, close: pd.Series, 
                         k_period: int = 14, d_period: int = 3) -> Dict[str, pd.Series]:
    """Calculate Stochastic Oscillator."""
    lowest_low = low.rolling(window=k_period).min()
    highest_high = high.rolling(window=k_period).max()
    
    k = 100 * (close - lowest_low) / (highest_high - lowest_low)
    d = k.rolling(window=d_period).mean()
    
    return {
        'stoch_k': k,
        'stoch_d': d
    }


def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Average True Range."""
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    
    return atr


def calculate_atr_percentile(atr: pd.Series, lookback: int = 100) -> pd.Series:
    """Calculate ATR percentile rank for volatility context."""
    return atr.rolling(window=lookback).apply(
        lambda x: pd.Series(x).rank(pct=True).iloc[-1] * 100 if len(x) == lookback else np.nan
    )


def calculate_ema_distance(close: pd.Series, periods: list = [20, 50, 200]) -> Dict[str, pd.Series]:
    """Calculate percentage distance from EMAs."""
    distances = {}
    
    for period in periods:
        ema = close.ewm(span=period, adjust=False).mean()
        distance = ((close - ema) / ema) * 100
        distances[f'ema{period}_dist'] = distance
    
    return distances


def calculate_volume_ratio(volume: pd.Series, period: int = 20) -> pd.Series:
    """Calculate volume ratio vs moving average."""
    vol_ma = volume.rolling(window=period).mean()
    return volume / vol_ma


def calculate_wave_trend(hlc3: pd.Series, channel_period: int = 10, average_period: int = 21) -> Dict[str, pd.Series]:
    """
    Calculate Wave Trend (WT) indicator.

    Used in Lorentzian Classification. Combines price action with momentum.

    Args:
        hlc3: (high + low + close) / 3
        channel_period: Period for EMA calculation
        average_period: Period for smoothing

    Returns:
        Dict with 'wt1' and 'wt2' series
    """
    # Calculate EMA of HLC3
    esa = hlc3.ewm(span=channel_period, adjust=False).mean()

    # Calculate absolute difference
    d = abs(hlc3 - esa)
    d_ema = d.ewm(span=channel_period, adjust=False).mean()

    # Calculate CI (Channel Index)
    ci = (hlc3 - esa) / (0.015 * d_ema)

    # Wave Trend 1 (main line)
    wt1 = ci.ewm(span=average_period, adjust=False).mean()

    # Wave Trend 2 (signal line)
    wt2 = wt1.rolling(window=4).mean()

    return {
        'wt1': wt1,
        'wt2': wt2
    }


def calculate_cci(close: pd.Series, high: pd.Series, low: pd.Series, period: int = 20) -> pd.Series:
    """
    Calculate Commodity Channel Index (CCI).

    Used in Lorentzian Classification. Measures deviation from average price.

    Args:
        close: Close prices
        high: High prices
        low: Low prices
        period: Lookback period

    Returns:
        CCI series
    """
    # Typical Price
    tp = (high + low + close) / 3

    # Simple Moving Average of TP
    sma_tp = tp.rolling(window=period).mean()

    # Mean Deviation
    mad = tp.rolling(window=period).apply(lambda x: np.abs(x - x.mean()).mean())

    # CCI calculation
    cci = (tp - sma_tp) / (0.015 * mad)

    return cci


def calculate_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate Average Directional Index (ADX).

    Measures trend strength (not direction).

    Args:
        high: High prices
        low: Low prices
        close: Close prices
        period: Lookback period

    Returns:
        ADX series
    """
    # Calculate +DM and -DM
    high_diff = high.diff()
    low_diff = -low.diff()

    plus_dm = pd.Series(np.where((high_diff > low_diff) & (high_diff > 0), high_diff, 0), index=high.index)
    minus_dm = pd.Series(np.where((low_diff > high_diff) & (low_diff > 0), low_diff, 0), index=low.index)

    # Calculate True Range
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Smooth with Wilder's smoothing (EMA)
    atr = tr.ewm(span=period, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(span=period, adjust=False).mean() / (atr + 1e-10)
    minus_di = 100 * minus_dm.ewm(span=period, adjust=False).mean() / (atr + 1e-10)

    # Calculate DX and ADX
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
    adx = dx.ewm(span=period, adjust=False).mean()

    return adx



def normalize_series(series: pd.Series, method: str = 'zscore', lookback: int = 100) -> pd.Series:
    """
    Normalize series for ML input.
    
    Args:
        series: Input series
        method: 'zscore' or 'minmax'
        lookback: Rolling window for normalization
    """
    if method == 'zscore':
        mean = series.rolling(window=lookback).mean()
        std = series.rolling(window=lookback).std()
        return (series - mean) / std
    
    elif method == 'minmax':
        min_val = series.rolling(window=lookback).min()
        max_val = series.rolling(window=lookback).max()
        return (series - min_val) / (max_val - min_val)
    
    return series


def calculate_all_technicals(df: pd.DataFrame, normalize: bool = True) -> pd.DataFrame:
    """
    Calculate all technical indicators for a dataframe.
    
    Args:
        df: DataFrame with OHLCV columns
        normalize: Whether to normalize features
    
    Returns:
        DataFrame with added technical indicator columns
    """
    result = df.copy()
    
    # RSI
    result['rsi'] = calculate_rsi(df['close'])
    
    # MACD
    macd = calculate_macd(df['close'])
    result['macd'] = macd['macd']
    result['macd_signal'] = macd['signal']
    result['macd_hist'] = macd['histogram']
    
    # Stochastic
    stoch = calculate_stochastic(df['high'], df['low'], df['close'])
    result['stoch_k'] = stoch['stoch_k']
    result['stoch_d'] = stoch['stoch_d']
    
    # ATR and percentile
    result['atr'] = calculate_atr(df['high'], df['low'], df['close'])
    result['atr_percentile'] = calculate_atr_percentile(result['atr'])
    
    # Wave Trend (for Lorentzian)
    hlc3 = (df['high'] + df['low'] + df['close']) / 3
    wt = calculate_wave_trend(hlc3)
    result['wt1'] = wt['wt1']
    result['wt2'] = wt['wt2']
    
    # CCI (for Lorentzian)
    result['cci'] = calculate_cci(df['close'], df['high'], df['low'])
    
    # ADX (for Lorentzian)
    result['adx'] = calculate_adx(df['high'], df['low'], df['close'])
    
    # EMA distances
    ema_dists = calculate_ema_distance(df['close'])
    for key, value in ema_dists.items():
        result[key] = value
    
    # Volume ratio
    result['volume_ratio'] = calculate_volume_ratio(df['volume'])
    
    # Normalize if requested
    if normalize:
        features_to_normalize = [
            'macd', 'macd_signal', 'macd_hist',
            'ema20_dist', 'ema50_dist', 'ema200_dist'
        ]
        
        for feature in features_to_normalize:
            if feature in result.columns:
                result[f'{feature}_norm'] = normalize_series(result[feature])
    
    return result
