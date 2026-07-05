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
    `assert_no_position_overlap` if that combination isn't actually valid --
    use `resolve_overlapping_trades` first if you expect overlaps (common
    once you're combining 3+ pairs; 2-pair books were often overlap-free by
    luck, that doesn't generalize).
    """
    non_empty = [t for t in trade_logs if not t.empty]
    if not non_empty:
        return pd.DataFrame()
    assert_no_position_overlap(*trade_logs)
    return pd.concat(non_empty, ignore_index=True).sort_values("exit_time").reset_index(drop=True)


def resolve_overlapping_trades(*trade_logs: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Merge trade logs from different pairs under a single-position-across-
    the-whole-book rule: whichever trade is already open wins, a later
    trade that would overlap it is dropped rather than double-counted.

    This is the realistic assumption for a small account that can't post
    margin for several simultaneous positions across different pairs at
    once -- same one-position-at-a-time philosophy `engine.runner.run()`
    already enforces within a single instrument (via
    `state.has_open_position`), just applied across pairs post-hoc since
    there's no single-engine-loop way to run multiple instruments together
    (see module docstring).

    First-come-first-served by entry_time, not by which pair "should" win
    -- no pair gets priority. Returns (kept_trades_df, n_dropped).
    """
    non_empty = [t for t in trade_logs if not t.empty]
    if not non_empty:
        return pd.DataFrame(), 0

    all_trades = pd.concat(non_empty, ignore_index=True).sort_values("entry_time").reset_index(drop=True)
    kept_rows = []
    dropped = 0
    open_until = None
    for _, t in all_trades.iterrows():
        if open_until is not None and t["entry_time"] < open_until:
            dropped += 1
            continue
        kept_rows.append(t)
        open_until = t["exit_time"]

    kept = pd.DataFrame(kept_rows).sort_values("exit_time").reset_index(drop=True) if kept_rows else pd.DataFrame()
    return kept, dropped
