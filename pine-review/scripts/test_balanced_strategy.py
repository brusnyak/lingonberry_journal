"""
Balanced ML Strategy - Finding the sweet spot

Testing different parameter combinations to find optimal balance between:
- Trade frequency
- Win rate
- Risk-reward ratio
"""

import sys
import os

# Add parent directory to path
script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
parent_dir = os.path.join(script_dir, '..')
sys.path.insert(0, parent_dir)

import pandas as pd
import numpy as np
from src.data.loader import DataLoader
from src.features.technicals import calculate_all_technicals
from src.features.market_structure import analyze_market_structure
from src.ml.features import prepare_ml_features
from src.ml.lorentzian import LorentzianClassifier, create_labels


def find_nearest_liquidity(ms: dict, trade_idx: int, direction: str, entry_price: float, max_distance_pct: float = 5.0) -> tuple:
    """Find nearest unswept liquidity level for take profit."""
    nearest_liq = None
    min_distance = float('inf')
    
    for liq in ms['liquidity_levels']:
        if liq.start_index > trade_idx or (liq.start_index <= trade_idx and not liq.swept):
            if direction == 'long' and liq.price > entry_price:
                distance = liq.price - entry_price
                distance_pct = (distance / entry_price) * 100
                if distance_pct <= max_distance_pct and distance < min_distance:
                    min_distance = distance
                    nearest_liq = liq.price
            elif direction == 'short' and liq.price < entry_price:
                distance = entry_price - liq.price
                distance_pct = (distance / entry_price) * 100
                if distance_pct <= max_distance_pct and distance < min_distance:
                    min_distance = distance
                    nearest_liq = liq.price
    
    if nearest_liq is not None:
        distance_pct = (min_distance / entry_price) * 100
        return nearest_liq, distance_pct
    
    return None, None


def get_premium_discount_zone(ms: dict, trade_idx: int, price: float) -> str:
    """Get premium/discount zone at trade index."""
    for zone in ms['premium_discount_zones']:
        if zone.start_index <= trade_idx <= zone.end_index:
            if price > zone.equilibrium:
                return 'premium'
            else:
                return 'discount'
    return 'neutral'


