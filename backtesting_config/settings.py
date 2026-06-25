"""Central configuration — GFT accounts, pairs, timeframes, risk."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal

# ──────────────────────────────────────────────
# GFT Account Rules
# ──────────────────────────────────────────────

GFT_RULES_25K_PRO = {
    "name": "25k Pro 2-Step",
    "initial_balance": 25_000,
    "phase1_target": 0.08,  # 8% = $2,000
    "phase2_target": 0.05,  # 5% = $1,250
    "daily_dd": 0.05,  # 5% balance-based
    "max_loss": 0.10,  # 10% static → floor at $22,500
    "min_days_per_phase": 3,
    "min_profit_day_pct": 0.005,  # 0.5% = $125
}

GFT_RULES_100K_1STEP = {
    "name": "100k 1-Step",
    "initial_balance": 100_000,
    "phase1_target": 0.10,  # 10% = $10,000
    "phase2_target": None,  # single phase
    "daily_dd": 0.04,  # 4% balance-based
    "max_loss": 0.06,  # 6% static → floor at $94,000
    "min_days_per_phase": 3,
    "min_profit_day_pct": None,
}

# ──────────────────────────────────────────────
# Tradeable Instruments
# ──────────────────────────────────────────────

@dataclass
class PairConfig:
    symbol: str                     # TradeLocker name (e.g. "EURUSD", "XAUUSD")
    name: str                       # Human-readable label
    # Timeframe resolutions available on TradeLocker:
    # 1M, 1W, 1D, 4H, 1H, 30m, 15m, 5m, 1m
    # (3m is NOT available — use 5m for LTF)
    htf_resolution: str = "4H"      # Directional bias / sentiment
    mtf_resolution: str = "30m"     # Structure / OB / FVG zones
    mtf2_resolution: str = "15m"    # Finer structure / liquidity
    ltf_resolution: str = "5m"      # Entry confirmation (BOS/CHoCH)

    # SMC swing_lengths (passed to smc.swing_highs_lows which DOUBLES internally)
    # 4h:  swing=7  → effective 14 candles (~2.3 days)
    # 30m: swing=10 → effective 20 candles (10 hours)
    # 15m: swing=8  → effective 16 candles (4 hours)
    # 5m:  swing=4  → effective 9 candles (45 min) — LTF entry
    htf_swing_length: int = 7
    mtf_swing_length: int = 10
    mtf2_swing_length: int = 8
    ltf_swing_length: int = 4

    min_rr: float = 2.0
    min_score: float = 60.0

PAIRS: list[PairConfig] = [
    PairConfig(symbol="EURUSD.X", name="EUR/USD"),
    PairConfig(symbol="GBPUSD.X", name="GBP/USD"),
    PairConfig(symbol="GBPAUD.X", name="GBP/AUD"),
    PairConfig(symbol="GBPCAD.X", name="GBP/CAD"),
    PairConfig(symbol="XAUUSD.X", name="Gold"),
]

# Mean-reversion pairs (used by run_backtest.py by default)
MR_PAIRS: list[str] = ["GBPUSD.X", "GBPAUD.X", "GBPCAD.X", "EURUSD.X"]

# ──────────────────────────────────────────────
# Risk Per Account
# ──────────────────────────────────────────────

@dataclass
class RiskRule:
    account_name: str
    initial_balance: float
    max_daily_loss_pct: float
    max_overall_loss_pct: float
    risk_per_trade_pct: float = 0.01
    max_positions: int = 1
    default_leverage: int = 50

RISK_RULES: list[RiskRule] = [
    RiskRule(
        account_name="25k Pro",
        initial_balance=25_000,
        max_daily_loss_pct=GFT_RULES_25K_PRO["daily_dd"],
        max_overall_loss_pct=GFT_RULES_25K_PRO["max_loss"],
    ),
    RiskRule(
        account_name="100k 1-Step",
        initial_balance=100_000,
        risk_per_trade_pct=0.005,
        max_daily_loss_pct=GFT_RULES_100K_1STEP["daily_dd"],
        max_overall_loss_pct=GFT_RULES_100K_1STEP["max_loss"],
    ),
]

# ──────────────────────────────────────────────
# Sessions / Kill Zones (UTC) — ICT standard
# ──────────────────────────────────────────────

KILL_ZONES = {
    "asian":     {"start": "00:00", "end": "06:00", "desc": "Asian range"},
    "london":    {"start": "07:00", "end": "16:00", "desc": "London open — manipulation"},
    "new_york":  {"start": "12:00", "end": "21:00", "desc": "NY open — distribution"},
}

# ──────────────────────────────────────────────
# Scanner
# ──────────────────────────────────────────────

SCAN_INTERVAL_MINUTES: int = int(os.getenv("SCAN_INTERVAL_MINUTES", "5"))

# LTF confirmation thresholds (5m candles)
LTF_CONF_BASE_SCORE = 40
LTF_RECENCY_BONUS = 15       # Max points for most recent signal
LTF_VOLUME_SPIKE_THRESHOLD = 1.5
LTF_VOLUME_BONUS = 10
LTF_LOOKBACK_CANDLES = 16    # Check last N 5m candles (~80 min)
LTF_MIN_SCORE = 40

# ──────────────────────────────────────────────
# Confluence scoring weights (max 100)
# ──────────────────────────────────────────────

SCORE_WEIGHTS = {
    "order_block": 20,
    "fvg": 15,
    "bos_choch": 15,
    "killzone": 10,
    "htf_alignment": 20,
    "liquidity_sweep": 10,
    "freshness": 10,
}
