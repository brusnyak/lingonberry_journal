"""
Trading journal database package.

Split from the original journal_db.py (2133 lines) into:
  - schema.py:    DB connection, helpers, schema init, row normalization
  - crud.py:      Account/trade/review/drawing/MC/webhook CRUD operations
  - stats.py:     Statistics and analytics functions

All public functions from journal_db.py are re-exported here for backwards compat.
"""

from bot.journal.schema import (
    DB_PATH,
    _normalize_session_name,
    _normalize_trade_row,
    _parse_timestamp,
    _safe_float,
    _table_columns,
    compute_rr_ratio,
    get_connection,
    init_db,
)

from bot.journal.crud import (
    add_manual_trade,
    backfill_trade_metadata,
    capture_indicators_at_timestamp,
    close_trade,
    create_account,
    create_trade,
    find_open_trade_by_symbol,
    find_trade_by_external_id,
    get_account,
    get_accounts,
    get_all_trades,
    get_daily_loss_state,
    get_drawings_for_trade,
    get_monte_carlo_stats,
    get_open_trades,
    get_trade,
    get_trade_events,
    get_trades_by_week,
    get_weekly_goals,
    get_weekly_review,
    record_pine_webhook,
    save_drawing,
    save_monte_carlo_run,
    set_trade_chart_paths,
    update_account_rules,
    update_trade_chart_path,
    update_trade_sl_tp,
    upsert_trade_review_note,
    upsert_weekly_goal,
    upsert_weekly_review,
)

from bot.journal.stats import (
    analyze_direction_correctness,
    get_analytics_breakdown,
    get_direction_accuracy_stats,
    get_stats,
    get_week_stats,
)

__all__ = [
    # schema
    "DB_PATH", "_normalize_session_name", "_normalize_trade_row",
    "_parse_timestamp", "_safe_float", "_table_columns",
    "compute_rr_ratio", "get_connection", "init_db",
    # crud
    "add_manual_trade", "backfill_trade_metadata", "capture_indicators_at_timestamp",
    "close_trade", "create_account", "create_trade",
    "find_open_trade_by_symbol", "find_trade_by_external_id",
    "get_account", "get_accounts", "get_all_trades", "get_daily_loss_state",
    "get_drawings_for_trade", "get_monte_carlo_stats", "get_open_trades",
    "get_trade", "get_trade_events", "get_trades_by_week",
    "get_weekly_goals", "get_weekly_review", "record_pine_webhook",
    "save_drawing", "save_monte_carlo_run", "set_trade_chart_paths",
    "update_account_rules", "update_trade_chart_path", "update_trade_sl_tp",
    "upsert_trade_review_note", "upsert_weekly_goal", "upsert_weekly_review",
    # stats
    "analyze_direction_correctness", "get_analytics_breakdown",
    "get_direction_accuracy_stats", "get_stats", "get_week_stats",
]
