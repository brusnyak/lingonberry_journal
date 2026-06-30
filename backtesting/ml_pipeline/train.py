"""
XGBoost training wrapper for direction classification.

Gracefully handles missing xgboost installation — raises ImportError at
call time, not import time, so the rest of the package is usable without it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

try:
    import xgboost as xgb

    _XGBOOST_AVAILABLE = True
except ImportError:
    _XGBOOST_AVAILABLE = False
    xgb = None  # type: ignore


@dataclass
class TrainResult:
    """Trained model + metadata."""

    model: Any | None = None  # xgb.Booster or xgb.XGBClassifier
    accuracy: float = 0.0
    n_features: int = 0
    n_train: int = 0
    n_test: int = 0
    feature_names: list[str] = field(default_factory=list)
    feature_importance: dict[str, float] = field(default_factory=dict)


def train_xgb(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    feature_names: list[str] | None = None,
    params: dict[str, Any] | None = None,
) -> TrainResult:
    """
    Train an XGBoost classifier for direction prediction.

    Args:
        X_train: feature matrix (n_samples, n_features)
        y_train: labels (0 or 1)
        X_test: test feature matrix
        y_test: test labels
        feature_names: optional column names for feature importance
        params: xgboost parameters (defaults tuned for small feature sets)

    Returns:
        TrainResult with model, accuracy, feature importance
    """
    if not _XGBOOST_AVAILABLE:
        raise ImportError(
            "xgboost is not installed. Run: pip install xgboost"
        )

    default_params = {
        "objective": "binary:logistic",
        "eval_metric": "logloss",
        "max_depth": 4,
        "learning_rate": 0.1,
        "n_estimators": 200,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "seed": 42,
    }
    if params:
        default_params.update(params)

    model = xgb.XGBClassifier(**default_params)
    model.fit(
        X_train,
        y_train,
        eval_set=[(X_test, y_test)],
        verbose=False,
    )

    y_pred = model.predict(X_test)
    accuracy = float(np.mean(y_pred == y_test))

    fi = {}
    if feature_names and hasattr(model, "feature_importances_"):
        fi = dict(zip(feature_names, map(float, model.feature_importances_)))

    return TrainResult(
        model=model,
        accuracy=round(accuracy, 4),
        n_features=X_train.shape[1],
        n_train=len(X_train),
        n_test=len(X_test),
        feature_names=feature_names or [],
        feature_importance=fi,
    )
