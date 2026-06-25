"""
Test ML model with ICT features - compare baseline vs enhanced.
"""
import sys
sys.path.append('backend')

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from src.features.technicals import calculate_all_technicals
from src.ml.lorentzian import LorentzianClassifier, create_labels
from src.ml.features import (
    prepare_ml_features, normalize_features,
    analyze_feature_correlations, select_optimal_features
)
from src.ml.filters import VolatilityFilter, RegimeFilter, ADXFilter, combine_filters


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


def test_baseline_model():
    """Test baseline model (5 features)."""
    print("\n" + "="*60)
    print("BASELINE MODEL (5 Features)")
    print("="*60)
    
    # Load data
    df = load_data('BTCUSD', '15', limit=5000)
    df = calculate_all_technicals(df, normalize=False)
    
    # Prepare baseline features
    features = prepare_ml_features(df, include_ict=False)
    print(f"\nFeatures: {list(features.columns)}")
    print(f"Feature count: {len(features.columns)}")
    
    # Normalize
    features_norm = normalize_features(features, method='minmax', lookback=2000)
    
    # Create labels
    labels = create_labels(df, forward_bars=4)
    
    # Train classifier
    classifier = LorentzianClassifier(k=8, lookback=2000)
    predictions = classifier.predict_series(features_norm, labels, start_idx=2000)
    
    # Apply filters
    vol_filter = VolatilityFilter(min_percentile=20, max_percentile=80)
    regime_filter = RegimeFilter(ema_fast=50, ema_slow=200)
    adx_filter = ADXFilter(min_adx=20, max_adx=50)
    
    vol_mask = vol_filter.filter(df)
    regime_mask = regime_filter.filter(df)
    adx_mask = adx_filter.filter(df)
    combined_mask = combine_filters(vol_mask, regime_mask, adx_mask)
    
    # Backtest
    results = backtest_signals(df, predictions, combined_mask)
    
    return results, features_norm, labels


def test_ict_enhanced_model():
    """Test ICT-enhanced model (13 features)."""
    print("\n" + "="*60)
    print("ICT-ENHANCED MODEL (13 Features)")
    print("="*60)
    
    # Load data
    df = load_data('BTCUSD', '15', limit=5000)
    df = calculate_all_technicals(df, normalize=False)
    
    # Prepare ICT features
    features = prepare_ml_features(df, include_ict=True)
    print(f"\nFeatures: {list(features.columns)}")
    print(f"Feature count: {len(features.columns)}")
    
    # Normalize
    features_norm = normalize_features(features, method='minmax', lookback=2000)
    
    # Create labels
    labels = create_labels(df, forward_bars=4)
    
    # Train classifier
    classifier = LorentzianClassifier(k=8, lookback=2000)
    predictions = classifier.predict_series(features_norm, labels, start_idx=2000)
    
    # Apply filters
    vol_filter = VolatilityFilter(min_percentile=20, max_percentile=80)
    regime_filter = RegimeFilter(ema_fast=50, ema_slow=200)
    adx_filter = ADXFilter(min_adx=20, max_adx=50)
    
    vol_mask = vol_filter.filter(df)
    regime_mask = regime_filter.filter(df)
    adx_mask = adx_filter.filter(df)
    combined_mask = combine_filters(vol_mask, regime_mask, adx_mask)
    
    # Backtest
    results = backtest_signals(df, predictions, combined_mask)
    
    return results, features_norm, labels


def test_optimized_model():
    """Test optimized model (feature selection)."""
    print("\n" + "="*60)
    print("OPTIMIZED MODEL (Feature Selection)")
    print("="*60)
    
    # Load data
    df = load_data('BTCUSD', '15', limit=5000)
    df = calculate_all_technicals(df, normalize=False)
    
    # Prepare all features
    features_all = prepare_ml_features(df, include_ict=True)
    labels = create_labels(df, forward_bars=4)
    
    # Analyze correlations
    print("\n" + "-"*60)
    print("Feature Correlation Analysis")
    print("-"*60)
    
    analysis, redundant_pairs = analyze_feature_correlations(
        features_all.iloc[2000:], 
        labels.iloc[2000:],
        threshold=0.8
    )
    
    print("\nFeature importance (by label correlation):")
    print(analysis.to_string(index=False))
    
    if redundant_pairs:
        print(f"\nRedundant feature pairs (correlation > 0.8):")
        for pair in redundant_pairs:
            print(f"  {pair['feature1']} <-> {pair['feature2']}: {pair['correlation']:.3f}")
    else:
        print("\nNo highly redundant features found.")
    
    # Select optimal features
    optimal_features = select_optimal_features(
        features_all.iloc[2000:],
        labels.iloc[2000:],
        max_features=10,
        correlation_threshold=0.8
    )
    
    print(f"\nOptimal features selected: {optimal_features}")
    print(f"Feature count: {len(optimal_features)}")
    
    # Prepare optimized feature set
    features = features_all[optimal_features].copy()
    features_norm = normalize_features(features, method='minmax', lookback=2000)
    
    # Train classifier
    classifier = LorentzianClassifier(k=8, lookback=2000)
    predictions = classifier.predict_series(features_norm, labels, start_idx=2000)
    
    # Apply filters
    vol_filter = VolatilityFilter(min_percentile=20, max_percentile=80)
    regime_filter = RegimeFilter(ema_fast=50, ema_slow=200)
    adx_filter = ADXFilter(min_adx=20, max_adx=50)
    
    vol_mask = vol_filter.filter(df)
    regime_mask = regime_filter.filter(df)
    adx_mask = adx_filter.filter(df)
    combined_mask = combine_filters(vol_mask, regime_mask, adx_mask)
    
    # Backtest
    results = backtest_signals(df, predictions, combined_mask)
    
    return results, features_norm, labels, optimal_features


