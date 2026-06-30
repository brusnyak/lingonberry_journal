"""
ML pipeline for direction classification (v2 — clean research foundation).

Level 3 entry point. Trains XGBoost classifiers on validated features from
features_v2, with proper time-series cross-validation.

Packages:
    crossval  — TimeSeriesSplit with purging and embargo
    train     — XGBoost training wrapper (graceful if xgboost not installed)
    evaluate  — Accuracy, feature importance, confusion matrix
"""
