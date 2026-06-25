"""
Test script for ML module (Lorentzian Classification).
"""
import sys
sys.path.append('backend')

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from src.features.technicals import calculate_all_technicals
from src.ml.lorentzian import LorentzianClassifier, create_labels
from src.ml.features import prepare_ml_features, normalize_features
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


def test_lorentzian_classifier():
    """Test Lorentzian Classification."""
    print("\n" + "="*60)
    print("Testing Lorentzian Classification")
    print("="*60)
    
    # Load data
    df = load_data('BTCUSD', '15', limit=5000)
    
    # Calculate indicators
    df = calculate_all_technicals(df, normalize=False)
    
    # Prepare features
    features = prepare_ml_features(df)
    print(f"\nFeatures: {list(features.columns)}")
    print(f"Feature shape: {features.shape}")
    
    # Normalize features
    features_norm = normalize_features(features, method='minmax', lookback=2000)
    print(f"\nNormalized features (sample):")
    print(features_norm.tail())
    
    # Create labels (future price direction)
    labels = create_labels(df, forward_bars=4)
    print(f"\nLabels distribution:")
    print(f"  Long (1): {(labels == 1).sum()}")
    print(f"  Short (-1): {(labels == -1).sum()}")
    print(f"  Neutral (0): {(labels == 0).sum()}")
    
    # Initialize classifier
    classifier = LorentzianClassifier(k=8, lookback=2000)
    
    # Generate predictions
    print(f"\nGenerating predictions...")
    predictions = classifier.predict_series(features_norm, labels, start_idx=2000)
    
    print(f"\nPredictions shape: {predictions.shape}")
    print(f"\nPrediction distribution:")
    print(f"  Long (1): {(predictions['signal'] == 1).sum()}")
    print(f"  Short (-1): {(predictions['signal'] == -1).sum()}")
    print(f"  Neutral (0): {(predictions['signal'] == 0).sum()}")
    
    print(f"\nAverage confidence: {predictions['confidence'].mean():.3f}")
    print(f"\nSample predictions (last 10):")
    print(predictions.tail(10))
    
    return df, features_norm, labels, predictions


def test_filters():
    """Test signal filters."""
    print("\n" + "="*60)
    print("Testing Signal Filters")
    print("="*60)
    
    # Load data
    df = load_data('BTCUSD', '15', limit=5000)
    df = calculate_all_technicals(df, normalize=False)
    
    # Test volatility filter
    vol_filter = VolatilityFilter(min_percentile=20, max_percentile=80)
    vol_mask = vol_filter.filter(df)
    print(f"\nVolatility Filter:")
    print(f"  Pass rate: {vol_mask.sum() / len(vol_mask) * 100:.1f}%")
    
    # Test regime filter
    regime_filter = RegimeFilter(ema_fast=50, ema_slow=200)
    regime_mask = regime_filter.filter(df)
    print(f"\nRegime Filter:")
    print(f"  Pass rate: {regime_mask.sum() / len(regime_mask) * 100:.1f}%")
    
    # Test ADX filter
    adx_filter = ADXFilter(min_adx=20, max_adx=50)
    adx_mask = adx_filter.filter(df)
    print(f"\nADX Filter:")
    print(f"  Pass rate: {adx_mask.sum() / len(adx_mask) * 100:.1f}%")
    
    # Combine filters
    combined_mask = combine_filters(vol_mask, regime_mask, adx_mask)
    print(f"\nCombined Filters:")
    print(f"  Pass rate: {combined_mask.sum() / len(combined_mask) * 100:.1f}%")
    
    return df, combined_mask


