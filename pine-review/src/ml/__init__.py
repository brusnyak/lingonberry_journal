"""
Machine Learning module for trading signals.
Implements Lorentzian Classification and related ML techniques.
"""
from .lorentzian import lorentzian_distance, LorentzianClassifier
from .features import prepare_ml_features, normalize_features
from .filters import VolatilityFilter, RegimeFilter, ADXFilter

__all__ = [
    'lorentzian_distance',
    'LorentzianClassifier',
    'prepare_ml_features',
    'normalize_features',
    'VolatilityFilter',
    'RegimeFilter',
    'ADXFilter'
]
