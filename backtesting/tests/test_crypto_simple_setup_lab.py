from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtesting.crypto.simple_setup_lab import (
    SimpleSetupConfig,
    apply_trade_filters,
    asof_structure_row,
    build_candidate_feature_table,
    build_candidate_filter_diagnostics,
    build_full_review_packet,
    continuation_reclaim_signal,
    delayed_context_signal,
    daily_first_context_signal,
    direction_context,
    dmi_alignment,
    dataframe_to_markdown,
    exit_kind,
    profit_factor,
    primary_daily_blocker,
    rolling_window_summary,
    run_portfolio_validation,
    session_bucket,
    setup_signal,
    micro_reclaim_context_signal,
    output_suffix,
    structure_confirmed_context_signal,
    summarize_trades,
    summarize_windows,
    write_candidate_filter_report,
    write_frequency_report,
)


def test_setup_signal_context_change_fires_only_on_fresh_direction():
    bars = pd.DataFrame({"close": [100, 101, 102, 103]})
    combo = np.array(["neutral", "bull", "bull", "bear"])

    signal = setup_signal(bars, combo, "context_change")

    assert signal.tolist() == [False, True, False, True]


def test_delayed_context_signal_waits_for_context_to_hold():
    combo = pd.Series(["neutral", "bull", "bull", "bear", "bear", "bear"])

    signal = delayed_context_signal(combo, delay_bars=2)

    assert signal.tolist() == [False, False, False, False, False, True]


def test_daily_first_context_signal_fires_once_per_active_day():
    bars = pd.DataFrame(
        {
            "ts": pd.to_datetime(
                [
                    "2026-01-01T00:00Z",
                    "2026-01-01T00:15Z",
                    "2026-01-01T00:30Z",
                    "2026-01-02T00:00Z",
                    "2026-01-02T00:15Z",
                ]
            )
        }
    )
    combo = pd.Series(["neutral", "bull", "bull", "bull", "bear"])

    signal = daily_first_context_signal(bars, combo)

    assert signal.tolist() == [False, True, False, True, False]


def test_micro_reclaim_context_requires_reclaim_and_recent_structure():
    bars = pd.DataFrame(
        {
            "close": [100, 99, 98, 99, 101, 102, 103] + [104] * 60,
            "high": [101, 100, 99, 100, 102, 103, 104] + [105] * 60,
            "low": [99, 98, 97, 98, 99, 101, 102] + [103] * 60,
        }
    )
    combo = pd.Series(["bull"] * len(bars))
    structure = pd.DataFrame(
        {
            "bos_up": [False, False, True, False, False, False, False] + [False] * 60,
            "choch_up": [False] * len(bars),
            "bos_down": [False] * len(bars),
            "choch_down": [False] * len(bars),
        }
    )

    signal = micro_reclaim_context_signal(bars, combo, structure, confirm_lookback=5)

    assert signal.any()


def test_continuation_reclaim_waits_for_mature_context_and_same_direction_bos():
    bars = pd.DataFrame(
        {
            "close": [100, 101, 102, 100, 99, 103, 104],
            "high": [101, 102, 103, 101, 100, 104, 105],
            "low": [99, 100, 101, 99, 98, 102, 103],
        }
    )
    combo = pd.Series(["neutral", "bull", "bull", "bull", "bull", "bull", "bull"])
    structure = pd.DataFrame(
        {
            "regime": ["neutral", "bull", "bull", "bull", "bull", "bull", "bull"],
            "bos_up": [False, False, True, False, False, False, False],
            "bos_down": [False] * len(bars),
            "choch_up": [False] * len(bars),
            "choch_down": [False] * len(bars),
        }
    )

    signal = continuation_reclaim_signal(bars, combo, structure, confirm_lookback=4, pullback_lookback=3)

    assert signal.tolist() == [False, False, False, False, False, True, False]


def test_continuation_reclaim_blocks_recent_opposite_choch():
    bars = pd.DataFrame(
        {
            "close": [100, 101, 102, 100, 99, 103],
            "high": [101, 102, 103, 101, 100, 104],
            "low": [99, 100, 101, 99, 98, 102],
        }
    )
    combo = pd.Series(["neutral", "bull", "bull", "bull", "bull", "bull"])
    structure = pd.DataFrame(
        {
            "regime": ["neutral", "bull", "bull", "bull", "bull", "bull"],
            "bos_up": [False, False, True, False, False, False],
            "bos_down": [False] * len(bars),
            "choch_up": [False] * len(bars),
            "choch_down": [False, False, False, False, True, False],
        }
    )

    signal = continuation_reclaim_signal(bars, combo, structure, confirm_lookback=4, pullback_lookback=3)

    assert not signal.any()


