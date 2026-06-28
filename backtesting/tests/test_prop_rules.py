from __future__ import annotations

import pandas as pd

from backtesting.prop_rules import GFT_100K_1STEP, evaluate_prop_rules


def test_prop_rules_scale_from_source_balance():
    trades = pd.DataFrame(
        {
            "exit_time": pd.to_datetime(["2026-01-01", "2026-01-02"], utc=True),
            "pnl": [1_000.0, -500.0],
        }
    )
    report = evaluate_prop_rules(trades, GFT_100K_1STEP, source_initial_balance=25_000.0)
    assert report["return_pct"] == 2.0
    assert report["max_daily_loss_pct"] == 2.0
    assert report["target_hit"] is False