def backtest_signals(df, predictions, filter_mask):
    """Backtest ML signals."""
    # Align data
    df = df.reset_index()
    predictions = predictions.reset_index()
    filter_mask = filter_mask.reset_index(drop=True)
    
    df_test = df.iloc[-len(predictions):].copy().reset_index(drop=True)
    df_test['signal'] = predictions['signal'].values
    df_test['confidence'] = predictions['confidence'].values
    df_test['filter'] = filter_mask.iloc[-len(predictions):].values
    
    # Apply filter
    df_test['filtered_signal'] = df_test['signal'] * df_test['filter']
    
    # Calculate returns
    df_test['returns'] = df_test['close'].pct_change()
    df_test['strategy_returns'] = df_test['filtered_signal'].shift(1) * df_test['returns']
    
    # Calculate cumulative returns
    df_test['cum_returns'] = (1 + df_test['returns']).cumprod()
    df_test['cum_strategy'] = (1 + df_test['strategy_returns']).cumprod()
    
    # Calculate metrics
    total_return = (df_test['cum_strategy'].iloc[-1] - 1) * 100
    buy_hold_return = (df_test['cum_returns'].iloc[-1] - 1) * 100
    n_trades = (df_test['filtered_signal'].diff() != 0).sum()
    
    # Sharpe ratio
    sharpe = 0.0
    if df_test['strategy_returns'].std() > 0:
        sharpe = df_test['strategy_returns'].mean() / df_test['strategy_returns'].std() * np.sqrt(252 * 24 * 4)
    
    # Win rate
    winning_trades = df_test[df_test['strategy_returns'] > 0]
    win_rate = len(winning_trades) / n_trades * 100 if n_trades > 0 else 0
    
    results = {
        'total_return': total_return,
        'buy_hold_return': buy_hold_return,
        'outperformance': total_return - buy_hold_return,
        'n_trades': n_trades,
        'sharpe': sharpe,
        'win_rate': win_rate,
        'avg_confidence': df_test['confidence'].mean(),
        'df_test': df_test
    }
    
    print(f"\nBacktest Results:")
    print(f"  Total Return: {total_return:.2f}%")
    print(f"  Buy & Hold: {buy_hold_return:.2f}%")
    print(f"  Outperformance: {results['outperformance']:.2f}%")
    print(f"  Trades: {n_trades}")
    print(f"  Sharpe Ratio: {sharpe:.2f}")
    print(f"  Win Rate: {win_rate:.1f}%")
    print(f"  Avg Confidence: {results['avg_confidence']:.3f}")
    
    return results


def compare_models(baseline, ict_enhanced, optimized):
    """Compare model performance."""
    print("\n" + "="*60)
    print("MODEL COMPARISON")
    print("="*60)
    
    comparison = pd.DataFrame({
        'Model': ['Baseline (5)', 'ICT Enhanced (13)', 'Optimized (10)'],
        'Return %': [
            baseline['total_return'],
            ict_enhanced['total_return'],
            optimized['total_return']
        ],
        'Sharpe': [
            baseline['sharpe'],
            ict_enhanced['sharpe'],
            optimized['sharpe']
        ],
        'Trades': [
            baseline['n_trades'],
            ict_enhanced['n_trades'],
            optimized['n_trades']
        ],
        'Win Rate %': [
            baseline['win_rate'],
            ict_enhanced['win_rate'],
            optimized['win_rate']
        ],
        'Confidence': [
            baseline['avg_confidence'],
            ict_enhanced['avg_confidence'],
            optimized['avg_confidence']
        ]
    })
    
    print("\n" + comparison.to_string(index=False))
    
    # Calculate improvements
    print("\n" + "-"*60)
    print("Improvements vs Baseline:")
    print("-"*60)
    
    ict_improvement = ict_enhanced['total_return'] - baseline['total_return']
    opt_improvement = optimized['total_return'] - baseline['total_return']
    
    print(f"ICT Enhanced: {ict_improvement:+.2f}% return, {ict_enhanced['sharpe'] - baseline['sharpe']:+.2f} Sharpe")
    print(f"Optimized: {opt_improvement:+.2f}% return, {optimized['sharpe'] - baseline['sharpe']:+.2f} Sharpe")
    
    return comparison