def test_asof_structure_row_returns_latest_known_row():
    structure = pd.DataFrame(
        {
            "ts": pd.to_datetime(["2026-01-01T00:00Z", "2026-01-01T00:15Z", "2026-01-01T00:30Z"]),
            "long_structural_sl": [90.0, 95.0, 80.0],
        }
    )

    row = asof_structure_row(structure, pd.Timestamp("2026-01-01T00:16Z"))

    assert row is not None
    assert row["long_structural_sl"] == 95.0


def test_direction_context_htf_only_ignores_entry_ema_disagreement(monkeypatch):
    coarse = pd.DataFrame({"ts": pd.to_datetime(["2026-01-01T00:00Z"]), "direction": ["bull"]})
    entry = pd.DataFrame({"ts": pd.to_datetime(["2026-01-01T00:15Z"]), "close": [100.0]})

    monkeypatch.setattr("backtesting.crypto.simple_setup_lab.structure_ema_direction", lambda bars, **kwargs: coarse)
    monkeypatch.setattr("backtesting.crypto.simple_setup_lab.vec_ema_state", lambda bars: pd.Series(["bearish"]))

    assert direction_context(pd.DataFrame(), pd.DataFrame(), entry, mode="strict").tolist() == ["neutral"]
    assert direction_context(pd.DataFrame(), pd.DataFrame(), entry, mode="htf_only").tolist() == ["bull"]


def test_structure_confirmed_context_waits_for_same_direction_bos_after_context_change():
    combo = pd.Series(["neutral", "bull", "bull", "bull", "bull", "bear", "bear"])
    structure = pd.DataFrame(
        {
            "regime": ["neutral", "neutral", "bull", "bull", "bull", "bear", "bear"],
            "bos_up": [False, False, True, False, False, False, False],
            "bos_down": [False, False, False, False, False, True, False],
            "choch_up": [False] * 7,
            "choch_down": [False, False, False, True, False, False, False],
        }
    )

    signal = structure_confirmed_context_signal(combo, structure, context_lookback=3, confirm_lookback=2)

    assert signal.tolist() == [False, False, True, False, False, False, True]


def test_structure_confirmed_context_blocks_after_opposing_choch():
    combo = pd.Series(["neutral", "bull", "bull", "bull"])
    structure = pd.DataFrame(
        {
            "regime": ["neutral", "neutral", "bull", "bull"],
            "bos_up": [False, False, True, True],
            "bos_down": [False] * 4,
            "choch_up": [False] * 4,
            "choch_down": [False, False, True, False],
        }
    )

    signal = structure_confirmed_context_signal(combo, structure, context_lookback=3, confirm_lookback=2)

    assert not signal.any()


def test_setup_signal_pullback_reclaim_requires_existing_context_and_ema_reclaim():
    bars = pd.DataFrame(
        {
            "close": [100, 100, 100, 100, 99, 101, 102],
            "high": [101, 101, 101, 101, 100, 102, 103],
            "low": [99, 99, 99, 99, 98, 100, 101],
        }
    )
    combo = np.array(["bull"] * len(bars))

    signal = setup_signal(bars, combo, "pullback_reclaim")

    assert signal.sum() == 1
    assert np.where(signal)[0][0] > 0


def test_setup_signal_rejects_unknown_setup():
    with pytest.raises(ValueError):
        setup_signal(pd.DataFrame({"close": [1, 2, 3]}), np.array(["bull", "bull", "bull"]), "bad")


def test_profit_factor_and_exit_kind():
    assert profit_factor(np.array([1.0, 2.0, -1.0])) == 3.0
    assert exit_kind(1.5) == "target"
    assert exit_kind(-1.0) == "stop"
    assert exit_kind(0.0) == "expiry"
    assert dmi_alignment("long", 30.0, 20.0) == "aligned"
    assert dmi_alignment("short", 30.0, 20.0) == "opposed"


