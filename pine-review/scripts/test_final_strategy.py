"""
Final Optimized ML Strategy

Based on testing, using a balanced approach:
- Light confidence filtering (20th percentile)
- Zone awareness for better entries
- Liquidity-based TPs when available
- Minimum 1.5:1 RR ratio
- Trailing stops for winners
"""

import sys
import os

# Add parent directory to path
script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
parent_dir = os.path.join(script_dir, '..')
sys.path.insert(0, parent_dir)

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
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


def final_strategy(df: pd.DataFrame, features_norm: pd.DataFrame, ms: dict) -> list:
    """Run final optimized strategy."""
    # Parameters
    k = 15
    lookback = 2000
    min_confidence_percentile = 20
    min_rr_ratio = 1.5
    default_rr_ratio = 2.0
    max_tp_distance_pct = 5.0
    atr_multiplier = 2.0
    trailing_atr_mult = 1.5
    
    # Create labels
    labels = create_labels(df, forward_bars=4)
    
    # Initialize classifier
    clf = LorentzianClassifier(k=k, lookback=lookback)
    
    # Generate predictions
    print("Generating predictions...")
    predictions = clf.predict_series(features_norm, labels, start_idx=lookback)
    
    # Calculate confidence threshold
    confidence_threshold = np.percentile(predictions['confidence'], min_confidence_percentile)
    print(f"Confidence threshold ({min_confidence_percentile}th percentile): {confidence_threshold:.3f}")
    
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
    trailing_stop = None
    highest_price = None
    lowest_price = None
    entry_zone = None
    
    stats = {
        'total_signals': 0,
        'confidence_filtered': 0,
        'zone_filtered': 0,
        'rr_filtered': 0,
        'liquidity_tp_used': 0,
        'atr_tp_used': 0
    }
    
    print("Simulating trades...")
    for i in range(lookback, len(df)):
        if in_position:
            # Update trailing stop
            current_price = df.iloc[i]['close']
            
            if entry_signal == 1:
                if current_price > highest_price:
                    highest_price = current_price
                    atr = df.iloc[i]['atr']
                    new_trailing = highest_price - (atr * trailing_atr_mult)
                    if new_trailing > trailing_stop:
                        trailing_stop = new_trailing
            elif entry_signal == -1:
                if current_price < lowest_price:
                    lowest_price = current_price
                    atr = df.iloc[i]['atr']
                    new_trailing = lowest_price + (atr * trailing_atr_mult)
                    if new_trailing < trailing_stop:
                        trailing_stop = new_trailing
            
            # Check exits
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
            if exit_reason is None and trailing_stop is not None:
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
                    'confidence': signals.iloc[entry_idx]['confidence'],
                    'entry_zone': entry_zone
                })
                
                in_position = False
        
        else:
            # Check entry
            if signals.iloc[i]['signal'] != 0:
                stats['total_signals'] += 1
                signal = signals.iloc[i]['signal']
                confidence = signals.iloc[i]['confidence']
                
                # Filter: Confidence
                if confidence < confidence_threshold:
                    stats['confidence_filtered'] += 1
                    continue
                
                current_price = df.iloc[i]['close']
                zone = get_premium_discount_zone(ms, i, current_price)
                
                # Soft zone filter: prefer aligned zones but don't require
                zone_penalty = 0
                if signal == 1 and zone == 'premium':
                    zone_penalty = 0.2  # Reduce effective RR requirement
                elif signal == -1 and zone == 'discount':
                    zone_penalty = 0.2
                
                # Calculate stop loss
                atr_stop = df.iloc[i]['atr'] * atr_multiplier
                if signal == 1:
                    sl = current_price - atr_stop
                else:
                    sl = current_price + atr_stop
                
                # Find take profit (try liquidity first)
                tp, tp_distance_pct = find_nearest_liquidity(
                    ms, i, 'long' if signal == 1 else 'short', current_price,
                    max_distance_pct=max_tp_distance_pct
                )
                
                if tp is not None:
                    stats['liquidity_tp_used'] += 1
                else:
                    # Use ATR-based TP
                    if signal == 1:
                        tp = current_price + (atr_stop * default_rr_ratio)
                    else:
                        tp = current_price - (atr_stop * default_rr_ratio)
                    stats['atr_tp_used'] += 1
                
                # Calculate RR ratio
                risk = abs(current_price - sl)
                reward = abs(tp - current_price)
                rr_ratio = reward / risk if risk > 0 else 0
                
                # Apply zone penalty to RR requirement
                effective_min_rr = min_rr_ratio - zone_penalty
                
                # Filter: Minimum RR
                if rr_ratio < effective_min_rr:
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
                entry_zone = zone
    
    return trades, stats


