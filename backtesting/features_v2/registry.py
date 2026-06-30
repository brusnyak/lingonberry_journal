"""
Candle pattern registry — single source of truth for all tested patterns.

Each pattern is registered with metadata: function, category, parameters,
and a slot for literature-backed findings to be filled from research.

Usage:
    from backtesting.features_v2.registry import registry, register
    df = registry.info()                # catalog table
    signals = registry.run("engulfing", open, high, low, close)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

# ── Type alias: a pattern function takes OHLC arrays and returns signal array ──
PatternFunc = Callable[
    [np.ndarray, np.ndarray, np.ndarray, np.ndarray],
    np.ndarray,  # +1 bullish, -1 bearish, 0 neutral
]


@dataclass
class PatternInfo:
    """Metadata for one candle pattern."""

    name: str
    func: PatternFunc
    category: str  # "single", "multi", "combo"
    params: dict[str, object] = field(default_factory=dict)
    # ── Research results (filled from literature / Level 1 tests) ──────
    accuracy_pct: float | None = None       # best observed direction accuracy
    horizon: int | None = None              # bar horizon for that accuracy
    pairs_tested: list[str] | None = None   # e.g. ["GBPAUD", "EURUSD"]
    timeframes_tested: list[str] | None = None
    literature_ref: str | None = None       # paper / source
    notes: str | None = None


class PatternRegistry:
    """Registry of all candle patterns with metadata."""

    def __init__(self):
        self._patterns: dict[str, PatternInfo] = {}

    def register(
        self,
        name: str,
        category: str,
        params: dict | None = None,
    ) -> Callable[[PatternFunc], PatternFunc]:
        """Decorator to register a pattern function."""
        def decorator(func: PatternFunc) -> PatternFunc:
            self._patterns[name] = PatternInfo(
                name=name,
                func=func,
                category=category,
                params=params or {},
            )
            return func
        return decorator

    def set_research(
        self,
        name: str,
        accuracy_pct: float | None = None,
        horizon: int | None = None,
        pairs_tested: list[str] | None = None,
        timeframes_tested: list[str] | None = None,
        literature_ref: str | None = None,
        notes: str | None = None,
    ) -> None:
        """Fill research metadata for a registered pattern."""
        p = self._patterns.get(name)
        if p is None:
            raise KeyError(f"Cannot set research on unknown pattern: {name}")
        if accuracy_pct is not None:
            p.accuracy_pct = accuracy_pct
        if horizon is not None:
            p.horizon = horizon
        if pairs_tested is not None:
            p.pairs_tested = pairs_tested
        if timeframes_tested is not None:
            p.timeframes_tested = timeframes_tested
        if literature_ref is not None:
            p.literature_ref = literature_ref
        if notes is not None:
            p.notes = notes

    def get(self, name: str) -> PatternInfo | None:
        return self._patterns.get(name)

    def run(self, name: str, open: np.ndarray, high: np.ndarray,
            low: np.ndarray, close: np.ndarray) -> np.ndarray:
        p = self._patterns.get(name)
        if p is None:
            raise KeyError(f"Unknown pattern: {name}")
        return p.func(open, high, low, close)

    def info(self) -> list[dict]:
        return [
            {
                "name": p.name,
                "category": p.category,
                "accuracy_pct": p.accuracy_pct,
                "horizon": p.horizon,
            }
            for p in self._patterns.values()
        ]

    @property
    def names(self) -> list[str]:
        return list(self._patterns.keys())

    def __len__(self) -> int:
        return len(self._patterns)

    def __contains__(self, name: str) -> bool:
        return name in self._patterns

    def __repr__(self) -> str:
        return f"PatternRegistry({len(self)} patterns: {', '.join(self.names)})"


# Module-level singleton
registry = PatternRegistry()
