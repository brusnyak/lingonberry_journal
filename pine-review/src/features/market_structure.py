"""
Market structure detection: swings, liquidity, FVGs, order blocks, structure breaks.
Implements ICT concepts with AMD logic.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import time as dt_time


@dataclass
class SwingPoint:
    """Represents a swing high or low."""
    price: float
    time: pd.Timestamp
    index: int
    swept: bool = False
    type: str = 'high'  # 'high' or 'low'


@dataclass
class FairValueGap:
    """Represents a Fair Value Gap."""
    top: float
    bottom: float
    time: pd.Timestamp
    index: int
    type: str  # 'bullish' or 'bearish'
    mitigated: bool = False
    mitigation_type: str = 'partial'  # 'touch', 'partial', 'full'


@dataclass
class OrderBlock:
    """Represents an Order Block."""
    top: float
    bottom: float
    time: pd.Timestamp
    index: int
    type: str  # 'bullish' or 'bearish'
    mitigated: bool = False
    volume: float = 0.0  # Volume of the OB candle


@dataclass
class StructureBreak:
    """Represents a BOS or CHoCH."""
    type: str  # 'BOS' or 'CHoCH'
    direction: str  # 'bullish' or 'bearish'
    price: float
    time: pd.Timestamp
    index: int


@dataclass
@dataclass
class AsianSession:
    """Represents Asian session range (AMD - Accumulation)."""
    high: float
    low: float
    start_time: pd.Timestamp
    end_time: pd.Timestamp
    high_swept: bool = False
    low_swept: bool = False


@dataclass
class LiquidityLevel:
    """Represents a liquidity level (swing high/low extended as line)."""
    price: float
    type: str  # 'high' or 'low'
    start_index: int
    start_time: pd.Timestamp
    swept: bool = False
    swept_index: int = None
    swept_time: pd.Timestamp = None


@dataclass
class RoundLevel:
    """Represents a round number level (00, 50)."""
    price: float
    level_type: str  # '00' or '50'


@dataclass
class OpenLevel:
    """Represents a session open level (Daily/Weekly/Monthly)."""
    price: float
    level_type: str  # 'daily', 'weekly', 'monthly'
    time: pd.Timestamp
    index: int = 0


@dataclass
class PremiumDiscountZone:
    """Represents premium/discount zones based on range."""
    high: float
    low: float
    equilibrium: float  # 50% level
    premium_start: float  # Above 50%
    discount_end: float  # Below 50%
    start_time: pd.Timestamp
    end_time: pd.Timestamp
    start_index: int = 0
    end_index: int = 0


def detect_swings(high: pd.Series, low: pd.Series, period: int = 5) -> Tuple[List[SwingPoint], List[SwingPoint]]:
    """
    Detect swing highs and lows using fractal method.
    
    Args:
        high: High prices
        low: Low prices
        period: Number of candles on each side to compare
    
    Returns:
        Tuple of (swing_highs, swing_lows)
    """
    swing_highs = []
    swing_lows = []
    
    for i in range(period, len(high) - period):
        # Check swing high
        left_highs = high.iloc[i-period:i]
        right_highs = high.iloc[i+1:i+period+1]
        
        if high.iloc[i] > left_highs.max() and high.iloc[i] > right_highs.max():
            swing_highs.append(SwingPoint(
                price=high.iloc[i],
                time=high.index[i],
                index=i,
                type='high'
            ))
        
        # Check swing low
        left_lows = low.iloc[i-period:i]
        right_lows = low.iloc[i+1:i+period+1]
        
        if low.iloc[i] < left_lows.min() and low.iloc[i] < right_lows.min():
            swing_lows.append(SwingPoint(
                price=low.iloc[i],
                time=low.index[i],
                index=i,
                type='low'
            ))
    
    return swing_highs, swing_lows


def label_swing_structure(swing_highs: List[SwingPoint], swing_lows: List[SwingPoint]) -> Dict[int, str]:
    """
    Label swings as HH, LH, HL, LL.
    
    Returns:
        Dict mapping index to label
    """
    labels = {}
    
    # Label highs
    for i in range(1, len(swing_highs)):
        prev_high = swing_highs[i-1].price
        curr_high = swing_highs[i].price
        
        if curr_high > prev_high:
            labels[swing_highs[i].index] = 'HH'  # Higher High
        else:
            labels[swing_highs[i].index] = 'LH'  # Lower High
    
    # Label lows
    for i in range(1, len(swing_lows)):
        prev_low = swing_lows[i-1].price
        curr_low = swing_lows[i].price
        
        if curr_low > prev_low:
            labels[swing_lows[i].index] = 'HL'  # Higher Low
        else:
            labels[swing_lows[i].index] = 'LL'  # Lower Low
    
    return labels


def detect_liquidity_sweeps(df: pd.DataFrame, swing_highs: List[SwingPoint], 
                            swing_lows: List[SwingPoint], pip_threshold: float = 0.0005,
                            reversal_candles: int = 3) -> Tuple[List[SwingPoint], List[SwingPoint]]:
    """
    Detect liquidity sweeps (price breaks level then reverses).
    
    Args:
        df: OHLC dataframe
        swing_highs: List of swing highs
        swing_lows: List of swing lows
        pip_threshold: Minimum break distance (default 5 pips for forex)
        reversal_candles: Candles to check for reversal
    """
    swept_highs = []
    swept_lows = []
    
    # Check swing highs for sweeps
    for swing in swing_highs:
        if swing.swept:
            continue
            
        # Look for price breaking above then reversing
        for i in range(swing.index + 1, min(swing.index + 20, len(df))):
            if df['high'].iloc[i] > swing.price + pip_threshold:
                # Check for reversal within next N candles
                reversal_window = df.iloc[i:i+reversal_candles]
                if len(reversal_window) > 0 and reversal_window['close'].iloc[-1] < swing.price:
                    swing.swept = True
                    swept_highs.append(swing)
                    break
    
    # Check swing lows for sweeps
    for swing in swing_lows:
        if swing.swept:
            continue
            
        # Look for price breaking below then reversing
        for i in range(swing.index + 1, min(swing.index + 20, len(df))):
            if df['low'].iloc[i] < swing.price - pip_threshold:
                # Check for reversal within next N candles
                reversal_window = df.iloc[i:i+reversal_candles]
                if len(reversal_window) > 0 and reversal_window['close'].iloc[-1] > swing.price:
                    swing.swept = True
                    swept_lows.append(swing)
                    break
    
    return swept_highs, swept_lows


def detect_fair_value_gaps(df: pd.DataFrame, min_gap_pct: float = 0.5,
                          min_gap_atr: float = 0.3,
                          mitigation_type: str = 'partial',
                          mitigation_threshold: float = 0.382) -> List[FairValueGap]:
    """
    Detect Fair Value Gaps (FVGs) with filtering and mitigation tracking.

    Bullish FVG: low[0] > high[2] (gap up)
    Bearish FVG: high[0] < low[2] (gap down)

    Args:
        df: OHLC dataframe
        min_gap_pct: Minimum gap size as percentage of price (default 0.5%)
        min_gap_atr: Minimum gap size as multiple of ATR (default 0.3x)
        mitigation_type: 'touch', 'partial', or 'full'
        mitigation_threshold: For partial mitigation (default 0.382 = 38.2%)

    Returns:
        List of significant FairValueGap objects with mitigation status
    """
    fvgs = []

    # Calculate ATR for filtering
    atr = df['high'].rolling(14).max() - df['low'].rolling(14).min()
    atr = atr.rolling(14).mean()

    for i in range(2, len(df)):
        # Bullish FVG
        if df['low'].iloc[i] > df['high'].iloc[i-2]:
            gap_size = df['low'].iloc[i] - df['high'].iloc[i-2]
            gap_pct = (gap_size / df['close'].iloc[i]) * 100
            gap_atr_ratio = gap_size / atr.iloc[i] if atr.iloc[i] > 0 else 0

            # Filter by minimum gap size
            if gap_pct >= min_gap_pct or gap_atr_ratio >= min_gap_atr:
                fvg = FairValueGap(
                    top=df['low'].iloc[i],
                    bottom=df['high'].iloc[i-2],
                    time=df.index[i],
                    index=i,
                    type='bullish'
                )

                # Check mitigation in future bars
                for j in range(i + 1, len(df)):
                    mitigated = False

                    if mitigation_type == 'touch':
                        # Price touches top of FVG
                        mitigated = df['low'].iloc[j] <= fvg.top
                    elif mitigation_type == 'partial':
                        # Price fills X% of FVG
                        threshold_price = fvg.top - (gap_size * mitigation_threshold)
                        mitigated = df['low'].iloc[j] <= threshold_price
                    else:  # 'full'
                        # Price completely fills FVG
                        mitigated = df['low'].iloc[j] <= fvg.bottom

                    if mitigated:
                        fvg.mitigated = True
                        fvg.mitigated_index = j
                        break

                fvgs.append(fvg)

        # Bearish FVG
        elif df['high'].iloc[i] < df['low'].iloc[i-2]:
            gap_size = df['low'].iloc[i-2] - df['high'].iloc[i]
            gap_pct = (gap_size / df['close'].iloc[i]) * 100
            gap_atr_ratio = gap_size / atr.iloc[i] if atr.iloc[i] > 0 else 0

            # Filter by minimum gap size
            if gap_pct >= min_gap_pct or gap_atr_ratio >= min_gap_atr:
                fvg = FairValueGap(
                    top=df['low'].iloc[i-2],
                    bottom=df['high'].iloc[i],
                    time=df.index[i],
                    index=i,
                    type='bearish'
                )

                # Check mitigation in future bars
                for j in range(i + 1, len(df)):
                    mitigated = False

                    if mitigation_type == 'touch':
                        # Price touches bottom of FVG
                        mitigated = df['high'].iloc[j] >= fvg.bottom
                    elif mitigation_type == 'partial':
                        # Price fills X% of FVG
                        threshold_price = fvg.bottom + (gap_size * mitigation_threshold)
                        mitigated = df['high'].iloc[j] >= threshold_price
                    else:  # 'full'
                        # Price completely fills FVG
                        mitigated = df['high'].iloc[j] >= fvg.top

                    if mitigated:
                        fvg.mitigated = True
                        fvg.mitigated_index = j
                        break

                fvgs.append(fvg)

    return fvgs


def check_fvg_mitigation(df: pd.DataFrame, fvgs: List[FairValueGap], 
                        mitigation_type: str = 'partial', 
                        partial_threshold: float = 0.382) -> List[FairValueGap]:
    """
    Check if FVGs have been mitigated.
    
    Args:
        df: OHLC dataframe
        fvgs: List of FVGs to check
        mitigation_type: 'touch', 'partial', or 'full'
        partial_threshold: Threshold for partial mitigation (default 38.2% Fibonacci)
    
    Returns:
        Updated list of FVGs with mitigation status
    """
    for fvg in fvgs:
        if fvg.mitigated:
            continue
        
        gap_size = fvg.top - fvg.bottom
        
        # Check subsequent candles
        for i in range(fvg.index + 1, len(df)):
            mitigated = False
            
            if fvg.type == 'bullish':
                # Price fills down into gap
                if mitigation_type == 'touch':
                    mitigated = df['low'].iloc[i] <= fvg.top
                elif mitigation_type == 'partial':
                    threshold_level = fvg.top - (gap_size * partial_threshold)
                    mitigated = df['low'].iloc[i] <= threshold_level
                elif mitigation_type == 'full':
                    mitigated = df['low'].iloc[i] <= fvg.bottom
            
            else:  # bearish
                # Price fills up into gap
                if mitigation_type == 'touch':
                    mitigated = df['high'].iloc[i] >= fvg.bottom
                elif mitigation_type == 'partial':
                    threshold_level = fvg.bottom + (gap_size * partial_threshold)
                    mitigated = df['high'].iloc[i] >= threshold_level
                elif mitigation_type == 'full':
                    mitigated = df['high'].iloc[i] >= fvg.top
            
            if mitigated:
                fvg.mitigated = True
                fvg.mitigation_type = mitigation_type
                break
    
    return fvgs


def detect_asian_session(df: pd.DataFrame, session_start: str = '20:00',
                         session_end: str = '00:00') -> List[AsianSession]:
    """
    Detect Asian session ranges (AMD - Accumulation phase).

    Asian session is typically 20:00-00:00 UTC (8PM-Midnight).
    This is the accumulation phase before manipulation and distribution.

    Args:
        df: OHLC dataframe with timezone-aware index
        session_start: Session start time (HH:MM format)
        session_end: Session end time (HH:MM format)

    Returns:
        List of AsianSession objects
    """
    sessions = []

    # Parse times
    start_hour, start_min = map(int, session_start.split(':'))
    end_hour, end_min = map(int, session_end.split(':'))
    start_time = dt_time(start_hour, start_min)
    end_time = dt_time(end_hour, end_min)

    # Track current session
    in_session = False
    session_high = None
    session_low = None
    session_start_idx = None

    for i in range(len(df)):
        current_time = df.index[i].time()

        # Check if entering session
        if not in_session and current_time >= start_time:
            in_session = True
            session_high = df['high'].iloc[i]
            session_low = df['low'].iloc[i]
            session_start_idx = i

        # Update session range
        elif in_session:
            session_high = max(session_high, df['high'].iloc[i])
            session_low = min(session_low, df['low'].iloc[i])

            # Check if exiting session
            if current_time >= end_time or (end_time < start_time and current_time < start_time):
                sessions.append(AsianSession(
                    high=session_high,
                    low=session_low,
                    start_time=df.index[session_start_idx],
                    end_time=df.index[i]
                ))
                in_session = False

    return sessions


def detect_manipulation(df: pd.DataFrame, asian_sessions: List[AsianSession]) -> List[AsianSession]:
    """
    Detect manipulation phase (sweep of Asian session range).

    Manipulation occurs when price sweeps the Asian high or low,
    then reverses. This creates liquidity for distribution.

    Args:
        df: OHLC dataframe
        asian_sessions: List of Asian sessions

    Returns:
        Updated list with sweep detection
    """
    for session in asian_sessions:
        # Find bars after session ends
        session_end_idx = df.index.get_loc(session.end_time)

        # Check next 20 bars for manipulation
        for i in range(session_end_idx + 1, min(session_end_idx + 20, len(df))):
            # Check for high sweep
            if not session.high_swept and df['high'].iloc[i] > session.high:
                session.high_swept = True

            # Check for low sweep
            if not session.low_swept and df['low'].iloc[i] < session.low:
                session.low_swept = True

    return asian_sessions


def calculate_open_levels(df: pd.DataFrame) -> Dict[str, pd.Series]:
    """
    Calculate Daily, Weekly, and Monthly open levels.

    These act as key support/resistance levels.

    Args:
        df: OHLC dataframe

    Returns:
        Dict with 'daily', 'weekly', 'monthly' open series
    """
    # Resample to get opens at different timeframes
    daily_opens = df['open'].resample('D').first().reindex(df.index, method='ffill')
    weekly_opens = df['open'].resample('W').first().reindex(df.index, method='ffill')
    monthly_opens = df['open'].resample('M').first().reindex(df.index, method='ffill')

    return {
        'daily_open': daily_opens,
        'weekly_open': weekly_opens,
        'monthly_open': monthly_opens
    }



def detect_order_blocks(df: pd.DataFrame, swing_highs: List[SwingPoint],
                       swing_lows: List[SwingPoint], structure_breaks: List[StructureBreak],
                       lookback: int = 50, volume_filter: bool = True,
                       volume_threshold: float = 1.2) -> List[OrderBlock]:
    """
    Detect Order Blocks - last opposite candle before structure break.

    Bullish OB: Last bearish candle before bullish break
    Bearish OB: Last bullish candle before bearish break

    Args:
        df: OHLC dataframe
        swing_highs: List of swing highs
        swing_lows: List of swing lows
        structure_breaks: List of structure breaks to find OBs for
        lookback: How far back to search for OB candle
        volume_filter: Whether to filter by volume
        volume_threshold: Minimum volume ratio (vs 20-bar average)

    Returns:
        List of OrderBlock objects
    """
    order_blocks = []

    # Calculate volume filter if needed and volume data is valid
    has_valid_volume = df['volume'].std() > 0  # Check if volume varies

    if volume_filter and has_valid_volume:
        avg_vol = df['volume'].rolling(20).mean()
        is_high_vol = df['volume'] > (avg_vol * volume_threshold)
    else:
        # If no valid volume data or filter disabled, accept all candles
        is_high_vol = pd.Series([True] * len(df), index=df.index)

    # Process each structure break to find the OB
    for break_point in structure_breaks:
        break_idx = break_point.index

        if break_point.direction == 'bullish':
            # Find last bearish candle before the break
            for k in range(break_idx - 1, max(break_idx - lookback, 0), -1):
                if df['close'].iloc[k] < df['open'].iloc[k]:  # Bearish candle
                    # Check volume filter
                    if not volume_filter or is_high_vol.iloc[k]:
                        order_blocks.append(OrderBlock(
                            top=df['high'].iloc[k],
                            bottom=df['low'].iloc[k],
                            time=df.index[k],
                            index=k,
                            type='bullish',
                            volume=df['volume'].iloc[k]
                        ))
                        break  # Stop at FIRST (most recent) opposite candle

        elif break_point.direction == 'bearish':
            # Find last bullish candle before the break
            for k in range(break_idx - 1, max(break_idx - lookback, 0), -1):
                if df['close'].iloc[k] > df['open'].iloc[k]:  # Bullish candle
                    # Check volume filter
                    if not volume_filter or is_high_vol.iloc[k]:
                        order_blocks.append(OrderBlock(
                            top=df['high'].iloc[k],
                            bottom=df['low'].iloc[k],
                            time=df.index[k],
                            index=k,
                            type='bearish',
                            volume=df['volume'].iloc[k]
                        ))
                        break  # Stop at FIRST (most recent) opposite candle

    return order_blocks


def detect_structure_breaks(df: pd.DataFrame, swing_highs: List[SwingPoint],
                           swing_lows: List[SwingPoint], break_type: str = 'body') -> Tuple[List[StructureBreak], str]:
    """
    Detect BOS (Break of Structure) and CHoCH (Change of Character).

    BOS = Break in direction of trend (continuation)
    CHoCH = Break against trend (reversal)

    Args:
        df: OHLC dataframe
        swing_highs: List of swing highs
        swing_lows: List of swing lows
        break_type: 'body' or 'wick' - what constitutes a break

    Returns:
        Tuple of (list of structure breaks, current trend)
    """
    breaks = []
    trend = "neutral"

    # Determine what price to use for break detection
    if break_type == 'body':
        check_high = df[['open', 'close']].max(axis=1)
        check_low = df[['open', 'close']].min(axis=1)
    else:  # wick
        check_high = df['high']
        check_low = df['low']

    # Track the most recent unbroken swing high/low
    last_high = None
    last_low = None

    # Combine and sort all swings chronologically
    all_swings = [(s, 'high') for s in swing_highs] + [(s, 'low') for s in swing_lows]
    all_swings.sort(key=lambda x: x[0].index)

    # Process each bar to check for breaks
    for i in range(len(df)):
        # Update last_high and last_low as we encounter new swings
        for swing, swing_type in all_swings:
            if swing.index == i:
                if swing_type == 'high':
                    last_high = swing
                else:
                    last_low = swing

        # Check for bullish break (price breaks above last high)
        if last_high is not None and check_high.iloc[i] > last_high.price:
            # Determine if BOS or CHoCH based on current trend
            if trend == "bearish":
                break_pattern = "CHoCH"  # Change of Character (reversal)
            else:
                break_pattern = "BOS"  # Break of Structure (continuation)

            breaks.append(StructureBreak(
                type=break_pattern,
                direction='bullish',
                price=last_high.price,
                time=df.index[i],
                index=i
            ))

            # Update trend and reset the broken high
            trend = "bullish"
            last_high = None

        # Check for bearish break (price breaks below last low)
        if last_low is not None and check_low.iloc[i] < last_low.price:
            # Determine if BOS or CHoCH based on current trend
            if trend == "bullish":
                break_pattern = "CHoCH"  # Change of Character (reversal)
            else:
                break_pattern = "BOS"  # Break of Structure (continuation)

            breaks.append(StructureBreak(
                type=break_pattern,
                direction='bearish',
                price=last_low.price,
                time=df.index[i],
                index=i
            ))

            # Update trend and reset the broken low
            trend = "bearish"
            last_low = None

    return breaks, trend



def track_liquidity_levels(df: pd.DataFrame, swing_highs: List[SwingPoint],
                          swing_lows: List[SwingPoint]) -> List[LiquidityLevel]:
    """
    Track liquidity levels from swing highs/lows.

    Each swing creates a liquidity level that extends forward until swept.
    Swept = price breaks through the level.

    Args:
        df: OHLC dataframe
        swing_highs: List of swing highs
        swing_lows: List of swing lows

    Returns:
        List of LiquidityLevel objects with sweep status
    """
    liquidity_levels = []

    # Process swing highs
    for swing in swing_highs:
        level = LiquidityLevel(
            price=swing.price,
            type='high',
            start_index=swing.index,
            start_time=swing.time,
            swept=False
        )

        # Check if swept in subsequent bars
        for i in range(swing.index + 1, len(df)):
            if df['high'].iloc[i] > swing.price:
                level.swept = True
                level.swept_index = i
                level.swept_time = df.index[i]
                break

        liquidity_levels.append(level)

    # Process swing lows
    for swing in swing_lows:
        level = LiquidityLevel(
            price=swing.price,
            type='low',
            start_index=swing.index,
            start_time=swing.time,
            swept=False
        )

        # Check if swept in subsequent bars
        for i in range(swing.index + 1, len(df)):
            if df['low'].iloc[i] < swing.price:
                level.swept = True
                level.swept_index = i
                level.swept_time = df.index[i]
                break

        liquidity_levels.append(level)

    return liquidity_levels


def detect_round_levels(df: pd.DataFrame, interval: int = None) -> List[RoundLevel]:
    """
    Detect round number levels (00, 50) within price range.

    These are psychological levels where price often reacts.

    Args:
        df: OHLC dataframe
        interval: Base interval (auto-detected if None)
                 e.g., 100 for BTC (90000, 90100, 90200...)
                       1 for forex (1.0800, 1.0850, 1.0900...)

    Returns:
        List of RoundLevel objects
    """
    price_min = df['low'].min()
    price_max = df['high'].max()

    # Auto-detect interval based on price range
    if interval is None:
        price_range = price_max - price_min
        if price_max > 10000:  # Crypto/indices
            interval = 100
        elif price_max > 1000:  # Some stocks
            interval = 10
        elif price_max > 100:  # Some stocks
            interval = 1
        else:  # Forex
            interval = 0.01

    levels = []

    # Generate 00 levels
    current = int(price_min / interval) * interval
    while current <= price_max:
        levels.append(RoundLevel(
            price=float(current),
            level_type='00'
        ))
        current += interval

    # Generate 50 levels (halfway between 00 levels)
    half_interval = interval / 2
    current = int(price_min / interval) * interval + half_interval
    while current <= price_max:
        levels.append(RoundLevel(
            price=float(current),
            level_type='50'
        ))
        current += interval

    return levels



def detect_open_levels(df: pd.DataFrame) -> Dict[str, List[OpenLevel]]:
    """
    Detect session open levels (Daily/Weekly/Monthly).

    These are key levels where price often reacts.

    Args:
        df: OHLC dataframe with datetime index

    Returns:
        Dict with 'daily', 'weekly', 'monthly' lists of OpenLevel objects
    """
    levels = {
        'daily': [],
        'weekly': [],
        'monthly': []
    }

    # Detect daily opens
    if hasattr(df.index, 'date'):
        prev_date = None
        for i in range(len(df)):
            current_date = df.index[i].date()
            if prev_date is not None and current_date != prev_date:
                levels['daily'].append(OpenLevel(
                    price=df['open'].iloc[i],
                    level_type='daily',
                    time=df.index[i],
                    index=i
                ))
            prev_date = current_date

    # Detect weekly opens
    if hasattr(df.index, 'isocalendar'):
        prev_week = None
        for i in range(len(df)):
            current_week = df.index[i].isocalendar()[1]
            if prev_week is not None and current_week != prev_week:
                levels['weekly'].append(OpenLevel(
                    price=df['open'].iloc[i],
                    level_type='weekly',
                    time=df.index[i],
                    index=i
                ))
            prev_week = current_week

    # Detect monthly opens
    if hasattr(df.index, 'month'):
        prev_month = None
        for i in range(len(df)):
            current_month = df.index[i].month
            if prev_month is not None and current_month != prev_month:
                levels['monthly'].append(OpenLevel(
                    price=df['open'].iloc[i],
                    level_type='monthly',
                    time=df.index[i],
                    index=i
                ))
            prev_month = current_month

    return levels


def detect_premium_discount_zones(df: pd.DataFrame,
                                  lookback: int = 100) -> List[PremiumDiscountZone]:
    """
    Detect premium and discount zones based on price range.

    Premium zone: Above 50% of range (sell zone)
    Discount zone: Below 50% of range (buy zone)
    Equilibrium: 50% level

    Args:
        df: OHLC dataframe
        lookback: Period to calculate range

    Returns:
        List of PremiumDiscountZone objects
    """
    zones = []

    for i in range(lookback, len(df)):
        # Calculate range over lookback period
        period_high = df['high'].iloc[i-lookback:i+1].max()
        period_low = df['low'].iloc[i-lookback:i+1].min()

        # Calculate levels
        equilibrium = (period_high + period_low) / 2

        zone = PremiumDiscountZone(
            high=period_high,
            low=period_low,
            equilibrium=equilibrium,
            premium_start=equilibrium,
            discount_end=equilibrium,
            start_time=df.index[i-lookback],
            end_time=df.index[i],
            start_index=i-lookback,
            end_index=i
        )

        zones.append(zone)

    return zones


def detect_manipulation(df: pd.DataFrame, asian_sessions: List[AsianSession]) -> List[AsianSession]:
    """
    Detect manipulation (sweep of Asian session range).

    Manipulation occurs when price sweeps the Asian session high or low
    during London/NY session, then reverses.

    Args:
        df: OHLC dataframe
        asian_sessions: List of Asian sessions

    Returns:
        Updated list with manipulation flags
    """
    for session in asian_sessions:
        # Find bars after session end
        session_end_idx = df.index.get_loc(session.end_time)

        # Check next 50 bars for manipulation
        for i in range(session_end_idx + 1, min(session_end_idx + 50, len(df))):
            # Check if high was swept
            if df['high'].iloc[i] > session.high:
                session.high_swept = True

            # Check if low was swept
            if df['low'].iloc[i] < session.low:
                session.low_swept = True

    return asian_sessions


def calculate_market_structure_score(df: pd.DataFrame, index: int,
                                     structure: Dict) -> float:
    """
    Calculate confluence score at a given bar.

    Higher score = more ICT concepts aligning at this level.

    Args:
        df: OHLC dataframe
        index: Bar index to check
        structure: Market structure dict from analyze_market_structure()

    Returns:
        Confluence score (0-10)
    """
    score = 0.0
    current_price = df['close'].iloc[index]
    tolerance = df['close'].iloc[index] * 0.001  # 0.1% tolerance

    # Check proximity to swing points (1 point each)
    for swing in structure.get('swing_highs', []):
        if abs(current_price - swing.price) < tolerance:
            score += 1.0
            break

    for swing in structure.get('swing_lows', []):
        if abs(current_price - swing.price) < tolerance:
            score += 1.0
            break

    # Check if inside FVG (2 points)
    for fvg in structure.get('fvgs', []):
        if not fvg.mitigated and fvg.bottom <= current_price <= fvg.top:
            score += 2.0
            break

    # Check if inside Order Block (2 points)
    for ob in structure.get('order_blocks', []):
        if not ob.mitigated and ob.bottom <= current_price <= ob.top:
            score += 2.0
            break

    # Check proximity to liquidity levels (1 point)
    for liq in structure.get('liquidity_levels', []):
        if not liq.swept and abs(current_price - liq.price) < tolerance:
            score += 1.0
            break

    # Check proximity to open levels (1 point)
    open_levels = structure.get('open_levels', {})
    for level_type in ['daily', 'weekly', 'monthly']:
        for level in open_levels.get(level_type, []):
            if abs(current_price - level.price) < tolerance:
                score += 1.0
                break

    # Check if at premium/discount zone boundary (1 point)
    zones = structure.get('premium_discount_zones', [])
    if zones:
        latest_zone = zones[-1]
        if abs(current_price - latest_zone.equilibrium) < tolerance:
            score += 1.0

    # Check recent structure break (2 points)
    for brk in structure.get('structure_breaks', []):
        if brk.index == index or brk.index == index - 1:
            score += 2.0
            break

    return min(score, 10.0)  # Cap at 10




def analyze_market_structure(df: pd.DataFrame, swing_period: int = 5,
                           break_type: str = 'body',
                           fvg_mitigation: str = 'partial',
                           fvg_mitigation_threshold: float = 0.382,
                           fvg_min_gap_pct: float = 0.5,
                           fvg_min_gap_atr: float = 0.3,
                           volume_filter: bool = True,
                           detect_amd: bool = False,
                           round_level_interval: int = None,
                           premium_discount_lookback: int = 100) -> Dict:
    """
    Complete market structure analysis with ICT concepts.

    Args:
        df: OHLC dataframe
        swing_period: Period for swing detection
        break_type: 'body' or 'wick' for structure breaks
        fvg_mitigation: 'touch', 'partial', or 'full'
        fvg_mitigation_threshold: Threshold for partial mitigation (0.382 = 38.2%)
        fvg_min_gap_pct: Minimum FVG gap size as % of price
        fvg_min_gap_atr: Minimum FVG gap size as multiple of ATR
        volume_filter: Whether to filter OBs by volume
        detect_amd: Whether to detect Asian session (AMD logic)
        round_level_interval: Interval for round levels (auto if None)
        premium_discount_lookback: Lookback for premium/discount zones

    Returns:
        Dict with all structure components
    """
    # Detect swings
    swing_highs, swing_lows = detect_swings(df['high'], df['low'], swing_period)

    # Label swing structure
    swing_labels = label_swing_structure(swing_highs, swing_lows)

    # Detect liquidity sweeps
    swept_highs, swept_lows = detect_liquidity_sweeps(df, swing_highs, swing_lows)

    # Detect structure breaks (BOS/CHoCH) - MUST come before OBs
    structure_breaks, current_trend = detect_structure_breaks(df, swing_highs, swing_lows,
                                                              break_type=break_type)

    # Detect FVGs with mitigation tracking
    fvgs = detect_fair_value_gaps(
        df,
        min_gap_pct=fvg_min_gap_pct,
        min_gap_atr=fvg_min_gap_atr,
        mitigation_type=fvg_mitigation,
        mitigation_threshold=fvg_mitigation_threshold
    )

    # Detect order blocks (needs structure breaks)
    order_blocks = detect_order_blocks(df, swing_highs, swing_lows, structure_breaks,
                                      volume_filter=volume_filter)

    # Track liquidity levels
    liquidity_levels = track_liquidity_levels(df, swing_highs, swing_lows)

    # Detect round number levels
    round_levels = detect_round_levels(df, interval=round_level_interval)

    # Detect open levels (D/W/M)
    open_levels = detect_open_levels(df)

    # Detect premium/discount zones
    premium_discount_zones = detect_premium_discount_zones(df, lookback=premium_discount_lookback)

    # AMD logic (optional)
    asian_sessions = []
    if detect_amd:
        asian_sessions = detect_asian_session(df)
        asian_sessions = detect_manipulation(df, asian_sessions)

    # Build result dict
    result = {
        'swing_highs': swing_highs,
        'swing_lows': swing_lows,
        'swing_labels': swing_labels,
        'swept_highs': swept_highs,
        'swept_lows': swept_lows,
        'fvgs': fvgs,
        'order_blocks': order_blocks,
        'structure_breaks': structure_breaks,
        'current_trend': current_trend,
        'liquidity_levels': liquidity_levels,
        'round_levels': round_levels,
        'open_levels': open_levels,
        'premium_discount_zones': premium_discount_zones,
        'asian_sessions': asian_sessions
    }

    return result
