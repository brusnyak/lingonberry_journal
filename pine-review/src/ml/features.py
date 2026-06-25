"""
Feature engineering for ML models.
Prepares and normalizes features for Lorentzian Classification.
"""
import pandas as pd
import numpy as np
from typing import List, Optional
from .ict_features import add_ict_features_to_dataframe


def prepare_ml_features(df: pd.DataFrame, 
                       feature_cols: Optional[List[str]] = None,
                       include_ict: bool = False) -> pd.DataFrame:
    """
    Prepare features for ML model.
    
    Default features (from orig.pine Lorentzian):
    - RSI (14)
    - Wave Trend 1 (WT1)
    - Wave Trend 2 (WT2)
    - CCI (20)
    - ADX (14)
    
    ICT features (if include_ict=True):
    - dist_bull_ob: Distance to nearest bullish Order Block
    - dist_bear_ob: Distance to nearest bearish Order Block
    - dist_bull_fvg: Distance to nearest bullish FVG
    - dist_bear_fvg: Distance to nearest bearish FVG
    - dist_liquidity: Distance to nearest liquidity level
    - premium_discount: Premium/Discount zone indicator (-1 to +1)
    - structure_momentum: Recent structure break momentum (0-1)
    - confluence_score: Market structure confluence (0-10)
    
    Args:
        df: Dataframe with technical indicators
        feature_cols: List of feature column names (None = use defaults)
        include_ict: Whether to add ICT-based features
    
    Returns:
        DataFrame with selected features
    """
    # Add ICT features if requested
    if include_ict:
        print("Calculating ICT features...")
        df = add_ict_features_to_dataframe(df, swing_period=5)
    
    if feature_cols is None:
        # Default features from Lorentzian Classification
        feature_cols = ['rsi', 'wt1', 'wt2', 'cci', 'adx']
        
        # Add ICT features to default set
        if include_ict:
            ict_cols = [
                'dist_bull_ob', 'dist_bear_ob',
                'dist_bull_fvg', 'dist_bear_fvg',
                'dist_liquidity', 'premium_discount',
                'structure_momentum', 'confluence_score'
            ]
            feature_cols = feature_cols + ict_cols
    
    # Select features
    features = df[feature_cols].copy()
    
    # Handle missing values
    features = features.ffill().bfill()
    
    return features


def normalize_features(features: pd.DataFrame, 
                      method: str = 'minmax',
                      lookback: int = 2000) -> pd.DataFrame:
    """
    Normalize features for ML model.
    
    Args:
        features: Feature dataframe
        method: Normalization method ('minmax', 'zscore', 'none')
        lookback: Rolling window for normalization
    
    Returns:
        Normalized feature dataframe
    """
    if method == 'none':
        return features
    
    normalized = features.copy()
    
    if method == 'minmax':
        # Min-max normalization to [0, 1]
        for col in features.columns:
            rolling_min = features[col].rolling(lookback, min_periods=1).min()
            rolling_max = features[col].rolling(lookback, min_periods=1).max()
            
            # Avoid division by zero
            range_val = rolling_max - rolling_min
            range_val = range_val.replace(0, 1)
            
            normalized[col] = (features[col] - rolling_min) / range_val
    
    elif method == 'zscore':
        # Z-score normalization
        for col in features.columns:
            rolling_mean = features[col].rolling(lookback, min_periods=1).mean()
            rolling_std = features[col].rolling(lookback, min_periods=1).std()
            
            # Avoid division by zero
            rolling_std = rolling_std.replace(0, 1)
            
            normalized[col] = (features[col] - rolling_mean) / rolling_std
    
    return normalized


