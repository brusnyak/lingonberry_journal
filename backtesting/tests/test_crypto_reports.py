from __future__ import annotations

import pandas as pd

from backtesting.crypto_reports import BacktestContext, build_report_tables, challenge_outcome
from backtesting.engine.orders import ClosedTrade, Direction, ExitReason
from backtesting.engine.runner import BacktestResult


def _trade(idx: int, entry: str, exit_: str, pnl: float, r: float) -> ClosedTrade:
    return ClosedTrade(
        id=idx,
        direction=Direction.LONG,
        entry_price=100.0,
        entry_time=pd.Timestamp(entry, tz="UTC"),
        exit_price=101.0,
        exit_time=pd.Timestamp(exit_, tz="UTC"),
        exit_reason=ExitReason.TP1 if pnl > 0 else ExitReason.SL,
        lots=1.0,
        pnl=pnl,
        r_multiple=r,
        label="unit",
    )


def test_challenge_outcome_hits_target():
    trades = [
        _trade(1, "2026-01-01", "2026-01-01 01:00", 20.0, 1.0),
        _trade(2, "2026-01-02", "2026-01-02 01:00", 30.0, 1.5),
        _trade(3, "2026-01-03", "2026-01-03 01:00", 30.0, 1.5),
    ]
    out = challenge_outcome(trades, initial_equity=20.0, target_equity=100.0)
    assert out["target_hit"] is True
    assert out["ruin_hit"] is False
    assert out["trades_to_target"] == 3
    assert out["final_equity"] == 100.0


def test_report_tables_include_windows_and_trade_pnl():
    trades = [
        _trade(1, "2026-01-01", "2026-01-01 00:30", 5.0, 1.0),
        _trade(2, "2026-02-15", "2026-02-15 01:00", -2.0, -0.4),
        _trade(3, "2026-03-20", "2026-03-20 02:00", 8.0, 1.6),
    ]
    result = BacktestResult(
        trades=trades,
        report={},
        elapsed_s=0.1,
        n_bars=100,
    )
    ctx = BacktestContext(
        strategy="unit",
        symbol="BTCUSDT",
        exchange="binance",
        timeframe="5m",
        duration_days=90,
        initial_equity=20.0,
    )

    summary, trade_df = build_report_tables(result, ctx, windows=(30, 60, 90))

    assert set(summary["window_days"]) == {30, 60, 90}
    assert summary.iloc[0]["symbol"] == "BTCUSDT"
    assert "win_rate" in summary.columns
    assert "payoff_ratio" in summary.columns
    assert "max_dd_pct" in summary.columns
    assert list(trade_df["pnl"]) == [5.0, -2.0, 8.0]
    assert list(trade_df["equity"]) == [25.0, 23.0, 31.0]
    assert trade_df["duration_min"].iloc[0] == 30.0
