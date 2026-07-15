from __future__ import annotations

from backtesting.crypto.session_range_setup_lab import SessionRangeConfig, output_suffix, session_range_signal


def test_session_range_signal_breakout_direction():
    assert session_range_signal(
        mode="breakout",
        close=102.0,
        ref_high=100.0,
        ref_low=95.0,
        ref_mid=97.5,
        atr=2.0,
        swept_high=False,
        swept_low=False,
        breakout_buffer_atr=0.25,
        reclaim_buffer_atr=0.0,
    ) == "long"
    assert session_range_signal(
        mode="breakout",
        close=94.0,
        ref_high=100.0,
        ref_low=95.0,
        ref_mid=97.5,
        atr=2.0,
        swept_high=False,
        swept_low=False,
        breakout_buffer_atr=0.25,
        reclaim_buffer_atr=0.0,
    ) == "short"


def test_session_range_signal_fakeout_requires_sweep_and_mid_reclaim():
    assert session_range_signal(
        mode="fakeout",
        close=97.0,
        ref_high=100.0,
        ref_low=95.0,
        ref_mid=97.5,
        atr=2.0,
        swept_high=True,
        swept_low=False,
        breakout_buffer_atr=0.25,
        reclaim_buffer_atr=0.0,
    ) == "short"
    assert session_range_signal(
        mode="fakeout",
        close=98.0,
        ref_high=100.0,
        ref_low=95.0,
        ref_mid=97.5,
        atr=2.0,
        swept_high=True,
        swept_low=False,
        breakout_buffer_atr=0.25,
        reclaim_buffer_atr=0.0,
    ) is None


def test_output_suffix_records_session_range_config():
    cfg = SessionRangeConfig(
        setup="ny_london_breakout",
        min_reference_range_atr=1.0,
        max_reference_range_atr=4.0,
        stress_round_trip_pct=0.004,
    )

    suffix = output_suffix(cfg)

    assert "ny_london_breakout" in suffix
    assert "ref1-4" in suffix
    assert "stressfee0p004" in suffix
