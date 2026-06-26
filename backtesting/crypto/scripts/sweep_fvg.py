"""
Multi-asset TrFvg sweep: FVG bear_fill (and bull/both) across all available instruments.
IS: max available data → 2026-05-23
OOS: 2026-05-24 → 2026-06-23

Per-asset pip config:
  Forex non-JPY : pip_size=0.0001,  sl_bufs=[5,8,10,15]
  Forex JPY     : pip_size=0.01,    sl_bufs=[5,8,10,15]
  Metals (XAU)  : pip_size=0.1,     sl_bufs=[50,100,200]   → $5/$10/$20 buffer
  Metals (XAG)  : pip_size=0.001,   sl_bufs=[50,100,200]
  Crypto BTC/ETH: pip_size=1.0,     sl_bufs=[50,100,200]   → $50/$100/$200 buffer
  Crypto minor  : pip_size=0.0001,  sl_bufs=[20,50,100]
"""
import sys, os, itertools
sys.path.insert(0, ".")

from backtesting.engine.data import load_data
from backtesting.engine.runner import run
from backtesting.engine.costs import ForexCosts, CryptoCosts
from backtesting.engine.metrics import summary_str, table_header, table_row
from backtesting.batch import run_batch, RunConfig
from backtesting.strategies.tr_fvg import TrFvg

IS_END    = "2026-05-23"
OOS_START = "2026-05-24"
OOS_END   = "2026-06-23"

ASSETS = [
    dict(sym="GBPJPY",  at=None,     pip=0.01,   sl=[5,8,10,15],   costs=ForexCosts(pip_size=0.01,   pip_value_per_lot=9.0)),
    dict(sym="GBPAUD",  at=None,     pip=0.0001, sl=[5,8,10,15],   costs=ForexCosts()),
    dict(sym="EURUSD",  at=None,     pip=0.0001, sl=[5,8,10,15],   costs=ForexCosts()),
    dict(sym="AUDUSD",  at=None,     pip=0.0001, sl=[5,8,10,15],   costs=ForexCosts()),
    dict(sym="USDCAD",  at=None,     pip=0.0001, sl=[5,8,10,15],   costs=ForexCosts()),
    dict(sym="GBPUSD",  at=None,     pip=0.0001, sl=[5,8,10,15],   costs=ForexCosts()),
    dict(sym="XAUUSD",  at=None,     pip=0.1,    sl=[50,100,200],  costs=ForexCosts(pip_size=0.1,    pip_value_per_lot=100.0)),
    dict(sym="XAGUSD",  at=None,     pip=0.001,  sl=[50,100,200],  costs=ForexCosts(pip_size=0.001,  pip_value_per_lot=50.0)),
    dict(sym="BTCUSD",  at="crypto", pip=1.0,    sl=[50,100,200],  costs=CryptoCosts()),
    dict(sym="ETHUSD",  at="crypto", pip=1.0,    sl=[30,50,100],   costs=CryptoCosts()),
    dict(sym="ADAUSDT", at="crypto", pip=0.0001, sl=[20,50,100],   costs=CryptoCosts()),
]


def make_configs(a: dict, start: str) -> list[RunConfig]:
    configs = []
    for sl, tp, gap, dirn in itertools.product(
        a["sl"], [0.8, 1.0, 1.5, 2.0], [0.2, 0.3, 0.5], ["bear", "bull", "both"]
    ):
        configs.append(RunConfig(
            pair=a["sym"], entry_tf="5", support_tfs=["240"],
            params=dict(sl_buffer_pips=sl, tp1_r=tp, min_gap_atr_pct=gap,
                        direction=dirn, pip_size=a["pip"]),
            start=start, end=IS_END,
            asset_type=a["at"],
            costs=a["costs"],
        ))
    return configs


if __name__ == "__main__":
    print(f"TrFvg multi-asset sweep  IS→{IS_END}  OOS {OOS_START}→{OOS_END}")
    print("="*90)

    summary_rows = []

    for a in ASSETS:
        sym = a["sym"]
        at_kw = {"asset_type": a["at"]} if a["at"] else {}
        df_check = load_data(sym, tf="5", end=IS_END, **at_kw)
        if df_check.empty or len(df_check) < 300:
            print(f"\n{sym}: NO DATA — skip")
            continue

        start = str(df_check.ts.min().date())
        n_configs = len(a["sl"]) * 4 * 3 * 3  # sl × tp × gap × dir
        print(f"\n{sym}  {len(df_check)} bars  {start}→{IS_END}  ({n_configs} configs)")

        configs = make_configs(a, start)
        df_res = run_batch(TrFvg, configs, workers=min(6, os.cpu_count()), min_trades=30)

        valid = df_res[df_res["error"].isna() & (df_res["trades"] >= 30)]
        if valid.empty:
            print(f"  No valid configs (all < 30 trades)")
            continue

        best = valid.loc[valid["profit_factor"].idxmax()]
        top3 = valid.nlargest(3, "profit_factor")

        print(f"\n  {'Label':30s}  {'T':>5}  {'WR':>7}  {'RR':>5}  {'PF':>6}  {'DD':>7}")
        print(f"  {'-'*70}")
        for _, row in top3.iterrows():
            label = f"sl={row['sl_buffer_pips']} tp={row['tp1_r']} gap={row['min_gap_atr_pct']} {row['direction']}"
            print(f"  {label:30s}  {row['trades']:>5}  {row['win_rate']:>7.1%}  "
                  f"{row['payoff_ratio']:>5.2f}  {row['profit_factor']:>6.3f}  "
                  f"{row['max_drawdown_pct']:>7.1%}")

        # OOS on best params
        df5o  = load_data(sym, tf="5",   start=OOS_START, end=OOS_END, **at_kw)
        df4ho = load_data(sym, tf="240", start=OOS_START, end=OOS_END, **at_kw)
        oos_str = "N/A"
        if not df5o.empty and len(df5o) >= 50:
            r_oos = run(
                TrFvg(sl_buffer_pips=int(best["sl_buffer_pips"]),
                      tp1_r=float(best["tp1_r"]),
                      min_gap_atr_pct=float(best["min_gap_atr_pct"]),
                      direction=str(best["direction"]),
                      pip_size=a["pip"]),
                {"5": df5o, "240": df4ho}, entry_tf="5",
                costs=a["costs"], initial_equity=10_000,
            )
            rep = r_oos.report
            oos_str = (f"T={rep['trades']}  WR={rep['win_rate']:.1%}  "
                       f"PF={rep['profit_factor']:.3f}  DD={rep['max_drawdown_pct']:.1%}")

        print(f"  OOS: {oos_str}")
        summary_rows.append(dict(
            sym=sym,
            is_pf=round(best["profit_factor"], 3),
            is_wr=round(best["win_rate"], 3),
            is_t=int(best["trades"]),
            best_params=f"sl={best['sl_buffer_pips']} tp={best['tp1_r']} gap={best['min_gap_atr_pct']} {best['direction']}",
            oos=oos_str,
        ))

    # Final summary table
    print("\n" + "="*90)
    print("  SUMMARY — best IS PF per asset")
    print("="*90)
    print(f"  {'Sym':10} {'IS_PF':>6} {'IS_WR':>7} {'IS_T':>6}  {'Best params':35s}  OOS")
    print(f"  {'-'*85}")
    for r in sorted(summary_rows, key=lambda x: x["is_pf"], reverse=True):
        print(f"  {r['sym']:10} {r['is_pf']:>6.3f} {r['is_wr']:>7.1%} {r['is_t']:>6}  "
              f"{r['best_params']:35s}  {r['oos']}")