def analyze_results(trades: list, df: pd.DataFrame, initial_capital: float = 20000):
    """Analyze and visualize results."""
    if not trades:
        print("\nNo trades executed!")
        return None
    
    trades_df = pd.DataFrame(trades)
    
    print(f"\n{'='*60}")
    print(f"FINAL STRATEGY RESULTS")
    print(f"{'='*60}")
    
    # Basic stats
    total_trades = len(trades_df)
    winners = trades_df[trades_df['pnl_pct'] > 0]
    losers = trades_df[trades_df['pnl_pct'] <= 0]
    
    print(f"\nTrade Statistics:")
    print(f"  Total Trades: {total_trades}")
    print(f"  Winners: {len(winners)} ({len(winners)/total_trades*100:.1f}%)")
    print(f"  Losers: {len(losers)} ({len(losers)/total_trades*100:.1f}%)")
    
    # PnL stats
    print(f"\nPnL Analysis:")
    print(f"  Avg PnL: {trades_df['pnl_pct'].mean():.2f}%")
    print(f"  Avg Winner: {winners['pnl_pct'].mean():.2f}%")
    print(f"  Avg Loser: {losers['pnl_pct'].mean():.2f}%")
    print(f"  Best Trade: {trades_df['pnl_pct'].max():.2f}%")
    print(f"  Worst Trade: {trades_df['pnl_pct'].min():.2f}%")
    
    # Risk-Reward
    avg_win = winners['pnl_pct'].mean() if len(winners) > 0 else 0
    avg_loss = abs(losers['pnl_pct'].mean()) if len(losers) > 0 else 1
    rr_ratio = avg_win / avg_loss if avg_loss > 0 else 0
    print(f"\nRisk-Reward:")
    print(f"  Avg Win: {avg_win:.2f}%")
    print(f"  Avg Loss: {avg_loss:.2f}%")
    print(f"  RR Ratio: {rr_ratio:.2f}:1 {'✅' if rr_ratio >= 2.0 else '⚠️'}")
    
    # Profit factor
    total_wins = winners['pnl_pct'].sum()
    total_losses = abs(losers['pnl_pct'].sum())
    profit_factor = total_wins / total_losses if total_losses > 0 else 0
    print(f"  Profit Factor: {profit_factor:.2f}")
    
    # Time analysis
    print(f"\nTime Analysis:")
    print(f"  Avg Bars in Trade: {trades_df['bars_in_trade'].mean():.1f}")
    avg_hours = trades_df['bars_in_trade'].mean() * 0.25
    print(f"  Avg Time in Trade: {avg_hours:.1f} hours")
    
    # Trade frequency
    date_range = (df.index[-1] - df.index[0]).days
    trades_per_week = (total_trades / date_range) * 7
    print(f"\nTrade Frequency:")
    print(f"  Trades per Week: {trades_per_week:.1f}")
    
    # Exit reasons
    print(f"\nExit Reasons:")
    exit_counts = trades_df['exit_reason'].value_counts()
    for reason, count in exit_counts.items():
        reason_trades = trades_df[trades_df['exit_reason'] == reason]
        win_rate = len(reason_trades[reason_trades['pnl_pct'] > 0]) / len(reason_trades) * 100
        print(f"  {reason}: {count} ({count/total_trades*100:.1f}%), {win_rate:.1f}% win rate")
    
    # Zone analysis
    print(f"\nEntry Zone Analysis:")
    zone_counts = trades_df['entry_zone'].value_counts()
    for zone, count in zone_counts.items():
        zone_trades = trades_df[trades_df['entry_zone'] == zone]
        win_rate = len(zone_trades[zone_trades['pnl_pct'] > 0]) / len(zone_trades) * 100
        avg_pnl = zone_trades['pnl_pct'].mean()
        print(f"  {zone}: {count} trades, {win_rate:.1f}% win rate, {avg_pnl:.2f}% avg PnL")
    
    # Capital simulation
    print(f"\nCapital Simulation (${initial_capital:,.0f} initial, 1% risk per trade):")
    capital = initial_capital
    equity_curve = [capital]
    
    for _, trade in trades_df.iterrows():
        # Risk 1% per trade
        risk_amount = capital * 0.01
        # Simplified: assume stop loss = 1% distance
        pnl_dollars = risk_amount * trade['pnl_pct']
        capital += pnl_dollars
        equity_curve.append(capital)
    
    final_capital = capital
    total_return = ((final_capital - initial_capital) / initial_capital) * 100
    
    print(f"  Final Capital: ${final_capital:,.2f}")
    print(f"  Total Return: {total_return:+.2f}%")
    
    # Max drawdown
    equity_series = pd.Series(equity_curve)
    running_max = equity_series.expanding().max()
    drawdown = (equity_series - running_max) / running_max * 100
    max_drawdown = drawdown.min()
    print(f"  Max Drawdown: {max_drawdown:.2f}%")
    
    # Sharpe ratio
    returns = trades_df['pnl_pct'].values
    sharpe = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0
    print(f"  Sharpe Ratio: {sharpe:.2f}")
    
    # Visualize equity curve
    plt.figure(figsize=(14, 6))
    plt.plot(equity_curve, linewidth=2)
    plt.axhline(initial_capital, color='gray', linestyle='--', alpha=0.5, label='Initial Capital')
    plt.title('Equity Curve - Final Strategy', fontsize=14, fontweight='bold')
    plt.xlabel('Trade Number')
    plt.ylabel('Capital ($)')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig('data/final_strategy_equity.png', dpi=150, bbox_inches='tight')
    print(f"\nEquity curve saved to: data/final_strategy_equity.png")
    
    return trades_df


