"""
Improved ML Strategy with ICT-based Risk Management

Key Improvements:
1. Minimum 2:1 RR requirement using liquidity levels as TP
2. High confidence filter (>median)
3. Premium/discount zone alignment
4. Trailing stops for winners
5. Better position sizing
"""

import sys
import os

# Add parent directory to path
script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
parent_dir = os.path.join(script_dir, '..')
sys.path.insert(0, parent_dir)

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from src.data.loader import DataLoader
from src.features.technicals import calculate_all_technicals
from src.features.market_structure import analyze_market_structure
from src.ml.features import prepare_ml_features
from src.ml.lorentzian import LorentzianClassifier, create_labels


def load_data(symbol: str = 'BTCUSD', timeframe: str = '15', limit: int = 5000) -> pd.DataFrame:
    """Load and prepare data."""
    print(f"\n{'='*60}")
    print(f"Loading {symbol} {timeframe}min data...")
    print(f"{'='*60}")
    
    loader = DataLoader()
    df = loader.load(symbol, timeframe, limit=limit)
    df = calculate_all_technicals(df)
    
    # Calculate date range
    start_date = df.index[0]
    end_date = df.index[-1]
    days = (end_date - start_date).days
    
    print(f"\nData Range:")
    print(f"  Start: {start_date}")
    print(f"  End: {end_date}")
    print(f"  Duration: {days} days ({days/30:.1f} months)")
    print(f"  Bars: {len(df)}")
    
    return df


def find_nearest_liquidity(ms: dict, trade_idx: int, direction: str, entry_price: float) -> tuple:
    """
    Find nearest unswept liquidity level for take profit.
    
    Returns:
        (tp_price, distance_pct)
    """
    nearest_liq = None
    min_distance = float('inf')
    
    for liq in ms['liquidity_levels']:
        # Only consider future liquidity (not yet formed or unswept)
        if liq.start_index > trade_idx or (liq.start_index <= trade_idx and not liq.swept):
            # For longs, look for liquidity above
            if direction == 'long' and liq.price > entry_price:
                distance = liq.price - entry_price
                if distance < min_distance:
                    min_distance = distance
                    nearest_liq = liq.price
            # For shorts, look for liquidity below
            elif direction == 'short' and liq.price < entry_price:
                distance = entry_price - liq.price
                if distance < min_distance:
                    min_distance = distance
                    nearest_liq = liq.price
    
    if nearest_liq is not None:
        distance_pct = (min_distance / entry_price) * 100
        return nearest_liq, distance_pct
    
    return None, None


def calculate_atr_stop_loss(df: pd.DataFrame, idx: int, atr_multiplier: float = 2.0) -> float:
    """Calculate ATR-based stop loss distance."""
    return df.iloc[idx]['atr'] * atr_multiplier


def get_premium_discount_zone(ms: dict, trade_idx: int, price: float) -> str:
    """Get premium/discount zone at trade index."""
    for zone in ms['premium_discount_zones']:
        if zone.start_index <= trade_idx <= zone.end_index:
            if price > zone.equilibrium:
                return 'premium'
            else:
                return 'discount'
    return 'neutral'