def test_strategy_config(df: pd.DataFrame, features_norm: pd.DataFrame, ms: dict,
                         config: dict) -> dict:
    """Test a specific strategy configuration."""
    # Create labels
    labels = create_labels(df, forward_bars=4)
    
    # Initialize classifier
    clf = LorentzianClassifier(k=config['k'], lookback=config['lookback'])
    
    # Generate predictions
    predictions = clf.predict_series(features_norm, labels, start_idx=config['lookback'])
    
    # Calculate confidence threshold
    if config['min_confidence_percentile'] > 0:
        confidence_threshold = np.percentile(predictions['confidence'], config['min_confidence_percentile'])
    else:
        confidence_threshold = 0.0
    
    # Align predictions with df
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
    trailing_stop = None
    highest_price = None
    lowest_price = None
    
    stats = {
        'confidence_filtered': 0,
        'zone_filtered': 0,
        'rr_filtered': 0,
        'no_liquidity': 0
    }
    
    for i in range(config['lookback'], len(df)):
        if in_position:
            # Update trailing stop
            if config['use_trailing_stop']:
                current_price = df.iloc[i]['close']
                
                if entry_signal == 1:
                    if current_price > highest_price:
                        highest_price = current_price
                        atr = df.iloc[i]['atr']
                        new_trailing = highest_price - (atr * config['trailing_atr_mult'])
                        if new_trailing > trailing_stop:
                            trailing_stop = new_trailing
                elif entry_signal == -1:
                    if current_price < lowest_price:
                        lowest_price = current_price
                        atr = df.iloc[i]['atr']
                        new_trailing = lowest_price + (atr * config['trailing_atr_mult'])
                        if new_trailing < trailing_stop:
                            trailing_stop = new_trailing
            
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
            
            # Trailing stop
            if exit_reason is None and config['use_trailing_stop'] and trailing_stop is not None:
                if entry_signal == 1 and current_price <= trailing_stop:
                    exit_reason = 'trailing_stop'
                    exit_price = trailing_stop
                elif entry_signal == -1 and current_price >= trailing_stop:
                    exit_reason = 'trailing_stop'
                    exit_price = trailing_stop
            
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
                    'pnl_pct': pnl_pct,
                    'bars_in_trade': i - entry_idx,
                    'exit_reason': exit_reason,
                })
                
                in_position = False
        
        else:
            # Check entry
            if signals.iloc[i]['signal'] != 0:
                signal = signals.iloc[i]['signal']
                confidence = signals.iloc[i]['confidence']
                
                # Filter: Confidence
                if confidence < confidence_threshold:
                    stats['confidence_filtered'] += 1
                    continue
                
                current_price = df.iloc[i]['close']
                zone = get_premium_discount_zone(ms, i, current_price)
                
                # Filter: Zone alignment (optional)
                if config['require_zone_alignment']:
                    if signal == 1 and zone == 'premium':
                        stats['zone_filtered'] += 1
                        continue
                    if signal == -1 and zone == 'discount':
                        stats['zone_filtered'] += 1
                        continue
                
                # Calculate stop loss
                atr_stop = df.iloc[i]['atr'] * config['atr_multiplier']
                if signal == 1:
                    sl = current_price - atr_stop
                else:
                    sl = current_price + atr_stop
                
                # Find take profit
                tp, tp_distance_pct = find_nearest_liquidity(
                    ms, i, 'long' if signal == 1 else 'short', current_price,
                    max_distance_pct=config['max_tp_distance_pct']
                )
                
                # If no liquidity, use ATR-based TP or skip
                if tp is None:
                    if config['require_liquidity_tp']:
                        stats['no_liquidity'] += 1
                        continue
                    else:
                        # Use ATR-based TP
                        if signal == 1:
                            tp = current_price + (atr_stop * config['default_rr_ratio'])
                        else:
                            tp = current_price - (atr_stop * config['default_rr_ratio'])
                
                # Calculate RR ratio
                risk = abs(current_price - sl)
                reward = abs(tp - current_price)
                rr_ratio = reward / risk if risk > 0 else 0
                
                # Filter: Minimum RR
                if rr_ratio < config['min_rr_ratio']:
                    stats['rr_filtered'] += 1
                    continue
                
                # Enter position
                in_position = True
                entry_idx = i
                entry_price = current_price
                entry_signal = signal
                stop_loss = sl
                take_profit = tp
                trailing_stop = sl
                highest_price = current_price if signal == 1 else None
                lowest_price = current_price if signal == -1 else None
    
    # Calculate results
    if not trades:
        return None
    
    trades_df = pd.DataFrame(trades)
    winners = trades_df[trades_df['pnl_pct'] > 0]
    losers = trades_df[trades_df['pnl_pct'] <= 0]
    
    date_range = (df.index[-1] - df.index[0]).days
    
    results = {
        'config': config,
        'total_trades': len(trades_df),
        'win_rate': len(winners) / len(trades_df) * 100,
        'avg_win': winners['pnl_pct'].mean() if len(winners) > 0 else 0,
        'avg_loss': abs(losers['pnl_pct'].mean()) if len(losers) > 0 else 0,
        'avg_pnl': trades_df['pnl_pct'].mean(),
        'total_return': trades_df['pnl_pct'].sum(),
        'trades_per_week': (len(trades_df) / date_range) * 7,
        'avg_bars': trades_df['bars_in_trade'].mean(),
        'stats': stats
    }
    
    # Calculate RR ratio
    if results['avg_loss'] > 0:
        results['rr_ratio'] = results['avg_win'] / results['avg_loss']
    else:
        results['rr_ratio'] = 0
    
    # Calculate profit factor
    total_wins = winners['pnl_pct'].sum()
    total_losses = abs(losers['pnl_pct'].sum())
    results['profit_factor'] = total_wins / total_losses if total_losses > 0 else 0
    
    return results