def test_summarize_trades_reports_cost_fragility_fields():
    trades = pd.DataFrame(
        {
            "setup": ["pullback_reclaim", "pullback_reclaim"],
            "symbol": ["BTCUSDT", "BTCUSDT"],
            "base_net_r": [1.4, -1.2],
            "stress_net_r": [0.8, -1.8],
            "gross_r": [1.5, -1.0],
            "stop_pct": [0.5, 0.3],
            "planned_rr": [1.5, 1.5],
            "base_cost_r": [0.1, 0.2],
            "stress_cost_r": [0.7, 0.8],
            "exit_kind": ["target", "stop"],
            "mfe_r": [1.6, 0.4],
            "mae_r": [-0.2, -1.0],
            "trend_strength": ["trend", "transition"],
            "consolidation_state": ["directional", "transition"],
            "shock_alignment": ["no_shock", "aligned_shock"],
            "dmi_alignment": ["aligned", "opposed"],
        }
    )

    summary = summarize_trades(trades)

    assert {"base_avg_r", "base_pf", "stress_avg_r", "median_base_cost_r"}.issubset(summary.columns)
    assert summary.iloc[0]["trades"] == 2
    assert summary.iloc[0]["median_stop_pct"] == 0.4
    assert summary.iloc[0]["top_trend_strength"] == "transition"


def test_apply_trade_filters_cost_and_session_gate():
    trades = pd.DataFrame(
        {
            "base_cost_r": [0.10, 0.20, 0.10],
            "stress_cost_r": [0.30, 0.40, 0.60],
            "session_utc": ["ny", "ny", "late_us"],
            "trend_strength": ["trend", "weak_or_range", "trend"],
            "consolidation_state": ["directional", "range", "directional"],
            "shock_alignment": ["no_shock", "no_shock", "opposing_shock"],
            "dmi_alignment": ["aligned", "opposed", "aligned"],
        }
    )
    cfg = SimpleSetupConfig(
        max_base_cost_r=0.15,
        max_stress_cost_r=0.50,
        sessions=("ny",),
        trend_strengths=("trend",),
        consolidation_states=("directional",),
        shock_alignments=("no_shock",),
        dmi_alignments=("aligned",),
    )

    out = apply_trade_filters(trades, cfg)

    assert len(out) == 1
    assert out.iloc[0]["base_cost_r"] == 0.10


def test_asof_structure_row_uses_known_after_ts_when_available():
    structure = pd.DataFrame(
        {
            "ts": pd.to_datetime(["2026-01-01T00:00Z", "2026-01-01T00:15Z"]),
            "known_after_ts": pd.to_datetime(["2026-01-01T00:15Z", "2026-01-01T00:30Z"]),
            "regime": ["bull", "bear"],
        }
    )

    early = asof_structure_row(structure, pd.Timestamp("2026-01-01T00:14Z"))
    at_first_confirm = asof_structure_row(structure, pd.Timestamp("2026-01-01T00:15Z"))
    before_second_confirm = asof_structure_row(structure, pd.Timestamp("2026-01-01T00:29Z"))

    assert early is None
    assert at_first_confirm["regime"] == "bull"
    assert before_second_confirm["regime"] == "bull"


def test_output_suffix_records_non_default_structure_window():
    cfg = SimpleSetupConfig(
        structure_left=8,
        structure_right=8,
        context_structure_left=5,
        context_structure_right=5,
    )

    suffix = output_suffix("context_change", cfg)

    assert "structL8R8" in suffix
    assert "ctxL5R5" in suffix


def test_apply_trade_filters_can_cap_stale_wide_stops():
    trades = pd.DataFrame(
        {
            "base_cost_r": [0.01, 0.01],
            "stress_cost_r": [0.02, 0.02],
            "stop_pct": [1.0, 12.0],
        }
    )
    cfg = SimpleSetupConfig(max_stop_pct=2.0)

    out = apply_trade_filters(trades, cfg)

    assert out["stop_pct"].tolist() == [1.0]


def test_rolling_window_summary_and_summary_windows():
    trades = pd.DataFrame(
        {
            "entry_ts": pd.to_datetime(
                ["2026-01-01T00:00Z", "2026-01-05T00:00Z", "2026-01-20T00:00Z", "2026-02-05T00:00Z"]
            ),
            "base_net_r": [1.0, -0.5, 0.5, -1.0],
            "stress_net_r": [0.5, -0.8, 0.2, -1.2],
            "stop_pct": [0.5, 0.6, 0.7, 0.8],
        }
    )

    windows = rolling_window_summary(trades, window_days=30, step_days=15, min_trades=1)
    summary = summarize_windows(windows)

    assert not windows.empty
    assert {"base_pf", "stress_pf", "base_return_r"}.issubset(windows.columns)
    assert summary.iloc[0]["windows"] == len(windows)


