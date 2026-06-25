"""
Test proper backtesting with realistic parameters.

Parameters:
- Initial balance: $20,000
- Risk per trade: 1% ($200)
- Minimum RR: 2:1
- Slippage: 2 ticks
- Commission: 0.1% per side (0.2% round trip)
"""
import sys
sys.path.append('backend')

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from src.features.technicals import calculate_all_technicals
from src.ml.lorentzian import LorentzianClassifier, create_labels
from src.ml.features import prepare_ml_features, normalize_features
from src.ml.filters import VolatilityFilter, ADXFilter, combine_filters
from src.backtest.engine import BacktestEngine, BacktestResult
from typing import Dict


def load_data(symbol: str = 'BTCUSD', timeframe: str = '15', limit: int = 5000) -> pd.DataFrame:
    """Load data from CSV files."""
    filepath = f'data/charts/crypto/{symbol}{timeframe}.csv'
    
    df = pd.read_csv(filepath, sep='\s+', header=None,
                    names=['datetime', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.set_index('datetime')
    
    if limit and len(df) > limit:
        df = df.iloc[-limit:]
    
    return df


def calculate_atr_stop_loss(df: pd.DataFrame, atr_multiplier: float = 2.0) -> pd.Series:
    """
    Calculate ATR-based stop loss levels.
    
    Args:
        df: OHLC dataframe with ATR
        atr_multiplier: ATR multiplier for stop distance
    
    Returns:
        Series of stop loss distances
    """
    if 'atr' not in df.columns:
        # Calculate ATR if not present
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        atr = true_range.rolling(14).mean()
    else:
        atr = df['atr']
    
    return atr * atr_multiplier


def ml_strategy_with_risk_management(df: pd.DataFrame, features_norm: pd.DataFrame,
                                    predictions: pd.DataFrame, filter_mask: pd.Series,
                                    min_rr: float = 2.0) -> Dict:
    """
    ML strategy with proper risk management.
    
    Args:
        df: OHLC dataframe
        features_norm: Normalized features
        predictions: ML predictions
        filter_mask: Signal filter mask
        min_rr: Minimum risk-reward ratio
    
    Returns:
        Dict with signals and risk parameters
    """
    # Align data
    df = df.iloc[-len(predictions):].copy().reset_index()
    predictions = predictions.reset_index(drop=True)
    filter_mask = filter_mask.iloc[-len(predictions):].reset_index(drop=True)
    
    # Calculate ATR-based stops
    atr_stops = calculate_atr_stop_loss(df, atr_multiplier=2.0)
    
    signals = []
    
    for i in range(len(df)):
        signal = predictions['signal'].iloc[i]
        confidence = predictions['confidence'].iloc[i]
        passed_filter = filter_mask.iloc[i]
        
        if not passed_filter or signal == 0:
            signals.append({
                'signal': 0,
                'entry_price': None,
                'stop_loss': None,
                'take_profit': None,
                'confidence': confidence
            })
            continue
        
        entry_price = df['close'].iloc[i]
        atr_stop = atr_stops.iloc[i]
        
        if signal == 1:  # Long
            stop_loss = entry_price - atr_stop
            risk = entry_price - stop_loss
            take_profit = entry_price + (risk * min_rr)
            
        else:  # Short
            stop_loss = entry_price + atr_stop
            risk = stop_loss - entry_price
            take_profit = entry_price - (risk * min_rr)
        
        signals.append({
            'signal': signal,
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'confidence': confidence
        })
    
    return pd.DataFrame(signals, index=df['datetime'])


def run_proper_backtest():
    """Run backtest with proper risk management."""
    print("\n" + "="*60)
    print("PROPER BACKTESTING WITH RISK MANAGEMENT")
    print("="*60)
    
    # Parameters
    initial_capital = 20000.0
    risk_per_trade = 0.01  # 1%
    min_rr = 2.0
    commission = 0.001  # 0.1% per side
    slippage_pct = 0.0002  # 0.02% (2 ticks)
    
    print(f"\nBacktest Parameters:")
    print(f"  Initial Capital: ${initial_capital:,.2f}")
    print(f"  Risk per Trade: {risk_per_trade*100:.1f}% (${initial_capital*risk_per_trade:,.2f})")
    print(f"  Minimum RR: {min_rr}:1")
    print(f"  Commission: {commission*100:.2f}% per side ({commission*2*100:.2f}% round trip)")
    print(f"  Slippage: {slippage_pct*100:.3f}%")
    
    # Load data
    print(f"\nLoading data...")
    df = load_data('BTCUSD', '15', limit=5000)
    df = calculate_all_technicals(df, normalize=False)
    
    # Prepare ML features
    print(f"Preparing ML features...")
    features = prepare_ml_features(df, include_ict=True)
    features_norm = normalize_features(features, method='minmax', lookback=2000)
    labels = create_labels(df, forward_bars=4)
    
    # Train classifier
    print(f"Training classifier...")
    classifier = LorentzianClassifier(k=8, lookback=2000)
    classifier.fit(features_norm.values, labels.values)
    
    # Generate predictions
    print(f"Generating predictions...")
    predictions = classifier.predict_series(features_norm, labels, start_idx=2000)
    
    # Apply filters
    print(f"Applying filters...")
    vol_filter = VolatilityFilter(min_percentile=20, max_percentile=80)
    adx_filter = ADXFilter(min_adx=20, max_adx=50)
    
    vol_mask = vol_filter.filter(df)
    adx_mask = adx_filter.filter(df)
    combined_mask = combine_filters(vol_mask, adx_mask)
    
    # Generate strategy signals with risk management
    print(f"Generating strategy signals...")
    strategy_signals = ml_strategy_with_risk_management(
        df, features_norm, predictions, combined_mask, min_rr=min_rr
    )
    
    # Initialize backtest engine
    engine = BacktestEngine(
        initial_capital=initial_capital,
        commission=commission,
        slippage=slippage_pct,
        risk_per_trade=risk_per_trade
    )
    
    # Run backtest
    print(f"\nRunning backtest...")
    df_test = df.iloc[-len(predictions):].copy()
    df_test = df_test.reset_index()
    
    for i in range(len(df_test)):
        current_time = df_test['datetime'].iloc[i]
        current_high = df_test['high'].iloc[i]
        current_low = df_test['low'].iloc[i]
        current_close = df_test['close'].iloc[i]
        
        signal_data = strategy_signals.iloc[i]
        
        # Update existing positions
        engine.update(current_time, current_high, current_low, current_close)
        
        # Check for new signals
        if signal_data['signal'] != 0 and not engine.current_trade:
            direction = 'long' if signal_data['signal'] == 1 else 'short'
            
            engine.open_trade(
                time=current_time,
                price=signal_data['entry_price'],
                direction=direction,
                stop_loss=signal_data['stop_loss'],
                take_profit=signal_data['take_profit']
            )
    
    # Create result
    if len(engine.equity_curve) > 0:
        equity_series = pd.Series([e[1] for e in engine.equity_curve],
                                 index=[e[0] for e in engine.equity_curve])
    else:
        equity_series = pd.Series([initial_capital])
    
    result = BacktestResult(
        trades=engine.closed_trades,
        equity_curve=equity_series,
        initial_capital=initial_capital,
        final_capital=engine.capital
    )
    
    # Print results
    print("\n" + "="*60)
    print("BACKTEST RESULTS")
    print("="*60)
    
    summary = result.summary()
    
    print(f"\nCapital:")
    print(f"  Initial: ${initial_capital:,.2f}")
    print(f"  Final: ${result.final_capital:,.2f}")
    print(f"  Total P&L: ${summary['total_pnl']:,.2f} ({summary['total_return_pct']:.2f}%)")
    
    print(f"\nTrades:")
    print(f"  Total: {summary['total_trades']}")
    print(f"  Winners: {summary['winning_trades']} ({summary['win_rate']:.1f}%)")
    print(f"  Losers: {summary['losing_trades']}")
    
    print(f"\nPerformance:")
    print(f"  Avg Win: ${summary['avg_win']:,.2f}")
    print(f"  Avg Loss: ${summary['avg_loss']:,.2f}")
    print(f"  Avg RR: {summary['avg_rr']:.2f}:1")
    print(f"  Expectancy: ${summary['expectancy']:,.2f}")
    print(f"  Profit Factor: {summary['profit_factor']:.2f}")
    
    print(f"\nRisk Metrics:")
    print(f"  Max Drawdown: {summary['max_drawdown']:.2f}%")
    print(f"  Sharpe Ratio: {summary['sharpe_ratio']:.2f}")
    
    # Compare to buy & hold
    buy_hold_return = ((df_test['close'].iloc[-1] - df_test['close'].iloc[0]) / 
                       df_test['close'].iloc[0] * 100)
    print(f"\nComparison:")
    print(f"  Strategy Return: {summary['total_return_pct']:.2f}%")
    print(f"  Buy & Hold Return: {buy_hold_return:.2f}%")
    print(f"  Outperformance: {summary['total_return_pct'] - buy_hold_return:.2f}%")
    
    return result, df_test, strategy_signals


def visualize_backtest(result: BacktestResult, df: pd.DataFrame, 
                       strategy_signals: pd.DataFrame):
    """Visualize backtest results."""
    print("\n" + "="*60)
    print("Generating Visualizations")
    print("="*60)
    
    plt.style.use('dark_background')
    fig = plt.figure(figsize=(18, 12))
    gs = fig.add_gridspec(4, 2, hspace=0.3, wspace=0.3)
    
    # Plot 1: Equity curve
    ax1 = fig.add_subplot(gs[0, :])
    ax1.plot(result.equity_curve.index, result.equity_curve.values, linewidth=2, color='cyan')
    ax1.axhline(y=result.initial_capital, color='yellow', linestyle='--', 
               alpha=0.5, label='Initial Capital')
    ax1.set_title('Equity Curve', fontsize=14, fontweight='bold')
    ax1.set_ylabel('Equity ($)')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
    
    # Plot 2: Price with trades
    ax2 = fig.add_subplot(gs[1, :])
    ax2.plot(df['datetime'], df['close'], linewidth=1, alpha=0.7, color='white')
    
    # Mark trades
    for trade in result.trades:
        color = 'green' if trade.pnl > 0 else 'red'
        marker = '^' if trade.direction == 'long' else 'v'
        
        # Entry
        ax2.scatter(trade.entry_time, trade.entry_price, 
                   color=color, marker=marker, s=100, alpha=0.7, edgecolors='white')
        
        # Exit
        ax2.scatter(trade.exit_time, trade.exit_price,
                   color=color, marker='x', s=100, alpha=0.7)
        
        # Connect entry to exit
        ax2.plot([trade.entry_time, trade.exit_time],
                [trade.entry_price, trade.exit_price],
                color=color, alpha=0.3, linewidth=1)
    
    ax2.set_title('Price Chart with Trades', fontsize=14, fontweight='bold')
    ax2.set_ylabel('Price ($)')
    ax2.grid(True, alpha=0.3)
    
    # Plot 3: Trade P&L distribution
    ax3 = fig.add_subplot(gs[2, 0])
    pnls = [t.pnl for t in result.trades]
    ax3.hist(pnls, bins=30, color='cyan', alpha=0.7, edgecolor='white')
    ax3.axvline(x=0, color='yellow', linestyle='--', alpha=0.5)
    ax3.set_title('Trade P&L Distribution', fontsize=12, fontweight='bold')
    ax3.set_xlabel('P&L ($)')
    ax3.set_ylabel('Frequency')
    ax3.grid(True, alpha=0.3, axis='y')
    
    # Plot 4: Cumulative P&L
    ax4 = fig.add_subplot(gs[2, 1])
    cumulative_pnl = np.cumsum(pnls)
    ax4.plot(range(len(cumulative_pnl)), cumulative_pnl, linewidth=2, color='green')
    ax4.axhline(y=0, color='yellow', linestyle='--', alpha=0.5)
    ax4.set_title('Cumulative P&L', fontsize=12, fontweight='bold')
    ax4.set_xlabel('Trade Number')
    ax4.set_ylabel('Cumulative P&L ($)')
    ax4.grid(True, alpha=0.3)
    
    # Plot 5: Win/Loss streaks
    ax5 = fig.add_subplot(gs[3, 0])
    wins_losses = [1 if t.pnl > 0 else -1 for t in result.trades]
    colors = ['green' if w > 0 else 'red' for w in wins_losses]
    ax5.bar(range(len(wins_losses)), wins_losses, color=colors, alpha=0.7)
    ax5.axhline(y=0, color='white', linestyle='-', alpha=0.3)
    ax5.set_title('Win/Loss Sequence', fontsize=12, fontweight='bold')
    ax5.set_xlabel('Trade Number')
    ax5.set_ylabel('Win (+1) / Loss (-1)')
    ax5.grid(True, alpha=0.3, axis='y')
    
    # Plot 6: Risk-Reward distribution
    ax6 = fig.add_subplot(gs[3, 1])
    rr_ratios = [t.pnl / abs(t.entry_price - t.stop_loss) 
                 for t in result.trades if t.stop_loss]
    ax6.hist(rr_ratios, bins=30, color='orange', alpha=0.7, edgecolor='white')
    ax6.axvline(x=0, color='yellow', linestyle='--', alpha=0.5)
    ax6.axvline(x=2, color='green', linestyle='--', alpha=0.5, label='Target RR (2:1)')
    ax6.set_title('Risk-Reward Distribution', fontsize=12, fontweight='bold')
    ax6.set_xlabel('R-Multiple')
    ax6.set_ylabel('Frequency')
    ax6.legend()
    ax6.grid(True, alpha=0.3, axis='y')
    
    plt.savefig('data/proper_backtest_results.png', dpi=150, bbox_inches='tight')
    print(f"\nChart saved to: data/proper_backtest_results.png")
    plt.close()


def main():
    """Run proper backtest."""
    try:
        # Run backtest
        result, df_test, strategy_signals = run_proper_backtest()
        
        # Visualize
        visualize_backtest(result, df_test, strategy_signals)
        
        print("\n" + "="*60)
        print("BACKTEST COMPLETED SUCCESSFULLY!")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
