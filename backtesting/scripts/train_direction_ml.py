#!/usr/bin/env python3
"""Train direction prediction ML model on price action + candle patterns.

Target: binary (price goes UP or DOWN over next N bars).
Features: 84-column matrix (structure, price action, candle patterns, volatility).
Data: all available forex pairs at 60m.
Validation: walk-forward expanding window.

Usage:
    python -m backtesting.scripts.train_direction_ml --symbols GBPAUD,EURUSD --days 365
"""
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = ROOT / "backtesting" / "results"
OUT.mkdir(parents=True, exist_ok=True)

FOREX_SYMBOLS = [
    "GBPAUD", "EURUSD", "GBPUSD", "EURGBP", "GBPJPY", "EURJPY",
    "AUDJPY", "AUDCAD", "AUDCHF", "AUDNZD", "AUDUSD",
    "CADJPY", "CHFJPY", "EURCHF", "EURCAD", "EURAUD",
    "GBPCAD", "GBPCHF", "USDCAD", "USDCHF",
]
BASE_TF = "60"
HORIZONS = [1, 4, 8, 24, 48]  # 60m bars: 1h, 4h, 8h, 24h, 48h forward


def asset_type_for(symbol: str) -> str:
    if symbol in ("XAUUSD",):
        return "commodity"
    if symbol in ("NAS100", "SPX500", "US30"):
        return "index"
    return "forex"


def direction_labels(close: np.ndarray, horizon: int) -> np.ndarray:
    """Create binary direction labels: 1 if price higher after N bars, 0 otherwise."""
    n = len(close)
    labels = np.full(n, np.nan)
    for i in range(n - horizon):
        labels[i] = 1.0 if close[i + horizon] > close[i] else 0.0
    return labels


def load_symbol_features(
    symbol: str,
    days: int = 365,
    swing_left: int = 3,
    swing_right: int = 3,
) -> tuple[pd.DataFrame, dict[int, np.ndarray]]:
    """Load feature matrix and direction labels for one symbol."""
    from backtesting.engine.data import load_data
    from backtesting.ml.features import features_from_ohlc

    atype = asset_type_for(symbol)
    df = load_data(symbol, BASE_TF, days=days, asset_type=atype)
    if df.empty or len(df) < 500:
        return pd.DataFrame(), {}

    # Build feature matrix
    features = features_from_ohlc(
        df,
        swing_left=swing_left,
        swing_right=swing_right,
        fvg_min_gap_mult=0.01,
    )
    if features.empty or len(features) < 500:
        return pd.DataFrame(), {}

    # Ensure aligned
    min_len = min(len(features), len(df))
    features = features.iloc[:min_len].reset_index(drop=True)

    # Create direction labels for each horizon
    close = df["close"].to_numpy(dtype=float)
    labels_by_horizon: dict[int, np.ndarray] = {}
    for h in HORIZONS:
        labels = direction_labels(close[:min_len], h)
        labels_by_horizon[h] = labels

    return features, labels_by_horizon


def drop_low_importance_features(features: pd.DataFrame, min_importance: float = 0.001) -> pd.DataFrame:
    """Remove features that have near-zero variance or are mostly NaN."""
    # Drop constant columns
    constant = features.columns[features.nunique(dropna=False) <= 1]
    if len(constant):
        features = features.drop(columns=constant)

    # Drop columns that are > 50% NaN
    high_nan = features.columns[features.isna().mean() > 0.50]
    if len(high_nan):
        features = features.drop(columns=high_nan)

    return features


