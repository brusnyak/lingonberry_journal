"""
Candle pattern detection and testing (v2 — clean research foundation).

Packages:
    registry   — PatternRegistry singleton, @register decorator
    candle     — Single-bar patterns (doji, hammer, pin bar, etc.)
    multi_bar  — Multi-bar patterns (engulfing, harami, star, etc.)
    pipeline   — Batch extraction across assets and timeframes

Usage:
    from backtesting.features_v2 import registry
    from backtesting.features_v2 import candle, multi_bar
    registry.run("doji", open, high, low, close)
"""

from backtesting.features_v2.registry import registry

# ── Import pattern modules so their @register decorators fire ──
from backtesting.features_v2 import candle  # noqa: F401
from backtesting.features_v2 import multi_bar  # noqa: F401

# ── Populate research metadata from literature survey ────────────────────────
registry.set_research("doji",
    literature_ref="Wangchailert 2025 (MIDDAM); MDPI 2020",
    notes="Tier 1: unreliable on forex. 42% WR, -0.12R expectancy. Deprioritize.")
registry.set_research("hammer",
    accuracy_pct=62.0, pairs_tested=["EURUSD", "GBPUSD", "NQ"],
    literature_ref="Bulkowski 2012; MT5 Guide 2026",
    notes="Tier 2: 62% WR, 2.5R target. High variance across instruments. Needs S/R context.")
registry.set_research("shooting_star",
    accuracy_pct=55.0, horizon=10,
    pairs_tested=["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDJPY", "USDCHF", "USDCAD"],
    literature_ref="SMART Trading Strategies 2026; Bulkowski 2012",
    notes="Tier 2: most promising single pattern but not stat. significant vs random. 55% WR.")
registry.set_research("pin_bar",
    accuracy_pct=60.0,
    literature_ref="Bulkowski 2012",
    notes="Tier 2: 60-70% at key S/R levels. Context-dependent.")
registry.set_research("marubozu",
    literature_ref="Bulkowski 2012; IEEE Access 2021",
    notes="Tier 2: continuation signal. Part of >60% predictive pattern set. Tall candle bias.")
registry.set_research("spinning_top",
    notes="Tier 2: indecision pattern, neutral by design. 0-signal context marker only.")
registry.set_research("bullish_engulfing",
    accuracy_pct=79.0,
    pairs_tested=["EURUSD", "USDJPY", "SPY"],
    literature_ref="Bulkowski 2012 (79% reversal); QuantifiedStrategies 2024 (74% WR, 5.37% CAR)",
    notes="Tier 1-2: best multi-study performer. 58% WR on EURUSD, 79% reversal rate per Bulkowski.")
registry.set_research("bearish_engulfing",
    accuracy_pct=79.0,
    literature_ref="Bulkowski 2012 (79% reversal); QuantifiedStrategies 2024 (70%+ WR by D17)",
    notes="Tier 1-2: mirror of bullish engulfing. Strong reversal signal.")
registry.set_research("bullish_harami",
    accuracy_pct=52.0,
    literature_ref="Shinde 2026; FXNX 2024",
    notes="Tier 2-3: 50-52% WR, often just a pause. Only pattern that held cross-instrument (Shinde).")
registry.set_research("bearish_harami",
    accuracy_pct=52.0,
    literature_ref="Shinde 2026; FXNX 2024",
    notes="Tier 2-3: 50-52% WR. Mirror of bullish harami. Secondary signal.")
registry.set_research("piercing",
    accuracy_pct=60.0, horizon=19,
    literature_ref="QuantifiedStrategies 2024 (PF 1.60, CAR 4.38 at 19d)",
    notes="Tier 3: good at 19d horizon. Weaker version of bullish engulfing.")
registry.set_research("dark_cloud_cover",
    accuracy_pct=71.5, horizon=19,
    literature_ref="QuantifiedStrategies 2024 (71.52% WR at 19d)",
    notes="Tier 3: peaks at 71.5% WR at 19d. Strong for swing trading.")
registry.set_research("morning_star",
    accuracy_pct=60.0, horizon=10,
    pairs_tested=["EURUSD", "GBPUSD", "USDJPY"],
    literature_ref="Bulkowski 2012; FXNX 2024 (55-60% WR); fxscanner 2024 (65% live)",
    notes="Tier 2: complete sentiment cycle. Consistent 55-65% WR. High priority.")
registry.set_research("evening_star",
    accuracy_pct=72.0,
    literature_ref="Bulkowski 2012 (#4 overall, 72% bearish reversal); FXNX 2024 (55-60%)",
    notes="Tier 2: #4 performer per Bulkowski. Mirror of morning star.")
registry.set_research("three_soldiers",
    accuracy_pct=65.0,
    literature_ref="Bulkowski 2012; QuantifiedStrategies 2024",
    notes="Tier 2-3: continuation bias. Three Inside Up (related) has highest PF=2.5.")
registry.set_research("three_crows",
    accuracy_pct=78.0,
    literature_ref="Bulkowski 2012 (#3 overall, 78% bearish reversal)",
    notes="Tier 2: #3 performer per Bulkowski. Strong bearish signal.")
registry.set_research("inside_bar",
    literature_ref="Bulkowski 2012",
    notes="Tier 2: volatility contraction. Breakout direction signal. Needs S/R context.")
# ── End research metadata ────────────────────────────────────────────────────
