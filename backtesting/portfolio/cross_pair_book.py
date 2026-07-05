"""
Cross-pair combined book: merges independently-run backtests on DIFFERENT
instruments (e.g. ETHUSDT + XRPUSDT) into one shared-account equity/DD view.

Different from combined_book.py: that wraps two strategies sharing ONE
instrument's bar loop (single position slot enforced by the engine itself).
This engine only steps through one instrument's bars at a time, so there's
no way to run two different symbols through one `engine.runner.run()` call.
Instead, each pair is backtested solo (own bars, own equity baseline), then
the resulting trade logs are merged chronologically and re-checked with
`rolling_window_return_stats` as if they'd shared one account.

That merge is only valid if the strategies never actually hold positions on
both pairs at once -- otherwise a real account couldn't have taken both
trades at the risk_pct each solo run assumed. `assert_no_position_overlap`
enforces that before any merge happens; don't skip it.
"""
from __future__ import annotations

import pandas as pd


def assert_no_position_overlap(*trade_logs: pd.DataFrame) -> None:
    """Raise if any pair of trade logs has overlapping open positions.

    Each trades df needs ['entry_time', 'exit_time']. O(n*m) pairwise
    check -- fine at backtest trade-count scale (tens to low hundreds).
    """
    for a_idx in range(len(trade_logs)):
        for b_idx in range(a_idx + 1, len(trade_logs)):
            a, b = trade_logs[a_idx], trade_logs[b_idx]
            if a.empty or b.empty:
                continue
            for _, t in a.iterrows():
                mask = (b["entry_time"] < t["exit_time"]) & (b["exit_time"] > t["entry_time"])
                if mask.any():
                    raise ValueError(
                        f"Position overlap between trade logs {a_idx} and {b_idx} at "
                        f"{t['entry_time']}..{t['exit_time']} -- merging would assume "
                        f"simultaneous risk_pct on both that a real shared account "
                        f"couldn't actually take. Re-derate risk_pct and re-run solo "
                        f"backtests, or don't merge these two."
                    )


def merge_cross_pair_trades(*trade_logs: pd.DataFrame) -> pd.DataFrame:
    """Merge non-overlapping solo trade logs into one chronological log.

    Each input must already be a solo `run(...).to_df()` result computed at
    the SAME `initial_equity` (the shared account's equity), so dollar pnl
    values scale consistently once combined. Raises via
    `assert_no_position_overlap` if that combination isn't actually valid.
    """
    non_empty = [t for t in trade_logs if not t.empty]
    if not non_empty:
        return pd.DataFrame()
    assert_no_position_overlap(*trade_logs)
    return pd.concat(non_empty, ignore_index=True).sort_values("exit_time").reset_index(drop=True)
