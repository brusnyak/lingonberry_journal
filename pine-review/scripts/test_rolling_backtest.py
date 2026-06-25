"""
Test rolling window backtests with proper position sizing.
Target: 15-20% account growth per 2-month window with 2% risk per trade.
"""
import sys
sys.path.append('backend')

import pandas as pd
import numpy as np
from src.data.loader import DataLoader
from src.features.technicals import calculate_all_technicals
from src.backtest.engine import BacktestEngine
import matplotlib.pyplot as plt


def simple_rsi_strategy(engine, df, i):
    """Simple RSI mean reversion strategy with proper risk management."""
    if i < 50:
        return
    
    rsi = df['rsi'].iloc[i]
    price = df['close'].iloc[i]
    atr = df['atr'].iloc[i]
    
    # Entry signals
    if engine.current_trade is None:
        if rsi < 30:  # Oversold - go long
            sl = price - (2 * atr)  # 2 ATR stop loss
            tp = price + (4 * atr)  # 4 ATR take profit (2:1 RR)
            engine.open_trade(df.index[i], price, 'long', 
                            stop_loss=sl, take_profit=tp)
        elif rsi > 70:  # Overbought - go short
            sl = price + (2 * atr)  # 2 ATR stop loss
            tp = price - (4 * atr)  # 4 ATR take profit (2:1 RR)
            engine.open_trade(df.index[i], price, 'short',
                            stop_loss=sl, take_profit=tp)
    
    # Exit signals (optional early exit)
    else:
        if engine.current_trade.direction == 'long' and rsi > 50:
            engine.close_trade(df.index[i], price, 'signal')
        elif engine.current_trade.direction == 'short' and rsi < 50:
            engine.close_trade(df.index[i], price, 'signal')


def test_rolling_backtest():
    """Test rolling window backtest."""
    print("="*70)
    print("ROLLING WINDOW BACKTEST - 2 MONTH INTERVALS")
    print("Target: 15-20% growth per window with 2% risk per trade")
    print("="*70)
    
    # Load data
    loader = DataLoader()
    df = loader.load('BTCUSD', '15', limit=10000)  # Last 10k bars (~104 days on 15m)
    
    print(f"\nData loaded: {len(df)} bars")
    print(f"Date range: {df.index[0]} to {df.index[-1]}")
    print(f"Duration: {(df.index[-1] - df.index[0]).days} days")
    
    # Add indicators
    df = calculate_all_technicals(df, normalize=False)
    
    # Run rolling window backtest
    engine = BacktestEngine(
        initial_capital=10000,
        commission=0.001,
        risk_per_trade=0.02,  # 2% risk per trade
        position_sizing='risk_pct'
    )
    
    print(f"\nRunning rolling window backtest (60-day windows)...")
    results = engine.run_rolling_windows(df, simple_rsi_strategy, window_days=60)
    
    print(f"\nCompleted {len(results)} windows")
    print("\n" + "="*70)
    print("WINDOW RESULTS")
    print("="*70)
    
    # Analyze each window
    window_stats = []
    for i, result in enumerate(results):
        summary = result.summary()
        
        # Calculate days in window
        days = (result.equity_curve.index[-1] - result.equity_curve.index[0]).days
        
        window_stats.append({
            'window': i + 1,
            'trades': summary['total_trades'],
            'win_rate': summary['win_rate'],
            'return_pct': summary['total_return_pct'],
            'max_dd': summary['max_drawdown'],
            'profit_factor': summary['profit_factor'],
            'sharpe': summary['sharpe_ratio'],
            'avg_rr': summary['avg_rr'],
            'expectancy': summary['expectancy'],
            'days': days
        })
        
        # Print window summary
        status = "✅ TARGET MET" if 15 <= summary['total_return_pct'] <= 25 else "❌ MISSED"
        print(f"\nWindow {i+1} ({days} days): {status}")
        print(f"  Return: {summary['total_return_pct']:.2f}%")
        print(f"  Trades: {summary['total_trades']}")
        print(f"  Win Rate: {summary['win_rate']:.1f}%")
        print(f"  Max DD: {summary['max_drawdown']:.2f}%")
        print(f"  Profit Factor: {summary['profit_factor']:.2f}")
        print(f"  Avg R:R: {summary['avg_rr']:.2f}")
        print(f"  Expectancy: ${summary['expectancy']:.2f}")
    
    # Overall statistics
    print("\n" + "="*70)
    print("OVERALL STATISTICS")
    print("="*70)
    
    returns = [w['return_pct'] for w in window_stats]
    target_met = sum(1 for r in returns if 15 <= r <= 25)
    
    print(f"\nWindows analyzed: {len(window_stats)}")
    print(f"Target met (15-20%): {target_met} / {len(window_stats)} ({target_met/len(window_stats)*100:.1f}%)")
    print(f"\nReturn statistics:")
    print(f"  Mean: {np.mean(returns):.2f}%")
    print(f"  Median: {np.median(returns):.2f}%")
    print(f"  Std Dev: {np.std(returns):.2f}%")
    print(f"  Min: {np.min(returns):.2f}%")
    print(f"  Max: {np.max(returns):.2f}%")
    
    win_rates = [w['win_rate'] for w in window_stats]
    print(f"\nWin rate statistics:")
    print(f"  Mean: {np.mean(win_rates):.1f}%")
    print(f"  Median: {np.median(win_rates):.1f}%")
    
    max_dds = [w['max_dd'] for w in window_stats]
    print(f"\nMax drawdown statistics:")
    print(f"  Mean: {np.mean(max_dds):.2f}%")
    print(f"  Worst: {np.max(max_dds):.2f}%")
    
    # Visualize results
    plot_rolling_results(window_stats)
    
    return results, window_stats


