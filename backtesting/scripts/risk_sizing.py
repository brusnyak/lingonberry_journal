"""
Fixed-balance risk sizing for prop firm compliance.
Tests GBPJPY FVG at different risk% with FIXED position sizing (% of initial balance).
Prop limits: 25k daily DD 5% ($1,233), max loss 10% ($2,466).
"""
import sys
sys.path.insert(0, ".")

from backtesting.engine.data import load_data
from backtesting.engine.runner import run
from backtesting.engine.costs import ForexCosts
from backtesting.engine.metrics import summary_str

# Monkey-patch to use fixed initial equity for risk calc (non-compounding)
from backtesting.engine import runner as _runner
import backtesting.engine.orders as _orders

if __name__ == "__main__":
    df5  = load_data("GBPJPY", tf="5", start="2024-10-01", end="2026-05-23")
    df4h = load_data("GBPJPY", tf="240", start="2024-10-01", end="2026-05-23")
    print(f"IS data: {len(df5)} bars")

    from backtesting.strategies.tr_fvg import TrFvg

    print("\n  GBPJPY FVG bear_fill  |  Fixed-balance risk (% of initial $25k)")
    print(f"  {'risk%':>6}  {'T':>5}  {'WR':>7}  {'RR':>5}  {'PF':>6}  {'DD%':>6}  "
          f"{'DD$25k':>8}  {'PnL@25k':>10}  {'monthly%':>9}")
    print("  " + "-"*80)

    for risk_pct in [0.005, 0.004, 0.003, 0.0025, 0.002]:
        r = run(
            TrFvg(sl_buffer_pips=10, tp1_r=2.0, min_gap_atr_pct=0.3,
                  direction="bear", pip_size=0.01, risk_pct=risk_pct),
            {"5": df5, "240": df4h}, entry_tf="5",
            costs=ForexCosts(), initial_equity=25_000,
        )
        rep = r.report
        dd_dollars = rep["max_drawdown"]
        pnl_25k = rep["total_pnl"]
        months = 19
        monthly_pct = (rep["return_pct"] / months) * 100

        over_limit = "⚠" if dd_dollars > 2466 else " "
        print(f"  {risk_pct*100:>5.2f}%  {rep['trades']:>5}  "
              f"{rep['win_rate']:>7.1%}  {rep['payoff_ratio']:>5.2f}  "
              f"{rep['profit_factor']:>6.3f}  {rep['max_drawdown_pct']:>6.1%}  "
              f"${dd_dollars:>7.0f}{over_limit}  "
              f"${pnl_25k:>9.0f}  {monthly_pct:>8.1f}%")

    # Also show OOS at 0.3% risk on $25k
    print("\n  OOS 30d at 0.30% risk on $25k:")
    df5o  = load_data("GBPJPY", tf="5", start="2026-05-24", end="2026-06-23")
    df4ho = load_data("GBPJPY", tf="240", start="2026-05-24", end="2026-06-23")
    r = run(
        TrFvg(sl_buffer_pips=10, tp1_r=2.0, min_gap_atr_pct=0.3,
              direction="bear", pip_size=0.01, risk_pct=0.003),
        {"5": df5o, "240": df4ho}, entry_tf="5",
        costs=ForexCosts(), initial_equity=25_000,
    )
    rep = r.report
    print(f"  T={rep['trades']}  WR={rep['win_rate']:.1%}  PF={rep['profit_factor']:.3f}  "
          f"DD=${rep['max_drawdown']:.0f}  PnL=${rep['total_pnl']:.0f}")
