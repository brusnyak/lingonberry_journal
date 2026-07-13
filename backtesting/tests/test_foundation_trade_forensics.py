from __future__ import annotations

import pandas as pd

from backtesting.crypto.foundation_trade_forensics import (
    analyze_foundation_review_labels,
    apply_cost_stress,
    build_foundation_review_packet,
    diagnose_rolling_failures,
    evaluate_contribution_concentration,
    evaluate_direction_audit,
    evaluate_extreme_config_matrix,
    evaluate_frequency_expansion,
    evaluate_rolling_validation,
    ForensicsRunConfig,
    frequency_variant_masks,
    is_strict_candidate,
    profit_factor,
    rsi_bucket,
    rule_masks,
    select_concrete_execution,
    session_vwap_snapshot,
    volume_bucket,
    vwap_extension,
    vwap_state,
)


def test_select_concrete_execution_dedupes_physical_entry_variants():
    ts = pd.Timestamp("2026-01-01 00:00Z")
    journal = pd.DataFrame({
        "exchange": ["binance", "binance", "binance"],
        "symbol": ["BTCUSDT", "BTCUSDT", "BTCUSDT"],
        "direction": ["long", "long", "long"],
        "entry_ts": [ts, ts, ts],
        "entry": [100.0, 100.0, 100.0],
        "stop": [99.0, 99.0, 99.0],
        "target_model": ["fixed_2r", "fixed_2r", "fixed_1_5r"],
        "management_model": ["hold_target_expiry", "hold_target_expiry", "hold_target_expiry"],
        "setup_name": ["late_us_short_bull_flush_ce", "ny_long_neutral_reversal_ce", "ny_long_neutral_reversal_ce"],
        "exit_ts": [ts, ts, ts],
    })

    concrete = select_concrete_execution(journal, "fixed_2r", "hold_target_expiry")

    assert len(concrete) == 1
    assert concrete.iloc[0]["setup_name"] == "ny_long_neutral_reversal_ce"


def test_strict_candidate_accepts_separate_setup_families():
    assert is_strict_candidate({
        "setup_name": "london_long_middle_local_retest",
        "mtf_mode": "trend_aligned",
        "entry_hour_utc": 9,
    })
    assert is_strict_candidate({
        "setup_name": "ny_long_neutral_reversal_ce",
        "mtf_mode": "range_or_transition",
        "entry_hour_utc": 13,
    })
    assert is_strict_candidate({
        "setup_name": "late_us_short_bull_flush_ce",
        "mtf_mode": "countertrend",
        "entry_hour_utc": 22,
    })
    assert not is_strict_candidate({
        "setup_name": "london_long_middle_local_retest",
        "mtf_mode": "pullback_in_uptrend",
        "entry_hour_utc": 9,
    })


def test_rule_masks_include_direction_only_filters():
    events = pd.DataFrame({
        "setup_name": ["late_us_short_bull_flush_ce", "late_us_short_bull_flush_ce", "ny_long_neutral_reversal_ce"],
        "mtf_mode": ["countertrend", "countertrend", "range_or_transition"],
        "entry_hour_utc": [22, 22, 13],
        "vwap_direction_agreement": ["agrees", "opposes", "agrees"],
        "global_ema_state": ["bearish", "bullish", "bullish"],
        "middle_ema_state": ["bearish", "bullish", "bullish"],
        "local_ema_state": ["mixed", "mixed", "bullish"],
        "ema_21_55_state": ["bearish", "mixed", "bullish"],
        "rsi_14": [50.0, 50.0, 50.0],
        "compression_state": ["normal", "normal", "normal"],
        "shock_alignment": ["no_shock", "no_shock", "no_shock"],
    })

    masks = rule_masks(events)

    assert masks["strict_candidates"].sum() == 3
    assert masks["strict_vwap_agrees"].sum() == 2
    assert masks["late_us_fade_vwap_agrees"].sum() == 1
    assert masks["strict_late_us_vwap_agrees"].sum() == 2
    assert masks["strict_late_us_no_weak_ema"].sum() == 2


def test_indicator_buckets_are_stable():
    assert rsi_bucket(25) == "oversold"
    assert rsi_bucket(72) == "overbought"
    assert rsi_bucket(60) == "bullish_mid"
    assert volume_bucket(2.0) == "high"
    assert volume_bucket(-1.2) == "low"
    assert vwap_state(0.3) == "above"
    assert vwap_state(-0.3) == "below"
    assert vwap_state(0.1) == "near"
    assert vwap_extension(2.2) == "extended"
    assert vwap_extension(1.2) == "stretched"


