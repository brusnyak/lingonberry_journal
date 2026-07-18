"""
Re-validate TrIct/ETH+XRP+DOGE (the one crypto strategy that survived null +
split-half + rolling-DD checks, see memory crypto_trict_eth_xrp_audit.md)
under corrections the prior audit flagged but never wired into the engine:

  1. BingX's real VIP0 fee schedule (0.05% taker / 0.02% maker) instead of the
     CryptoCosts default (Binance 0.04% taker) -- this is the exchange the
     user's live $20 account actually sits on.
  2. Slippage on entries and SL exits, via the new CryptoCosts.entry_slippage_pct
     / sl_slippage_pct params (previously zero -- perfect fills assumed).
     Swept at 0%, 0.05%, 0.10%.
  3. Sample size. The pure Binance/Bybit exchange-scoped data (post the
     2026-07-12 loader-purity fix) only covers ~107 days -> 2-7 trades per
     pair, too thin to conclude anything. The `legacy` source has years of
     history but is UNVERIFIED provenance -- the 2026-07-12 audit found
     legacy diverges from real Bybit prices on 99.85% of overlapping closes
     (median diff $4.18, max $275) while matching Binance exactly on the one
     pair spot-checked (BTC). So: legacy results below are a robustness/
     stress read on a much larger sample, NOT live-deployment evidence.
     Every row is tagged with its data_provenance so this isn't silently lost.

Usage: python -m backtesting.crypto.bingx_slippage_sweep
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from backtesting.crypto.data import load_crypto, load_market_specs
from backtesting.crypto.data import load_funding_rate as load_funding_rate_crypto
from backtesting.crypto.data_quality import require_funding_coverage
from backtesting.engine.costs import CryptoCosts
from backtesting.engine.data import load_data, load_funding_rate
from backtesting.engine.runner import run
from backtesting.crypto.strategies.ict import TrIct

# Per-pair min_stop_pct per crypto_trict_eth_xrp_audit memory (Phase 6F/6G):
# XRP/DOGE validated at 0.25, ETH stays unfiltered (data-limited, filter hurts it).
PAIRS = {
    "ETHUSDT": None,
    "XRPUSDT": 0.25,
    "DOGEUSDT": 0.25,
}
RISK_PCT = 0.002          # the value that hit <1% combined DD in the prior audit
INITIAL_EQUITY = 20.0     # actual account size

# BingX VIP0 perpetual futures fees (WebSearch, Jul 2026) -- worse taker than
# the Binance default (0.04%), maker unchanged.
BINGX_TAKER_FEE = 0.0005
BINGX_MAKER_FEE = 0.0002
BINGX_MIN_NOTIONAL = 2.0  # confirmed live via ccxt.bingx().load_markets(), same across DOGE/XRP/ETH/WLD/SUI

SLIPPAGE_SWEEP = [0.0, 0.0005, 0.0010]  # 0%, 0.05%, 0.10%

WINDOWS = {
    "pure_exchange_3.5mo": dict(source="exchange", exchange="binance"),
    "legacy_full_history": dict(source="legacy", exchange=None),
}


def _costs(specs: dict, funding_df, entry_slip: float, sl_slip: float) -> CryptoCosts:
    return CryptoCosts(
        maker_fee=BINGX_MAKER_FEE,
        taker_fee=BINGX_TAKER_FEE,
        leverage=50.0,
        funding_df=funding_df if funding_df is not None and not funding_df.empty else None,
        min_notional=specs.get("min_notional", 0.0) or BINGX_MIN_NOTIONAL,
        min_qty=specs.get("min_qty", 0.0),
        qty_step=specs.get("qty_step", 0.0),
        tick_size=specs.get("tick_size", 0.0),
        entry_slippage_pct=entry_slip,
        sl_slippage_pct=sl_slip,
    )


def _resample_240(df30: pd.DataFrame) -> pd.DataFrame:
    d = df30.set_index("ts").sort_index()
    out = d.resample("4h").agg({"open": "first", "high": "max", "low": "min",
                                  "close": "last", "volume": "sum"}).dropna()
    return out.reset_index()[["ts", "open", "high", "low", "close", "volume"]]


def run_pure_exchange(pair: str, min_stop_pct, entry_slip: float, sl_slip: float) -> dict:
    """Post-2026-07-12-fix pure exchange data. Correct provenance, thin sample (~107d)."""
    data = {}
    for tf in ("30", "240"):
        df = load_data(pair, tf=tf, exchange="binance")
        if df.empty:
            return {"pair": pair, "error": f"no data tf={tf}"}
        data[tf] = df
    funding_df = load_funding_rate(pair, exchange="binance")
    require_funding_coverage(data, funding_df)
    specs = load_market_specs(pair, "binance")
    costs = _costs(specs, funding_df, entry_slip, sl_slip)
    strat = TrIct(risk_pct=RISK_PCT, min_stop_pct=min_stop_pct)
    result = run(strat, data, entry_tf="30", costs=costs, initial_equity=INITIAL_EQUITY)
    return _report_row(pair, entry_slip, result)


def run_legacy(pair: str, min_stop_pct, entry_slip: float, sl_slip: float) -> dict:
    """Unverified-provenance legacy data. Large sample (years), stress/robustness read only."""
    df30 = load_crypto(pair, tf="30", source="legacy", resample=False)
    if df30.empty:
        return {"pair": pair, "error": "no legacy 30m data"}
    df240 = _resample_240(df30)  # derive from 30m locally -- legacy's raw 240 file is thin/absent for some pairs
    data = {"30": df30, "240": df240}

    funding_df = load_funding_rate_crypto(pair)  # tries binance/bybit/legacy; may be empty (e.g. DOGE) -> zero-cost approx
    specs = load_market_specs(pair, "binance")  # legacy has no market_specs.parquet; borrow binance's as an approximation
    costs = _costs(specs, funding_df, entry_slip, sl_slip)
    strat = TrIct(risk_pct=RISK_PCT, min_stop_pct=min_stop_pct)
    result = run(strat, data, entry_tf="30", costs=costs, initial_equity=INITIAL_EQUITY)
    return _report_row(pair, entry_slip, result)


def _report_row(pair: str, entry_slip: float, result) -> dict:
    rep = result.report
    return {
        "pair": pair,
        "slippage_pct": entry_slip * 100,
        "trades": rep.get("trades", 0),
        "win_rate": rep.get("win_rate", 0),
        "profit_factor": rep.get("profit_factor", 0),
        "return_pct": rep.get("return_pct", 0),
        "max_drawdown_pct": rep.get("max_drawdown_pct", 0),
        "final_equity": rep.get("final_equity", 0),
        "error": None,
    }


def main():
    rows = []
    for window_name, w in WINDOWS.items():
        runner = run_pure_exchange if w["source"] == "exchange" else run_legacy
        for slip in SLIPPAGE_SWEEP:
            for pair, min_stop in PAIRS.items():
                try:
                    row = runner(pair, min_stop, entry_slip=slip, sl_slip=slip)
                except Exception as e:
                    row = {"pair": pair, "slippage_pct": slip * 100, "error": f"{type(e).__name__}: {e}"}
                row["window"] = window_name
                rows.append(row)

    df = pd.DataFrame(rows)
    cols = ["window", "pair", "slippage_pct"] + [c for c in df.columns if c not in ("window", "pair", "slippage_pct")]
    df = df[cols]
    pd.set_option("display.width", 160)
    print(df.to_string(index=False))

    out = ROOT / "backtesting" / "crypto" / "reports" / "bingx_slippage_sweep.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
