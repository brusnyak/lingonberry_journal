"""
Online/Incremental Learning System for ML models.
Tracks predictions, outcomes, and performance metrics in SQLite database.
"""
import sqlite3
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path


class OnlineLearningTracker:
    """
    Tracks ML predictions and outcomes for continuous learning.
    
    Stores:
    - Predictions with features and confidence
    - Actual outcomes (labels)
    - Performance metrics over time
    - Feature importance evolution
    """
    
    def __init__(self, db_path: str = 'data/ml_learning.db'):
        """
        Initialize tracker with SQLite database.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Create database tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Predictions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                bar_index INTEGER NOT NULL,
                prediction INTEGER NOT NULL,
                confidence REAL NOT NULL,
                actual_outcome INTEGER,
                correct INTEGER,
                features TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT
            )
        ''')
        
        # Performance metrics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                window_size INTEGER NOT NULL,
                accuracy REAL NOT NULL,
                precision_long REAL,
                precision_short REAL,
                recall_long REAL,
                recall_short REAL,
                sharpe_ratio REAL,
                total_predictions INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
        ''')
        
        # Feature importance table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feature_importance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                feature_name TEXT NOT NULL,
                importance_score REAL NOT NULL,
                label_correlation REAL,
                created_at TEXT NOT NULL
            )
        ''')
        
        # Model versions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS model_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version TEXT NOT NULL,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                features TEXT NOT NULL,
                hyperparameters TEXT NOT NULL,
                performance_summary TEXT,
                created_at TEXT NOT NULL,
                active INTEGER DEFAULT 1
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def log_prediction(self, timestamp: pd.Timestamp, symbol: str, timeframe: str,
                      bar_index: int, prediction: int, confidence: float,
                      features: Dict[str, float]) -> int:
        """
        Log a prediction to the database.
        
        Args:
            timestamp: Bar timestamp
            symbol: Trading symbol
            timeframe: Timeframe (e.g., '15')
            bar_index: Bar index in dataset
            prediction: Predicted signal (1, -1, 0)
            confidence: Prediction confidence (0-1)
            features: Dict of feature values
        
        Returns:
            Prediction ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO predictions 
            (timestamp, symbol, timeframe, bar_index, prediction, confidence, features, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            timestamp.isoformat(),
            symbol,
            timeframe,
            bar_index,
            prediction,
            confidence,
            str(features),
            datetime.now().isoformat()
        ))
        
        pred_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return pred_id
    
    def update_outcome(self, prediction_id: int, actual_outcome: int):
        """
        Update prediction with actual outcome.
        
        Args:
            prediction_id: Prediction ID from log_prediction
            actual_outcome: Actual label (1, -1, 0)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get prediction
        cursor.execute('SELECT prediction FROM predictions WHERE id = ?', (prediction_id,))
        result = cursor.fetchone()
        
        if result:
            prediction = result[0]
            correct = 1 if prediction == actual_outcome else 0
            
            cursor.execute('''
                UPDATE predictions 
                SET actual_outcome = ?, correct = ?, updated_at = ?
                WHERE id = ?
            ''', (actual_outcome, correct, datetime.now().isoformat(), prediction_id))
            
            conn.commit()
        
        conn.close()
    
    def calculate_performance_metrics(self, symbol: str, timeframe: str,
                                     window_size: int = 100) -> Dict:
        """
        Calculate performance metrics for recent predictions.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            window_size: Number of recent predictions to analyze
        
        Returns:
            Dict of performance metrics
        """
        conn = sqlite3.connect(self.db_path)
        
        # Get recent predictions with outcomes
        query = '''
            SELECT prediction, actual_outcome, correct, confidence
            FROM predictions
            WHERE symbol = ? AND timeframe = ? AND actual_outcome IS NOT NULL
            ORDER BY id DESC
            LIMIT ?
        '''
        
        df = pd.read_sql_query(query, conn, params=(symbol, timeframe, window_size))
        conn.close()
        
        if len(df) == 0:
            return {}
        
        # Calculate metrics
        accuracy = df['correct'].mean()
        
        # Precision and recall for long/short
        long_preds = df[df['prediction'] == 1]
        short_preds = df[df['prediction'] == -1]
        
        precision_long = long_preds['correct'].mean() if len(long_preds) > 0 else 0
        precision_short = short_preds['correct'].mean() if len(short_preds) > 0 else 0
        
        long_actual = df[df['actual_outcome'] == 1]
        short_actual = df[df['actual_outcome'] == -1]
        
        recall_long = (long_actual['correct'].sum() / len(long_actual)) if len(long_actual) > 0 else 0
        recall_short = (short_actual['correct'].sum() / len(short_actual)) if len(short_actual) > 0 else 0
        
        metrics = {
            'accuracy': accuracy,
            'precision_long': precision_long,
            'precision_short': precision_short,
            'recall_long': recall_long,
            'recall_short': recall_short,
            'total_predictions': len(df),
            'avg_confidence': df['confidence'].mean()
        }
        
        return metrics
    
    def log_performance_metrics(self, timestamp: pd.Timestamp, symbol: str,
                               timeframe: str, metrics: Dict):
        """
        Log performance metrics to database.
        
        Args:
            timestamp: Current timestamp
            symbol: Trading symbol
            timeframe: Timeframe
            metrics: Dict of metrics from calculate_performance_metrics
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO performance_metrics
            (timestamp, symbol, timeframe, window_size, accuracy, precision_long,
             precision_short, recall_long, recall_short, total_predictions, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            timestamp.isoformat(),
            symbol,
            timeframe,
            100,  # Default window size
            metrics.get('accuracy', 0),
            metrics.get('precision_long', 0),
            metrics.get('precision_short', 0),
            metrics.get('recall_long', 0),
            metrics.get('recall_short', 0),
            metrics.get('total_predictions', 0),
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
    
    def log_feature_importance(self, timestamp: pd.Timestamp, symbol: str,
                              timeframe: str, feature_importance: Dict[str, float],
                              label_correlations: Dict[str, float] = None):
        """
        Log feature importance scores.
        
        Args:
            timestamp: Current timestamp
            symbol: Trading symbol
            timeframe: Timeframe
            feature_importance: Dict of feature names to importance scores
            label_correlations: Dict of feature names to label correlations
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for feature_name, importance in feature_importance.items():
            correlation = label_correlations.get(feature_name, 0) if label_correlations else 0
            
            cursor.execute('''
                INSERT INTO feature_importance
                (timestamp, symbol, timeframe, feature_name, importance_score, 
                 label_correlation, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                timestamp.isoformat(),
                symbol,
                timeframe,
                feature_name,
                importance,
                correlation,
                datetime.now().isoformat()
            ))
        
        conn.commit()
        conn.close()
    
    def get_performance_history(self, symbol: str, timeframe: str,
                               limit: int = 100) -> pd.DataFrame:
        """
        Get performance metrics history.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            limit: Number of records to retrieve
        
        Returns:
            DataFrame of performance metrics over time
        """
        conn = sqlite3.connect(self.db_path)
        
        query = '''
            SELECT timestamp, accuracy, precision_long, precision_short,
                   recall_long, recall_short, total_predictions
            FROM performance_metrics
            WHERE symbol = ? AND timeframe = ?
            ORDER BY id DESC
            LIMIT ?
        '''
        
        df = pd.read_sql_query(query, conn, params=(symbol, timeframe, limit))
        conn.close()
        
        return df
    
    def get_feature_importance_history(self, symbol: str, timeframe: str,
                                      feature_name: str = None,
                                      limit: int = 100) -> pd.DataFrame:
        """
        Get feature importance history.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            feature_name: Specific feature (None = all features)
            limit: Number of records per feature
        
        Returns:
            DataFrame of feature importance over time
        """
        conn = sqlite3.connect(self.db_path)
        
        if feature_name:
            query = '''
                SELECT timestamp, feature_name, importance_score, label_correlation
                FROM feature_importance
                WHERE symbol = ? AND timeframe = ? AND feature_name = ?
                ORDER BY id DESC
                LIMIT ?
            '''
            params = (symbol, timeframe, feature_name, limit)
        else:
            query = '''
                SELECT timestamp, feature_name, importance_score, label_correlation
                FROM feature_importance
                WHERE symbol = ? AND timeframe = ?
                ORDER BY id DESC
                LIMIT ?
            '''
            params = (symbol, timeframe, limit)
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        return df
    
    def should_retrain(self, symbol: str, timeframe: str,
                      accuracy_threshold: float = 0.6,
                      window_size: int = 100) -> Tuple[bool, str]:
        """
        Determine if model should be retrained based on recent performance.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            accuracy_threshold: Minimum acceptable accuracy
            window_size: Window for performance calculation
        
        Returns:
            Tuple of (should_retrain, reason)
        """
        metrics = self.calculate_performance_metrics(symbol, timeframe, window_size)
        
        if not metrics:
            return False, "No predictions yet"
        
        if metrics['accuracy'] < accuracy_threshold:
            return True, f"Accuracy {metrics['accuracy']:.2%} below threshold {accuracy_threshold:.2%}"
        
        if metrics['total_predictions'] < window_size:
            return False, f"Not enough predictions ({metrics['total_predictions']} < {window_size})"
        
        return False, "Performance acceptable"
    
    def get_statistics(self, symbol: str, timeframe: str) -> Dict:
        """
        Get overall statistics for a symbol/timeframe.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
        
        Returns:
            Dict of statistics
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total predictions
        cursor.execute('''
            SELECT COUNT(*) FROM predictions
            WHERE symbol = ? AND timeframe = ?
        ''', (symbol, timeframe))
        total_predictions = cursor.fetchone()[0]
        
        # Predictions with outcomes
        cursor.execute('''
            SELECT COUNT(*) FROM predictions
            WHERE symbol = ? AND timeframe = ? AND actual_outcome IS NOT NULL
        ''', (symbol, timeframe))
        predictions_with_outcomes = cursor.fetchone()[0]
        
        # Overall accuracy
        cursor.execute('''
            SELECT AVG(correct) FROM predictions
            WHERE symbol = ? AND timeframe = ? AND actual_outcome IS NOT NULL
        ''', (symbol, timeframe))
        overall_accuracy = cursor.fetchone()[0] or 0
        
        conn.close()
        
        return {
            'total_predictions': total_predictions,
            'predictions_with_outcomes': predictions_with_outcomes,
            'overall_accuracy': overall_accuracy,
            'coverage': predictions_with_outcomes / total_predictions if total_predictions > 0 else 0
        }
