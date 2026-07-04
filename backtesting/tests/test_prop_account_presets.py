from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from backtesting.prop.rules import CRYPTO_50, CRYPTO_300, GFT_25K_2STEP, ACCOUNTS, get_account


def test_crypto_accounts_use_gft_25k_dd_shape():
    assert CRYPTO_50.daily_dd_pct == GFT_25K_2STEP.daily_dd_pct == 0.05
    assert CRYPTO_50.max_dd_pct == GFT_25K_2STEP.max_dd_pct == 0.10
    assert CRYPTO_300.daily_dd_pct == 0.05
    assert CRYPTO_300.max_dd_pct == 0.10


def test_crypto_accounts_have_no_target():
    assert CRYPTO_50.target_pct is None
    assert CRYPTO_300.target_pct is None
    assert CRYPTO_50.target_dollars is None


def test_crypto_accounts_check_target_always_false():
    # check_target() is the "did it pass a challenge" gate -- doesn't apply
    # to uncapped-return live accounts, always False regardless of equity.
    assert CRYPTO_50.check_target(equity=1_000_000.0) is False


def test_crypto_accounts_dd_checks_still_work_normally():
    # DD enforcement is unaffected by target_pct=None -- these accounts
    # still have real risk limits, just no profit ceiling/pass gate.
    assert CRYPTO_50.check_daily_dd(equity=44.0, day_start_equity=50.0) is True   # 12% > 5%
    assert CRYPTO_50.check_daily_dd(equity=49.0, day_start_equity=50.0) is False  # 2% < 5%
    assert CRYPTO_300.check_max_dd(equity=260.0, peak_equity=300.0) is True       # 13.3% > 10%


def test_crypto_accounts_correct_dollar_sizes():
    assert CRYPTO_50.initial_equity == 50.0
    assert CRYPTO_300.initial_equity == 300.0


def test_crypto_accounts_registered_in_lookup():
    assert get_account("CRYPTO_50") is CRYPTO_50
    assert get_account("CRYPTO_300") is CRYPTO_300
    assert "CRYPTO_50" in ACCOUNTS and "CRYPTO_300" in ACCOUNTS
