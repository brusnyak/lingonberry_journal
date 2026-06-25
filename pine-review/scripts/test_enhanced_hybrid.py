"""
Enhanced Hybrid ICT + ML Strategy with Walk-Forward Validation

Targets:
- 70-80% win rate
- 2.5:1+ RR ratio
- <2% max drawdown
- +15% account growth
- 4 quality trades/week

Enhancements:
1. Volume confirmation at liquidity sweeps
2. RSI divergence detection
3. Volatility regime filter
4. Higher confidence threshold
5. Better exit logic (partial profits)
6. Walk-forward validation
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


def prepare_features(df: pd.DataFrame) -> pd.DataFrame:
    """Prepare original Lorentzian features."""
    features = pd.DataFrame(index=df.index)
    features['rsi'] = df['rsi']
    features['wt1'] = df['wt1']
    features['wt2'] = df['wt2']
    features['cci'] = df['cci']
    features['adx'] = df['adx']
    
    # Normalize
    for col in features.columns:
        series = features[col]
        rolling_min = series.rolling(window=2000, min_periods=1).min()
        rolling_max = series.rolling(window=2000, min_periods=1).max()
        features[col] = (series - rolling_min) / (rolling_max - rolling_min + 1e-10)
    
    return features.fillna(0)


def detect_rsi_divergence(df: pd.DataFrame, idx: int, direction: str, lookback: int = 20) -> bool:
    """
    Detect RSI divergence.
    Bullish: Price makes lower low, RSI makes higher low
    Bearish: Price makes higher high, RSI makes lower high
    """
    if idx < lookback:
        return False
    
    window = df.iloc[idx-lookback:idx+1]
    
    if direction == 'bullish':
        # Find recent lows
        price_lows = window['low'].nsmallest(2)
        if len(price_lows) < 2:
            return False
        
        # Price making lower low
        if price_lows.iloc[-1] < price_lows.iloc[0]:
            # Check if RSI making higher low
            rsi_at_lows = window.loc[price_lows.index, 'rsi']
            if len(rsi_at_lows) >= 2 and rsi_at_lows.iloc[-1] > rsi_at_lows.iloc[0]:
                return True
    
    elif direction == 'bearish':
        # Find recent highs
        price_highs = window['high'].nlargest(2)
        if len(price_highs) < 2:
            return False
        
        # Price making higher high
        if price_highs.iloc[-1] > price_highs.iloc[0]:
            # Check if RSI making lower high
            rsi_at_highs = window.loc[price_highs.index, 'rsi']
            if len(rsi_at_highs) >= 2 and rsi_at_highs.iloc[-1] < rsi_at_highs.iloc[0]:
                return True
    
    return False


def check_volume_confirmation(df: pd.DataFrame, idx: int, lookback: int = 20) -> bool:
    """
    Check if recent volume spike confirms liquidity sweep.
    Volume should be above 1.5x average.
    """
    if idx < lookback:
        return False
    
    recent_volume = df.iloc[idx]['volume']
    avg_volume = df.iloc[idx-lookback:idx]['volume'].mean()
    
    return recent_volume > (avg_volume * 1.5)


def check_volatility_regime(df: pd.DataFrame, idx: int, lookback: int = 50) -> str:
    """
    Determine volatility regime.
    Returns: 'high', 'medium', 'low'
    """
    if idx < lookback:
        return 'medium'
    
    atr = df.iloc[idx]['atr']
    atr_percentile = df.iloc[idx-lookback:idx]['atr'].rank(pct=True).iloc[-1] * 100
    
    if atr_percentile > 70:
        return 'high'
    elif atr_percentile < 30:
        return 'low'
    else:
        return 'medium'


def detect_market_structure_shift(df: pd.DataFrame, ms: dict, idx: int, direction: str, lookback: int = 30) -> bool:
    """Check for market structure shift."""
    for sb in ms['structure_breaks']:
        if idx - lookback <= sb.index <= idx:
            if direction == 'bullish' and sb.direction == 'bullish':
                return True
            elif direction == 'bearish' and sb.direction == 'bearish':
                return True
    return False


def find_entry_zone(df: pd.DataFrame, ms: dict, idx: int, direction: str, tolerance_pct: float = 2.0) -> dict:
    """Find entry zone at FVG or OB."""
    current_price = df.iloc[idx]['close']
    
    # Check FVGs
    for fvg in ms['fvgs']:
        if idx - 50 <= fvg.index < idx and not fvg.mitigated:
            fvg_mid = (fvg.top + fvg.bottom) / 2
            distance_pct = abs(current_price - fvg_mid) / current_price * 100
            
            if direction == 'bullish' and fvg.type == 'bullish' and distance_pct <= tolerance_pct:
                return {
                    'valid': True,
                    'type': 'fvg',
                    'zone_high': fvg.top,
                    'zone_low': fvg.bottom,
                    'fvg_50': fvg_mid
                }
            elif direction == 'bearish' and fvg.type == 'bearish' and distance_pct <= tolerance_pct:
                return {
                    'valid': True,
                    'type': 'fvg',
                    'zone_high': fvg.top,
                    'zone_low': fvg.bottom,
                    'fvg_50': fvg_mid
                }
    
    # Check Order Blocks
    for ob in ms['order_blocks']:
        if idx - 50 <= ob.index < idx and not ob.mitigated:
            ob_mid = (ob.top + ob.bottom) / 2
            distance_pct = abs(current_price - ob_mid) / current_price * 100
            
            if direction == 'bullish' and ob.type == 'bullish' and distance_pct <= tolerance_pct:
                return {
                    'valid': True,
                    'type': 'ob',
                    'zone_high': ob.top,
                    'zone_low': ob.bottom,
                    'fvg_50': None
                }
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
    """Find liquidity target."""
    lookback = 50
    
    if direction == 'bullish':
        recent_high = df.iloc[max(0, idx-lookback):idx]['high'].max()
        if recent_high > entry_price:
            distance_pct = ((recent_high - entry_price) / entry_price) * 100
            if distance_pct <= 5.0:
                return {
                    'found': True,
                    'price': recent_high,
                    'type': 'swing_high',
                    'distance_pct': distance_pct
                }
        
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
    else:
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


def enhanced_strategy(df: pd.DataFrame, features: pd.DataFrame, ms: dict,
                      min_confidence_percentile: float = 60.0,
                      min_rr_ratio: float = 2.5) -> tuple:
    """
    Enhanced strategy with additional filters.
    """
    # Create labels
    labels = create_labels(df, forward_bars=4)
    
    # Train ML
    print(f"  Training ML (k=8, lookback=2000)...")
    clf = LorentzianClassifier(k=8, lookback=2000)
    predictions = clf.predict_series(features, labels, start_idx=2000)
    
    # Calculate confidence threshold
    confidence_threshold = np.percentile(predictions['confidence'], min_confidence_percentile)
    print(f"  Confidence threshold ({min_confidence_percentile}th percentile): {confidence_threshold:.3f}")
    
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
    partial_tp = None
    partial_closed = False
    
    stats = {
        'ml_signals': 0,
        'confidence_filtered': 0,
        'volatility_filtered': 0,
        'mss_confirmed': 0,
        'entry_zones_found': 0,
        'volume_confirmed': 0,
        'divergence_confirmed': 0,
        'liquidity_targets_found': 0,
        'rr_filtered': 0,
        'trades_executed': 0
    }
    
    print(f"  Simulating trades...")
    for i in range(2000, len(df)):
        if in_position:
            # Check exits
            current_price = df.iloc[i]['close']
            exit_reason = None
            exit_price = None
            
            # Partial TP (50% at 1.5:1 RR)
            if not partial_closed and partial_tp is not None:
                if entry_signal == 1 and current_price >= partial_tp:
                    partial_closed = True
                elif entry_signal == -1 and current_price <= partial_tp:
                    partial_closed = True
            
            # Full TP
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
            
            # Opposite signal (only exit if in loss or at breakeven)
            if exit_reason is None and signals.iloc[i]['signal'] == -entry_signal:
                # Check if in profit
                current_pnl_pct = ((current_price - entry_price) / entry_price) * entry_signal * 100
                if current_pnl_pct <= 0.1:  # Only exit if not significantly in profit
                    exit_reason = 'opposite_signal'
                    exit_price = current_price
            
            if exit_reason is not None:
                # Calculate PnL (accounting for partial close)
                if partial_closed:
                    # 50% closed at partial TP, 50% at exit
                    partial_pnl = ((partial_tp - entry_price) / entry_price) * entry_signal * 100 * 0.5
                    full_pnl = ((exit_price - entry_price) / entry_price) * entry_signal * 100 * 0.5
                    pnl_pct = partial_pnl + full_pnl
                else:
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
                    'partial_closed': partial_closed,
                    'planned_rr': (abs(take_profit - entry_price) / abs(entry_price - stop_loss)),
                })
                
                in_position = False
                partial_closed = False
        
        else:
            # Check for setup
            ml_signal = signals.iloc[i]['signal']
            
            if ml_signal != 0:
                stats['ml_signals'] += 1
                ml_direction = 'bullish' if ml_signal == 1 else 'bearish'
                confidence = signals.iloc[i]['confidence']
                
                # Filter 1: Confidence
                if confidence < confidence_threshold:
                    stats['confidence_filtered'] += 1
                    continue
                
                # Filter 2: Volatility regime (avoid low volatility)
                vol_regime = check_volatility_regime(df, i, lookback=50)
                if vol_regime == 'low':
                    stats['volatility_filtered'] += 1
                    continue
                
                # Filter 3: Market structure shift
                if not detect_market_structure_shift(df, ms, i, ml_direction, lookback=30):
                    continue
                stats['mss_confirmed'] += 1
                
                # Filter 4: Entry zone
                entry_zone = find_entry_zone(df, ms, i, ml_direction, tolerance_pct=2.0)
                if not entry_zone['valid']:
                    continue
                stats['entry_zones_found'] += 1
                
                # Filter 5: Volume confirmation (optional but adds confidence)
                has_volume = check_volume_confirmation(df, i, lookback=20)
                if has_volume:
                    stats['volume_confirmed'] += 1
                
                # Filter 6: RSI divergence (optional but adds confidence)
                has_divergence = detect_rsi_divergence(df, i, ml_direction, lookback=20)
                if has_divergence:
                    stats['divergence_confirmed'] += 1
                
                # Filter 7: Liquidity target
                current_price = df.iloc[i]['close']
                liq_target = find_liquidity_target(df, ms, i, ml_direction, current_price)
                if not liq_target['found']:
                    continue
                stats['liquidity_targets_found'] += 1
                
                # Calculate stops
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
                
                if rr_ratio < min_rr_ratio:
                    stats['rr_filtered'] += 1
                    continue
                
                # Calculate partial TP (1.5:1 RR)
                if ml_signal == 1:
                    partial_tp = current_price + (risk * 1.5)
                else:
                    partial_tp = current_price - (risk * 1.5)
                
                # Enter trade
                in_position = True
                entry_idx = i
                entry_price = current_price
                entry_signal = ml_signal
                stop_loss = sl
                take_profit = tp
                stats['trades_executed'] += 1
    
    return trades, stats


def walk_forward_validation(df: pd.DataFrame, train_size: int = 2500, test_size: int = 500, step: int = 250):
    """
    Walk-forward validation.
    """
    print(f"\n{'='*60}")
    print(f"WALK-FORWARD VALIDATION")
    print(f"{'='*60}")
    print(f"Train size: {train_size}, Test size: {test_size}, Step: {step}")
    
    windows = []
    start_idx = 0
    
    while start_idx + train_size + test_size <= len(df):
        train_start = start_idx
        train_end = start_idx + train_size
        test_start = train_end
        test_end = test_start + test_size
        
        windows.append({
            'train_start': train_start,
            'train_end': train_end,
            'test_start': test_start,
            'test_end': test_end
        })
        
        start_idx += step
    
    print(f"Total windows: {len(windows)}\n")
    
    all_results = []
    
    for i, window in enumerate(windows, 1):
        print(f"Window {i}/{len(windows)}:")
        print(f"  Train: {df.index[window['train_start']]} to {df.index[window['train_end']-1]}")
        print(f"  Test: {df.index[window['test_start']]} to {df.index[window['test_end']-1]}")
        
        # Get window data
        window_df = df.iloc[window['train_start']:window['test_end']].copy()
        
        # Prepare features
        features = prepare_features(window_df)
        
        # Analyze market structure
        ms = analyze_market_structure(window_df)
        
        # Run strategy
        trades, stats = enhanced_strategy(window_df, features, ms, min_confidence_percentile=60.0, min_rr_ratio=2.5)
        
        # Filter trades to test period only
        test_trades = [t for t in trades if window['test_start'] <= t['entry_idx'] < window['test_end']]
        
        if test_trades:
            trades_df = pd.DataFrame(test_trades)
            winners = trades_df[trades_df['pnl_pct'] > 0]
            losers = trades_df[trades_df['pnl_pct'] <= 0]
            
            win_rate = len(winners) / len(trades_df) * 100
            avg_win = winners['pnl_pct'].mean() if len(winners) > 0 else 0
            avg_loss = abs(losers['pnl_pct'].mean()) if len(losers) > 0 else 1
            rr_ratio = avg_win / avg_loss if avg_loss > 0 else 0
            total_return = trades_df['pnl_pct'].sum()
            avg_planned_rr = trades_df['planned_rr'].mean()
            
            # Calculate max drawdown
            equity = 20000
            equity_curve = [equity]
            for _, trade in trades_df.iterrows():
                risk_amount = equity * 0.01
                pnl_dollars = risk_amount * trade['pnl_pct']
                equity += pnl_dollars
                equity_curve.append(equity)
            
            equity_series = pd.Series(equity_curve)
            running_max = equity_series.expanding().max()
            drawdown = (equity_series - running_max) / running_max * 100
            max_dd = abs(drawdown.min())
            
            result = {
                'window': i,
                'trades': len(trades_df),
                'win_rate': win_rate,
                'rr_ratio': rr_ratio,
                'planned_rr': avg_planned_rr,
                'total_return': total_return,
                'max_dd': max_dd,
                'avg_win': avg_win,
                'avg_loss': avg_loss
            }
            
            all_results.append(result)
            
            print(f"  Trades: {len(trades_df)}, WR: {win_rate:.1f}%, Actual RR: {rr_ratio:.2f}:1, Planned RR: {avg_planned_rr:.2f}:1, Return: {total_return:.2f}%, MaxDD: {max_dd:.2f}%")
        else:
            print(f"  No trades in test period")
    
    return all_results


def analyze_walk_forward_results(results: list):
    """Analyze walk-forward results."""
    if not results:
        print("\nNo results to analyze!")
        return
    
    results_df = pd.DataFrame(results)
    
    print(f"\n{'='*60}")
    print(f"WALK-FORWARD SUMMARY")
    print(f"{'='*60}")
    
    print(f"\nOverall Statistics:")
    print(f"  Windows: {len(results_df)}")
    print(f"  Total Trades: {results_df['trades'].sum()}")
    print(f"  Avg Trades/Window: {results_df['trades'].mean():.1f}")
    
    print(f"\nWin Rate:")
    print(f"  Mean: {results_df['win_rate'].mean():.1f}%")
    print(f"  Std: {results_df['win_rate'].std():.1f}%")
    print(f"  Min: {results_df['win_rate'].min():.1f}%")
    print(f"  Max: {results_df['win_rate'].max():.1f}%")
    
    print(f"\nRR Ratio:")
    print(f"  Actual Mean: {results_df['rr_ratio'].mean():.2f}:1")
    print(f"  Planned Mean: {results_df['planned_rr'].mean():.2f}:1")
    print(f"  Actual Min: {results_df['rr_ratio'].min():.2f}:1")
    print(f"  Actual Max: {results_df['rr_ratio'].max():.2f}:1")
    
    print(f"\nReturns:")
    print(f"  Mean: {results_df['total_return'].mean():.2f}%")
    print(f"  Total: {results_df['total_return'].sum():.2f}%")
    
    print(f"\nMax Drawdown:")
    print(f"  Mean: {results_df['max_dd'].mean():.2f}%")
    print(f"  Worst: {results_df['max_dd'].max():.2f}%")
    
    # Check benchmarks
    print(f"\n{'='*60}")
    print(f"BENCHMARK CHECK:")
    avg_wr = results_df['win_rate'].mean()
    avg_rr = results_df['rr_ratio'].mean()
    worst_dd = results_df['max_dd'].max()
    total_return = results_df['total_return'].sum()
    
    print(f"  Win Rate: {avg_wr:.1f}% (Target: 70-80%) {'✅' if avg_wr >= 70 else '❌'}")
    print(f"  RR Ratio: {avg_rr:.2f}:1 (Target: 2.5:1+) {'✅' if avg_rr >= 2.5 else '❌'}")
    print(f"  Max DD: {worst_dd:.2f}% (Target: <2%) {'✅' if worst_dd < 2.0 else '❌'}")
    print(f"  Total Return: {total_return:.2f}% (Target: +15%) {'✅' if total_return >= 15 else '❌'}")
    print(f"{'='*60}\n")


def main():
    """Main function."""
    print(f"\n{'='*60}")
    print(f"ENHANCED HYBRID STRATEGY - WALK-FORWARD VALIDATION")
    print(f"{'='*60}")
    
    # Load data
    print("\nLoading data...")
    loader = DataLoader()
    df = loader.load('BTCUSD', '15', limit=5000)
    df = calculate_all_technicals(df)
    
    print(f"Data: {df.index[0].date()} to {df.index[-1].date()} ({len(df)} bars)")
    
    # Run walk-forward validation
    results = walk_forward_validation(df, train_size=2500, test_size=500, step=250)
    
    # Analyze results
    analyze_walk_forward_results(results)


if __name__ == '__main__':
    main()