def add_custom_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add custom features from market structure.
    
    Args:
        df: Dataframe with OHLC and indicators
    
    Returns:
        DataFrame with additional features
    """
    df = df.copy()
    
    # Price momentum features
    df['returns_1'] = df['close'].pct_change(1)
    df['returns_5'] = df['close'].pct_change(5)
    df['returns_10'] = df['close'].pct_change(10)
    
    # Volatility features
    df['volatility_10'] = df['returns_1'].rolling(10).std()
    df['volatility_20'] = df['returns_1'].rolling(20).std()
    
    # Volume features
    if 'volume' in df.columns and df['volume'].std() > 0:
        df['volume_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
        df['volume_delta_ratio'] = df.get('volume_delta', 0) / df['volume']
    
    # Range features
    df['range'] = (df['high'] - df['low']) / df['close']
    df['body'] = abs(df['close'] - df['open']) / df['close']
    
    return df


def select_best_features(df: pd.DataFrame, 
                        labels: pd.Series,
                        n_features: int = 5) -> List[str]:
    """
    Select best features using correlation with labels.
    
    Args:
        df: Feature dataframe
        labels: Target labels
        n_features: Number of features to select
    
    Returns:
        List of best feature names
    """
    # Calculate correlation with labels
    correlations = {}
    
    for col in df.columns:
        if df[col].dtype in [np.float64, np.int64]:
            corr = abs(df[col].corr(labels))
            if not np.isnan(corr):
                correlations[col] = corr
    
    # Sort by correlation
    sorted_features = sorted(correlations.items(), 
                           key=lambda x: x[1], 
                           reverse=True)
    
    # Return top n features
    return [f for f, _ in sorted_features[:n_features]]



def analyze_feature_correlations(features: pd.DataFrame, 
                                 labels: pd.Series,
                                 threshold: float = 0.8) -> pd.DataFrame:
    """
    Analyze feature correlations to identify redundant features.
    
    Args:
        features: Feature dataframe
        labels: Target labels
        threshold: Correlation threshold for redundancy (default 0.8)
    
    Returns:
        DataFrame with correlation analysis
    """
    # Calculate correlation matrix
    corr_matrix = features.corr().abs()
    
    # Calculate correlation with labels
    label_corr = {}
    for col in features.columns:
        if features[col].dtype in [np.float64, np.int64]:
            corr = abs(features[col].corr(labels))
            if not np.isnan(corr):
                label_corr[col] = corr
    
    # Find highly correlated feature pairs
    redundant_pairs = []
    for i in range(len(corr_matrix.columns)):
        for j in range(i+1, len(corr_matrix.columns)):
            if corr_matrix.iloc[i, j] > threshold:
                feat1 = corr_matrix.columns[i]
                feat2 = corr_matrix.columns[j]
                redundant_pairs.append({
                    'feature1': feat1,
                    'feature2': feat2,
                    'correlation': corr_matrix.iloc[i, j],
                    'feat1_label_corr': label_corr.get(feat1, 0),
                    'feat2_label_corr': label_corr.get(feat2, 0)
                })
    
    # Create analysis dataframe
    analysis = pd.DataFrame({
        'feature': list(label_corr.keys()),
        'label_correlation': list(label_corr.values())
    }).sort_values('label_correlation', ascending=False)
    
    return analysis, redundant_pairs


def select_optimal_features(features: pd.DataFrame,
                           labels: pd.Series,
                           max_features: int = 13,
                           correlation_threshold: float = 0.8) -> List[str]:
    """
    Select optimal feature set by removing redundant features.
    
    Strategy:
    1. Calculate correlation with labels
    2. Remove features with high inter-correlation (keep one with higher label correlation)
    3. Keep top N features by label correlation
    
    Args:
        features: Feature dataframe
        labels: Target labels
        max_features: Maximum number of features to keep
        correlation_threshold: Threshold for feature redundancy
    
    Returns:
        List of selected feature names
    """
    analysis, redundant_pairs = analyze_feature_correlations(
        features, labels, correlation_threshold
    )
    
    # Start with all features
    selected = set(features.columns)
    
    # Remove redundant features (keep one with higher label correlation)
    for pair in redundant_pairs:
        feat1 = pair['feature1']
        feat2 = pair['feature2']
        
        if feat1 in selected and feat2 in selected:
            # Remove the one with lower label correlation
            if pair['feat1_label_corr'] >= pair['feat2_label_corr']:
                selected.remove(feat2)
            else:
                selected.remove(feat1)
    
    # Sort by label correlation and keep top N
    selected_analysis = analysis[analysis['feature'].isin(selected)]
    top_features = selected_analysis.head(max_features)['feature'].tolist()
    
    return top_features