def test_session_vwap_snapshot_uses_completed_candles_only():
    data = pd.DataFrame({
        "ts": pd.date_range("2026-01-01", periods=4, freq="15min", tz="UTC"),
        "open": [100.0, 101.0, 102.0, 500.0],
        "high": [101.0, 102.0, 103.0, 600.0],
        "low": [99.0, 100.0, 101.0, 400.0],
        "close": [100.0, 101.0, 102.0, 500.0],
        "volume": [1.0, 1.0, 1.0, 1000.0],
    })
    atr = pd.Series([1.0, 1.0, 1.0, 1.0])

    snap = session_vwap_snapshot(data, pd.Timestamp("2026-01-01 00:45:00Z"), atr)

    assert round(snap["session_vwap"], 6) == 101.0
    assert snap["session_vwap"] < 200.0


def test_profit_factor_handles_no_losses():
    assert profit_factor(pd.Series([1.0, 2.0])) == float("inf")
    assert profit_factor(pd.Series([1.0, -0.5])) == 2.0


def test_apply_cost_stress_converts_bps_to_r_units():
    trades = pd.DataFrame({
        "entry": [100.0],
        "risk_price": [1.0],
        "net_r": [1.5],
    })

    stressed = apply_cost_stress(trades, fee_round_trip_bps=10.0, slippage_side_bps=5.0)

    assert stressed.iloc[0]["extra_cost_r"] == 0.2
    assert stressed.iloc[0]["net_r"] == 1.3


def test_extreme_config_matrix_includes_portfolio_variants():
    ts = pd.date_range("2026-01-01", periods=4, freq="1h", tz="UTC")
    events = pd.DataFrame({
        "exchange": ["binance"] * 4,
        "symbol": ["BTCUSDT", "ETHUSDT", "BTCUSDT", "ETHUSDT"],
        "entry_ts": ts,
        "exit_ts": ts + pd.Timedelta(hours=1),
        "bars_to_exit": [4, 4, 4, 4],
        "entry": [100.0, 100.0, 100.0, 100.0],
        "risk_price": [1.0, 1.0, 1.0, 1.0],
        "net_r": [1.0, -0.5, 1.5, -1.0],
        "setup_name": ["ny_long_neutral_reversal_ce"] * 4,
        "mtf_mode": ["range_or_transition"] * 4,
        "entry_hour_utc": [13, 13, 13, 13],
        "shock_alignment": ["no_shock"] * 4,
    })

    matrix = evaluate_extreme_config_matrix(events, ForensicsRunConfig())

    assert {"base", "aggressive", "micro_risk_tight"}.issubset(set(matrix["config"]))
    assert {"baseline", "punitive_40bps", "nightmare_60bps"}.issubset(set(matrix["scenario"]))


