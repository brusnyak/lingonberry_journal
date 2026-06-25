"""
Fixed Hybrid ICT + ML Strategy with Proper Walk-Forward Validation

Key Fixes:
1. NO opposite signal exits - only TP/SL
2. Proper WFO - re-optimize parameters each window
3. Track planned vs actual RR
4. Track Walk-Forward Efficiency (WFE)

Targets:
- 70-80% win rate
- 2.5:1+ actual RR ratio (matching planned)
- <2% max drawdown
- +15% account growth
- 4 quality trades/week
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
                }
            elif direction == 'bearish' and fvg.type == 'bearish' and distance_pct <= tolerance_pct:
                return {
                    'valid': True,
                    'type': 'fvg',
                    'zone_high': fvg.top,
                    'zone_low': fvg.bottom,
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
                }
            elif direction == 'bearish' and ob.type == 'bearish' and distance_pct <= tolerance_pct:
                return {
                    'valid': True,
                    'type': 'ob',
                    'zone_high': ob.top,
                    'zone_low': ob.bottom,
                }
    
    return {'valid': False, 'type': None, 'zone_high': None, 'zone_low': None}


def find_liquidity_target(df: pd.DataFrame, ms: dict, idx: int, direction: str, entry_price: float, min_rr: float = 2.5) -> dict:
    """
    Find liquidity target with realistic distance.
    Use ATR-based targets for consistent RR.
    """
    # Calculate ATR for reference
    atr = df.iloc[idx]['atr']
    
    # Use ATR-based target (2.5-3x ATR for realistic 15min targets)
    if direction == 'bullish':
        target_price = entry_price + (atr * 2.5)
    else:
        target_price = entry_price - (atr * 2.5)
    
    distance_pct = abs((target_price - entry_price) / entry_price) * 100
    
    return {
        'found': True,
        'price': target_price,
        'type': 'atr_based',
        'distance_pct': distance_pct
    }


def fixed_strategy(df: pd.DataFrame, features: pd.DataFrame, ms: dict,
                   k: int = 8, lookback: int = 2000,
                   min_confidence_percentile: float = 50.0,
                   min_rr_ratio: float = 2.5,
                   max_bars_in_trade: int = 100) -> tuple:
    """
    Fixed strategy - NO opposite signal exits, only TP/SL/Time.
    """
    # Create labels
    labels = create_labels(df, forward_bars=4)
    
    # Train ML
    clf = LorentzianClassifier(k=k, lookback=lookback)
    predictions = clf.predict_series(features, labels, start_idx=lookback)
    
    # Calculate confidence threshold
    confidence_threshold = np.percentile(predictions['confidence'], min_confidence_percentile)
    
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
    
    for i in range(lookback, len(df)):
        if in_position:
            # Check exits - ONLY TP/SL/Time, NO opposite signals
            current_price = df.iloc[i]['close']
            exit_reason = None
            exit_price = None
            
            # Take Profit
            if take_profit is not None:
                if entry_signal == 1 and current_price >= take_profit:
                    exit_reason = 'take_profit'
                    exit_price = take_profit
                elif entry_signal == -1 and current_price <= take_profit:
                    exit_reason = 'take_profit'
                    exit_price = take_profit
            
            # Stop Loss
            if exit_reason is None and stop_loss is not None:
                if entry_signal == 1 and current_price <= stop_loss:
                    exit_reason = 'stop_loss'
                    exit_price = stop_loss
                elif entry_signal == -1 and current_price >= stop_loss:
                    exit_reason = 'stop_loss'
                    exit_price = stop_loss
            
            # Time-based exit (max bars in trade)
            if exit_reason is None and (i - entry_idx) >= max_bars_in_trade:
                exit_reason = 'time_exit'
                exit_price = current_price
            
            if exit_reason is not None:
                # Calculate PnL
                pnl_pct = ((exit_price - entry_price) / entry_price) * entry_signal * 100
                
                # Calculate actual RR
                if pnl_pct > 0:
                    actual_rr = abs(pnl_pct) / abs((stop_loss - entry_price) / entry_price * 100)
                else:
                    actual_rr = -abs(pnl_pct) / abs((stop_loss - entry_price) / entry_price * 100)
                
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
                    'planned_rr': (abs(take_profit - entry_price) / abs(entry_price - stop_loss)),
                    'actual_rr': actual_rr,
                })
                
                in_position = False
        
        else:
            # Check for setup
            ml_signal = signals.iloc[i]['signal']
            
            if ml_signal != 0:
                ml_direction = 'bullish' if ml_signal == 1 else 'bearish'
                confidence = signals.iloc[i]['confidence']
                
                # Filter 1: Confidence
                if confidence < confidence_threshold:
                    continue
                
                # Filter 2: Market structure shift
                if not detect_market_structure_shift(df, ms, i, ml_direction, lookback=30):
                    continue
                
                # Filter 3: Entry zone (make optional - just check if near structure)
                entry_zone = find_entry_zone(df, ms, i, ml_direction, tolerance_pct=3.0)  # Increased tolerance
                # Don't require entry zone, just use it if available
                
                # Filter 4: Liquidity target (always available now)
                current_price = df.iloc[i]['close']
                liq_target = find_liquidity_target(df, ms, i, ml_direction, current_price, min_rr_ratio)
                
                # Calculate stops with consistent ATR-based approach
                atr = df.iloc[i]['atr']
                
                if entry_zone['valid']:
                    # Use entry zone for SL
                    if ml_signal == 1:
                        sl = entry_zone['zone_low'] - (atr * 0.5)
                    else:
                        sl = entry_zone['zone_high'] + (atr * 0.5)
                else:
                    # Use ATR-based SL (1.5x ATR)
                    if ml_signal == 1:
                        sl = current_price - (atr * 1.5)
                    else:
                        sl = current_price + (atr * 1.5)
                
                tp = liq_target['price']
                
                # Verify RR is reasonable (should be close to 2.5:1 with our ATR-based approach)
                risk = abs(current_price - sl)
                reward = abs(tp - current_price)
                rr_ratio = reward / risk if risk > 0 else 0
                
                # Skip if RR is way off (indicates calculation error)
                if rr_ratio < 1.5 or rr_ratio > 5.0:
                    continue
                
                # Enter trade
                in_position = True
                entry_idx = i
                entry_price = current_price
                entry_signal = ml_signal
                stop_loss = sl
                take_profit = tp
    
    return trades


def optimize_parameters(df: pd.DataFrame, features: pd.DataFrame, ms: dict) -> dict:
    """
    Optimize parameters on training data.
    Grid search over k, confidence threshold.
    """
    print("  Optimizing parameters...")
    
    # Parameter grid - expand search space
    k_values = [5, 8, 12, 15]
    confidence_values = [30, 40, 50]  # Lower thresholds for more trades
    
    best_score = -999
    best_params = None
    
    for k in k_values:
        for conf in confidence_values:
            trades = fixed_strategy(df, features, ms, k=k, lookback=2000, 
                                   min_confidence_percentile=conf, min_rr_ratio=2.5)
            
            if len(trades) >= 5:  # Need minimum trades
                trades_df = pd.DataFrame(trades)
                winners = trades_df[trades_df['pnl_pct'] > 0]
                win_rate = len(winners) / len(trades_df) * 100
                avg_rr = trades_df['actual_rr'].mean()
                total_return = trades_df['pnl_pct'].sum()
                
                # Score = win_rate * avg_rr * total_return (balanced metric)
                score = (win_rate / 100) * avg_rr * total_return
                
                if score > best_score:
                    best_score = score
                    best_params = {
                        'k': k,
                        'confidence': conf,
                        'trades': len(trades_df),
                        'win_rate': win_rate,
                        'avg_rr': avg_rr,
                        'total_return': total_return,
                        'score': score
                    }
    
    if best_params:
        print(f"  Best params: k={best_params['k']}, conf={best_params['confidence']}th percentile")
        print(f"  Train performance: {best_params['trades']} trades, {best_params['win_rate']:.1f}% WR, {best_params['avg_rr']:.2f}:1 RR")
    else:
        print("  No valid parameters found, using defaults")
        best_params = {'k': 8, 'confidence': 50}
    
    return best_params


def walk_forward_validation(df: pd.DataFrame, train_size: int = 2500, test_size: int = 500, step: int = 250):
    """
    Proper walk-forward validation with re-optimization each window.
    """
    print(f"\n{'='*60}")
    print(f"WALK-FORWARD VALIDATION (PROPER)")
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
        print(f"\nWindow {i}/{len(windows)}:")
        print(f"  Train: {df.index[window['train_start']]} to {df.index[window['train_end']-1]}")
        print(f"  Test: {df.index[window['test_start']]} to {df.index[window['test_end']-1]}")
        
        # Get window data
        train_df = df.iloc[window['train_start']:window['train_end']].copy()
        test_df = df.iloc[window['test_start']:window['test_end']].copy()
        full_df = df.iloc[window['train_start']:window['test_end']].copy()
        
        # Prepare features
        train_features = prepare_features(train_df)
        full_features = prepare_features(full_df)
        
        # Analyze market structure
        train_ms = analyze_market_structure(train_df)
        full_ms = analyze_market_structure(full_df)
        
        # OPTIMIZE on training data
        best_params = optimize_parameters(train_df, train_features, train_ms)
        
        # TEST on test data with optimized parameters
        all_trades = fixed_strategy(full_df, full_features, full_ms, 
                                    k=best_params['k'], 
                                    lookback=2000,
                                    min_confidence_percentile=best_params['confidence'],
                                    min_rr_ratio=2.5)
        
        # Filter trades to test period only
        test_trades = [t for t in all_trades if window['test_start'] <= t['entry_idx'] < window['test_end']]
        
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
            avg_actual_rr = trades_df['actual_rr'].mean()
            
            # Exit reason breakdown
            exit_reasons = trades_df['exit_reason'].value_counts()
            
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
            
            # Calculate WFE (Walk-Forward Efficiency)
            # WFE = test performance / train performance
            if 'total_return' in best_params:
                wfe = (total_return / best_params['total_return']) * 100 if best_params['total_return'] != 0 else 0
            else:
                wfe = 0
            
            result = {
                'window': i,
                'k': best_params['k'],
                'confidence': best_params['confidence'],
                'trades': len(trades_df),
                'win_rate': win_rate,
                'rr_ratio': rr_ratio,
                'planned_rr': avg_planned_rr,
                'actual_rr': avg_actual_rr,
                'total_return': total_return,
                'max_dd': max_dd,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'wfe': wfe,
                'tp_exits': exit_reasons.get('take_profit', 0),
                'sl_exits': exit_reasons.get('stop_loss', 0),
                'time_exits': exit_reasons.get('time_exit', 0),
            }
            
            all_results.append(result)
            
            print(f"  Test Results:")
            print(f"    Trades: {len(trades_df)}")
            print(f"    Win Rate: {win_rate:.1f}%")
            print(f"    Planned RR: {avg_planned_rr:.2f}:1")
            print(f"    Actual RR: {avg_actual_rr:.2f}:1")
            print(f"    Return: {total_return:.2f}%")
            print(f"    Max DD: {max_dd:.2f}%")
            print(f"    WFE: {wfe:.1f}%")
            print(f"    Exits: TP={exit_reasons.get('take_profit', 0)}, SL={exit_reasons.get('stop_loss', 0)}, Time={exit_reasons.get('time_exit', 0)}")
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
    print(f"  Windows with trades: {len(results_df)}")
    print(f"  Total Trades: {results_df['trades'].sum()}")
    print(f"  Avg Trades/Window: {results_df['trades'].mean():.1f}")
    
    print(f"\nWin Rate:")
    print(f"  Mean: {results_df['win_rate'].mean():.1f}%")
    print(f"  Std: {results_df['win_rate'].std():.1f}%")
    print(f"  Min: {results_df['win_rate'].min():.1f}%")
    print(f"  Max: {results_df['win_rate'].max():.1f}%")
    
    print(f"\nRR Ratio:")
    print(f"  Planned Mean: {results_df['planned_rr'].mean():.2f}:1")
    print(f"  Actual Mean: {results_df['actual_rr'].mean():.2f}:1")
    print(f"  Difference: {(results_df['actual_rr'].mean() - results_df['planned_rr'].mean()):.2f}")
    
    print(f"\nReturns:")
    print(f"  Mean: {results_df['total_return'].mean():.2f}%")
    print(f"  Total: {results_df['total_return'].sum():.2f}%")
    
    print(f"\nMax Drawdown:")
    print(f"  Mean: {results_df['max_dd'].mean():.2f}%")
    print(f"  Worst: {results_df['max_dd'].max():.2f}%")
    
    print(f"\nWalk-Forward Efficiency:")
    print(f"  Mean: {results_df['wfe'].mean():.1f}%")
    print(f"  Std: {results_df['wfe'].std():.1f}%")
    
    print(f"\nExit Reasons:")
    total_tp = results_df['tp_exits'].sum()
    total_sl = results_df['sl_exits'].sum()
    total_time = results_df['time_exits'].sum()
    total_exits = total_tp + total_sl + total_time
    print(f"  Take Profit: {total_tp} ({total_tp/total_exits*100:.1f}%)")
    print(f"  Stop Loss: {total_sl} ({total_sl/total_exits*100:.1f}%)")
    print(f"  Time Exit: {total_time} ({total_time/total_exits*100:.1f}%)")
    
    print(f"\nParameter Stability:")
    print(f"  k values: {results_df['k'].unique()}")
    print(f"  Confidence values: {results_df['confidence'].unique()}")
    
    # Check benchmarks
    print(f"\n{'='*60}")
    print(f"BENCHMARK CHECK:")
    avg_wr = results_df['win_rate'].mean()
    avg_actual_rr = results_df['actual_rr'].mean()
    avg_planned_rr = results_df['planned_rr'].mean()
    worst_dd = results_df['max_dd'].max()
    total_return = results_df['total_return'].sum()
    avg_wfe = results_df['wfe'].mean()
    
    print(f"  Win Rate: {avg_wr:.1f}% (Target: 70-80%) {'✅' if avg_wr >= 70 else '❌'}")
    print(f"  Actual RR: {avg_actual_rr:.2f}:1 (Target: 2.5:1+) {'✅' if avg_actual_rr >= 2.5 else '❌'}")
    print(f"  Planned RR: {avg_planned_rr:.2f}:1")
    print(f"  RR Match: {'✅' if abs(avg_actual_rr - avg_planned_rr) < 0.5 else '❌'}")
    print(f"  Max DD: {worst_dd:.2f}% (Target: <2%) {'✅' if worst_dd < 2.0 else '❌'}")
    print(f"  Total Return: {total_return:.2f}% (Target: +15%) {'✅' if total_return >= 15 else '❌'}")
    print(f"  WFE: {avg_wfe:.1f}% (Target: >70%) {'✅' if avg_wfe >= 70 else '❌'}")
    print(f"{'='*60}\n")


def main():
    """Main function."""
    print(f"\n{'='*60}")
    print(f"FIXED HYBRID STRATEGY - PROPER WALK-FORWARD")
    print(f"{'='*60}")
    print(f"\nKey Fixes:")
    print(f"  1. NO opposite signal exits - only TP/SL/Time")
    print(f"  2. Re-optimize parameters each window")
    print(f"  3. Track planned vs actual RR")
    print(f"  4. Track Walk-Forward Efficiency (WFE)")
    
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