def test_run_portfolio_validation_converts_simple_lab_trades_to_risk_path():
    trades = pd.DataFrame(
        {
            "entry_ts": pd.to_datetime(["2026-01-01T00:00Z", "2026-01-01T00:15Z", "2026-01-01T01:30Z"]),
            "symbol": ["BTCUSDT", "ETHUSDT", "BTCUSDT"],
            "setup": ["context_change"] * 3,
            "entry": [100.0, 100.0, 100.0],
            "sl": [99.0, 99.0, 99.0],
            "tp": [102.0, 102.0, 102.0],
            "planned_rr": [2.0, 2.0, 2.0],
            "bars_to_exit": [4, 4, 1],
            "exit_kind": ["target", "stop", "target"],
            "stress_net_r": [2.0, -1.0, 2.0],
        }
    )

    accepted, summary = run_portfolio_validation(
        trades,
        net_column="stress_net_r",
        risk_pct=0.01,
        max_open=1,
        max_open_per_symbol=1,
        daily_loss_limit_pct=1.0,
        cooldown_after_loss_bars=0,
    )

    assert len(accepted) < len(trades)
    assert summary["accepted"] == len(accepted)
    assert summary["risk_per_trade_pct"] == 0.01


def test_build_full_review_packet_exports_every_accepted_trade(tmp_path):
    accepted = pd.DataFrame(
        {
            "entry_ts": pd.to_datetime(["2026-01-01T00:00Z", "2026-01-02T00:00Z"]),
            "exit_ts": pd.to_datetime(["2026-01-01T01:00Z", "2026-01-02T00:30Z"]),
            "symbol": ["BTCUSDT", "ETHUSDT"],
            "exchange": ["binance", "binance"],
            "setup": ["context_change", "context_change"],
            "direction": ["long", "short"],
            "session_utc": ["asia", "ny"],
            "entry": [100.0, 200.0],
            "stop": [99.0, 202.0],
            "target": [102.0, 196.0],
            "planned_rr": [2.0, 2.0],
            "bars_to_exit": [4, 2],
            "net_r": [1.8, -1.2],
            "pnl_pct": [0.0036, -0.0024],
            "risk_per_trade_pct": [0.002, 0.002],
            "mfe_r": [2.0, 0.3],
            "mae_r": [-0.2, -1.0],
            "exit_reason": ["target", "stop"],
            "trend_strength": ["trend", "transition"],
            "consolidation_state": ["directional", "range"],
            "shock_alignment": ["no_shock", "no_shock"],
            "compression_state": ["normal", "normal"],
            "dmi_alignment": ["aligned", "opposed"],
            "base_net_r": [1.9, -1.1],
            "stress_net_r": [1.8, -1.2],
        }
    )
    output = tmp_path / "full_review.csv"

    packet = build_full_review_packet(accepted, output_path=output, target_r=2.0)

    assert len(packet) == 2
    assert output.exists()
    assert (tmp_path / "full_review_BTCUSDT.csv").exists()
    assert {"ts", "exit_ts", "outcome_2r", "return_pct", "review_bucket", "notes_hint"} <= set(packet.columns)
    assert packet["review_bucket"].eq("accepted_trade").all()


def test_build_candidate_feature_table_exports_labels(tmp_path):
    trades = pd.DataFrame(
        {
            "entry_ts": pd.to_datetime(["2026-01-01T08:00Z", "2026-01-02T13:00Z"]),
            "symbol": ["ETHUSDT", "SOLUSDT"],
            "setup": ["context_change", "context_change"],
            "direction": ["long", "short"],
            "session_utc": ["london", "ny"],
            "stop_pct": [0.8, 1.2],
            "target_pct": [1.6, 2.4],
            "planned_rr": [2.0, 2.0],
            "base_cost_r": [0.05, 0.08],
            "stress_cost_r": [0.18, 0.24],
            "mfe_r": [2.1, 0.4],
            "mae_r": [-0.3, -1.0],
            "bars_to_exit": [10, 12],
            "trend_strength": ["trend", "transition"],
            "consolidation_state": ["directional", "range"],
            "shock_alignment": ["no_shock", "no_shock"],
            "compression_state": ["normal", "compressed"],
            "dmi_alignment": ["aligned", "opposed"],
            "adx_14": [22.0, 18.0],
            "pre_range_atr_16": [1.1, 0.9],
            "plus_di_14": [30.0, 20.0],
            "minus_di_14": [18.0, 25.0],
            "exit_kind": ["target", "stop"],
            "stress_net_r": [1.8, -1.2],
        }
    )

    table = build_candidate_feature_table(trades, output_path=tmp_path / "features.csv")

    assert table["label_target"].tolist() == [True, False]
    assert table["label_positive_stress_r"].tolist() == [True, False]
    assert table["label_mfe_ge_2r"].tolist() == [True, False]
    assert (tmp_path / "features.csv").exists()


