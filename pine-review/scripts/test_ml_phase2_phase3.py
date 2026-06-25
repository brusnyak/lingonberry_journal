"""
Test ML Phase 2 (Online Learning) and Phase 3 (Walk-Forward Validation).
"""
import sys
sys.path.append('backend')

import pandas as pd
import numpy as np
from src.features.technicals import calculate_all_technicals
from src.ml.lorentzian import LorentzianClassifier, create_labels
from src.ml.features import prepare_ml_features, normalize_features
from src.ml.online_learning import OnlineLearningTracker
from src.ml.walk_forward import WalkForwardValidator, optimize_hyperparameters


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


def test_online_learning():
    """Test online learning tracker."""
    print("\n" + "="*60)
    print("PHASE 2: ONLINE LEARNING SYSTEM")
    print("="*60)
    
    # Initialize tracker
    tracker = OnlineLearningTracker(db_path='data/ml_learning.db')
    
    # Load data
    df = load_data('BTCUSD', '15', limit=3000)
    df = calculate_all_technicals(df, normalize=False)
    
    # Prepare features (use optimized set from Phase 1)
    features = prepare_ml_features(df, include_ict=True)
    features_norm = normalize_features(features, method='minmax', lookback=2000)
    labels = create_labels(df, forward_bars=4)
    
    # Train classifier
    classifier = LorentzianClassifier(k=8, lookback=2000)
    classifier.fit(features_norm.values, labels.values)
    
    print("\nSimulating online learning...")
    print("  Logging predictions and outcomes...")
    
    # Simulate online learning: predict and log
    prediction_ids = []
    for i in range(2000, len(features_norm)):
        # Make prediction
        pred = classifier.predict(features_norm.iloc[i].values, i)
        
        # Log prediction
        pred_id = tracker.log_prediction(
            timestamp=features_norm.index[i],
            symbol='BTCUSD',
            timeframe='15',
            bar_index=i,
            prediction=pred.signal,
            confidence=pred.confidence,
            features=features_norm.iloc[i].to_dict()
        )
        prediction_ids.append(pred_id)
        
        # Update with actual outcome (simulate waiting for next bar)
        if i < len(labels):
            tracker.update_outcome(pred_id, int(labels.iloc[i]))
        
        # Periodically calculate and log performance
        if i % 100 == 0 and i > 2000:
            metrics = tracker.calculate_performance_metrics('BTCUSD', '15', window_size=100)
            if metrics:
                tracker.log_performance_metrics(
                    timestamp=features_norm.index[i],
                    symbol='BTCUSD',
                    timeframe='15',
                    metrics=metrics
                )
                
                # Check if retraining needed
                should_retrain, reason = tracker.should_retrain('BTCUSD', '15', 
                                                                accuracy_threshold=0.6)
                if should_retrain:
                    print(f"\n  Bar {i}: Retraining recommended - {reason}")
    
    # Get statistics
    stats = tracker.get_statistics('BTCUSD', '15')
    print(f"\nOnline Learning Statistics:")
    print(f"  Total predictions: {stats['total_predictions']}")
    print(f"  Predictions with outcomes: {stats['predictions_with_outcomes']}")
    print(f"  Overall accuracy: {stats['overall_accuracy']:.2%}")
    print(f"  Coverage: {stats['coverage']:.2%}")
    
    # Get performance history
    perf_history = tracker.get_performance_history('BTCUSD', '15', limit=10)
    if len(perf_history) > 0:
        print(f"\nRecent Performance (last 10 windows):")
        print(f"  Mean accuracy: {perf_history['accuracy'].mean():.2%}")
        print(f"  Std accuracy: {perf_history['accuracy'].std():.2%}")
        print(f"  Mean precision (long): {perf_history['precision_long'].mean():.2%}")
        print(f"  Mean precision (short): {perf_history['precision_short'].mean():.2%}")
    
    return tracker, features_norm, labels


def test_walk_forward_validation():
    """Test walk-forward validation."""
    print("\n" + "="*60)
    print("PHASE 3: WALK-FORWARD VALIDATION")
    print("="*60)
    
    # Load data
    df = load_data('BTCUSD', '15', limit=5000)
    df = calculate_all_technicals(df, normalize=False)
    
    # Prepare features (use optimized set)
    features = prepare_ml_features(df, include_ict=True)
    features_norm = normalize_features(features, method='minmax', lookback=2000)
    labels = create_labels(df, forward_bars=4)
    
    # Initialize validator
    validator = WalkForwardValidator(
        train_size=2000,
        test_size=500,
        step_size=250
    )
    
    # Run validation
    results = validator.run_validation(
        features_norm,
        labels,
        k=8,
        lookback=2000,
        verbose=True
    )
    
    # Aggregate results
    print("\n" + "-"*60)
    print("Aggregated Results:")
    print("-"*60)
    
    aggregated = validator.aggregate_results(results)
    print(f"\nTotal windows: {aggregated['total_windows']}")
    print(f"Total predictions: {aggregated['total_predictions']}")
    print(f"\nAccuracy:")
    print(f"  Mean: {aggregated['mean_accuracy']:.2%}")
    print(f"  Std: {aggregated['std_accuracy']:.2%}")
    print(f"  Min: {aggregated['min_accuracy']:.2%}")
    print(f"  Max: {aggregated['max_accuracy']:.2%}")
    print(f"\nPrecision:")
    print(f"  Long: {aggregated['mean_precision_long']:.2%}")
    print(f"  Short: {aggregated['mean_precision_short']:.2%}")
    print(f"\nStability: {aggregated['stability']:.2%}")
    print(f"Avg Confidence: {aggregated['mean_confidence']:.3f}")
    
    # Plot results
    validator.plot_results(results, save_path='data/walk_forward_results.png')
    
    return results, aggregated


