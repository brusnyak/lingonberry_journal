from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from backtesting.analysis.prop_check import check_prop_compliance
from backtesting.prop.rules import PropAccount

ACCT = PropAccount(name="test", initial_equity=10_000.0, daily_dd_pct=0.05,
                    max_dd_pct=0.10, target_pct=0.08)


def _trades(pnls, days=None):
    days = days or [f"2026-01-{i+1:02d}" for i in range(len(pnls))]
    return pd.DataFrame({
        "entry_time": [pd.Timestamp(d, tz="UTC") for d in days],
        "pnl": pnls,
    })


def test_no_trades_returns_flat_result():
    r = check_prop_compliance(pd.DataFrame(), ACCT)
    assert r.n_trades == 0
    assert r.breached is False
    assert r.target_hit is False


def test_target_hit_when_return_exceeds_target_pct():
    r = check_prop_compliance(_trades([900.0]), ACCT, initial_equity=10_000.0)
    assert r.target_hit is True
    assert r.breached is False


def test_max_dd_breach_detected_across_multiple_days():
    # Each day's own drawdown stays under the 5% daily limit, but the
    # cumulative drop across days exceeds the 10% max-DD ceiling.
    pnls = [-400.0] * 3  # 3 separate days, 4% each vs a shrinking equity -> under daily limit each time, over max cumulatively
    r = check_prop_compliance(_trades(pnls), ACCT, initial_equity=10_000.0)
    assert r.breached is True
    assert r.breach_type == "max"


def test_daily_dd_breach_detected_same_day():
    r = check_prop_compliance(_trades([-600.0], days=["2026-01-01"]), ACCT, initial_equity=10_000.0)
    assert r.breached is True
    assert r.breach_type == "daily"


def test_scale_invariant_across_initial_equity():
    r10k = check_prop_compliance(_trades([900.0]), ACCT, initial_equity=10_000.0)
    r100k = check_prop_compliance(_trades([9000.0]), ACCT, initial_equity=100_000.0)
    assert r10k.target_hit == r100k.target_hit == True
    assert round(r10k.return_pct, 1) == round(r100k.return_pct, 1)


NO_TARGET_ACCT = PropAccount(name="crypto_test", initial_equity=50.0,
                              daily_dd_pct=0.05, max_dd_pct=0.10, target_pct=None)


def test_no_target_account_returns_none_not_false():
    r = check_prop_compliance(_trades([900.0]), NO_TARGET_ACCT, initial_equity=10_000.0)
    assert r.target_hit is None
    assert round(r.return_pct, 6) == 9.0


def test_no_target_account_no_trades_still_none():
    r = check_prop_compliance(pd.DataFrame(), NO_TARGET_ACCT)
    assert r.target_hit is None


def test_no_target_account_dd_rules_still_enforced():
    r = check_prop_compliance(_trades([-600.0], days=["2026-01-01"]), NO_TARGET_ACCT, initial_equity=10_000.0)
    assert r.breached is True
    assert r.breach_type == "daily"
    assert r.target_hit is None
