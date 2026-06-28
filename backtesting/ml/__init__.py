"""
ML module for direction accuracy improvement.

Components:
    labels.py      — Triple-barrier labeling (3-class: HOLD/LONG/SHORT)
    features.py    — Causal feature matrix from structure_lib indicators
    train.py       — LightGBM+XGBoost+CatBoost ensemble, walk-forward CV
    predict.py     — Mlpredictor wrapper for live inference

Usage:
    from backtesting.ml import build_feature_matrix, walk_forward_train
    feat = build_feature_matrix("GBPAUD", "5", days=120)
    result = walk_forward_train(feat.values, labels, feat.columns)
"""

from backtesting.ml.labels import triple_barrier_labels, triple_barrier_labels_from_events, class_distribution
from backtesting.ml.features import build_feature_matrix, features_from_ohlc, feature_summary
from backtesting.ml.train import train_ensemble, walk_forward_train, run_pipeline
from backtesting.ml.predict import Mlpredictor, run_inference, OnlineFeatureExtractor

__all__ = [
    "triple_barrier_labels",
    "triple_barrier_labels_from_events",
    "class_distribution",
    "build_feature_matrix",
    "features_from_ohlc",
    "feature_summary",
    "train_ensemble",
    "walk_forward_train",
    "run_pipeline",
    "Mlpredictor",
    "OnlineFeatureExtractor",
    "run_inference",
]