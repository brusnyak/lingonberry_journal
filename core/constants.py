"""
Shared constants across the trading-journal codebase.

Central locations for session definitions, OOS wall, and other global defaults
so they don't drift between backtesting engine, hypothesis engine, and bot code.
"""

# Session definitions (UTC hour ranges).
# Used by hypothesis_engine levels 0-3 for session-based pocket scanning.
SESSIONS: dict[str, tuple[int, int]] = {
    "asia":      (0, 7),
    "london":    (7, 16),
    "ny":        (12, 21),
    "london_ny": (12, 16),   # overlap
    "24h":       (0, 24),
}
