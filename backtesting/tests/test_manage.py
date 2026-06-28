"""Unit tests for the management layer — isolated, no market data."""
from types import SimpleNamespace

import numpy as np

from backtesting.engine.manage import StructuralManager, direction_sign


def _mgr(n=10, **kw):
    z = lambda: np.zeros(n, dtype=bool)
    return StructuralManager(
        bearish_bos=z(), bullish_bos=z(), bearish_choch=z(), bullish_choch=z(),
        last_swing_high=np.full(n, np.nan), last_swing_low=np.full(n, np.nan), **kw,
    )


def _pos(direction="long", entry=1.1000, sl=1.0950):
    return SimpleNamespace(direction=direction, entry_price=entry, original_sl=sl)


def _bar(close):
    return SimpleNamespace(close=close)


def test_direction_sign():
    assert direction_sign("long") == 1
    assert direction_sign("short") == -1
    assert direction_sign("LONG") == 1
    assert direction_sign(None) == 0


def test_entry_sl_long_uses_swing_low():
    m = _mgr(); m.last_swing_low[5] = 1.0940
    sl = m.entry_sl("long", entry_price=1.1000, i=5)
    assert abs(sl - 1.0940) < 1e-9


def test_entry_sl_buffer_and_min_stop():
    m = _mgr(sl_buffer=0.0005, min_stop=0.0080)
    m.last_swing_low[5] = 1.0990  # too close → min_stop expands it
    sl = m.entry_sl("long", entry_price=1.1000, i=5)
    assert abs(sl - (1.1000 - 0.0080)) < 1e-9


def test_entry_sl_none_when_swing_above_entry():
    m = _mgr(); m.last_swing_low[5] = 1.1050  # swing above entry → invalid for long
    assert m.entry_sl("long", entry_price=1.1000, i=5) is None


def test_entry_sl_short_uses_swing_high():
    m = _mgr(); m.last_swing_high[5] = 1.1060
    sl = m.entry_sl("short", entry_price=1.1000, i=5)
    assert abs(sl - 1.1060) < 1e-9


def test_floating_r():
    m = _mgr()
    # long entry 1.1000 sl 1.0950 → 50 pip risk; price 1.1050 = +1R
    assert abs(m.floating_r("long", 1.1000, 1.0950, 1.1050) - 1.0) < 1e-9
    assert abs(m.floating_r("short", 1.1000, 1.1050, 1.0950) - 1.0) < 1e-9


def test_choch_ignored_before_activation():
    m = _mgr(activate_r=1.0); m.bearish_choch[5] = True
    # long underwater, CHoCH is transitional → do NOT churn the loser
    assert m.should_exit(_pos(), _bar(1.0980), i=5) is False


def test_bos_cuts_loser_always():
    m = _mgr(activate_r=1.0); m.bearish_bos[5] = True
    # long underwater (-0.4R), confirmed adverse BOS → cut before the wide SL
    assert m.should_exit(_pos(), _bar(1.0980), i=5) is True


def test_choch_exits_when_armed():
    m = _mgr(activate_r=1.0); m.bearish_choch[5] = True
    # long +1.4R armed → protect the winner on adverse CHoCH
    assert m.should_exit(_pos(), _bar(1.1070), i=5) is True


def test_exit_on_bearish_break_when_armed_long():
    m = _mgr(activate_r=1.0); m.bearish_bos[5] = True
    assert m.should_exit(_pos(), _bar(1.1070), i=5) is True


def test_exit_on_bullish_break_when_armed_short():
    m = _mgr(activate_r=1.0); m.bullish_choch[5] = True
    assert m.should_exit(_pos("short", 1.1000, 1.1050), _bar(1.0925), i=5) is True


def test_no_exit_without_structure_break():
    m = _mgr(activate_r=1.0)  # armed but no break flagged
    assert m.should_exit(_pos(), _bar(1.1080), i=5) is False
