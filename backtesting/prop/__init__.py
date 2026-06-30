"""
Prop firm rule engine — position sizing, drawdown limits, target calculations.

Used by Level 4 backtests to ensure strategies pass prop firm challenges
before any live capital is risked. Rules are read from a JSON config or
applied as defaults for known accounts (GFT 25k, 100k).
"""