def visualize_comparison(baseline, ict_enhanced, optimized):
    """Visualize model comparison."""
    print("\n" + "="*60)
    print("Generating Comparison Charts")
    print("="*60)
    
    plt.style.use('dark_background')
    fig, axes = plt.subplots(2, 2, figsize=(18, 12))
    
    # Plot 1: Cumulative returns
    ax1 = axes[0, 0]
    ax1.plot(baseline['df_test']['cum_strategy'], label='Baseline (5)', linewidth=2, alpha=0.8)
    ax1.plot(ict_enhanced['df_test']['cum_strategy'], label='ICT Enhanced (13)', linewidth=2, alpha=0.8)
    ax1.plot(optimized['df_test']['cum_strategy'], label='Optimized (10)', linewidth=2, alpha=0.8)
    ax1.plot(baseline['df_test']['cum_returns'], label='Buy & Hold', 
            linewidth=1.5, linestyle='--', alpha=0.5, color='gray')
    ax1.set_title('Cumulative Returns Comparison', fontsize=14, fontweight='bold')
    ax1.set_ylabel('Cumulative Return')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)
    
    # Plot 2: Performance metrics
    ax2 = axes[0, 1]
    models = ['Baseline\n(5)', 'ICT Enhanced\n(13)', 'Optimized\n(10)']
    returns = [baseline['total_return'], ict_enhanced['total_return'], optimized['total_return']]
    sharpes = [baseline['sharpe'], ict_enhanced['sharpe'], optimized['sharpe']]
    
    x = np.arange(len(models))
    width = 0.35
    
    bars1 = ax2.bar(x - width/2, returns, width, label='Return %', alpha=0.8)
    ax2_twin = ax2.twinx()
    bars2 = ax2_twin.bar(x + width/2, sharpes, width, label='Sharpe', alpha=0.8, color='orange')
    
    ax2.set_title('Performance Metrics', fontsize=14, fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(models)
    ax2.set_ylabel('Return %')
    ax2_twin.set_ylabel('Sharpe Ratio')
    ax2.legend(loc='upper left')
    ax2_twin.legend(loc='upper right')
    ax2.grid(True, alpha=0.3, axis='y')
    
    # Plot 3: Trade statistics
    ax3 = axes[1, 0]
    trades = [baseline['n_trades'], ict_enhanced['n_trades'], optimized['n_trades']]
    win_rates = [baseline['win_rate'], ict_enhanced['win_rate'], optimized['win_rate']]
    
    bars3 = ax3.bar(x - width/2, trades, width, label='Trades', alpha=0.8)
    ax3_twin = ax3.twinx()
    bars4 = ax3_twin.bar(x + width/2, win_rates, width, label='Win Rate %', alpha=0.8, color='green')
    
    ax3.set_title('Trade Statistics', fontsize=14, fontweight='bold')
    ax3.set_xticks(x)
    ax3.set_xticklabels(models)
    ax3.set_ylabel('Number of Trades')
    ax3_twin.set_ylabel('Win Rate %')
    ax3.legend(loc='upper left')
    ax3_twin.legend(loc='upper right')
    ax3.grid(True, alpha=0.3, axis='y')
    
    # Plot 4: Confidence levels
    ax4 = axes[1, 1]
    ax4.plot(baseline['df_test']['confidence'], label='Baseline', linewidth=1, alpha=0.7)
    ax4.plot(ict_enhanced['df_test']['confidence'], label='ICT Enhanced', linewidth=1, alpha=0.7)
    ax4.plot(optimized['df_test']['confidence'], label='Optimized', linewidth=1, alpha=0.7)
    ax4.axhline(y=0.5, color='yellow', linestyle='--', alpha=0.5)
    ax4.set_title('Prediction Confidence Over Time', fontsize=14, fontweight='bold')
    ax4.set_ylabel('Confidence')
    ax4.set_xlabel('Bar Index')
    ax4.legend(loc='upper left')
    ax4.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('data/ml_ict_comparison.png', dpi=150, bbox_inches='tight')
    print(f"\nChart saved to: data/ml_ict_comparison.png")
    plt.close()


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("ML ICT ENHANCEMENT VALIDATION")
    print("="*60)
    
    try:
        # Test 1: Baseline
        baseline, _, _ = test_baseline_model()
        
        # Test 2: ICT Enhanced
        ict_enhanced, _, _ = test_ict_enhanced_model()
        
        # Test 3: Optimized
        optimized, _, _, optimal_features = test_optimized_model()
        
        # Compare
        comparison = compare_models(baseline, ict_enhanced, optimized)
        
        # Visualize
        visualize_comparison(baseline, ict_enhanced, optimized)
        
        print("\n" + "="*60)
        print("ALL TESTS COMPLETED SUCCESSFULLY!")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
