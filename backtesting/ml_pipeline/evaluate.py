"""
Evaluation metrics for direction classification.

Focus: direction accuracy (is the model right about up vs down?),
feature importance (which patterns drive predictions), and drawdown
analysis for the backtest phase.

All metrics are designed to be comparable with hypothesis_engine results.
"""

from __future__ import annotations

import numpy as np


def direction_accuracy(
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> float:
    """Fraction of correct direction predictions (0-1)."""
    if len(y_true) == 0:
        return 0.5
    return float(np.mean(y_pred == y_true))


def confusion_matrix(
    y_true: np.ndarray,
    y_pred: np.ndarray,
) -> dict[str, float]:
    """
    Returns TP, TN, FP, FN rates.

    Positive = bullish (up), Negative = bearish (down).
    """
    tp = float(np.sum((y_pred == 1) & (y_true == 1)))
    tn = float(np.sum((y_pred == 0) & (y_true == 0)))
    fp = float(np.sum((y_pred == 1) & (y_true == 0)))
    fn = float(np.sum((y_pred == 0) & (y_true == 1)))

    total_pos = tp + fn
    total_neg = tn + fp

    return {
        "true_positive_rate": round(tp / total_pos, 4) if total_pos > 0 else 0.0,
        "true_negative_rate": round(tn / total_neg, 4) if total_neg > 0 else 0.0,
        "false_positive_rate": round(fp / total_neg, 4) if total_neg > 0 else 0.0,
        "false_negative_rate": round(fn / total_pos, 4) if total_pos > 0 else 0.0,
        "precision": round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0,
        "recall": round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0,
        "f1": round(2 * tp / (2 * tp + fp + fn), 4) if (2 * tp + fp + fn) > 0 else 0.0,
    }


def win_rate_at_threshold(
    y_prob: np.ndarray,
    y_true: np.ndarray,
    threshold: float = 0.5,
) -> float:
    """
    Direction accuracy when model confidence exceeds threshold.
    High-confidence predictions only.
    """
    confident = y_prob >= threshold if len(y_prob.shape) == 1 else np.max(y_prob, axis=1) >= threshold
    if confident.sum() == 0:
        return 0.0
    y_pred = (y_prob >= threshold).astype(int)
    return float(np.mean(y_pred[confident] == y_true[confident]))