def test_hyperparameter_optimization():
    """Test hyperparameter optimization."""
    print("\n" + "="*60)
    print("HYPERPARAMETER OPTIMIZATION")
    print("="*60)
    
    # Load data
    df = load_data('BTCUSD', '15', limit=5000)
    df = calculate_all_technicals(df, normalize=False)
    
    # Prepare features
    features = prepare_ml_features(df, include_ict=True)
    features_norm = normalize_features(features, method='minmax', lookback=2000)
    labels = create_labels(df, forward_bars=4)
    
    # Define parameter grid
    param_grid = {
        'k': [5, 8, 10, 12, 15],
        'lookback': [1500, 2000, 2500]
    }
    
    print(f"\nParameter grid:")
    print(f"  k: {param_grid['k']}")
    print(f"  lookback: {param_grid['lookback']}")
    
    # Split data: train (2000), val (500), test (rest)
    train_start = 0
    train_end = 2000
    val_start = 2000
    val_end = 2500
    
    print(f"\nOptimizing on validation set...")
    best_params = optimize_hyperparameters(
        features_norm,
        labels,
        param_grid,
        train_start,
        train_end,
        val_start,
        val_end
    )
    
    print(f"\nBest parameters:")
    print(f"  k: {best_params['k']}")
    print(f"  lookback: {best_params['lookback']}")
    print(f"  Validation accuracy: {best_params['accuracy']:.2%}")
    
    # Test on holdout set
    test_start = 2500
    test_end = len(features_norm)
    
    print(f"\nTesting on holdout set ({test_end - test_start} bars)...")
    
    classifier = LorentzianClassifier(
        k=best_params['k'],
        lookback=best_params['lookback']
    )
    
    train_features = features_norm.iloc[train_start:val_end]
    train_labels = labels.iloc[train_start:val_end]
    classifier.fit(train_features.values, train_labels.values)
    
    test_features = features_norm.iloc[test_start:test_end]
    test_labels = labels.iloc[test_start:test_end]
    
    correct = 0
    for i in range(len(test_features)):
        # Use relative index within combined train+val data
        relative_idx = len(train_features) - 1
        pred = classifier.predict(test_features.iloc[i].values, relative_idx)
        if pred.signal == test_labels.iloc[i]:
            correct += 1
    
    test_accuracy = correct / len(test_features) if len(test_features) > 0 else 0
    
    print(f"  Test accuracy: {test_accuracy:.2%}")
    
    return best_params, test_accuracy


def main():
    """Run all Phase 2 and Phase 3 tests."""
    print("\n" + "="*60)
    print("ML PHASE 2 & 3 VALIDATION")
    print("="*60)
    
    try:
        # Phase 2: Online Learning
        tracker, features, labels = test_online_learning()
        
        # Phase 3: Walk-Forward Validation
        wf_results, wf_aggregated = test_walk_forward_validation()
        
        # Hyperparameter Optimization
        best_params, test_accuracy = test_hyperparameter_optimization()
        
        # Summary
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        
        print("\nPhase 2 - Online Learning:")
        stats = tracker.get_statistics('BTCUSD', '15')
        print(f"  ✅ Tracked {stats['total_predictions']} predictions")
        print(f"  ✅ Overall accuracy: {stats['overall_accuracy']:.2%}")
        print(f"  ✅ Database: data/ml_learning.db")
        
        print("\nPhase 3 - Walk-Forward Validation:")
        print(f"  ✅ Validated {wf_aggregated['total_windows']} windows")
        print(f"  ✅ Mean accuracy: {wf_aggregated['mean_accuracy']:.2%}")
        print(f"  ✅ Stability: {wf_aggregated['stability']:.2%}")
        
        print("\nHyperparameter Optimization:")
        print(f"  ✅ Best k: {best_params['k']}")
        print(f"  ✅ Best lookback: {best_params['lookback']}")
        print(f"  ✅ Test accuracy: {test_accuracy:.2%}")
        
        print("\n" + "="*60)
        print("ALL TESTS COMPLETED SUCCESSFULLY!")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
