from __future__ import annotations

import pandas as pd

from backtesting.crypto.strategies.mtf_cascade_foundation import MtfCascadeFoundation
from backtesting.crypto.synthetic_ohlcv import make_staircase_series
from backtesting.engine.base import BarData, EngineState
from backtesting.engine.costs import CryptoCosts
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
    import pytest
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
