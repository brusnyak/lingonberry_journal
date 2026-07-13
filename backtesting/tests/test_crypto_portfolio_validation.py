"""Tests for crypto portfolio-level validation."""

from __future__ import annotations

import pandas as pd

from backtesting.crypto.portfolio_validation import (
    PortfolioRiskConfig,
    filter_execution_bucket,
    simulate_portfolio,
)


def _trades() -> pd.DataFrame:
    ts = pd.date_range("2026-01-01 00:00", periods=5, freq="15min", tz="UTC")
    return pd.DataFrame({
        "entry_ts": ts,
        "bars_to_exit": [4, 4, 1, 1, 1],
        "exchange": ["binance", "bybit", "binance", "bybit", "binance"],
        "symbol": ["BTCUSDT", "ETHUSDT", "BTCUSDT", "SOLUSDT", "BTCUSDT"],
        "entry_model": ["structure_confirmed_fvg_top_retest"] * 5,
        "target_model": ["fixed_1_5r"] * 5,
        "management_model": ["partial_1r_be"] * 5,
        "net_r": [1.0, -1.0, 1.0, 0.5, 0.5],
        "hit_stop": [False, True, False, False, False],
        "exit_reason": ["target", "stop", "target", "expiry", "target"],
    })


def test_filter_execution_bucket_returns_only_requested_plan():
    trades = _trades()
    trades.loc[0, "target_model"] = "fixed_2r"

    out = filter_execution_bucket(
        trades,
        entry_model="structure_confirmed_fvg_top_retest",
        target_model="fixed_1_5r",
        management_model="partial_1r_be",
    )

    assert len(out) == 4
    assert set(out["target_model"]) == {"fixed_1_5r"}


def test_simulate_portfolio_enforces_concurrency_and_symbol_limits():
    accepted, summary = simulate_portfolio(
        _trades(),
        PortfolioRiskConfig(
            risk_per_trade_pct=0.01,
            max_open_trades=1,
            max_open_per_symbol=1,
            cooldown_after_loss_bars=0,
            daily_loss_limit_pct=1.0,
        ),
    )

    assert len(accepted) < len(_trades())
    assert summary["accepted"] == len(accepted)
    assert summary["max_open_trades"] == 1


def test_simulate_portfolio_applies_symbol_cooldown_after_loss():
    trades = _trades()
    trades.loc[0, "symbol"] = "BTCUSDT"
    trades.loc[0, "net_r"] = -1.0
    trades.loc[0, "bars_to_exit"] = 1
    trades.loc[2, "symbol"] = "BTCUSDT"

    accepted, _ = simulate_portfolio(
        trades,
        PortfolioRiskConfig(
            risk_per_trade_pct=0.01,
            max_open_trades=5,
            max_open_per_symbol=5,
            cooldown_after_loss_bars=8,
            daily_loss_limit_pct=1.0,
        ),
    )

    btc_entries = accepted[accepted["symbol"] == "BTCUSDT"]["entry_ts"].tolist()
    assert pd.Timestamp("2026-01-01 00:30Z") not in btc_entries


def test_simulate_portfolio_applies_daily_loss_cap():
    trades = _trades()
    trades["net_r"] = [-1.0, -1.0, 1.0, 1.0, 1.0]

    accepted, summary = simulate_portfolio(
        trades,
        PortfolioRiskConfig(
            risk_per_trade_pct=0.01,
            max_open_trades=5,
            max_open_per_symbol=5,
            daily_loss_limit_pct=0.01,
        ),
    )

    assert len(accepted) == 1
    assert summary["gross_return_pct"] == -0.01


def test_simulate_portfolio_dedupes_same_execution_preferring_confirmed():
    trades = _trades().head(1).copy()
    raw = trades.iloc[0].copy()
    raw["entry_model"] = "next_open"
    raw["confirmation_model"] = "none"
    confirmed = raw.copy()
    confirmed["entry_model"] = "structure_confirmed_next_open"
    confirmed["confirmation_model"] = "latest_bull_regime"
    data = pd.DataFrame([raw, confirmed])
    data["entry"] = 100.0
    data["stop"] = 99.0
    data["target"] = 102.0
    data["direction"] = "long"
    data["target_model"] = "fixed_2r"

    accepted, summary = simulate_portfolio(
        data,
        PortfolioRiskConfig(
            risk_per_trade_pct=0.01,
            max_open_trades=5,
            max_open_per_symbol=5,
            cooldown_after_loss_bars=0,
            daily_loss_limit_pct=1.0,
        ),
    )

    assert summary["candidates"] == 1
    assert len(accepted) == 1
    assert accepted.iloc[0]["entry_model"] == "structure_confirmed_next_open"
