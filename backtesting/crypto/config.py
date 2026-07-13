"""Single shared knob for how much history crypto scripts pull by default.

Change DEFAULT_DAYS here to reconfigure every crypto backtest/analysis script
at once, instead of editing N separate hardcoded defaults. Every script still
accepts --days / days= to override per-run.
"""

DEFAULT_DAYS = 400
DEFAULT_SOURCE = "merged"  # 'exchange' | 'legacy' | 'merged' -- see backtesting/crypto/data.py
