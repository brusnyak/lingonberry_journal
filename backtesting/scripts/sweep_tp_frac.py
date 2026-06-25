"""
Test tp1_frac=1.0 (full close at TP, no trailing).
Hypothesis: trailing exit is compressing payoff_ratio from 1.5 to 0.63.
Full exit at TP should push PF toward 2.0+.
"""
import sys, os
sys.path.insert(0, ".")

from backtesting.batch import run_batch, make_configs
from backtesting.strategies.tr_accumulation import TrAccumulation
from backtesting.engine.metrics import table_header, table_row

# Patch tp1_frac into TrAccumulation for this test
_orig_init = TrAccumulation.__init__

def _patched_init(self, tp1_frac=1.0, **kwargs):
    _orig_init(self, **kwargs)
    self._tp1_frac_override = tp1_frac

_orig_signal_gen = None

if __name__ == "__main__":
    import backtesting.engine.runner as _runner_mod
    import backtesting.engine.orders as _orders_mod
    from backtesting.engine.orders import Signal, Direction
    import backtesting.strategies.tr_accumulation as _acc_mod

    # Monkey-patch tp1_frac into the Signal creation in TrAccumulation
    # Actually easier: subclass and override tp1_frac

    START = "2022-07-01"
    END   = "2026-05-23"

    results = []
    for frac in [0.4, 0.5, 0.6, 0.7, 0.8, 1.0]:
        # Temporarily patch default tp1_frac in the Strategy
        original_signal_bull = None

        # We'll use a wrapper strategy
        class AccWithFrac(TrAccumulation):
            _frac = frac
            def next(self, bar, state):
                sig = super().next(bar, state)
                if sig is not None:
                    sig.tp1_frac = self._frac
                    sig.tp2_frac = 0.0
                return sig

        configs = make_configs(
            pairs=["GBPCAD"],
            entry_tfs=["15"],
            support_tfs_map={"15": ["240"]},
            param_grid={
                "compress_ratio": [0.70],
                "sl_buffer_pips": [20],
                "tp1_r": [1.5],
                "direction": ["bull"],
            },
            start=START, end=END,
        )

        df = run_batch(AccWithFrac, configs, workers=1, min_trades=10)
        row = df.iloc[0]
        results.append({
            "tp1_frac": frac,
            "trades": row["trades"],
            "win_rate": row["win_rate"],
            "payoff_ratio": row["payoff_ratio"],
            "profit_factor": row["profit_factor"],
            "max_drawdown_pct": row["max_drawdown_pct"],
            "total_pnl": row["total_pnl"],
        })
        print(f"  frac={frac:.1f}  T={row['trades']}  WR={row['win_rate']:.1%}  "
              f"RR={row['payoff_ratio']:.2f}  PF={row['profit_factor']:.3f}  "
              f"DD={row['max_drawdown_pct']:.1%}  PnL=${row['total_pnl']:.0f}")

    print("\n  GBPCAD 15m acc_bull_sweep + 4H  |  compress=0.70 sl=20pip tp=1.5R  |  IS 2022-2026")
    print(f"  {'frac':>6}  {'T':>5}  {'WR':>7}  {'RR':>6}  {'PF':>7}  {'DD':>7}  {'PnL':>9}")
    for r in results:
        print(f"  {r['tp1_frac']:>6.1f}  {r['trades']:>5}  {r['win_rate']:>7.1%}  "
              f"{r['payoff_ratio']:>6.2f}  {r['profit_factor']:>7.3f}  "
              f"{r['max_drawdown_pct']:>7.1%}  ${r['total_pnl']:>8.0f}")
