"""
Walk-forward validation for ML models.
Implements rolling window optimization and out-of-sample testing.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from .lorentzian import LorentzianClassifier, create_labels
from .features import normalize_features


@dataclass
class WalkForwardWindow:
    """Represents a walk-forward validation window."""
    train_start: int
    train_end: int
    test_start: int
    test_end: int
    window_id: int


@dataclass
class WalkForwardResult:
    """Results from a walk-forward window."""
    window_id: int
    train_period: Tuple[int, int]
    test_period: Tuple[int, int]
    predictions: pd.DataFrame
    metrics: Dict
    best_params: Dict = None


class WalkForwardValidator:
    """
    Walk-forward validation for time series ML models.
    
    Splits data into rolling windows:
    - Train on historical data
    - Test on out-of-sample future data
    - Roll forward and repeat
    
    This prevents look-ahead bias and tests model robustness.
    """
    
    def __init__(self, train_size: int = 2000, test_size: int = 500,
                 step_size: int = 250):
        """
        Initialize walk-forward validator.
        
        Args:
            train_size: Size of training window
            test_size: Size of test window
            step_size: Step size for rolling forward
        """
        self.train_size = train_size
        self.test_size = test_size
        self.step_size = step_size
    
    def create_windows(self, data_length: int) -> List[WalkForwardWindow]:
        """
        Create walk-forward windows.
        
        Args:
            data_length: Total length of dataset
        
        Returns:
            List of WalkForwardWindow objects
        """
        windows = []
        window_id = 0
        
        # Start with first full training window
        train_start = 0
        
        while True:
            train_end = train_start + self.train_size
            test_start = train_end
            test_end = test_start + self.test_size
            
            # Check if we have enough data
            if test_end > data_length:
                break
            
            windows.append(WalkForwardWindow(
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
                window_id=window_id
            ))
            
            window_id += 1
            train_start += self.step_size
        
        return windows
    
    def validate_window(self, features: pd.DataFrame, labels: pd.Series,
                       window: WalkForwardWindow,
                       k: int = 8, lookback: int = 2000) -> WalkForwardResult:
        """
        Validate a single walk-forward window.
        
        Args:
            features: Feature dataframe
            labels: Label series
            window: WalkForwardWindow object
            k: Number of neighbors for KNN
            lookback: Lookback for Lorentzian classifier
        
        Returns:
            WalkForwardResult object
        """
        # Split data
        train_features = features.iloc[window.train_start:window.train_end]
        train_labels = labels.iloc[window.train_start:window.train_end]
        test_features = features.iloc[window.test_start:window.test_end]
        test_labels = labels.iloc[window.test_start:window.test_end]
        
        # Train classifier
        classifier = LorentzianClassifier(k=k, lookback=lookback)
        classifier.fit(train_features.values, train_labels.values)
        
        # Generate predictions for test period
        predictions = []
        for i in range(len(test_features)):
            # Use relative index within training data
            relative_idx = len(train_features) - 1  # Use last training index as reference
            pred = classifier.predict(test_features.iloc[i].values, relative_idx)
            predictions.append({
                'signal': pred.signal,
                'confidence': pred.confidence,
                'actual': test_labels.iloc[i]
            })
        
        pred_df = pd.DataFrame(predictions, index=test_features.index)
        
        # Calculate metrics
        metrics = self._calculate_metrics(pred_df)
        
        return WalkForwardResult(
            window_id=window.window_id,
            train_period=(window.train_start, window.train_end),
            test_period=(window.test_start, window.test_end),
            predictions=pred_df,
            metrics=metrics
        )
    
    def _calculate_metrics(self, predictions: pd.DataFrame) -> Dict:
        """
        Calculate performance metrics for predictions.
        
        Args:
            predictions: DataFrame with 'signal', 'confidence', 'actual' columns
        
        Returns:
            Dict of metrics
        """
        # Accuracy
        correct = (predictions['signal'] == predictions['actual']).sum()
        accuracy = correct / len(predictions) if len(predictions) > 0 else 0
        
        # Precision/Recall for long/short
        long_preds = predictions[predictions['signal'] == 1]
        short_preds = predictions[predictions['signal'] == -1]
        
        precision_long = ((long_preds['signal'] == long_preds['actual']).sum() / 
                         len(long_preds)) if len(long_preds) > 0 else 0
        precision_short = ((short_preds['signal'] == short_preds['actual']).sum() / 
                          len(short_preds)) if len(short_preds) > 0 else 0
        
        # Signal distribution
        signal_dist = predictions['signal'].value_counts().to_dict()
        
        return {
            'accuracy': accuracy,
            'precision_long': precision_long,
            'precision_short': precision_short,
            'total_predictions': len(predictions),
            'long_signals': signal_dist.get(1, 0),
            'short_signals': signal_dist.get(-1, 0),
            'neutral_signals': signal_dist.get(0, 0),
            'avg_confidence': predictions['confidence'].mean()
        }
    
    def run_validation(self, features: pd.DataFrame, labels: pd.Series,
                      k: int = 8, lookback: int = 2000,
                      verbose: bool = True) -> List[WalkForwardResult]:
        """
        Run complete walk-forward validation.
        
        Args:
            features: Feature dataframe
            labels: Label series
            k: Number of neighbors for KNN
            lookback: Lookback for Lorentzian classifier
            verbose: Print progress
        
        Returns:
            List of WalkForwardResult objects
        """
        # Create windows
        windows = self.create_windows(len(features))
        
        if verbose:
            print(f"\nWalk-Forward Validation:")
            print(f"  Total windows: {len(windows)}")
            print(f"  Train size: {self.train_size}")
            print(f"  Test size: {self.test_size}")
            print(f"  Step size: {self.step_size}")
        
        # Validate each window
        results = []
        for i, window in enumerate(windows):
            if verbose:
                print(f"\n  Window {i+1}/{len(windows)}:")
                print(f"    Train: {window.train_start} - {window.train_end}")
                print(f"    Test: {window.test_start} - {window.test_end}")
            
            result = self.validate_window(features, labels, window, k, lookback)
            results.append(result)
            
            if verbose:
                print(f"    Accuracy: {result.metrics['accuracy']:.2%}")
                print(f"    Signals: {result.metrics['long_signals']}L / "
                      f"{result.metrics['short_signals']}S / "
                      f"{result.metrics['neutral_signals']}N")
        
        return results
    
    def aggregate_results(self, results: List[WalkForwardResult]) -> Dict:
        """
        Aggregate results across all windows.
        
        Args:
            results: List of WalkForwardResult objects
        
        Returns:
            Dict of aggregated metrics
        """
        if not results:
            return {}
        
        # Aggregate metrics
        accuracies = [r.metrics['accuracy'] for r in results]
        precision_longs = [r.metrics['precision_long'] for r in results]
        precision_shorts = [r.metrics['precision_short'] for r in results]
        confidences = [r.metrics['avg_confidence'] for r in results]
        
        # Calculate stability (std of accuracy across windows)
        stability = 1.0 - np.std(accuracies)
        
        aggregated = {
            'mean_accuracy': np.mean(accuracies),
            'std_accuracy': np.std(accuracies),
            'min_accuracy': np.min(accuracies),
            'max_accuracy': np.max(accuracies),
            'mean_precision_long': np.mean(precision_longs),
            'mean_precision_short': np.mean(precision_shorts),
            'mean_confidence': np.mean(confidences),
            'stability': stability,
            'total_windows': len(results),
            'total_predictions': sum(r.metrics['total_predictions'] for r in results)
        }
        
        return aggregated
    
    def plot_results(self, results: List[WalkForwardResult], 
                    save_path: str = 'data/walk_forward_results.png'):
        """
        Plot walk-forward validation results.
        
        Args:
            results: List of WalkForwardResult objects
            save_path: Path to save plot
        """
        import matplotlib.pyplot as plt
        
        if not results:
            return
        
        # Extract metrics
        window_ids = [r.window_id for r in results]
        accuracies = [r.metrics['accuracy'] for r in results]
        precision_longs = [r.metrics['precision_long'] for r in results]
        precision_shorts = [r.metrics['precision_short'] for r in results]
        confidences = [r.metrics['avg_confidence'] for r in results]
        
        # Create plot
        plt.style.use('dark_background')
        fig, axes = plt.subplots(2, 2, figsize=(16, 10))
        
        # Plot 1: Accuracy over windows
        ax1 = axes[0, 0]
        ax1.plot(window_ids, accuracies, marker='o', linewidth=2, markersize=6)
        ax1.axhline(y=np.mean(accuracies), color='yellow', linestyle='--', 
                   label=f'Mean: {np.mean(accuracies):.2%}')
        ax1.set_title('Accuracy Across Windows', fontsize=14, fontweight='bold')
        ax1.set_xlabel('Window ID')
        ax1.set_ylabel('Accuracy')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Plot 2: Precision (Long vs Short)
        ax2 = axes[0, 1]
        ax2.plot(window_ids, precision_longs, marker='o', label='Long', linewidth=2)
        ax2.plot(window_ids, precision_shorts, marker='s', label='Short', linewidth=2)
        ax2.set_title('Precision by Direction', fontsize=14, fontweight='bold')
        ax2.set_xlabel('Window ID')
        ax2.set_ylabel('Precision')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        # Plot 3: Confidence over windows
        ax3 = axes[1, 0]
        ax3.plot(window_ids, confidences, marker='o', color='cyan', linewidth=2)
        ax3.axhline(y=np.mean(confidences), color='yellow', linestyle='--',
                   label=f'Mean: {np.mean(confidences):.3f}')
        ax3.set_title('Average Confidence', fontsize=14, fontweight='bold')
        ax3.set_xlabel('Window ID')
        ax3.set_ylabel('Confidence')
        ax3.legend()
        ax3.grid(True, alpha=0.3)
        
        # Plot 4: Summary statistics
        ax4 = axes[1, 1]
        ax4.axis('off')
        
        aggregated = self.aggregate_results(results)
        summary_text = f"""
        Walk-Forward Validation Summary
        
        Total Windows: {aggregated['total_windows']}
        Total Predictions: {aggregated['total_predictions']}
        
        Accuracy:
          Mean: {aggregated['mean_accuracy']:.2%}
          Std: {aggregated['std_accuracy']:.2%}
          Min: {aggregated['min_accuracy']:.2%}
          Max: {aggregated['max_accuracy']:.2%}
        
        Precision:
          Long: {aggregated['mean_precision_long']:.2%}
          Short: {aggregated['mean_precision_short']:.2%}
        
        Stability: {aggregated['stability']:.2%}
        Avg Confidence: {aggregated['mean_confidence']:.3f}
        """
        
        ax4.text(0.1, 0.5, summary_text, fontsize=12, family='monospace',
                verticalalignment='center')
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"\nPlot saved to: {save_path}")
        plt.close()


def optimize_hyperparameters(features: pd.DataFrame, labels: pd.Series,
                            param_grid: Dict[str, List],
                            train_start: int, train_end: int,
                            val_start: int, val_end: int) -> Dict:
    """
    Optimize hyperparameters on validation set.
    
    Args:
        features: Feature dataframe
        labels: Label series
        param_grid: Dict of parameter names to lists of values
        train_start: Training start index
        train_end: Training end index
        val_start: Validation start index
        val_end: Validation end index
    
    Returns:
        Dict of best parameters
    """
    best_accuracy = 0
    best_params = {}
    
    # Grid search
    k_values = param_grid.get('k', [8])
    lookback_values = param_grid.get('lookback', [2000])
    
    for k in k_values:
        for lookback in lookback_values:
            # Train
            train_features = features.iloc[train_start:train_end]
            train_labels = labels.iloc[train_start:train_end]
            
            classifier = LorentzianClassifier(k=k, lookback=lookback)
            classifier.fit(train_features.values, train_labels.values)
            
            # Validate
            val_features = features.iloc[val_start:val_end]
            val_labels = labels.iloc[val_start:val_end]
            
            correct = 0
            for i in range(len(val_features)):
                # Use relative index within training data
                relative_idx = len(train_features) - 1
                pred = classifier.predict(val_features.iloc[i].values, relative_idx)
                if pred.signal == val_labels.iloc[i]:
                    correct += 1
            
            accuracy = correct / len(val_features) if len(val_features) > 0 else 0
            
            if accuracy > best_accuracy:
                best_accuracy = accuracy
                best_params = {'k': k, 'lookback': lookback, 'accuracy': accuracy}
    
    return best_params