def improved_ml_strategy(df: pd.DataFrame, features_norm: pd.DataFrame,
                        k: int = 15, lookback: int = 2000,
                        min_confidence_percentile: float = 50.0,
                        min_rr_ratio: float = 2.0,
                        use_trailing_stop: bool = True,
                        trailing_atr_mult: float = 1.5) -> list:
    """
    Run improved ML strategy with ICT-based risk management.
    
    Args:
        df: OHLC dataframe
        features_norm: Normalized features
        k: KNN neighbors
        lookback: Historical lookback
        min_confidence_percentile: Minimum confidence percentile (0-100)
        min_rr_ratio: Minimum risk-reward ratio
        use_trailing_stop: Enable trailing stops
        trailing_atr_mult: ATR multiplier for trailing stop
    
    Returns:
        List of trades
    """
    # Analyze market structure once
    print("\nAnalyzing market structure...")
    ms = analyze_market_structure(df)
    
    # Create labels
    labels = create_labels(df, forward_bars=4)
    
    # Initialize classifier
    clf = LorentzianClassifier(k=k, lookback=lookback)
    
    # Generate predictions
    print("Generating ML predictions...")
    predictions = clf.predict_series(features_norm, labels, start_idx=lookback)
    
    # Calculate confidence threshold
    confidence_threshold = np.percentile(predictions['confidence'], min_confidence_percentile)
    print(f"Confidence threshold ({min_confidence_percentile}th percentile): {confidence_threshold:.3f}")
    
    # Align predictions with df
    signals = pd.DataFrame(index=df.index)
    signals['signal'] = 0
    signals['confidence'] = 0.0
    
    signals.loc[predictions.index, 'signal'] = predictions['signal']
    signals.loc[predictions.index, 'confidence'] = predictions['confidence']
    
    # Collect trades
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
    
    print("\nSimulating trades with improved strategy...")
    filtered_signals = 0
    rr_filtered = 0
    zone_filtered = 0
    
    for i in range(lookback, len(df)):
        if in_position:
            # Update trailing stop for winners
            if use_trailing_stop:
                current_price = df.iloc[i]['close']
                
                if entry_signal == 1:  # Long
                    if current_price > highest_price:
                        highest_price = current_price
                        # Update trailing stop
                        atr = df.iloc[i]['atr']
                        new_trailing = highest_price - (atr * trailing_atr_mult)
                        if new_trailing > trailing_stop:
                            trailing_stop = new_trailing
                elif entry_signal == -1:  # Short
                    if current_price < lowest_price:
                        lowest_price = current_price
                        # Update trailing stop
                        atr = df.iloc[i]['atr']
                        new_trailing = lowest_price + (atr * trailing_atr_mult)
                        if new_trailing < trailing_stop:
                            trailing_stop = new_trailing
            
            # Check exit conditions
            current_price = df.iloc[i]['close']
            exit_reason = None
            exit_price = None
            
            # Take profit hit
            if take_profit is not None:
                if entry_signal == 1 and current_price >= take_profit:
                    exit_reason = 'take_profit'
                    exit_price = take_profit
                elif entry_signal == -1 and current_price <= take_profit:
                    exit_reason = 'take_profit'
                    exit_price = take_profit
            
            # Trailing stop hit
            if exit_reason is None and use_trailing_stop and trailing_stop is not None:
                if entry_signal == 1 and current_price <= trailing_stop:
                    exit_reason = 'trailing_stop'
                    exit_price = trailing_stop
                elif entry_signal == -1 and current_price >= trailing_stop:
                    exit_reason = 'trailing_stop'
                    exit_price = trailing_stop
            
            # Stop loss hit
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
            
            # Exit if condition met
            if exit_reason is not None:
                # Record trade
                pnl_pct = ((exit_price - entry_price) / entry_price) * entry_signal * 100
                bars_in_trade = i - entry_idx
                
                trades.append({
                    'entry_idx': entry_idx,
                    'entry_time': df.index[entry_idx],
                    'entry_price': entry_price,
                    'exit_idx': i,
                    'exit_time': df.index[i],
                    'exit_price': exit_price,
                    'direction': 'long' if entry_signal == 1 else 'short',
                    'pnl_pct': pnl_pct,
                    'bars_in_trade': bars_in_trade,
                    'exit_reason': exit_reason,
                    'stop_loss': stop_loss,
                    'take_profit': take_profit,
                    'confidence': signals.iloc[entry_idx]['confidence'],
                })
                
                in_position = False
                entry_idx = None
                entry_price = None
                entry_signal = None
                stop_loss = None
                take_profit = None
                trailing_stop = None
                highest_price = None
                lowest_price = None
        
        else:
            # Check entry conditions
            if signals.iloc[i]['signal'] != 0:
                signal = signals.iloc[i]['signal']
                confidence = signals.iloc[i]['confidence']
                
                # Filter 1: Confidence
                if confidence < confidence_threshold:
                    filtered_signals += 1
                    continue
                
                # Get current price and zone
                current_price = df.iloc[i]['close']
                zone = get_premium_discount_zone(ms, i, current_price)
                
                # Filter 2: Premium/Discount alignment
                if signal == 1 and zone == 'premium':
                    zone_filtered += 1
                    continue
                if signal == -1 and zone == 'discount':
                    zone_filtered += 1
                    continue
                
                # Calculate stop loss
                atr_stop = calculate_atr_stop_loss(df, i, atr_multiplier=2.0)
                if signal == 1:
                    sl = current_price - atr_stop
                else:
                    sl = current_price + atr_stop
                
                # Find take profit using liquidity
                tp, tp_distance_pct = find_nearest_liquidity(ms, i, 'long' if signal == 1 else 'short', current_price)
                
                # If no liquidity found, use ATR-based TP
                if tp is None:
                    if signal == 1:
                        tp = current_price + (atr_stop * min_rr_ratio)
                    else:
                        tp = current_price - (atr_stop * min_rr_ratio)
                
                # Calculate actual RR ratio
                risk = abs(current_price - sl)
                reward = abs(tp - current_price)
                rr_ratio = reward / risk if risk > 0 else 0
                
                # Filter 3: Minimum RR ratio
                if rr_ratio < min_rr_ratio:
                    rr_filtered += 1
                    continue
                
                # Enter position
                in_position = True
                entry_idx = i
                entry_price = current_price
                entry_signal = signal
                stop_loss = sl
                take_profit = tp
                trailing_stop = sl  # Initialize trailing stop at SL
                highest_price = current_price if signal == 1 else None
                lowest_price = current_price if signal == -1 else None
    
    print(f"\nFiltering Results:")
    print(f"  Confidence filtered: {filtered_signals}")
    print(f"  Zone filtered: {zone_filtered}")
    print(f"  RR filtered: {rr_filtered}")
    print(f"  Total filtered: {filtered_signals + zone_filtered + rr_filtered}")
    print(f"  Trades executed: {len(trades)}")
    
    return trades


