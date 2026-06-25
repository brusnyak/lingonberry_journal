"""
Hybrid ICT + ML Strategy

Based on research:
1. Use original Lorentzian settings (k=8, RSI/WT/CCI/ADX features)
2. ICT as entry filter (not features):
   - Liquidity sweep
   - Market structure shift (CHoCH/BOS)
   - Entry at FVG/OB
3. Liquidity-based TPs (session high/low, swing high/low, 50% FVG)
4. Proper risk management (2:1 minimum RR)
"""

import sys
import os
script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
parent_dir = os.path.join(script_dir, '..')
sys.path.insert(0, parent_dir)

import pandas as pd
import numpy as np
from src.data.loader import DataLoader
from src.features.technicals import calculate_all_technicals
from src.features.market_structure import analyze_market_structure
from src.ml.lorentzian import LorentzianClassifier, create_labels


def prepare_original_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare features using original Lorentzian indicators:
    RSI, WT (Wave Trend), CCI, ADX
    """
    features = pd.DataFrame(index=df.index)
    
    # RSI (14 period)
    features['rsi'] = df['rsi']
    
    # Wave Trend (WT1 and WT2)
    features['wt1'] = df['wt1']
    features['wt2'] = df['wt2']
    
    # CCI (20 period)
    features['cci'] = df['cci']
    
    # ADX (14 period)
    features['adx'] = df['adx']
    
    # Normalize to 0-1 range
    for col in features.columns:
        series = features[col]
        rolling_min = series.rolling(window=2000, min_periods=1).min()
        rolling_max = series.rolling(window=2000, min_periods=1).max()
        features[col] = (series - rolling_min) / (rolling_max - rolling_min + 1e-10)
    
    return features.fillna(0)


def detect_liquidity_sweep(df: pd.DataFrame, ms: dict, idx: int, lookback: int = 20) -> dict:
    """
    Detect if a liquidity sweep just occurred.
    
    Returns:
        dict with 'swept', 'direction', 'level_price'
    """
    if idx < lookback:
        return {'swept': False, 'direction': None, 'level_price': None}
    
    current_bar = df.iloc[idx]
    prev_bars = df.iloc[idx-lookback:idx]
    
    # Check for sweep of recent high (bearish sweep)
    recent_high = prev_bars['high'].max()
    recent_high_idx = prev_bars['high'].idxmax()
    
    # Sweep = wick above high but close below
    if current_bar['high'] > recent_high and current_bar['close'] < recent_high:
        return {
            'swept': True,
            'direction': 'bearish',  # Swept high, expect down
            'level_price': recent_high,
            'sweep_type': 'high'
        }
    
    # Check for sweep of recent low (bullish sweep)
    recent_low = prev_bars['low'].min()
    recent_low_idx = prev_bars['low'].idxmin()
    
    # Sweep = wick below low but close above
    if current_bar['low'] < recent_low and current_bar['close'] > recent_low:
        return {
            'swept': True,
            'direction': 'bullish',  # Swept low, expect up
            'level_price': recent_low,
            'sweep_type': 'low'
        }
    
    return {'swept': False, 'direction': None, 'level_price': None}


def detect_market_structure_shift(df: pd.DataFrame, ms: dict, idx: int, direction: str, lookback: int = 30) -> bool:
    """
    Check if market structure shift (CHoCH or BOS) occurred recently.
    More lenient - look back further and check for any structure break in direction.
    """
    # Look for recent structure breaks
    for sb in ms['structure_breaks']:
        if idx - lookback <= sb.index <= idx:
            # Check if structure break aligns with expected direction
            if direction == 'bullish' and sb.direction == 'bullish':
                return True
            elif direction == 'bearish' and sb.direction == 'bearish':
                return True
    
    return False


def find_entry_zone(df: pd.DataFrame, ms: dict, idx: int, direction: str, tolerance_pct: float = 2.0) -> dict:
    """
    Find if price is at or near a valid entry zone (FVG or OB).
    Increased tolerance to 2% to catch more setups.
    
    Returns:
        dict with 'valid', 'type', 'zone_high', 'zone_low'
    """
    current_price = df.iloc[idx]['close']
    
    # Check FVGs (look back 50 bars)
    for fvg in ms['fvgs']:
        if idx - 50 <= fvg.index < idx and not fvg.mitigated:
            fvg_mid = (fvg.top + fvg.bottom) / 2
            distance_pct = abs(current_price - fvg_mid) / current_price * 100
            
            # Bullish entry: price at or near bullish FVG
            if direction == 'bullish' and fvg.type == 'bullish' and distance_pct <= tolerance_pct:
                return {
                    'valid': True,
                    'type': 'fvg',
                    'zone_high': fvg.top,
                    'zone_low': fvg.bottom,
                    'fvg_50': fvg_mid
                }
            # Bearish entry: price at or near bearish FVG
            elif direction == 'bearish' and fvg.type == 'bearish' and distance_pct <= tolerance_pct:
                return {
                    'valid': True,
                    'type': 'fvg',
                    'zone_high': fvg.top,
                    'zone_low': fvg.bottom,
                    'fvg_50': fvg_mid
                }
    
    # Check Order Blocks (look back 50 bars)
    for ob in ms['order_blocks']:
        if idx - 50 <= ob.index < idx and not ob.mitigated:
            ob_mid = (ob.top + ob.bottom) / 2
            distance_pct = abs(current_price - ob_mid) / current_price * 100
            
            # Bullish entry: price at or near bullish OB
            if direction == 'bullish' and ob.type == 'bullish' and distance_pct <= tolerance_pct:
                return {
                    'valid': True,
                    'type': 'ob',
                    'zone_high': ob.top,
                    'zone_low': ob.bottom,
                    'fvg_50': None
                }
            # Bearish entry: price at or near bearish OB
            elif direction == 'bearish' and ob.type == 'bearish' and distance_pct <= tolerance_pct:
                return {
                    'valid': True,
                    'type': 'ob',
                    'zone_high': ob.top,
                    'zone_low': ob.bottom,
                    'fvg_50': None
                }
    
    return {'valid': False, 'type': None, 'zone_high': None, 'zone_low': None}


def find_liquidity_target(df: pd.DataFrame, ms: dict, idx: int, direction: str, entry_price: float) -> dict:
    """
    Find liquidity target for take profit.
    Priority: Swing high/low > Session high/low > 50% FVG
    """
    lookback = 50
    
    if direction == 'bullish':
        # Look for liquidity above
        # 1. Swing highs
        recent_high = df.iloc[max(0, idx-lookback):idx]['high'].max()
        if recent_high > entry_price:
            distance_pct = ((recent_high - entry_price) / entry_price) * 100
            if distance_pct <= 5.0:  # Within 5%
                return {
                    'found': True,
                    'price': recent_high,
                    'type': 'swing_high',
                    'distance_pct': distance_pct
                }
        
        # 2. Unswept liquidity levels
        for liq in ms['liquidity_levels']:
            if liq.type == 'high' and not liq.swept and liq.price > entry_price:
                distance_pct = ((liq.price - entry_price) / entry_price) * 100
                if distance_pct <= 5.0:
                    return {
                        'found': True,
                        'price': liq.price,
                        'type': 'liquidity_level',
                        'distance_pct': distance_pct
                    }
    
    else:  # bearish
        # Look for liquidity below
        # 1. Swing lows
        recent_low = df.iloc[max(0, idx-lookback):idx]['low'].min()
        if recent_low < entry_price:
            distance_pct = ((entry_price - recent_low) / entry_price) * 100
            if distance_pct <= 5.0:
                return {
                    'found': True,
                    'price': recent_low,
                    'type': 'swing_low',
                    'distance_pct': distance_pct
                }
        
        # 2. Unswept liquidity levels
        for liq in ms['liquidity_levels']:
            if liq.type == 'low' and not liq.swept and liq.price < entry_price:
                distance_pct = ((entry_price - liq.price) / entry_price) * 100
                if distance_pct <= 5.0:
                    return {
                        'found': True,
                        'price': liq.price,
                        'type': 'liquidity_level',
                        'distance_pct': distance_pct
                    }
    
    return {'found': False, 'price': None, 'type': None, 'distance_pct': None}


def hybrid_strategy(df: pd.DataFrame, features: pd.DataFrame, ms: dict) -> list:
    """
    Hybrid ICT + ML strategy.
    
    Process:
    1. ML predicts direction
    2. Wait for ICT setup:
       - Liquidity sweep
       - Market structure shift
       - Entry at FVG/OB
    3. Enter with liquidity-based TP
    """
    # Create labels
    labels = create_labels(df, forward_bars=4)
    
    # Train ML classifier (original settings: k=8)
    print("Training ML classifier (k=8, lookback=2000)...")
    clf = LorentzianClassifier(k=8, lookback=2000)
    predictions = clf.predict_series(features, labels, start_idx=2000)
    
    # Align predictions
    signals = pd.DataFrame(index=df.index)
    signals['signal'] = 0
    signals['confidence'] = 0.0
    signals.loc[predictions.index, 'signal'] = predictions['signal']
    signals.loc[predictions.index, 'confidence'] = predictions['confidence']
    
    # Simulate trades
    trades = []
    in_position = False
    entry_idx = None
    entry_price = None
    entry_signal = None
    stop_loss = None
    take_profit = None
    
    stats = {
        'ml_signals': 0,
        'liquidity_sweeps': 0,
        'mss_confirmed': 0,
        'entry_zones_found': 0,
        'liquidity_targets_found': 0,
        'trades_executed': 0
    }
    
    print("Simulating trades...")
    for i in range(2000, len(df)):
        if in_position:
            # Check exits
            current_price = df.iloc[i]['close']
            exit_reason = None
            exit_price = None
            
            # Take profit
            if take_profit is not None:
                if entry_signal == 1 and current_price >= take_profit:
                    exit_reason = 'take_profit'
                    exit_price = take_profit
                elif entry_signal == -1 and current_price <= take_profit:
                    exit_reason = 'take_profit'
                    exit_price = take_profit
            
            # Stop loss
            if exit_reason is None:
                if entry_signal == 1 and current_price <= stop_loss:
                    exit_reason = 'stop_loss'
                    exit_price = stop_loss
                elif entry_signal == -1 and current_price >= stop_loss:
                    exit_reason = 'stop_loss'
                    exit_price = stop_loss
            
            # Opposite signal
            if exit_reason is None and signals.iloc[i]['signal'] == -entry_signal:
                exit_reason = 'opposite_signal'
                exit_price = current_price
            
            if exit_reason is not None:
                pnl_pct = ((exit_price - entry_price) / entry_price) * entry_signal * 100
                trades.append({
                    'entry_idx': entry_idx,
                    'entry_time': df.index[entry_idx],
                    'entry_price': entry_price,
                    'exit_idx': i,
                    'exit_time': df.index[i],
                    'exit_price': exit_price,
                    'direction': 'long' if entry_signal == 1 else 'short',
                    'pnl_pct': pnl_pct,
                    'bars_in_trade': i - entry_idx,
                    'exit_reason': exit_reason,
                    'stop_loss': stop_loss,
                    'take_profit': take_profit,
                })
                
                in_position = False
        
        else:
            # Check for ICT setup (simplified - don't require sweep first)
            ml_signal = signals.iloc[i]['signal']
            
            if ml_signal != 0:
                stats['ml_signals'] += 1
                ml_direction = 'bullish' if ml_signal == 1 else 'bearish'
                
                # Step 1: Check for market structure shift (most important)
                if not detect_market_structure_shift(df, ms, i, ml_direction, lookback=30):
                    continue
                
                stats['mss_confirmed'] += 1
                
                # Step 2: Check if at entry zone (FVG/OB)
                entry_zone = find_entry_zone(df, ms, i, ml_direction, tolerance_pct=2.0)
                if not entry_zone['valid']:
                    continue
                
                stats['entry_zones_found'] += 1
                
                # Step 3: Check for recent liquidity sweep (optional confirmation)
                sweep = detect_liquidity_sweep(df, ms, i, lookback=20)
                if sweep['swept'] and sweep['direction'] == ml_direction:
                    stats['liquidity_sweeps'] += 1
                
                # Step 4: Find liquidity target
                current_price = df.iloc[i]['close']
                liq_target = find_liquidity_target(df, ms, i, ml_direction, current_price)
                if not liq_target['found']:
                    continue
                
                stats['liquidity_targets_found'] += 1
                
                # Calculate stop loss (below/above entry zone)
                if ml_signal == 1:
                    sl = entry_zone['zone_low'] - (df.iloc[i]['atr'] * 0.5)
                    tp = liq_target['price']
                else:
                    sl = entry_zone['zone_high'] + (df.iloc[i]['atr'] * 0.5)
                    tp = liq_target['price']
                
                # Check RR ratio
                risk = abs(current_price - sl)
                reward = abs(tp - current_price)
                rr_ratio = reward / risk if risk > 0 else 0
                
                if rr_ratio < 2.0:
                    continue
                
                # Enter trade
                in_position = True
                entry_idx = i
                entry_price = current_price
                entry_signal = ml_signal
                stop_loss = sl
                take_profit = tp
                stats['trades_executed'] += 1
    
    return trades, stats


def analyze_results(trades: list, df: pd.DataFrame):
    """Analyze and display results."""
    if not trades:
        print("\n❌ No trades executed!")
        return None
    
    trades_df = pd.DataFrame(trades)
    
    print(f"\n{'='*60}")
    print(f"HYBRID ICT + ML STRATEGY RESULTS")
    print(f"{'='*60}")
    
    # Basic stats
    total_trades = len(trades_df)
    winners = trades_df[trades_df['pnl_pct'] > 0]
    losers = trades_df[trades_df['pnl_pct'] <= 0]
    
    print(f"\nTrade Statistics:")
    print(f"  Total Trades: {total_trades}")
    print(f"  Winners: {len(winners)} ({len(winners)/total_trades*100:.1f}%)")
    print(f"  Losers: {len(losers)} ({len(losers)/total_trades*100:.1f}%)")
    
    # PnL
    print(f"\nPnL Analysis:")
    print(f"  Avg PnL: {trades_df['pnl_pct'].mean():.2f}%")
    print(f"  Avg Winner: {winners['pnl_pct'].mean():.2f}%")
    print(f"  Avg Loser: {losers['pnl_pct'].mean():.2f}%")
    
    # RR
    avg_win = winners['pnl_pct'].mean() if len(winners) > 0 else 0
    avg_loss = abs(losers['pnl_pct'].mean()) if len(losers) > 0 else 1
    rr_ratio = avg_win / avg_loss if avg_loss > 0 else 0
    print(f"\nRisk-Reward:")
    print(f"  RR Ratio: {rr_ratio:.2f}:1 {'✅' if rr_ratio >= 2.0 else '⚠️'}")
    
    # Profit factor
    total_wins = winners['pnl_pct'].sum()
    total_losses = abs(losers['pnl_pct'].sum())
    profit_factor = total_wins / total_losses if total_losses > 0 else 0
    print(f"  Profit Factor: {profit_factor:.2f}")
    
    # Frequency
    date_range = (df.index[-1] - df.index[0]).days
    trades_per_week = (total_trades / date_range) * 7
    print(f"\nTrade Frequency:")
    print(f"  Trades per Week: {trades_per_week:.1f} {'✅' if trades_per_week >= 4 else '⚠️'}")
    
    # Time
    avg_hours = trades_df['bars_in_trade'].mean() * 0.25
    print(f"  Avg Time in Trade: {avg_hours:.1f} hours")
    
    # Exit reasons
    print(f"\nExit Reasons:")
    exit_counts = trades_df['exit_reason'].value_counts()
    for reason, count in exit_counts.items():
        print(f"  {reason}: {count} ({count/total_trades*100:.1f}%)")
    
    # Capital simulation
    print(f"\nCapital Simulation ($20,000 initial, 1% risk):")
    capital = 20000
    for _, trade in trades_df.iterrows():
        risk_amount = capital * 0.01
        pnl_dollars = risk_amount * trade['pnl_pct']
        capital += pnl_dollars
    
    total_return = ((capital - 20000) / 20000) * 100
    print(f"  Final Capital: ${capital:,.2f}")
    print(f"  Total Return: {total_return:+.2f}%")
    
    # Benchmarks
    print(f"\n{'='*60}")
    print(f"BENCHMARK CHECK:")
    print(f"  Win Rate: {len(winners)/total_trades*100:.1f}% (Target: 60-80%) {'✅' if len(winners)/total_trades >= 0.6 else '❌'}")
    print(f"  RR Ratio: {rr_ratio:.2f}:1 (Target: 2:1+) {'✅' if rr_ratio >= 2.0 else '❌'}")
    print(f"  Trades/Week: {trades_per_week:.1f} (Target: ~4) {'✅' if trades_per_week >= 4 else '❌'}")
    print(f"{'='*60}\n")
    
    return trades_df


def main():
    """Main function."""
    print(f"\n{'='*60}")
    print(f"HYBRID ICT + ML STRATEGY")
    print(f"{'='*60}")
    
    # Load data
    print("\nLoading data...")
    loader = DataLoader()
    df = loader.load('BTCUSD', '15', limit=5000)
    df = calculate_all_technicals(df)
    
    start_date = df.index[0]
    end_date = df.index[-1]
    days = (end_date - start_date).days
    print(f"Data: {start_date.date()} to {end_date.date()} ({days} days)")
    
    # Prepare original Lorentzian features
    print("\nPreparing features (RSI, WT, CCI, ADX)...")
    features = prepare_original_features(df)
    print(f"Features: {list(features.columns)}")
    
    # Analyze market structure
    print("Analyzing market structure...")
    ms = analyze_market_structure(df)
    print(f"  FVGs: {len(ms['fvgs'])}")
    print(f"  Order Blocks: {len(ms['order_blocks'])}")
    print(f"  Structure Breaks: {len(ms['structure_breaks'])}")
    print(f"  Liquidity Levels: {len(ms['liquidity_levels'])}")
    
    # Run strategy
    trades, stats = hybrid_strategy(df, features, ms)
    
    # Show filtering stats
    print(f"\nICT Filtering Funnel:")
    print(f"  ML Signals: {stats['ml_signals']}")
    print(f"  → Liquidity Sweeps: {stats['liquidity_sweeps']}")
    print(f"  → MSS Confirmed: {stats['mss_confirmed']}")
    print(f"  → Entry Zones Found: {stats['entry_zones_found']}")
    print(f"  → Liquidity Targets Found: {stats['liquidity_targets_found']}")
    print(f"  → Trades Executed: {stats['trades_executed']}")
    
    # Analyze results
    trades_df = analyze_results(trades, df)


if __name__ == '__main__':
    main()
