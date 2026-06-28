"""
Inference module for ML-enhanced strategy signals.

Integrates with strategy next() to filter signals:
    1. Structure signal fires (TrIctSweep / SMC v1)
    2. Query ML model for probability
    3. If ML prob > threshold AND aligns with structure direction → take trade
    4. Else → skip

Supports serialized model loading for live/deployment use.
"""

from __future__ import annotations

import json
import pickle
import warnings
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from backtesting.ml.features import build_feature_matrix


class Mlpredictor:
    """
    ML direction filter for strategy signals.

    Wraps trained ensemble models with feature extraction + probability
    calculation. Call `predict()` at bar close to get direction and confidence.

    Usage:
        predictor = Mlpredictor.load("backtesting/ml/models/gbpaud_5m.pkl")
        signal = strategy.next(bar, state)
        if signal:
            direction, prob = predictor.predict(feature_vector)
            if prob > 0.6 and direction == signal.direction:
                place_trade(signal)
    """

    def __init__(
        self,
        models: dict,
        feature_names: list[str],
        threshold: float = 0.6,
        label_encoder: Optional = None,
        config: Optional[dict] = None,
    ):
        self.models = models
        self.feature_names = feature_names
        self.threshold = threshold
        self.label_encoder = label_encoder
        self.config = config or {}

    @classmethod
    def from_training(cls, train_result, threshold: float = 0.6) -> "Mlpredictor":
        """Create predictor from a TrainResult (train.py)."""
        return cls(
            models=train_result.models,
            feature_names=list(train_result.feature_names) if train_result.feature_names else [],
            threshold=threshold,
            config=train_result.config,
        )

    @classmethod
    def load(cls, path: str | Path) -> "Mlpredictor":
        """Load serialized predictor from pickle."""
        with open(path, "rb") as f:
            data = pickle.load(f)
        return cls(
            models=data["models"],
            feature_names=data["feature_names"],
            threshold=data.get("threshold", 0.6),
            label_encoder=data.get("label_encoder"),
            config=data.get("config"),
        )

    def save(self, path: str | Path) -> None:
        """Serialize to pickle."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "models": self.models,
            "feature_names": self.feature_names,
            "threshold": self.threshold,
            "label_encoder": self.label_encoder,
            "config": self.config,
        }
        with open(path, "wb") as f:
            pickle.dump(data, f)

    def predict(self, features: np.ndarray) -> tuple[int, float]:
        """
        Predict direction and probability for a single feature vector.

        Returns (direction, probability):
            direction: 1 = LONG, -1 = SHORT, 0 = HOLD (below threshold)
            probability: confidence score (0-1)
        """
        if features.ndim == 1:
            features = features.reshape(1, -1)

        probs_list = []
        for name, model in self.models.items():
            if hasattr(model, "predict_proba"):
                try:
                    probs_list.append(model.predict_proba(features))
                except Exception:
                    continue

        if not probs_list:
            return 0, 0.0

        avg_probs = np.mean(probs_list, axis=0)[0]

        # Map: 0→HOLD, 1→LONG, 2→SHORT
        long_prob = avg_probs[1] if len(avg_probs) > 1 else 0.0
        short_prob = avg_probs[2] if len(avg_probs) > 2 else 0.0

        if long_prob > short_prob and long_prob >= self.threshold:
            return 1, float(long_prob)
        elif short_prob > long_prob and short_prob >= self.threshold:
            return -1, float(short_prob)
        else:
            return 0, float(max(long_prob, short_prob))

    def predict_batch(self, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        Predict for a batch.

        Returns (directions, probabilities).
        """
        if X.ndim == 1:
            X = X.reshape(-1, len(self.feature_names))

        n = X.shape[0]
        directions = np.zeros(n, dtype=np.int8)
        probs = np.zeros(n)

        for i in range(n):
            d, p = self.predict(X[i])
            directions[i] = d
            probs[i] = p

        return directions, probs

    def filter_signal(
        self,
        structure_direction: int,
        feat_row: pd.Series | np.ndarray,
    ) -> tuple[bool, float]:
        """
        Filter a structure signal through ML.

        Args:
            structure_direction: 1 (long) or -1 (short)
            feat_row: feature vector for current bar

        Returns:
            (take_trade, confidence)
        """
        if isinstance(feat_row, pd.Series):
            feat_row = feat_row[self.feature_names].values.astype(float)

        ml_dir, prob = self.predict(feat_row)

        if ml_dir == 0 or prob < self.threshold:
            return False, prob

        ml_dir = 1 if ml_dir == 1 else -1
        return ml_dir == structure_direction, prob

    def top_features(self, n: int = 10) -> list[tuple[str, float]]:
        """Return top N features by importance."""
        importances = []
        for name, model in self.models.items():
            if hasattr(model, "feature_importances_"):
                fi = model.feature_importances_
                for j, imp in enumerate(fi):
                    fname = self.feature_names[j] if j < len(self.feature_names) else f"f{j}"
                    importances.append((f"{name}:{fname}", float(imp)))
        importances.sort(key=lambda x: -x[1])
        return importances[:n]


# ── Feature extraction helpers ────────────────────────────────────────────────────


class OnlineFeatureExtractor:
    """
    Extract feature vector from last bar for live inference.

    Mirrors build_feature_matrix but returns a single row.
    """

    def __init__(
        self,
        feature_names: list[str],
        symbol: str = "GBPAUD",
        tf: str = "5",
        buffer_days: int = 30,
    ):
        self.feature_names = feature_names
        self.symbol = symbol
        self.tf = tf
        self.buffer_days = buffer_days
        self._buffer = None

    def extract(
        self,
        ohlc: pd.DataFrame,
    ) -> pd.Series | None:
        """Extract feature vector for the LAST bar in ohlc.

        Returns pd.Series with feature_names as index, or None if error.
        """
        try:
            feat_df = build_feature_matrix(
                self.symbol, self.tf, days=self.buffer_days,
            )
            if feat_df.empty:
                return None
            # Align with ohlc by timestamp
            last_ts = ohlc.iloc[-1]["ts"] if "ts" in ohlc.columns else ohlc.index[-1]
            match = feat_df[feat_df["ts"] == last_ts]
            if match.empty:
                match = feat_df.iloc[-1:]
            row = match.iloc[0]
            return row[self.feature_names]
        except Exception:
            return None


# ── Predict script ────────────────────────────────────────────────────────────────


def run_inference(
    model_path: str | Path,
    symbol: str = "GBPAUD",
    tf: str = "5",
    days: int = 10,
    threshold: float = 0.6,
) -> pd.DataFrame:
    """
    Load model, build features, predict for last N days.
    Returns DataFrame with predictions vs actual outcomes.
    """
    predictor = Mlpredictor.load(model_path)

    feat_df = build_feature_matrix(symbol, tf, days=days)
    X = feat_df[predictor.feature_names].values

    directions, probs = predictor.predict_batch(X)

    result = feat_df[["ts", "close", "trend"]].copy()
    result["ml_direction"] = directions
    result["ml_prob"] = probs
    result["ml_signal"] = (directions != 0) & (probs >= threshold)

    return result


if __name__ == "__main__":
    import sys
    model_path = sys.argv[1] if len(sys.argv) > 1 else "backtesting/ml/models/gbpaud_5m.pkl"
    result = run_inference(model_path)
    signals = result[result["ml_signal"]]
    print(f"Total bars: {len(result)}, ML signals: {len(signals)}")
    print(signals.tail(10).to_string(index=False))
