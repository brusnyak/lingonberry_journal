"""
Lorentzian Distance and KNN Classification.

Lorentzian distance is more robust to outliers than Euclidean distance,
making it better for financial time series with fat-tailed distributions.
"""
import numpy as np
import pandas as pd
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class Prediction:
    """ML prediction result."""
    signal: int  # 1 for long, -1 for short, 0 for neutral
    confidence: float  # 0-1
    neighbors: List[int]  # Indices of nearest neighbors
    distances: List[float]  # Distances to neighbors


def lorentzian_distance(x1: np.ndarray, x2: np.ndarray) -> float:
    """
    Calculate Lorentzian distance between two feature vectors.
    
    Lorentzian distance: sum(log(1 + abs(x1 - x2)))
    
    More robust to outliers than Euclidean distance.
    Accounts for "price-time warping" from major market events.
    
    Args:
        x1: First feature vector
        x2: Second feature vector
    
    Returns:
        Lorentzian distance (lower = more similar)
    """
    return np.sum(np.log(1 + np.abs(x1 - x2)))


class LorentzianClassifier:
    """
    KNN classifier using Lorentzian distance.
    
    Based on TradingView's Lorentzian Classification implementation.
    Uses historical patterns to predict future price direction.
    """
    
    def __init__(self, k: int = 8, lookback: int = 2000):
        """
        Initialize classifier.
        
        Args:
            k: Number of nearest neighbors
            lookback: Historical bars to search
        """
        self.k = k
        self.lookback = lookback
        self.features_history = []
        self.labels_history = []
    
    def fit(self, features: np.ndarray, labels: np.ndarray):
        """
        Store historical features and labels.
        
        Args:
            features: Feature matrix (n_samples, n_features)
            labels: Labels (1 for up, -1 for down)
        """
        self.features_history = features
        self.labels_history = labels
    
    def predict(self, current_features: np.ndarray, 
                current_idx: int) -> Prediction:
        """
        Predict signal using KNN with Lorentzian distance.
        
        Args:
            current_features: Current feature vector
            current_idx: Current bar index
        
        Returns:
            Prediction object with signal and confidence
        """
        # Determine lookback window
        start_idx = max(0, current_idx - self.lookback)
        end_idx = current_idx
        
        if end_idx - start_idx < self.k:
            # Not enough history
            return Prediction(
                signal=0,
                confidence=0.0,
                neighbors=[],
                distances=[]
            )
        
        # Calculate distances to all historical points
        distances = []
        indices = []
        
        for i in range(start_idx, end_idx):
            dist = lorentzian_distance(
                current_features,
                self.features_history[i]
            )
            distances.append(dist)
            indices.append(i)
        
        # Find k nearest neighbors
        sorted_pairs = sorted(zip(distances, indices))
        k_nearest = sorted_pairs[:self.k]
        
        neighbor_distances = [d for d, _ in k_nearest]
        neighbor_indices = [i for _, i in k_nearest]
        
        # Get labels of nearest neighbors
        neighbor_labels = [self.labels_history[i] for i in neighbor_indices]
        
        # Vote: sum of labels weighted by inverse distance
        # Closer neighbors have more influence
        weights = [1.0 / (1.0 + d) for d in neighbor_distances]
        weighted_sum = sum(w * l for w, l in zip(weights, neighbor_labels))
        total_weight = sum(weights)
        
        # Normalize to get signal
        if total_weight > 0:
            vote = weighted_sum / total_weight
        else:
            vote = 0
        
        # Convert to signal (-1, 0, 1)
        if vote > 0.2:
            signal = 1  # Long
        elif vote < -0.2:
            signal = -1  # Short
        else:
            signal = 0  # Neutral
        
        # Confidence is based on agreement among neighbors
        confidence = abs(vote)
        
        return Prediction(
            signal=signal,
            confidence=confidence,
            neighbors=neighbor_indices,
            distances=neighbor_distances
        )
    
    def predict_series(self, features: pd.DataFrame, 
                      labels: pd.Series,
                      start_idx: int = None) -> pd.DataFrame:
        """
        Generate predictions for entire series.
        
        Args:
            features: Feature dataframe
            labels: True labels (for training)
            start_idx: Start prediction from this index
        
        Returns:
            DataFrame with predictions
        """
        if start_idx is None:
            start_idx = self.lookback
        
        # Convert to numpy
        features_np = features.values
        labels_np = labels.values
        
        # Store history
        self.fit(features_np, labels_np)
        
        # Generate predictions
        predictions = []
        
        for i in range(start_idx, len(features)):
            pred = self.predict(features_np[i], i)
            predictions.append({
                'signal': pred.signal,
                'confidence': pred.confidence,
                'n_neighbors': len(pred.neighbors)
            })
        
        # Create result dataframe
        result = pd.DataFrame(predictions, index=features.index[start_idx:])
        
        return result


def create_labels(df: pd.DataFrame, forward_bars: int = 4) -> pd.Series:
    """
    Create labels for training based on future price movement.
    
    Args:
        df: OHLC dataframe
        forward_bars: Bars to look ahead
    
    Returns:
        Series of labels (1 for up, -1 for down, 0 for neutral)
    """
    # Calculate future returns
    future_close = df['close'].shift(-forward_bars)
    returns = (future_close - df['close']) / df['close']
    
    # Create labels based on threshold
    threshold = 0.001  # 0.1% move
    
    labels = pd.Series(0, index=df.index)
    labels[returns > threshold] = 1  # Up
    labels[returns < -threshold] = -1  # Down
    
    return labels