def train_horizon_model(
    X: pd.DataFrame,
    y: np.ndarray,
    horizon: int,
) -> dict:
    """Train ensemble for one horizon, report metrics."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, confusion_matrix, classification_report
    from sklearn.model_selection import TimeSeriesSplit
    import lightgbm as lgb

    # Drop non-feature columns
    drop_cols = {"ts", "_symbol"}
    existing_drops = {c for c in drop_cols if c in X.columns}
    X = X.drop(columns=existing_drops)

    # Remove NaN labels
    valid = ~np.isnan(y)
    X_clean = X[valid].copy()
    y_clean = y[valid].astype(int)

    # Fill remaining NaN in features with median
    for col in X_clean.columns:
        if X_clean[col].isna().any():
            X_clean[col] = X_clean[col].fillna(X_clean[col].median())

    n = len(y_clean)
    if n < 200:
        return {"horizon": horizon, "n": n, "error": "too few samples"}

    # Walk-forward: expanding window with 60/20/20 split
    train_end = int(n * 0.60)
    val_end = int(n * 0.80)

    X_train = X_clean.iloc[:train_end]
    y_train = y_clean[:train_end]
    X_val = X_clean.iloc[train_end:val_end]
    y_val = y_clean[train_end:val_end]
    X_test = X_clean.iloc[val_end:]
    y_test = y_clean[val_end:]

    # Class balance check
    train_pos = y_train.mean()
    test_pos = y_test.mean()

    # LightGBM
    params = {
        "objective": "binary",
        "boosting_type": "gbdt",
        "num_leaves": 31,
        "learning_rate": 0.05,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 5,
        "verbose": -1,
        "random_state": 42,
        "n_jobs": -1,
        "min_child_samples": 20,
    }
    lgb_model = lgb.LGBMClassifier(**params)
    lgb_model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        eval_metric="binary_error",
        callbacks=[lgb.early_stopping(10), lgb.log_evaluation(0)],
    )

    # XGBoost
    try:
        import xgboost as xgb
        xgb_model = xgb.XGBClassifier(
            objective="binary:logistic",
            n_estimators=500,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            n_jobs=-1,
            verbosity=0,
            early_stopping_rounds=10,
        )
        xgb_model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False,
        )
    except Exception:
        xgb_model = None

    # CatBoost
    try:
        from catboost import CatBoostClassifier
        cat_model = CatBoostClassifier(
            iterations=500,
            learning_rate=0.05,
            depth=6,
            random_seed=42,
            verbose=0,
            early_stopping_rounds=10,
        )
        cat_model.fit(
            X_train, y_train,
            eval_set=(X_val, y_val),
            verbose=False,
        )
    except Exception:
        cat_model = None

    # Ensemble probabilities (soft voting)
    models = [m for m in [lgb_model, xgb_model, cat_model] if m is not None]
    n_models = len(models)

    if n_models == 0:
        return {"horizon": horizon, "n": n, "error": "no models trained"}

    # Predict probabilities and average
    test_probs = np.zeros(len(X_test))
    for m in models:
        if hasattr(m, "predict_proba"):
            proba = m.predict_proba(X_test)
            # proba[:, 1] is probability of class 1 (UP)
            test_probs += proba[:, 1] / n_models

    # Predictions at thresholds
    test_pred = (test_probs >= 0.5).astype(int)

    # Metrics
    acc = accuracy_score(y_test, test_pred)
    cm = confusion_matrix(y_test, test_pred)
    report = classification_report(y_test, test_pred, output_dict=True, zero_division=0)

    # Feature importance (from LightGBM)
    importance = pd.DataFrame({
        "feature": X_train.columns,
        "importance": lgb_model.feature_importances_,
    }).sort_values("importance", ascending=False)

    return {
        "horizon": horizon,
        "n": n,
        "n_models": n_models,
        "accuracy": round(acc * 100, 1),
        "precision_up": round(report["1"]["precision"] * 100, 1),
        "recall_up": round(report["1"]["recall"] * 100, 1),
        "f1_up": round(report["1"]["f1-score"] * 100, 1),
        "precision_down": round(report["0"]["precision"] * 100, 1),
        "recall_down": round(report["0"]["recall"] * 100, 1),
        "f1_down": round(report["0"]["f1-score"] * 100, 1),
        "class_balance_train": round(train_pos * 100, 1),
        "class_balance_test": round(test_pos * 100, 1),
        "confusion_matrix": cm.tolist(),
        "top_features": importance.head(15).to_dict("records"),
        "model": lgb_model,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Train direction ML model")
    parser.add_argument("--symbols", default="")
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--swing-left", type=int, default=3)
    parser.add_argument("--swing-right", type=int, default=3)
    parser.add_argument("--tag", default="direction_ml")
    parser.add_argument("--multipair", action="store_true",
                       help="Train one model on all pairs (default: per-pair)")
    args = parser.parse_args()

    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    else:
        symbols = FOREX_SYMBOLS

    if not symbols:
        raise SystemExit("No symbols specified")

    results = []

    if args.multipair:
        # Global model: train on all pairs combined
        print("Building global multi-pair dataset...")
        all_features = []
        all_labels: dict[int, list[np.ndarray]] = {h: [] for h in HORIZONS}
        pair_counts = {}

        for symbol in symbols:
            features, labels = load_symbol_features(symbol, args.days, args.swing_left, args.swing_right)
            if features.empty:
                print(f"  SKIP {symbol}: no data")
                continue
            features["_symbol"] = symbol
            all_features.append(features)
            for h in HORIZONS:
                all_labels[h].append(labels[h])
            pair_counts[symbol] = len(features)
            print(f"  {symbol}: {len(features)} bars")

        if not all_features:
            raise SystemExit("No data loaded")

        X = pd.concat(all_features, ignore_index=True)
        print(f"Total dataset: {len(X)} bars from {len(pair_counts)} pairs")
        print(f"  Pair breakdown: {pair_counts}")

        for h in HORIZONS:
            y = np.concatenate(all_labels[h])
            X_h = drop_low_importance_features(X.drop(columns=["_symbol"]))
            print(f"\n--- Horizon: {h} bars ({h*60}min) ---")
            result = train_horizon_model(X_h, y, h)
            results.append(result)
            if "error" in result:
                print(f"  ERROR: {result['error']}")
            else:
                print(f"  Accuracy: {result['accuracy']}%")
                print(f"  UP precision/recall: {result['precision_up']}%/{result['recall_up']}%")
                print(f"  DOWN precision/recall: {result['precision_down']}%/{result['recall_down']}%")
                print(f"  Class balance (train/test): {result['class_balance_train']}%/{result['class_balance_test']}%")
                print(f"  Top 5 features:")
                for f in result["top_features"][:5]:
                    print(f"    {f['feature']}: {f['importance']}")
    else:
        # Per-pair models
        for symbol in symbols:
            print(f"\n{symbol}...", flush=True)
            features, labels = load_symbol_features(symbol, args.days, args.swing_left, args.swing_right)
            if features.empty:
                print(f"  SKIP: no data")
                continue

            # Drop low-variance features
            X = drop_low_importance_features(features)
            print(f"  Features: {X.shape[1]} columns, {len(X)} bars")

            for h in HORIZONS:
                y = labels[h]
                print(f"  Horizon {h}b ({h*60}min): ", end="")
                result = train_horizon_model(X, y, h)
                result["symbol"] = symbol
                results.append(result)
                if "error" in result:
                    print(f"  ERROR: {result['error']}")
                else:
                    print(f"acc={result['accuracy']}% up_prec={result['precision_up']}% "
                          f"up_rec={result['recall_up']}% balance={result['class_balance_test']}%")

    # Save report
    report_rows = []
    for r in results:
        if "error" in r:
            continue
        report_rows.append({
            "symbol": r.get("symbol", "multi"),
            "horizon": r["horizon"],
            "n": r["n"],
            "models": r["n_models"],
            "accuracy": r["accuracy"],
            "precision_up": r["precision_up"],
            "recall_up": r["recall_up"],
            "f1_up": r["f1_up"],
            "precision_down": r["precision_down"],
            "recall_down": r["recall_down"],
            "f1_down": r["f1_down"],
            "class_balance_train": r["class_balance_train"],
            "class_balance_test": r["class_balance_test"],
        })

    report = pd.DataFrame(report_rows)
    path = OUT / f"{args.tag}_report.csv"
    report.to_csv(path, index=False)
    print(f"\nReport saved -> {path}")
    print(report.to_string(index=False))


if __name__ == "__main__":
    main()