def plot_rolling_results(window_stats):
    """Plot rolling window results."""
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))
    
    windows = [w['window'] for w in window_stats]
    returns = [w['return_pct'] for w in window_stats]
    win_rates = [w['win_rate'] for w in window_stats]
    max_dds = [w['max_dd'] for w in window_stats]
    profit_factors = [w['profit_factor'] for w in window_stats]
    
    # Returns per window
    colors = ['green' if 15 <= r <= 25 else 'orange' if r > 0 else 'red' for r in returns]
    ax1.bar(windows, returns, color=colors, alpha=0.7)
    ax1.axhline(y=15, color='green', linestyle='--', linewidth=1, label='Target Min (15%)')
    ax1.axhline(y=20, color='blue', linestyle='--', linewidth=1, label='Target Max (20%)')
    ax1.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    ax1.set_title('Returns per Window', fontweight='bold')
    ax1.set_xlabel('Window')
    ax1.set_ylabel('Return (%)')
    ax1.legend()
    ax1.grid(True, alpha=0.3, axis='y')
    
    # Win rate per window
    ax2.plot(windows, win_rates, marker='o', linewidth=2, markersize=6)
    ax2.axhline(y=50, color='red', linestyle='--', linewidth=1, alpha=0.5)
    ax2.set_title('Win Rate per Window', fontweight='bold')
    ax2.set_xlabel('Window')
    ax2.set_ylabel('Win Rate (%)')
    ax2.grid(True, alpha=0.3)
    
    # Max drawdown per window
    ax3.bar(windows, max_dds, color='red', alpha=0.6)
    ax3.set_title('Max Drawdown per Window', fontweight='bold')
    ax3.set_xlabel('Window')
    ax3.set_ylabel('Max DD (%)')
    ax3.grid(True, alpha=0.3, axis='y')
    
    # Profit factor per window
    ax4.bar(windows, profit_factors, color='blue', alpha=0.6)
    ax4.axhline(y=1.0, color='red', linestyle='--', linewidth=1)
    ax4.set_title('Profit Factor per Window', fontweight='bold')
    ax4.set_xlabel('Window')
    ax4.set_ylabel('Profit Factor')
    ax4.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig('data/rolling_backtest_results.png', dpi=150, bbox_inches='tight')
    print(f"\n📊 Chart saved to: data/rolling_backtest_results.png")
    plt.close()


if __name__ == "__main__":
    try:
        results, stats = test_rolling_backtest()
        print("\n✅ Rolling backtest completed successfully!")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
