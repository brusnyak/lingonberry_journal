from __future__ import annotations

import pandas as pd
import pytest

from backtesting.crypto.foundation_backtest import (
    CostScenario,
    _cost_model,
    run_cost_fragility_audit,
    trade_diagnostics,
)
from backtesting.crypto.strategies.mtf_cascade_foundation import MtfCascadeFoundation
from backtesting.crypto.synthetic_ohlcv import make_staircase_series
from backtesting.engine.base import BarData, EngineState
from backtesting.engine.costs import CryptoCosts, WorstCaseCryptoCosts
from backtesting.engine.orders import Direction, Position
from backtesting.engine.runner import run


def _resample(df: pd.DataFrame, minutes: int) -> pd.DataFrame:
    d = df.set_index("ts")
    r = d.resample(f"{minutes}min").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna()
    return r.reset_index()


def _synthetic_cascade_data(direction: str, seed: int) -> dict[str, pd.DataFrame]:
    ohlcv30 = make_staircase_series(direction, bars=30000, tf_minutes=30, seed=seed)
    ohlcv240 = _resample(ohlcv30, 240)
    ohlcv5 = make_staircase_series(direction, bars=30000 * 6, tf_minutes=5, seed=seed)
    return {"240": ohlcv240, "30": ohlcv30, "5": ohlcv5}


def test_strategy_trades_mostly_long_on_synthetic_uptrend():
    data = _synthetic_cascade_data("up", seed=41)
    strat = MtfCascadeFoundation(risk_pct=0.01, horizon_bars=200)
    result = run(strat, data, entry_tf="5", costs=CryptoCosts(), initial_equity=1000.0)
    df = result.to_df()
    assert len(df) > 5
    assert (df["direction"] == "long").mean() > 0.8, df["direction"].value_counts()


def test_strategy_trades_mostly_short_on_synthetic_downtrend():
    data = _synthetic_cascade_data("down", seed=43)
    strat = MtfCascadeFoundation(risk_pct=0.01, horizon_bars=200)
    result = run(strat, data, entry_tf="5", costs=CryptoCosts(), initial_equity=1000.0)
    df = result.to_df()
    assert len(df) > 5
    assert (df["direction"] == "short").mean() > 0.8, df["direction"].value_counts()


def test_should_close_fires_exactly_at_horizon():
    data = _synthetic_cascade_data("up", seed=41)
    strat = MtfCascadeFoundation(risk_pct=0.01, horizon_bars=10)
    strat.init(data)

    entry_ts = strat._ts[5]  # numpy.datetime64, matching runner._open_position's entry_time=bar.ts
    pos = Position(
        id=1, direction=Direction.LONG, entry_price=100.0, entry_time=entry_ts,
        sl=90.0, tp1=120.0, tp2=None, tp3=None, lots=1.0, risk_pct=0.01,
        tp1_frac=1.0, tp2_frac=0.0, trail=False,
    )

    bar_before = BarData(ts=strat._ts[14], open_=100, high=101, low=99, close=100, volume=0, index=14)
    assert strat.should_close(pos, bar_before, None) is False

    bar_at_horizon = BarData(ts=strat._ts[15], open_=100, high=101, low=99, close=100, volume=0, index=15)
    assert strat.should_close(pos, bar_at_horizon, None) is True


def test_strategy_requires_all_three_timeframes():
    strat = MtfCascadeFoundation()
    with pytest.raises(ValueError):
        strat.init({"240": pd.DataFrame(), "30": pd.DataFrame()})


def test_min_stop_pct_rejects_degenerate_stop_signal():
    """Phase 28: a stop a few cents from entry made calc_lots size off a
    near-zero risk denominator (leverage cap sizes the trade instead of
    risk_pct), and the R-multiple computed from that same tiny stop_dist
    blew up to -7601R on one real BTC trade. min_stop_pct must reject any
    entry whose stop distance is below the threshold, as % of entry price."""
    strat = MtfCascadeFoundation(min_stop_pct=0.1)
    entry = 95000.0
    degenerate_sl = 95000.01  # ~0.00001% away -- exactly the observed bug case
    real_sl = 94700.0         # ~0.32% away -- a legitimate structural stop
    assert (abs(entry - degenerate_sl) / entry * 100) < strat.min_stop_pct
    assert (abs(entry - real_sl) / entry * 100) > strat.min_stop_pct


