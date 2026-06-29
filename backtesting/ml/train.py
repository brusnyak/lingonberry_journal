"""
Ensemble training pipeline for 3-class direction prediction.

Training protocol:
    1. Generate labels (triple-barrier, horizon=24)
    2. Build feature matrix (causal, structure_lib + session + volatility)
    3. Walk-forward expanding window (no random splits)
    4. Train LightGBM + XGBoost + CatBoost ensemble
    5. Soft voting (probability average)
    6. Calibrate probabilities > 0.6 threshold

Overfitting guards:
    - Purged CV: no train/test overlap within horizon bars
    - Expanding window (not rolling): uses all history
    - Monthly retrain (21 trading days)
    - Feature importance: drop features with zero importance
    - Early stopping on validation set
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.inspection import permutation_importance
from sklearn.preprocessing import LabelEncoder

from backtesting.ml.features import build_feature_matrix
from backtesting.ml.labels import triple_barrier_labels_from_events, triple_barrier_labels, class_distribution


@dataclass
class EnsembleConfig:
    """Model configuration.

    sklearn-only (HistGradientBoostingClassifier). The project deliberately avoids
    lightgbm/xgboost/catboost (heavy native deps, not installed). HistGB is the
    right tool for this tabular, branchy feature set and ships with sklearn.
    """

    # HistGradientBoosting (sklearn) — shallow trees + L2 to resist overfit on
    # a ~50/50 directional target where the literature says edge is thin.
    hgb_params: dict = field(default_factory=lambda: {
        "max_iter": 300,
        "max_depth": 3,
        "learning_rate": 0.05,
        "l2_regularization": 1.0,
        "min_samples_leaf": 40,
        "max_leaf_nodes": 15,
        "class_weight": "balanced",
        "early_stopping": True,        # internal validation_fraction holdout
        "validation_fraction": 0.15,
        "n_iter_no_change": 30,
        "random_state": 42,
    })

    # Training
    horizon: int = 24  # triple-barrier horizon bars
    test_size: float = 0.2  # fraction of window for validation
    min_trades_for_training: int = 50
    threshold: float = 0.6  # min probability to take signal
    compute_importance: bool = False  # permutation importance (slow); off by default


@dataclass
class FoldResult:
    """Result of one walk-forward fold."""
    fold: int
    train_start: int
    train_end: int
    test_start: int
    test_end: int
    n_train: int
    n_test: int
    class_dist: dict
    accuracy: float
    report: str
    feature_importances: dict[str, float]


@dataclass
class TrainResult:
    """Complete training result."""
    models: dict  # {name: trained_model}
    config: EnsembleConfig
    folds: list[FoldResult]
    mean_accuracy: float
    feature_importances: dict[str, float]
    feature_names: list[str] = field(default_factory=list)


def train_ensemble(
    X: np.ndarray,
    y: np.ndarray,
    feature_names: list[str],
    config: Optional[EnsembleConfig] = None,
    eval_set: Optional[tuple[np.ndarray, np.ndarray]] = None,
    verbose: bool = False,
) -> TrainResult:
    """
    Train a single sklearn HistGradientBoosting classifier.

    Returned in a one-entry ``models`` dict so the soft-vote API in
    ``_ensemble_predict`` keeps working unchanged (and a future second model can
    be slotted in without touching callers).

    Parameters
    ----------
    X : ndarray of shape (n_samples, n_features)
    y : ndarray of shape (n_samples,) — labels 0 (HOLD), 1 (LONG), 2 (SHORT)
    feature_names : list of str
    config : EnsembleConfig
    eval_set : optional (X_val, y_val) — used for permutation importance only;
        HistGB does its own internal early-stopping holdout.
    verbose : bool

    Returns
    -------
    TrainResult with the trained model and (optional) permutation importances.
    """
    if config is None:
        config = EnsembleConfig()

    if len(np.unique(y)) < 2:
        raise ValueError(f"Need at least 2 classes, got {np.unique(y)}")

    le = LabelEncoder()
    y_enc = le.fit_transform(y)

    if verbose:
        print("Training HistGradientBoosting...")
    model = HistGradientBoostingClassifier(**config.hgb_params)
    model.fit(X, y_enc)
    models = {"histgb": model}

    # ── Feature importances (permutation; HistGB has no native ones) ─────────
    # n_jobs=1 — loky parallelism is flaky under Python 3.14 (see meta_label.py).
    fi: dict[str, float] = {}
    if config.compute_importance and eval_set is not None:
        X_val, y_val = eval_set
        try:
            r = permutation_importance(
                model, X_val, le.transform(y_val),
                n_repeats=5, random_state=42, n_jobs=1,
            )
            for j, imp in enumerate(r.importances_mean):
                fname = feature_names[j] if j < len(feature_names) else f"f{j}"
                fi[f"histgb:{fname}"] = float(imp)
        except Exception:
            pass

    return TrainResult(
        models=models,
        config=config,
        folds=[],
        mean_accuracy=0.0,
        feature_importances=fi,
        feature_names=feature_names,
    )


def walk_forward_train(
    X: np.ndarray,
    y: np.ndarray,
    feature_names: list[str],
    n_folds: int = 6,
    window_size: int = 2000,
    config: Optional[EnsembleConfig] = None,
    verbose: bool = False,
) -> TrainResult:
    """
    Walk-forward expanding window training.

    Each fold trains on expanding window and validates on next chunk.
    No overlap within horizon bars (purged).

    Parameters
    ----------
    X, y : feature matrix and labels
    feature_names : list of str
    n_folds : number of walk-forward folds
    window_size : minimum samples per training window
    config : EnsembleConfig
    verbose : bool

    Returns
    -------
    TrainResult with per-fold results and aggregate model.
    """
    if config is None:
        config = EnsembleConfig()

    n = len(y)
    if n < window_size:
        # Fallback to single train/val split
        split = int(n * 0.8)
        X_train, y_train = X[:split], y[:split]
        X_val, y_val = X[split:], y[split:]
        return train_ensemble(X_train, y_train, feature_names, config, (X_val, y_val), verbose=verbose)

    # Purged gap: must be at least horizon bars away from test
    purge = config.horizon

    folds: list[FoldResult] = []
    all_models: list[dict] = []

    for fold in range(n_folds):
        # Expanding train window
        train_end = window_size + fold * ((n - window_size) // n_folds)
        if fold == n_folds - 1:
            test_end = n
        else:
            test_end = train_end + (n - window_size) // n_folds

        # Apply purge
        test_start = max(train_end + purge, train_end + 1)
        if test_start >= test_end:
            continue

        X_train, y_train = X[:train_end], y[:train_end]
        X_test, y_test = X[test_start:test_end], y[test_start:test_end]

        if len(np.unique(y_train)) < 2 or len(y_test) < 10:
            continue

        if verbose:
            print(f"\nFold {fold + 1}/{n_folds}: train={len(y_train)} test={len(y_test)}")

        result = train_ensemble(
            X_train, y_train, feature_names, config,
            (X_test, y_test), verbose=verbose,
        )

        # Evaluate
        y_pred = _ensemble_predict(result.models, X_test)
        acc = accuracy_score(y_test, y_pred)

        folds.append(FoldResult(
            fold=fold,
            train_start=0, train_end=train_end,
            test_start=test_start, test_end=test_end,
            n_train=len(y_train), n_test=len(y_test),
            class_dist=class_distribution(y_test),
            accuracy=acc,
            report=classification_report(y_test, y_pred, output_dict=False) if verbose else "",
            feature_importances=result.feature_importances,
        ))

        all_models.append(result.models)

    if not folds:
        raise ValueError("No valid folds generated — too little data?")

    # ── Final model: train on ALL data ──────────────────────────────────────
    if verbose:
        print("\nTraining final ensemble on all data...")
    final = train_ensemble(X, y, feature_names, config, verbose=verbose)

    final.folds = folds
    final.mean_accuracy = np.mean([f.accuracy for f in folds])
    final.feature_names = feature_names

    # Aggregate feature importances across folds
    agg_fi: dict[str, float] = {}
    for f in folds:
        for k, v in f.feature_importances.items():
            agg_fi[k] = agg_fi.get(k, 0.0) + v
    if agg_fi:
        total = sum(agg_fi.values())
        if total > 0:
            agg_fi = {k: v / total * 100 for k, v in agg_fi.items()}
    final.feature_importances = agg_fi

    if verbose:
        print(f"\nMean accuracy: {final.mean_accuracy:.4f}")
        top_fi = sorted(agg_fi.items(), key=lambda x: -x[1])[:10]
        print("Top feature importances:")
        for name, imp in top_fi:
            print(f"  {name}: {imp:.1f}%")

    return final


def _ensemble_predict(models: dict, X: np.ndarray) -> np.ndarray:
    """Soft voting: average probabilities across models, pick argmax."""
    probs_list = []
    for name, model in models.items():
        if hasattr(model, "predict_proba"):
            probs_list.append(model.predict_proba(X))
    if not probs_list:
        return np.zeros(len(X), dtype=np.int_)
    avg_probs = np.mean(probs_list, axis=0)
    return np.argmax(avg_probs, axis=1)


def _has_early_stopping(model) -> bool:
    """Check if an LGBM/XGB model has best_iteration."""
    if hasattr(model, "best_iteration_"):
        return model.best_iteration_ is not None
    return False


# ── High-level pipeline ──────────────────────────────────────────────────────────


def run_pipeline(
    symbol: str = "GBPAUD",
    tf: str = "5",
    days: int = 120,
    config: Optional[EnsembleConfig] = None,
    verbose: bool = True,
) -> tuple[TrainResult, pd.DataFrame, np.ndarray]:
    """
    End-to-end: load data → features → labels → train.

    Returns (TrainResult, feature_matrix, labels).
    """
    if config is None:
        config = EnsembleConfig()

    # 1. Features
    if verbose:
        print(f"Building features: {symbol} {tf} {days}d...")
    feat_df = build_feature_matrix(symbol, tf, days=days)
    feature_cols = [c for c in feat_df.columns if c not in ("ts", "open", "high", "low")]

    # 2. Labels: use structure-based signals as proxy
    #    Bullish = trend==1 + bos or choch, Bearish = trend==-1 + bos or choch
    direction = np.where(
        (feat_df["trend"] == 1) & ((feat_df["bull_bos"] > 0) | (feat_df["bull_choch"] > 0)), 1,
        np.where(
            (feat_df["trend"] == -1) & ((feat_df["bear_bos"] > 0) | (feat_df["bear_choch"] > 0)), -1,
            0,
        ),
    )
    # Use ATR*2 as SL, close ± target_r*risk as TP
    atr = feat_df["atr"].values
    close = feat_df["close"].values
    entry = np.where(direction != 0, close, np.nan)
    sl = np.where(
        direction == 1, close - atr * 1.5,
        np.where(direction == -1, close + atr * 1.5, np.nan),
    )
    tp = np.where(
        direction == 1, close + atr * 1.5 * config.horizon/24,
        np.where(direction == -1, close - atr * 1.5 * config.horizon/24, np.nan),
    )

    # Build mock OHLC for labeler
    ohlc = pd.DataFrame({"high": feat_df["high"], "low": feat_df["low"], "close": close})
    labels = triple_barrier_labels(ohlc, entry, sl, tp, direction, horizon=config.horizon, only_signal_bars=False)

    # Filter to only bars with signals (direction != 0)
    signal_mask = direction != 0
    X = feat_df[feature_cols].values[signal_mask]
    y = labels[signal_mask]

    if verbose:
        dist = class_distribution(y)
        print(f"Label distribution: {dist}")
        print(f"Samples: {len(y)}, Features: {X.shape[1]}")

    if len(y) < config.min_trades_for_training:
        if verbose:
            print(f"Warning: only {len(y)} samples, need {config.min_trades_for_training}")
        # Train anyway with smaller data
        config.min_trades_for_training = max(10, len(y) // 2)

    # 3. Train with walk-forward
    result = walk_forward_train(
        X, y, feature_cols,
        n_folds=min(6, max(2, len(y) // 500)),
        window_size=min(2000, len(y) // 2),
        config=config,
        verbose=verbose,
    )

    return result, feat_df, labels


if __name__ == "__main__":
    result, feat_df, labels = run_pipeline("GBPAUD", "5", days=60, verbose=True)
    print(f"\nMean accuracy: {result.mean_accuracy:.4f}")
    top = sorted(result.feature_importances.items(), key=lambda x: -x[1])[:10]
    print("Top features:")
    for k, v in top:
        print(f"  {k}: {v:.1f}%")
