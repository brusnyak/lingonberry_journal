"""
ICT-based feature engineering for ML models.
Extracts features from market structure analysis (Order Blocks, FVGs, liquidity, etc.)
"""
import pandas as pd
import numpy as np
from typing import Dict, List
from ..features.market_structure import analyze_market_structure


def calculate_distance_to_price(price: float, level: float) -> float:
    """
    Calculate normalized distance from price to a level.
    
    Args:
        price: Current price
        level: Target level
    
    Returns:
        Normalized distance (positive = above, negative = below)
    """
    if price == 0:
        return 0.0
    return (level - price) / price


def find_nearest_order_block(current_idx: int, current_price: float, 
                             order_blocks: List, ob_type: str) -> float:
    """
    Find distance to nearest order block of specified type.
    
    Args:
        current_idx: Current bar index
        current_price: Current price
        order_blocks: List of OrderBlock objects
        ob_type: 'bullish' or 'bearish'
    
    Returns:
        Normalized distance to nearest OB (0 if none found)
    """
    min_distance = float('inf')
    
    for ob in order_blocks:
        # Only consider OBs that formed before current bar and not too old
        if ob.index < current_idx and (current_idx - ob.index) < 500:
            if ob.type == ob_type:
                # Distance to OB center
                ob_center = (ob.top + ob.bottom) / 2
                distance = abs(calculate_distance_to_price(current_price, ob_center))
                
                if distance < min_distance:
                    min_distance = distance
    
    return min_distance if min_distance != float('inf') else 0.0


def find_nearest_fvg(current_idx: int, current_price: float,
                    fvgs: List, fvg_type: str) -> float:
    """
    Find distance to nearest unmitigated FVG of specified type.
    
    Args:
        current_idx: Current bar index
        current_price: Current price
        fvgs: List of FairValueGap objects
        fvg_type: 'bullish' or 'bearish'
    
    Returns:
        Normalized distance to nearest FVG (0 if none found)
    """
    min_distance = float('inf')
    
    for fvg in fvgs:
        # Only consider unmitigated FVGs that formed before current bar
        if fvg.index < current_idx and not fvg.mitigated:
            if fvg.type == fvg_type:
                # Distance to FVG center
                fvg_center = (fvg.top + fvg.bottom) / 2
                distance = abs(calculate_distance_to_price(current_price, fvg_center))
                
                if distance < min_distance:
                    min_distance = distance
    
    return min_distance if min_distance != float('inf') else 0.0


def find_nearest_liquidity(current_idx: int, current_price: float,
                          liquidity_levels: List) -> float:
    """
    Find distance to nearest unswept liquidity level.
    
    Args:
        current_idx: Current bar index
        current_price: Current price
        liquidity_levels: List of LiquidityLevel objects
    
    Returns:
        Normalized distance to nearest liquidity (0 if none found)
    """
    min_distance = float('inf')
    
    for liq in liquidity_levels:
        # Only consider unswept liquidity that formed before current bar
        if liq.start_index < current_idx and not liq.swept:
            distance = abs(calculate_distance_to_price(current_price, liq.price))
            
            if distance < min_distance:
                min_distance = distance
    
    return min_distance if min_distance != float('inf') else 0.0


def get_premium_discount_zone(current_idx: int, current_price: float,
                              premium_discount_zones: List) -> float:
    """
    Get current premium/discount zone indicator.
    
    Args:
        current_idx: Current bar index
        current_price: Current price
        premium_discount_zones: List of PremiumDiscountZone objects
    
    Returns:
        Zone indicator: -1 (discount), 0 (equilibrium), +1 (premium)
    """
    # Find the most recent zone that includes current bar
    for zone in reversed(premium_discount_zones):
        if zone.start_index <= current_idx <= zone.end_index:
            # Calculate position within range
            range_size = zone.high - zone.low
            if range_size == 0:
                return 0.0
            
            position = (current_price - zone.low) / range_size
            
            # Map to -1, 0, +1
            if position < 0.4:
                return -1.0  # Discount
            elif position > 0.6:
                return 1.0   # Premium
            else:
                return 0.0   # Equilibrium
    
    return 0.0


def calculate_structure_break_momentum(current_idx: int, 
                                      structure_breaks: List) -> float:
    """
    Calculate bars since last structure break (normalized).
    
    Args:
        current_idx: Current bar index
        structure_breaks: List of StructureBreak objects
    
    Returns:
        Normalized momentum (0-1, higher = more recent break)
    """
    # Find most recent structure break
    most_recent_break = None
    
    for sb in structure_breaks:
        if sb.index < current_idx:
            if most_recent_break is None or sb.index > most_recent_break.index:
                most_recent_break = sb
    
    if most_recent_break is None:
        return 0.0
    
    bars_since = current_idx - most_recent_break.index
    
    # Normalize: recent breaks (0-20 bars) = high momentum
    # Older breaks (>100 bars) = low momentum
    momentum = max(0.0, 1.0 - (bars_since / 100.0))
    
    return momentum