def test_min_stop_pct_none_disables_the_filter():
    strat = MtfCascadeFoundation(min_stop_pct=None)
    assert strat.min_stop_pct is None


def test_next_rejects_signal_when_stop_is_degenerate():
    from unittest.mock import patch

    data = _synthetic_cascade_data("up", seed=41)
    strat = MtfCascadeFoundation(risk_pct=0.01, horizon_bars=200, min_stop_pct=0.1)
    strat.init(data)
    i = int(strat._changed[strat._changed].index[0])
    bar = BarData(ts=strat._ts[i], open_=100, high=101, low=99, close=100.0, volume=0, index=i)
    state = EngineState(equity=1000.0, initial_equity=1000.0, open_positions=[], closed_trades=[], bar_index=i)

    with patch(
        "backtesting.crypto.strategies.mtf_cascade_foundation.structural_stop_target",
        return_value=(99.99, 101.0),  # ~0.01% away -- degenerate
    ):
        assert strat.next(bar, state) is None

    with patch(
        "backtesting.crypto.strategies.mtf_cascade_foundation.structural_stop_target",
        return_value=(99.5, 101.0),  # ~0.5% away -- legitimate
    ):
        assert strat.next(bar, state) is not None


def test_trade_diagnostics_reports_stop_geometry_and_exit_mix():
    trades = pd.DataFrame(
        {
            "entry_price": [100.0, 100.0, 100.0, 100.0],
            "sl": [99.0, 99.8, 99.95, 101.0],
            "exit_reason": ["sl", "tp1", "signal", "eod"],
        }
    )

    diag = trade_diagnostics(trades)

    assert diag["median_stop_pct"] == pytest.approx(0.6)
    assert round(diag["p10_stop_pct"], 3) == 0.095
    assert diag["sub_10bps_stop_rate"] == 0.25
    assert diag["sl_rate"] == 0.25
    assert diag["tp_rate"] == 0.25
    assert diag["signal_exit_rate"] == 0.25
    assert diag["eod_exit_rate"] == 0.25


def test_cost_model_uses_worst_case_only_for_adverse_cost_scenarios():
    base = _cost_model(CostScenario("base_fee"), {"min_notional": 5.0}, leverage=25.0)
    stress = _cost_model(CostScenario("stress", adverse_round_trip_pct=0.002), {}, leverage=50.0)

    assert isinstance(base, CryptoCosts)
    assert not isinstance(base, WorstCaseCryptoCosts)
    assert base.min_notional == 5.0
    assert isinstance(stress, WorstCaseCryptoCosts)
    assert stress.round_trip_pct == 0.002


def test_cost_fragility_audit_measures_drag_from_zero_fee(monkeypatch):
    import backtesting.crypto.foundation_backtest as fb

    scenarios = [
        CostScenario("zero_fee", maker_fee=0.0, taker_fee=0.0),
        CostScenario("base_fee"),
    ]

    def fake_backtest(symbol, *, cost_scenario, **kwargs):
        avg_r = 0.25 if cost_scenario.name == "zero_fee" else 0.05
        return {
            "symbol": symbol,
            "cost_scenario": cost_scenario.name,
            "avg_r": avg_r,
            "trades": 10,
            "error": None,
            "_trades_df": pd.DataFrame(),
        }

    monkeypatch.setattr(fb, "run_foundation_backtest", fake_backtest)

    audit = run_cost_fragility_audit("BTCUSDT", scenarios=scenarios)

    assert list(audit["cost_scenario"]) == ["zero_fee", "base_fee"]
    assert list(audit["cost_drag_avg_r"]) == [0.0, 0.2]