def test_backtest_ml_signals(df, predictions, filter_mask):
    """Simple backtest of ML signals."""
    print("\n" + "="*60)
    print("Backtesting ML Signals")
    print("="*60)
    
    # Reset index to avoid duplicates
    df = df.reset_index()
    predictions = predictions.reset_index()
    filter_mask = filter_mask.reset_index(drop=True)
    
    # Align predictions with df by finding matching indices
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
    
    print(f"\nBacktest Results:")
    print(f"  Total Return: {total_return:.2f}%")
    print(f"  Buy & Hold: {buy_hold_return:.2f}%")
    print(f"  Outperformance: {total_return - buy_hold_return:.2f}%")
    print(f"  Number of Trades: {n_trades}")
    
    # Calculate Sharpe ratio
    if df_test['strategy_returns'].std() > 0:
        sharpe = df_test['strategy_returns'].mean() / df_test['strategy_returns'].std() * np.sqrt(252 * 24 * 4)  # 15min bars
        print(f"  Sharpe Ratio: {sharpe:.2f}")
    
    return df_test


def visualize_results(df_test):
    """Visualize ML predictions and performance."""
    print("\n" + "="*60)
    print("Generating Visualizations")
    print("="*60)
    
    # Set dark theme
    plt.style.use('dark_background')
    
    fig, axes = plt.subplots(3, 1, figsize=(16, 12))
    
    # Use numeric index for plotting
    x_axis = range(len(df_test))
    
    # Plot 1: Price with signals
    ax1 = axes[0]
    ax1.plot(x_axis, df_test['close'], label='Price', linewidth=1, alpha=0.7)
    
    # Mark long signals
    long_signals = df_test[df_test['filtered_signal'] == 1]
    long_idx = long_signals.index.tolist()
    ax1.scatter(long_idx, long_signals['close'], 
               color='green', marker='^', s=50, label='Long', alpha=0.7)
    
    # Mark short signals
    short_signals = df_test[df_test['filtered_signal'] == -1]
    short_idx = short_signals.index.tolist()
    ax1.scatter(short_idx, short_signals['close'], 
               color='red', marker='v', s=50, label='Short', alpha=0.7)
    
    ax1.set_title('ML Signals on Price Chart', fontsize=14, fontweight='bold')
    ax1.set_ylabel('Price')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)
    
    # Plot 2: Confidence
    ax2 = axes[1]
    ax2.plot(x_axis, df_test['confidence'], label='Confidence', 
            color='cyan', linewidth=1)
    ax2.axhline(y=0.5, color='yellow', linestyle='--', alpha=0.5, label='Threshold')
    ax2.set_title('Prediction Confidence', fontsize=14, fontweight='bold')
    ax2.set_ylabel('Confidence')
    ax2.legend(loc='upper left')
    ax2.grid(True, alpha=0.3)
    
    # Plot 3: Cumulative returns
    ax3 = axes[2]
    ax3.plot(x_axis, df_test['cum_returns'], 
            label='Buy & Hold', linewidth=1.5, alpha=0.7)
    ax3.plot(x_axis, df_test['cum_strategy'], 
            label='ML Strategy', linewidth=1.5, alpha=0.7)
    ax3.set_title('Cumulative Returns', fontsize=14, fontweight='bold')
    ax3.set_ylabel('Cumulative Return')
    ax3.set_xlabel('Bar Index')
    ax3.legend(loc='upper left')
    ax3.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('data/test_ml_predictions.png', dpi=150, bbox_inches='tight')
    print(f"\nChart saved to: data/test_ml_predictions.png")
    plt.close()


def main():
    """Run all ML tests."""
    print("\n" + "="*60)
    print("ML MODULE VALIDATION")
    print("="*60)
    
    try:
        # Test 1: Lorentzian classifier
        df, features, labels, predictions = test_lorentzian_classifier()
        
        # Test 2: Filters
        df_full, filter_mask = test_filters()
        
        # Test 3: Backtest
        df_test = test_backtest_ml_signals(df_full, predictions, filter_mask)
        
        # Test 4: Visualization
        visualize_results(df_test)
        
        print("\n" + "="*60)
        print("ALL ML TESTS COMPLETED SUCCESSFULLY!")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
