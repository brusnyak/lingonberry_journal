"""Central configuration — $70 personal account, crypto pairs, risk."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal

# ──────────────────────────────────────────────
# Account: $70 Personal (Binance/Bybit USDT-M)
# ──────────────────────────────────────────────

PERSONAL_ACCOUNT = {
    "name": "Crypto Personal",
    "initial_balance": 70.0,
    "max_daily_loss_pct": 0.05,     # 5% = $3.50
    "max_overall_loss_pct": 0.15,   # 15% = $10.50 (reset if hit)
    "min_balance": 50.0,            # stop trading if below
}

# ──────────────────────────────────────────────
# Tradeable Instruments — Crypto USDT-M Futures
# ──────────────────────────────────────────────

@dataclass
class PairConfig:
    symbol: str                     # Binance/Bybit name
    name: str                       # Human-readable label

    # Timeframe resolutions:
    # 15m or 5m entry, 1H/4H for structure bias
    htf_resolution: str = "4H"      # Directional bias
    mtf_resolution: str = "1H"      # Structure / OB / FVG zones
    ltf_resolution: str = "15m"     # Entry confirmation (BOS/CHoCH/FVG)

    # SMC swing_lengths
    htf_swing_length: int = 7
    mtf_swing_length: int = 10
    ltf_swing_length: int = 4

    min_rr: float = 1.5
    min_score: float = 60.0

CRYPTO_PAIRS: list[PairConfig] = [
    PairConfig(symbol="XRPUSDT",  name="Ripple"),
    PairConfig(symbol="ADAUSDT",  name="Cardano"),
    PairConfig(symbol="SOLUSDT",  name="Solana"),
    PairConfig(symbol="DOGEUSDT", name="Dogecoin"),
    PairConfig(symbol="AVAXUSDT", name="Avalanche"),
    PairConfig(symbol="NEARUSDT", name="Near Protocol"),
    PairConfig(symbol="LINKUSDT", name="Chainlink"),
    PairConfig(symbol="AAVEUSDT", name="Aave"),
    PairConfig(symbol="SUIUSDT",  name="Sui"),
]

# Bull-only configs (best performers from 30d backtest)
BULL_CONFIG = {
    "sl_buffer_pips": 20,
    "tp1_r": 2.0,
    "direction": "bull",
    "min_gap_atr_pct": 0.2,
    "sl_mode": "structure",
    "structure_sl_lookback": 20,
    "structure_sl_swing_n": 3,
}

# ──────────────────────────────────────────────
# Risk Rules — $70 Personal
# ──────────────────────────────────────────────

@dataclass
class RiskRule:
    account_name: str
    initial_balance: float
    max_daily_loss_pct: float
    max_overall_loss_pct: float
    risk_per_trade_pct: float = 0.005  # 0.5% = $0.35
    max_positions: int = 1
    default_leverage: int = 50

RISK_RULES: list[RiskRule] = [
    RiskRule(
        account_name="Crypto Personal",
        initial_balance=PERSONAL_ACCOUNT["initial_balance"],
        max_daily_loss_pct=PERSONAL_ACCOUNT["max_daily_loss_pct"],
        max_overall_loss_pct=PERSONAL_ACCOUNT["max_overall_loss_pct"],
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
# Scanner — Not used for crypto yet
# ──────────────────────────────────────────────

SCAN_INTERVAL_MINUTES: int = int(os.getenv("SCAN_INTERVAL_MINUTES", "5"))

LTF_CONF_BASE_SCORE = 40
LTF_RECENCY_BONUS = 15
LTF_VOLUME_SPIKE_THRESHOLD = 1.5
LTF_VOLUME_BONUS = 10
LTF_LOOKBACK_CANDLES = 16
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
