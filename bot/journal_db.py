"""
Backwards-compatible wrapper for the split journal package.

All public functions have been moved to bot/journal/{schema,crud,stats}.py.
This module re-exports everything so existing imports continue to work.

Prefer the new import paths for new code:
    from bot.journal.schema import init_db, get_connection
    from bot.journal.crud import create_trade, get_trade
    from bot.journal.stats import get_stats
"""

from bot.journal import *