def main():
    """Main function."""
    print(f"\n{'='*60}")
    print(f"FINAL OPTIMIZED ML STRATEGY")
    print(f"{'='*60}")
    
    # Load data
    print("\nLoading data...")
    loader = DataLoader()
    df = loader.load('BTCUSD', '15', limit=5000)
    df = calculate_all_technicals(df)
    
    start_date = df.index[0]
    end_date = df.index[-1]
    days = (end_date - start_date).days
    print(f"Data: {start_date.date()} to {end_date.date()} ({days} days, {days/30:.1f} months)")
    
    print("\nPreparing features...")
    features_norm = prepare_ml_features(df)
    
    print("Analyzing market structure...")
    ms = analyze_market_structure(df)
    
    # Run strategy
    trades, stats = final_strategy(df, features_norm, ms)
    
    # Show filtering stats
    print(f"\nFiltering Statistics:")
    print(f"  Total Signals: {stats['total_signals']}")
    print(f"  Confidence Filtered: {stats['confidence_filtered']}")
    print(f"  RR Filtered: {stats['rr_filtered']}")
    print(f"  Trades Executed: {len(trades)}")
    print(f"  Liquidity TP Used: {stats['liquidity_tp_used']}")
    print(f"  ATR TP Used: {stats['atr_tp_used']}")
    
    # Analyze results
    trades_df = analyze_results(trades, df, initial_capital=20000)
    
    print(f"\n{'='*60}")
    print(f"Analysis complete!")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
