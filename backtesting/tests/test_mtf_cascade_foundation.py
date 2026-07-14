from __future__ import annotations

import pandas as pd

from backtesting.crypto.strategies.mtf_cascade_foundation import MtfCascadeFoundation
from backtesting.crypto.synthetic_ohlcv import make_staircase_series
from backtesting.engine.base import BarData
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