def analyze_results(trades: list, df: pd.DataFrame, initial_capital: float = 20000):
    """Analyze trading results."""
    if not trades:
        print("\nNo trades executed!")
        return
    
    trades_df = pd.DataFrame(trades)
    
    print(f"\n{'='*60}")
    print(f"IMPROVED STRATEGY RESULTS")
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
    print(f"  RR Ratio: {rr_ratio:.2f}:1")
    
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
    
    # Capital simulation
    print(f"\nCapital Simulation (${initial_capital:,.0f} initial):")
    capital = initial_capital
    equity_curve = [capital]
    
    for _, trade in trades_df.iterrows():
        # Risk 1% per trade
        risk_amount = capital * 0.01
        # Calculate position size based on stop loss distance
        # This is simplified - in reality would depend on stop loss distance
        pnl_dollars = risk_amount * (trade['pnl_pct'] / 1.0)  # Assuming 1% stop = 1% risk
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
    
    # Sharpe ratio (simplified)
    returns = trades_df['pnl_pct'].values
    sharpe = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0
    print(f"  Sharpe Ratio: {sharpe:.2f}")
    
    return trades_df


def main():
    """Main function."""
    # Load data
    df = load_data('BTCUSD', '15', limit=5000)
    
    # Prepare features
    print(f"\nPreparing ML features...")
    features_norm = prepare_ml_features(df)
    
    # Run improved strategy
    trades = improved_ml_strategy(
        df, features_norm,
        k=15,
        lookback=2000,
        min_confidence_percentile=50.0,  # Top 50% confidence
        min_rr_ratio=2.0,  # Minimum 2:1 RR
        use_trailing_stop=True,
        trailing_atr_mult=1.5
    )
    
    # Analyze results
    trades_df = analyze_results(trades, df, initial_capital=20000)
    
    print(f"\n{'='*60}")
    print(f"Analysis complete!")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
