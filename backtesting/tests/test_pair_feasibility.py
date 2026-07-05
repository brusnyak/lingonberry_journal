from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from backtesting.crypto.pair_feasibility import check_pair_feasibility, filter_feasible_pairs


def _mock_specs(min_notional):
    return lambda pair, exchange: {"min_notional": min_notional, "min_qty": 0.001,
                                     "qty_step": 0.001, "tick_size": 0.1}


def test_btc_like_min_notional_infeasible_at_50_dollar_account():
    with patch("backtesting.crypto.pair_feasibility.load_market_specs", _mock_specs(50.0)):
        r = check_pair_feasibility("BTCUSDT", "binance", equity=50.0, leverage=5.0)
    assert r.feasible is False
    assert "min_notional" in r.reason


def test_small_min_notional_feasible_at_50_dollar_account():
    with patch("backtesting.crypto.pair_feasibility.load_market_specs", _mock_specs(5.0)):
        r = check_pair_feasibility("XRPUSDT", "binance", equity=50.0, leverage=5.0)
    assert r.feasible is True


def test_same_pair_feasible_at_larger_account():
    # BTC-like min_notional infeasible at $50, feasible at $5000 same leverage
    with patch("backtesting.crypto.pair_feasibility.load_market_specs", _mock_specs(50.0)):
        small = check_pair_feasibility("BTCUSDT", "binance", equity=50.0, leverage=5.0)
        large = check_pair_feasibility("BTCUSDT", "binance", equity=5000.0, leverage=5.0)
    assert small.feasible is False
    assert large.feasible is True


def test_no_spec_found_assumes_feasible_not_blocked():
    with patch("backtesting.crypto.pair_feasibility.load_market_specs", lambda p, e: {}):
        r = check_pair_feasibility("UNKNOWNUSDT", "binance", equity=50.0, leverage=5.0)
    assert r.feasible is True
    assert "no min_notional spec" in r.reason


def test_filter_feasible_pairs_splits_correctly():
    def fake_specs(pair, exchange):
        return {"min_notional": 50.0 if pair == "BTCUSDT" else 5.0}
    with patch("backtesting.crypto.pair_feasibility.load_market_specs", fake_specs):
        feasible, results = filter_feasible_pairs(
            ["BTCUSDT", "XRPUSDT", "DOGEUSDT"], "binance", equity=50.0, leverage=5.0)
    assert feasible == ["XRPUSDT", "DOGEUSDT"]
    assert len(results) == 3


def test_higher_leverage_increases_buying_power_and_feasibility():
    with patch("backtesting.crypto.pair_feasibility.load_market_specs", _mock_specs(50.0)):
        low_lev = check_pair_feasibility("BTCUSDT", "binance", equity=50.0, leverage=1.0)
        high_lev = check_pair_feasibility("BTCUSDT", "binance", equity=50.0, leverage=100.0)
    assert low_lev.feasible is False
    assert high_lev.feasible is True


def test_real_btc_infeasible_at_50_dollars_5x_leverage():
    """Integration check against the actual on-disk market specs that
    triggered this module's existence -- BTCUSDT produced zero trades
    across every Phase 6A config at $50/5x before this was diagnosed."""
    r = check_pair_feasibility("BTCUSDT", "binance", equity=50.0, leverage=5.0)
    assert r.feasible is False


def test_real_xrp_feasible_at_50_dollars_5x_leverage():
    r = check_pair_feasibility("XRPUSDT", "binance", equity=50.0, leverage=5.0)
    assert r.feasible is True