def main():
    """Test multiple configurations."""
    print(f"\n{'='*60}")
    print(f"BALANCED STRATEGY PARAMETER SEARCH")
    print(f"{'='*60}")
    
    # Load data
    print("\nLoading data...")
    loader = DataLoader()
    df = loader.load('BTCUSD', '15', limit=5000)
    df = calculate_all_technicals(df)
    
    print("Preparing features...")
    features_norm = prepare_ml_features(df)
    
    print("Analyzing market structure...")
    ms = analyze_market_structure(df)
    
    # Test configurations
    configs = [
        # Config 1: Moderate filtering
        {
            'name': 'Moderate',
            'k': 15,
            'lookback': 2000,
            'min_confidence_percentile': 30,
            'require_zone_alignment': False,
            'require_liquidity_tp': False,
            'min_rr_ratio': 1.5,
            'default_rr_ratio': 2.0,
            'max_tp_distance_pct': 5.0,
            'atr_multiplier': 2.0,
            'use_trailing_stop': True,
            'trailing_atr_mult': 1.5
        },
        # Config 2: Light filtering
        {
            'name': 'Light',
            'k': 15,
            'lookback': 2000,
            'min_confidence_percentile': 20,
            'require_zone_alignment': False,
            'require_liquidity_tp': False,
            'min_rr_ratio': 1.2,
            'default_rr_ratio': 2.0,
            'max_tp_distance_pct': 5.0,
            'atr_multiplier': 2.0,
            'use_trailing_stop': True,
            'trailing_atr_mult': 1.5
        },
        # Config 3: Zone-aware
        {
            'name': 'Zone-Aware',
            'k': 15,
            'lookback': 2000,
            'min_confidence_percentile': 25,
            'require_zone_alignment': True,
            'require_liquidity_tp': False,
            'min_rr_ratio': 1.5,
            'default_rr_ratio': 2.0,
            'max_tp_distance_pct': 5.0,
            'atr_multiplier': 2.0,
            'use_trailing_stop': True,
            'trailing_atr_mult': 1.5
        },
        # Config 4: Liquidity-focused
        {
            'name': 'Liquidity-Focused',
            'k': 15,
            'lookback': 2000,
            'min_confidence_percentile': 25,
            'require_zone_alignment': False,
            'require_liquidity_tp': True,
            'min_rr_ratio': 1.5,
            'default_rr_ratio': 2.0,
            'max_tp_distance_pct': 3.0,
            'atr_multiplier': 2.0,
            'use_trailing_stop': True,
            'trailing_atr_mult': 1.5
        },
        # Config 5: Aggressive
        {
            'name': 'Aggressive',
            'k': 15,
            'lookback': 2000,
            'min_confidence_percentile': 10,
            'require_zone_alignment': False,
            'require_liquidity_tp': False,
            'min_rr_ratio': 1.0,
            'default_rr_ratio': 2.0,
            'max_tp_distance_pct': 5.0,
            'atr_multiplier': 2.0,
            'use_trailing_stop': True,
            'trailing_atr_mult': 1.5
        },
    ]
    
    results = []
    for config in configs:
        print(f"\nTesting {config['name']} configuration...")
        result = test_strategy_config(df, features_norm, ms, config)
        if result:
            results.append(result)
    
    # Display results
    print(f"\n{'='*60}")
    print(f"RESULTS COMPARISON")
    print(f"{'='*60}\n")
    
    results_df = pd.DataFrame([{
        'Config': r['config']['name'],
        'Trades': r['total_trades'],
        'Trades/Week': f"{r['trades_per_week']:.1f}",
        'Win%': f"{r['win_rate']:.1f}",
        'Avg Win': f"{r['avg_win']:.2f}%",
        'Avg Loss': f"{r['avg_loss']:.2f}%",
        'RR': f"{r['rr_ratio']:.2f}",
        'PF': f"{r['profit_factor']:.2f}",
        'Total Return': f"{r['total_return']:.2f}%",
        'Avg Bars': f"{r['avg_bars']:.1f}"
    } for r in results])
    
    print(results_df.to_string(index=False))
    
    # Show filtering stats for best config
    print(f"\n{'='*60}")
    print(f"DETAILED ANALYSIS - BEST CONFIGS")
    print(f"{'='*60}")
    
    # Sort by total return
    sorted_results = sorted(results, key=lambda x: x['total_return'], reverse=True)
    
    for i, result in enumerate(sorted_results[:3], 1):
        print(f"\n#{i}: {result['config']['name']}")
        print(f"  Total Return: {result['total_return']:.2f}%")
        print(f"  Trades: {result['total_trades']} ({result['trades_per_week']:.1f}/week)")
        print(f"  Win Rate: {result['win_rate']:.1f}%")
        print(f"  RR Ratio: {result['rr_ratio']:.2f}:1")
        print(f"  Profit Factor: {result['profit_factor']:.2f}")
        print(f"  Filtering:")
        print(f"    Confidence: {result['stats']['confidence_filtered']}")
        print(f"    Zone: {result['stats']['zone_filtered']}")
        print(f"    RR: {result['stats']['rr_filtered']}")
        print(f"    No Liquidity: {result['stats']['no_liquidity']}")
    
    print(f"\n{'='*60}\n")


if __name__ == '__main__':
    main()