def extract_ict_features_for_bar(current_idx: int, df: pd.DataFrame,
                                 market_structure: Dict) -> Dict[str, float]:
    """
    Extract all ICT features for a single bar.
    
    Args:
        current_idx: Current bar index
        df: OHLC dataframe
        market_structure: Dict from analyze_market_structure()
    
    Returns:
        Dict of ICT features
    """
    current_price = df['close'].iloc[current_idx]
    
    # Extract features
    features = {
        'dist_bull_ob': find_nearest_order_block(
            current_idx, current_price, 
            market_structure['order_blocks'], 'bullish'
        ),
        'dist_bear_ob': find_nearest_order_block(
            current_idx, current_price,
            market_structure['order_blocks'], 'bearish'
        ),
        'dist_bull_fvg': find_nearest_fvg(
            current_idx, current_price,
            market_structure['fvgs'], 'bullish'
        ),
        'dist_bear_fvg': find_nearest_fvg(
            current_idx, current_price,
            market_structure['fvgs'], 'bearish'
        ),
        'dist_liquidity': find_nearest_liquidity(
            current_idx, current_price,
            market_structure['liquidity_levels']
        ),
        'premium_discount': get_premium_discount_zone(
            current_idx, current_price,
            market_structure['premium_discount_zones']
        ),
        'structure_momentum': calculate_structure_break_momentum(
            current_idx, market_structure['structure_breaks']
        )
    }
    
    return features


def add_ict_features_to_dataframe(df: pd.DataFrame, 
                                  swing_period: int = 5) -> pd.DataFrame:
    """
    Add ICT features to dataframe for ML training.
    
    Args:
        df: OHLC dataframe with technical indicators
        swing_period: Period for swing detection
    
    Returns:
        DataFrame with added ICT feature columns
    """
    # Analyze market structure
    market_structure = analyze_market_structure(
        df,
        swing_period=swing_period,
        fvg_mitigation='partial',
        fvg_mitigation_threshold=0.382,
        fvg_min_gap_pct=0.5,
        volume_filter=True,
        premium_discount_lookback=100
    )
    
    # Initialize feature columns
    ict_feature_names = [
        'dist_bull_ob', 'dist_bear_ob',
        'dist_bull_fvg', 'dist_bear_fvg',
        'dist_liquidity', 'premium_discount',
        'structure_momentum'
    ]
    
    for feature in ict_feature_names:
        df[feature] = 0.0
    
    # Calculate confluence score for each bar
    confluence_scores = []
    
    # Extract features for each bar
    for i in range(len(df)):
        if i < swing_period:
            # Not enough history
            confluence_scores.append(0.0)
            continue
        
        features = extract_ict_features_for_bar(i, df, market_structure)
        
        # Update dataframe
        for feature_name, value in features.items():
            df.iloc[i, df.columns.get_loc(feature_name)] = value
        
        # Calculate confluence score
        score = calculate_confluence_score_for_bar(i, df, market_structure)
        confluence_scores.append(score)
    
    # Add confluence score
    df['confluence_score'] = confluence_scores
    
    return df


def calculate_confluence_score_for_bar(current_idx: int, df: pd.DataFrame,
                                       market_structure: Dict) -> float:
    """
    Calculate market structure confluence score (0-10) for a bar.
    
    Score components:
    - Swing points: +1 each
    - Inside FVG: +2
    - Inside OB: +2
    - Near liquidity: +1
    - Near open level: +1
    - At premium/discount boundary: +1
    - Recent structure break: +2
    
    Args:
        current_idx: Current bar index
        df: OHLC dataframe
        market_structure: Dict from analyze_market_structure()
    
    Returns:
        Confluence score (0-10)
    """
    score = 0.0
    current_price = df['close'].iloc[current_idx]
    current_high = df['high'].iloc[current_idx]
    current_low = df['low'].iloc[current_idx]
    
    # Check if at swing point
    for swing in market_structure['swing_highs']:
        if swing.index == current_idx:
            score += 1
            break
    
    for swing in market_structure['swing_lows']:
        if swing.index == current_idx:
            score += 1
            break
    
    # Check if inside unmitigated FVG
    for fvg in market_structure['fvgs']:
        if fvg.index < current_idx and not fvg.mitigated:
            if fvg.bottom <= current_price <= fvg.top:
                score += 2
                break
    
    # Check if inside OB
    for ob in market_structure['order_blocks']:
        if ob.index < current_idx:
            if ob.bottom <= current_price <= ob.top:
                score += 2
                break
    
    # Check if near liquidity (within 0.5%)
    for liq in market_structure['liquidity_levels']:
        if liq.start_index < current_idx and not liq.swept:
            distance_pct = abs(current_price - liq.price) / current_price
            if distance_pct < 0.005:  # Within 0.5%
                score += 1
                break
    
    # Check if near open level (within 0.3%)
    # open_levels is a dict with 'daily', 'weekly', 'monthly' keys
    open_levels_dict = market_structure.get('open_levels', {})
    for level_type in ['daily', 'weekly', 'monthly']:
        for open_level in open_levels_dict.get(level_type, []):
            if open_level.index <= current_idx:
                distance_pct = abs(current_price - open_level.price) / current_price
                if distance_pct < 0.003:  # Within 0.3%
                    score += 1
                    break
    
    # Check if at premium/discount boundary
    for zone in market_structure['premium_discount_zones']:
        if zone.start_index <= current_idx <= zone.end_index:
            position = (current_price - zone.low) / (zone.high - zone.low) if zone.high != zone.low else 0.5
            # At equilibrium (45-55%)
            if 0.45 <= position <= 0.55:
                score += 1
            break
    
    # Check for recent structure break (within 10 bars)
    for sb in market_structure['structure_breaks']:
        if sb.index < current_idx and (current_idx - sb.index) <= 10:
            score += 2
            break
    
    return min(score, 10.0)  # Cap at 10
