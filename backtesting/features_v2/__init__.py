"""
Candle pattern detection and testing (v2 — clean research foundation).

Packages:
    registry   — PatternRegistry singleton, @register decorator
    candle     — Single-bar patterns (doji, hammer, pin bar, etc.)
    multi_bar  — Multi-bar patterns (engulfing, harami, star, etc.)
    pipeline   — Batch extraction across assets and timeframes

Usage:
    from backtesting.features_v2 import registry
    from backtesting.features_v2 import candle, multi_bar
    registry.run("doji", open, high, low, close)
"""

from backtesting.features_v2.registry import registry

# ── Import pattern modules so their @register decorators fire ──
from backtesting.features_v2 import candle  # noqa: F401
from backtesting.features_v2 import multi_bar  # noqa: F401