def test_candidate_filter_diagnostics_ranks_good_and_bad_buckets(tmp_path):
    features = pd.DataFrame(
        {
            "entry_ts": pd.to_datetime([f"2026-01-{day:02d}T08:00Z" for day in range(1, 9)]),
            "setup": ["context_change"] * 8,
            "symbol": ["ETHUSDT"] * 4 + ["DOGEUSDT"] * 4,
            "direction": ["long"] * 8,
            "session_utc": ["london"] * 8,
            "hour_utc": [8] * 8,
            "day_of_week": [1] * 8,
            "stop_pct": [0.8] * 8,
            "target_pct": [1.6] * 8,
            "planned_rr": [2.0] * 8,
            "base_cost_r": [0.05] * 8,
            "stress_cost_r": [0.15] * 8,
            "mfe_r": [2.1, 2.2, 1.8, 2.5, 0.3, 0.4, 0.5, 0.6],
            "mae_r": [-0.2, -0.3, -0.4, -0.2, -1.0, -1.1, -1.0, -1.2],
            "bars_to_exit": [10] * 8,
            "trend_strength": ["trend"] * 8,
            "consolidation_state": ["directional"] * 8,
            "shock_alignment": ["no_shock"] * 8,
            "compression_state": ["normal"] * 8,
            "dmi_alignment": ["aligned"] * 8,
            "adx_14": [26.0] * 8,
            "pre_range_atr_16": [1.5] * 8,
            "label_target": [True, True, True, True, False, False, False, False],
            "label_stop": [False, False, False, False, True, True, True, True],
            "label_expiry": [False] * 8,
            "label_positive_stress_r": [True, True, True, True, False, False, False, False],
            "label_mfe_ge_1r": [True, True, True, True, False, False, False, False],
            "label_mfe_ge_2r": [True, True, False, True, False, False, False, False],
            "outcome_stress_net_r": [1.8, 1.7, 1.9, 1.6, -1.2, -1.1, -1.3, -1.0],
        }
    )

    diagnostics = build_candidate_filter_diagnostics(features, min_count=3)
    write_candidate_filter_report(features, tmp_path / "feature_report.md", min_count=3)

    assert "symbol=ETHUSDT" in diagnostics["good_buckets"]["bucket"].tolist()
    assert "symbol=DOGEUSDT" in diagnostics["bad_buckets"]["bucket"].tolist()
    assert (tmp_path / "feature_report.md").exists()


def test_dataframe_to_markdown_escapes_pipe_values():
    text = dataframe_to_markdown(pd.DataFrame({"bucket": ["symbol=ETHUSDT | session_utc=asia"]}))

    assert "\\|" in text


def test_primary_daily_blocker_explains_untraded_days():
    assert primary_daily_blocker(pd.Series({"portfolio_accepted": 1})) == "traded"
    assert primary_daily_blocker(pd.Series({"portfolio_accepted": 0, "pre_portfolio_pass": 2})) == "portfolio_throttle"
    assert primary_daily_blocker(pd.Series({"raw_signals": 0, "active_context_bars": 12})) == "no_setup_signal"
    assert primary_daily_blocker(pd.Series({"raw_signals": 0, "active_context_bars": 0})) == "no_active_context"
    assert primary_daily_blocker(pd.Series({"raw_signals": 2, "blocked_cost": 1, "blocked_context": 0})) == "blocked_cost"


def test_write_frequency_report_outputs_blocker_summary(tmp_path):
    daily = pd.DataFrame(
        {
            "symbol": ["ETHUSDT", "ETHUSDT"],
            "day": [pd.Timestamp("2026-01-01").date(), pd.Timestamp("2026-01-02").date()],
            "primary_blocker": ["traded", "no_setup_signal"],
            "active_context_bars": [20, 10],
            "raw_signals": [2, 0],
            "pre_portfolio_pass": [1, 0],
            "portfolio_accepted": [1, 0],
        }
    )
    output = tmp_path / "freq.md"

    write_frequency_report(daily, output)

    text = output.read_text()
    assert "Frequency Audit" in text
    assert "no_setup_signal" in text


def test_session_bucket_uses_utc_pseudo_sessions():
    assert session_bucket(pd.Timestamp("2026-01-01T03:00:00Z")) == "asia"
    assert session_bucket(pd.Timestamp("2026-01-01T08:00:00Z")) == "london"
    assert session_bucket(pd.Timestamp("2026-01-01T13:00:00Z")) == "ny"
    assert session_bucket(pd.Timestamp("2026-01-01T20:00:00Z")) == "late_us"
