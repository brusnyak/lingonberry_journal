"""
Test script for ICT features and backtesting framework.
"""
import sys
sys.path.append('backend')

import pandas as pd
import numpy as np
from src.features.technicals import calculate_all_technicals
from src.features.market_structure import analyze_market_structure, calculate_market_structure_score
from src.backtest.engine import BacktestEngine
from src.visualization.charts import (plot_candlestick_with_structure, plot_equity_curve,
                                     plot_component_analysis, plot_monte_carlo_results)
import matplotlib.pyplot as plt


def load_data(symbol: str = 'BTCUSD', timeframe: str = '15', limit: int = 5000) -> pd.DataFrame:
    """Load data from CSV files."""
    # Map symbol to file
    if symbol == 'BTCUSD':
        filepath = f'data/charts/crypto/BTCUSD{timeframe}.csv'
    else:
        filepath = f'data/charts/crypto/{symbol}{timeframe}.csv'
    
    # CSV has no headers, columns are: datetime, open, high, low, close, volume
    df = pd.read_csv(filepath, sep='\s+', header=None,
                    names=['datetime', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.set_index('datetime')
    
    # Take last N bars for faster testing
    if limit and len(df) > limit:
        df = df.iloc[-limit:]
    
    return df


def test_indicators():
    """Test new indicators (WT, CCI, ADX)."""
    print("\n" + "="*60)
    print("Testing New Indicators (WT, CCI, ADX)")
    print("="*60)
    
    # Load data
    df = load_data('BTCUSD', '15')
    
    # Calculate indicators
    df_with_indicators = calculate_all_technicals(df, normalize=False)
    
    # Check new indicators
    print(f"\nData shape: {df_with_indicators.shape}")
    print(f"\nNew indicators added:")
    print(f"  - Wave Trend 1 (wt1): {df_with_indicators['wt1'].notna().sum()} values")
    print(f"  - Wave Trend 2 (wt2): {df_with_indicators['wt2'].notna().sum()} values")
    print(f"  - CCI: {df_with_indicators['cci'].notna().sum()} values")
    print(f"  - ADX: {df_with_indicators['adx'].notna().sum()} values")
    
    # Show sample values
    print(f"\nSample values (last 5 rows):")
    print(df_with_indicators[['close', 'wt1', 'wt2', 'cci', 'adx']].tail())
    
    return df_with_indicators


def test_market_structure():
    """Test updated market structure with ICT fixes."""
    print("\n" + "="*60)
    print("Testing Market Structure (ICT)")
    print("="*60)
    
    # Load data
    df = load_data('BTCUSD', '15')
    
    # Analyze structure with new features
    structure = analyze_market_structure(
        df,
        swing_period=5,
        break_type='body',
        fvg_mitigation='partial',
        fvg_mitigation_threshold=0.382,
        volume_filter=True,
        detect_amd=False,  # Skip AMD for now (needs timezone-aware data)
        premium_discount_lookback=100
    )
    
    # Print results
    print(f"\nSwing Highs: {len(structure['swing_highs'])}")
    print(f"Swing Lows: {len(structure['swing_lows'])}")
    print(f"\nFair Value Gaps: {len(structure['fvgs'])}")
    print(f"  - Bullish FVGs: {sum(1 for fvg in structure['fvgs'] if fvg.type == 'bullish')}")
    print(f"  - Bearish FVGs: {sum(1 for fvg in structure['fvgs'] if fvg.type == 'bearish')}")
    print(f"  - Mitigated: {sum(1 for fvg in structure['fvgs'] if fvg.mitigated)}")
    print(f"\nOrder Blocks: {len(structure['order_blocks'])}")
    print(f"  - Bullish OBs: {sum(1 for ob in structure['order_blocks'] if ob.type == 'bullish')}")
    print(f"  - Bearish OBs: {sum(1 for ob in structure['order_blocks'] if ob.type == 'bearish')}")
    print(f"\nStructure Breaks: {len(structure['structure_breaks'])}")
    print(f"  - BOS: {sum(1 for brk in structure['structure_breaks'] if brk.type == 'BOS')}")
    print(f"  - CHoCH: {sum(1 for brk in structure['structure_breaks'] if brk.type == 'CHoCH')}")
    print(f"\nLiquidity Levels: {len(structure.get('liquidity_levels', []))}")
    print(f"  - Swept: {sum(1 for liq in structure.get('liquidity_levels', []) if liq.swept)}")
    print(f"  - Unswept: {sum(1 for liq in structure.get('liquidity_levels', []) if not liq.swept)}")
    print(f"\nRound Levels: {len(structure.get('round_levels', []))}")
    print(f"\nOpen Levels:")
    print(f"  - Daily: {len(structure.get('open_levels', {}).get('daily', []))}")
    print(f"  - Weekly: {len(structure.get('open_levels', {}).get('weekly', []))}")
    print(f"  - Monthly: {len(structure.get('open_levels', {}).get('monthly', []))}")
    print(f"\nPremium/Discount Zones: {len(structure.get('premium_discount_zones', []))}")
    print(f"\nCurrent Trend: {structure['current_trend']}")
    
    # Show sample structure breaks
    if structure['structure_breaks']:
        print(f"\nSample Structure Breaks (last 5):")
        for brk in structure['structure_breaks'][-5:]:
            print(f"  {brk.type} {brk.direction} at {brk.price:.2f} ({brk.time})")
    
    # Test confluence scoring
    if len(df) > 100:
        test_idx = len(df) - 1
        score = calculate_market_structure_score(df, test_idx, structure)
        print(f"\nConfluence Score at current bar: {score:.1f}/10.0")
    
    return df, structure


def test_backtest():
    """Test backtesting framework with simple strategy."""
    print("\n" + "="*60)
    print("Testing Backtesting Framework")
    print("="*60)
    
    # Load data
    df = load_data('BTCUSD', '15')
    
    # Add indicators
    df = calculate_all_technicals(df, normalize=False)
    
    # Simple RSI strategy
    def rsi_strategy(engine, df, i):
        """Simple RSI mean reversion strategy."""
        if i < 50:  # Need enough data
            return
        
        rsi = df['rsi'].iloc[i]
        price = df['close'].iloc[i]
        
        # Entry signals
        if engine.current_trade is None:
            if rsi < 30:  # Oversold - go long
                sl = price * 0.98  # 2% stop loss
                tp = price * 1.04  # 4% take profit
                engine.open_trade(df.index[i], price, 'long', size=1.0, 
                                stop_loss=sl, take_profit=tp)
            elif rsi > 70:  # Overbought - go short
                sl = price * 1.02  # 2% stop loss
                tp = price * 0.96  # 4% take profit
                engine.open_trade(df.index[i], price, 'short', size=1.0,
                                stop_loss=sl, take_profit=tp)
        
        # Exit signals
        else:
            if engine.current_trade.direction == 'long' and rsi > 50:
                engine.close_trade(df.index[i], price, 'signal')
            elif engine.current_trade.direction == 'short' and rsi < 50:
                engine.close_trade(df.index[i], price, 'signal')
    
    # Run backtest
    engine = BacktestEngine(initial_capital=10000, commission=0.001)
    result = engine.run(df, rsi_strategy)
    
    # Print results
    summary = result.summary()
    print(f"\nBacktest Results:")
    print(f"  Total Trades: {summary['total_trades']}")
    print(f"  Win Rate: {summary['win_rate']:.2f}%")
    print(f"  Total P&L: ${summary['total_pnl']:.2f}")
    print(f"  Total Return: {summary['total_return_pct']:.2f}%")
    print(f"  Profit Factor: {summary['profit_factor']:.2f}")
    print(f"  Max Drawdown: {summary['max_drawdown']:.2f}%")
    print(f"  Sharpe Ratio: {summary['sharpe_ratio']:.2f}")
    print(f"  Avg Win: ${summary['avg_win']:.2f}")
    print(f"  Avg Loss: ${summary['avg_loss']:.2f}")
    print(f"  Avg R:R: {summary['avg_rr']:.2f}")
    print(f"  Expectancy: ${summary['expectancy']:.2f}")
    
    # Monte Carlo simulation
    print(f"\n--- Monte Carlo Simulation (1000 runs) ---")
    mc_results = result.monte_carlo_simulation(n_simulations=1000)
    print(f"  Mean Return: {mc_results['mean_return']:.2f}%")
    print(f"  Median Return: {mc_results['median_return']:.2f}%")
    print(f"  Std Dev: {mc_results['std_return']:.2f}%")
    print(f"  5th Percentile: {mc_results['percentile_5']:.2f}%")
    print(f"  95th Percentile: {mc_results['percentile_95']:.2f}%")
    print(f"  Probability of Profit: {mc_results['prob_profit']:.1f}%")
    print(f"  Mean Max DD: {mc_results['mean_max_dd']:.2f}%")
    print(f"  Worst DD: {mc_results['worst_dd']:.2f}%")
    
    return result, mc_results


def test_visualization(df, structure, result, mc_results):
    """Test visualization."""
    print("\n" + "="*60)
    print("Testing Visualization")
    print("="*60)
    
    # Set dark theme for charts
    plt.style.use('dark_background')
    
    # Take last 200 bars for clearer visualization
    df_subset = df.iloc[-200:].copy()
    
    # Need to adjust structure indices
    offset = len(df) - 200
    
    # Filter structure elements to subset
    structure_subset = {
        'swing_highs': [s for s in structure['swing_highs'] if s.index >= offset],
        'swing_lows': [s for s in structure['swing_lows'] if s.index >= offset],
        'swing_labels': {k-offset: v for k, v in structure['swing_labels'].items() if k >= offset},
        'fvgs': [fvg for fvg in structure['fvgs'] if fvg.index >= offset],
        'order_blocks': [ob for ob in structure['order_blocks'] if ob.index >= offset],
        'structure_breaks': [brk for brk in structure['structure_breaks'] if brk.index >= offset],
        'liquidity_levels': [liq for liq in structure.get('liquidity_levels', []) if liq.start_index >= offset],
        'round_levels': structure.get('round_levels', []),
        'open_levels': structure.get('open_levels', {}),
        'premium_discount_zones': structure.get('premium_discount_zones', []),
        'current_trend': structure['current_trend']
    }
    
    # Adjust indices
    for s in structure_subset['swing_highs']:
        s.index -= offset
    for s in structure_subset['swing_lows']:
        s.index -= offset
    for fvg in structure_subset['fvgs']:
        fvg.index -= offset
    for ob in structure_subset['order_blocks']:
        ob.index -= offset
    for brk in structure_subset['structure_breaks']:
        brk.index -= offset
    for liq in structure_subset['liquidity_levels']:
        liq.start_index -= offset
        if liq.swept_index is not None:
            liq.swept_index -= offset
    
    # Reset df index to numeric
    df_subset = df_subset.reset_index(drop=True)
    
    # Plot 1: Combined chart with intervals
    fig, ax = plot_candlestick_with_structure(
        df_subset,
        structure_subset,
        title="BTC/USD 15m - Market Structure (Combined)",
        show_swings=True,
        show_fvgs=True,
        show_obs=True,
        show_liquidity=True,
        show_round_levels=True,
        show_intervals=True
    )
    
    plt.savefig('data/test_market_structure_combined.png', dpi=150, bbox_inches='tight')
    print(f"\nCombined chart saved to: data/test_market_structure_combined.png")
    plt.close()
    
    # Plot 2: Component analysis (separate charts)
    fig, axes = plot_component_analysis(df_subset, structure_subset)
    plt.savefig('data/test_market_structure_components.png', dpi=150, bbox_inches='tight')
    print(f"Component charts saved to: data/test_market_structure_components.png")
    plt.close()
    
    # Plot 3: Monte Carlo results
    fig, axes = plot_monte_carlo_results(mc_results)
    plt.savefig('data/test_monte_carlo.png', dpi=150, bbox_inches='tight')
    print(f"Monte Carlo chart saved to: data/test_monte_carlo.png")
    plt.close()


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("ICT FEATURES & BACKTEST VALIDATION")
    print("="*60)
    
    try:
        # Test 1: New indicators
        df_indicators = test_indicators()
        
        # Test 2: Market structure
        df, structure = test_market_structure()
        
        # Test 3: Backtesting
        result, mc_results = test_backtest()
        
        # Test 4: Visualization
        test_visualization(df, structure, result, mc_results)
        
        print("\n" + "="*60)
        print("ALL TESTS COMPLETED SUCCESSFULLY!")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
