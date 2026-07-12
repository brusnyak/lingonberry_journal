"""Tests for crypto UI review-packet export."""

from __future__ import annotations

import pandas as pd

from backtesting.crypto.review_packet import build_portfolio_candidate_review_packet


def test_build_portfolio_candidate_review_packet_exports_review_schema(tmp_path):
    ts = pd.date_range("2026-01-01", periods=8, freq="15min", tz="UTC")
    rows = []
    for i, t in enumerate(ts):
        confirmed = i < 4
        rows.append({
            "entry_ts": t,
            "bars_to_exit": 1,
            "exchange": "binance",
            "symbol": "BTCUSDT" if i % 2 == 0 else "ETHUSDT",
            "tf": "15",
            "entry_model": "structure_confirmed_fvg_top_retest" if confirmed else "fvg_top_retest",
            "target_model": "fixed_1_5r",
            "management_model": "partial_1r_be",
            "entry": 100.0,
            "stop": 102.0,
            "target": 97.0,
            "risk_price": 2.0,
            "net_r": 1.0 if i % 3 else -1.0,
            "mfe_r": 1.5,
            "mae_r": -0.4,
            "hit_target": i % 3 != 0,
            "hit_stop": i % 3 == 0,
            "exit_reason": "target" if i % 3 else "stop",
            "bars_to_entry": 2 if i != 6 else 7,
            "confirmation_model": "bos_down" if confirmed else "none",
        })
    output = tmp_path / "packet.csv"

    packet = build_portfolio_candidate_review_packet(pd.DataFrame(rows), output_path=output, per_symbol=2)

    assert output.exists()
    assert {"ts", "predictor", "outcome_1.5r", "hit_1.5r", "review_bucket"} <= set(packet.columns)
    assert "accepted_winner" in set(packet["review_bucket"])
    assert "accepted_loser" in set(packet["review_bucket"])
    assert {"rejected_stale_retest", "rejected_no_confirmation"} & set(packet["review_bucket"])