def test_rolling_validation_reports_windows_and_gate_status():
    ts = pd.date_range("2026-01-01", periods=80, freq="12h", tz="UTC")
    events = pd.DataFrame({
        "exchange": ["binance"] * len(ts),
        "symbol": ["BTCUSDT", "ETHUSDT"] * (len(ts) // 2),
        "entry_ts": ts,
        "exit_ts": ts + pd.Timedelta(hours=2),
        "bars_to_exit": [8] * len(ts),
        "entry": [100.0] * len(ts),
        "risk_price": [1.0] * len(ts),
        "net_r": [1.0, -0.25, 1.5, -0.5] * (len(ts) // 4),
        "setup_name": ["ny_long_neutral_reversal_ce"] * len(ts),
        "mtf_mode": ["range_or_transition"] * len(ts),
        "entry_hour_utc": [13] * len(ts),
        "shock_alignment": ["no_shock"] * len(ts),
    })

    rows = evaluate_rolling_validation(events, ForensicsRunConfig())

    assert not rows.empty
    assert {14, 30}.issubset(set(rows["window_days"]))
    assert {"base", "prop_strict"}.issubset(set(rows["config"]))
    assert rows["passed_gate"].isin([True, False]).all()


def test_failure_diagnostics_and_review_packet_use_existing_review_schema():
    ts = pd.date_range("2026-01-01", periods=6, freq="1h", tz="UTC")
    trades = pd.DataFrame({
        "exchange": ["binance"] * 6,
        "symbol": ["BTCUSDT", "BTCUSDT", "ETHUSDT", "ETHUSDT", "SOLUSDT", "SOLUSDT"],
        "tf": ["15"] * 6,
        "entry_ts": ts,
        "entry": [100.0] * 6,
        "stop": [99.0] * 6,
        "target": [102.0] * 6,
        "risk_price": [1.0] * 6,
        "net_r": [-1.0, 1.2, -0.5, 1.5, -0.2, 2.0],
        "mfe_r": [0.2, 2.2, 0.4, 3.4, 0.8, 3.2],
        "mae_r": [-1.0, -0.8, -0.6, -0.2, -0.9, -0.1],
        "hit_target": [False, True, False, True, False, True],
        "exit_reason": ["stop", "target", "expiry", "target", "expiry", "target"],
        "setup_name": ["ny_long_neutral_reversal_ce"] * 6,
        "mtf_mode": ["range_or_transition"] * 6,
        "entry_model": ["ce_retest"] * 6,
        "target_model": ["fixed_2r"] * 6,
        "management_model": ["hold_target_expiry"] * 6,
        "scenario": ["punitive_40bps"] * 3 + ["baseline"] * 3,
        "window_days": [30] * 6,
        "window_id": [1] * 3 + [2] * 3,
        "rolling_passed_gate": [False] * 3 + [True] * 3,
        "rolling_fail_reason": ["negative_return"] * 3 + ["pass"] * 3,
        "rolling_window_return_pct": [-0.01] * 3 + [0.01] * 3,
        "rolling_window_pf": [0.8] * 3 + [2.0] * 3,
        "rsi_bucket": ["neutral_mid"] * 6,
        "atr_pct_bucket": ["normal"] * 6,
        "volume_bucket": ["normal"] * 6,
        "ema_21_55_state": ["mixed"] * 6,
        "compression_state": ["expanded"] * 6,
        "shock_alignment": ["opposing_shock"] * 6,
    })

    diagnostics = diagnose_rolling_failures(trades)
    packet = build_foundation_review_packet(trades, per_bucket=2)

    assert not diagnostics.empty
    assert {"feature", "failed_avg_r", "passed_avg_r"} <= set(diagnostics.columns)
    assert {"ts", "predictor", "review_bucket", "notes_hint"} <= set(packet.columns)
    assert "punitive_failed_loser" in set(packet["review_bucket"])


def test_review_label_audit_matches_foundation_packet(tmp_path):
    labels_path = tmp_path / "review_labels.json"
    labels_path.write_text(
        """
{
  "CryptoFoundationRollingReview_BTCUSDT_15_2026-01-01T00:00:00+00:00": {
    "symbol": "BTCUSDT",
    "tf": "15",
    "entry_time": "2026-01-01T00:00:00+00:00",
    "label": "bad",
    "notes": "against trend without confirmation"
  }
}
""".strip()
    )
    packet = pd.DataFrame({
        "ts": [pd.Timestamp("2026-01-01 00:00Z")],
        "symbol": ["BTCUSDT"],
        "tf": ["15"],
        "review_bucket": ["punitive_failed_loser"],
        "setup_name": ["late_us_short_bull_flush_ce"],
        "session": ["late_us"],
    })

    audit = analyze_foundation_review_labels(packet, labels_path)

    assert len(audit) == 1
    assert audit.iloc[0]["user_label"] == "bad"
    assert "against trend" in audit.iloc[0]["user_notes"]


def test_frequency_expansion_matrix_exposes_bad_more_trades_variant():
    ts = pd.date_range("2026-01-01", periods=12, freq="1h", tz="UTC")
    events = pd.DataFrame({
        "exchange": ["binance"] * len(ts),
        "symbol": ["BTCUSDT", "ETHUSDT"] * 6,
        "entry_ts": ts,
        "exit_ts": ts + pd.Timedelta(hours=1),
        "bars_to_exit": [4] * len(ts),
        "entry": [100.0] * len(ts),
        "stop": [99.0] * len(ts),
        "target": [102.0] * len(ts),
        "risk_price": [1.0] * len(ts),
        "net_r": [1.2, -0.3, 1.0, -0.2, 1.1, -0.4, -1.0, -0.8, -0.7, -0.6, -0.5, -0.4],
        "setup_name": ["ny_long_neutral_reversal_ce"] * 6 + ["london_long_middle_local_retest"] * 6,
        "mtf_mode": ["range_or_transition"] * 6 + ["mixed"] * 6,
        "entry_hour_utc": [13] * 12,
        "structure_confirmation": ["range_unconfirmed"] * 12,
        "ema_21_55_state": ["bullish"] * 6 + ["mixed"] * 6,
        "local_ema_state": ["bullish"] * 12,
        "shock_alignment": ["no_shock"] * 12,
        "hit_stop": [False, False, False, False, False, False, True, True, True, True, True, True],
        "exit_reason": ["target"] * 6 + ["stop"] * 6,
    })

    masks = frequency_variant_masks(events)
    matrix = evaluate_frequency_expansion(events, ForensicsRunConfig())

    assert "ny_london_plus_non_strict_confirmed" in masks
    assert "strict_current" in set(matrix["variant"])
    bad_rows = matrix[matrix["variant"] == "ny_london_plus_non_strict_confirmed"]
    assert not bad_rows.empty
    assert "reject_more_trades_break_edge" in set(bad_rows["frequency_verdict"])


def test_direction_audit_summarizes_structure_and_vwap_layers():
    ts = pd.date_range("2026-01-01", periods=8, freq="1h", tz="UTC")
    events = pd.DataFrame({
        "exchange": ["binance"] * len(ts),
        "symbol": ["BTCUSDT", "ETHUSDT"] * 4,
        "entry_ts": ts,
        "exit_ts": ts + pd.Timedelta(hours=1),
        "bars_to_exit": [4] * len(ts),
        "entry": [100.0] * len(ts),
        "risk_price": [1.0] * len(ts),
        "net_r": [1.0, 1.2, -0.5, 1.4, -1.0, 1.5, 0.5, -0.4],
        "direction": ["long", "long", "short", "long", "short", "long", "short", "short"],
        "setup_name": ["ny_long_neutral_reversal_ce"] * len(ts),
        "mtf_mode": ["range_or_transition"] * len(ts),
        "entry_hour_utc": [13] * len(ts),
        "structure_confirmation": ["range_unconfirmed"] * len(ts),
        "context_regime": ["neutral"] * len(ts),
        "middle_regime": ["neutral"] * len(ts),
        "local_regime": ["bull", "bull", "bear", "bull", "bear", "bull", "bear", "bear"],
        "global_ema_state": ["mixed"] * len(ts),
        "middle_ema_state": ["mixed"] * len(ts),
        "local_ema_state": ["bullish", "bullish", "bearish", "bullish", "bearish", "bullish", "bearish", "bearish"],
        "ema_21_55_state": ["mixed"] * len(ts),
        "session_vwap_state": ["above", "above", "below", "above", "below", "above", "below", "below"],
        "session_vwap_extension": ["normal"] * len(ts),
        "vwap_direction_agreement": ["agrees"] * len(ts),
        "compression_state": ["normal"] * len(ts),
        "shock_alignment": ["no_shock"] * len(ts),
        "direction_correct": [True, True, False, True, False, True, True, False],
        "bad_direction": [False, False, True, False, True, False, False, True],
        "bad_entry": [False] * len(ts),
        "hit_stop": [False, False, True, False, True, False, False, True],
        "exit_reason": ["target", "target", "stop", "target", "stop", "target", "expiry", "stop"],
        "mfe_r": [2.0] * len(ts),
        "mae_r": [-0.5] * len(ts),
    })

    audit = evaluate_direction_audit(events, min_events=2)

    assert {"direction_stack", "session_vwap_state", "vwap_direction_agreement"} <= set(audit["feature"])
    assert set(audit["scope"]) == {"all_physical", "strict"}


def test_contribution_concentration_reports_symbol_and_setup_share():
    ts = pd.date_range("2026-01-01", periods=6, freq="1h", tz="UTC")
    events = pd.DataFrame({
        "exchange": ["binance"] * 6,
        "symbol": ["BTCUSDT", "ETHUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT", "SOLUSDT"],
        "entry_ts": ts,
        "exit_ts": ts + pd.Timedelta(hours=1),
        "bars_to_exit": [4] * 6,
        "entry": [100.0] * 6,
        "risk_price": [1.0] * 6,
        "net_r": [1.5, 1.0, -0.5, 2.0, -1.0, 1.25],
        "setup_name": ["ny_long_neutral_reversal_ce"] * 6,
        "mtf_mode": ["range_or_transition"] * 6,
        "entry_hour_utc": [13] * 6,
        "session_utc": ["ny"] * 6,
        "shock_alignment": ["no_shock"] * 6,
    })

    concentration = evaluate_contribution_concentration(events)

    assert not concentration.empty
    assert {"symbol", "setup_name", "session_utc"} <= set(concentration["dimension"])
    assert "share_of_total_r" in concentration.columns
