"""Honest causal backtest of Yegor's encoded setup: sweep -> CHoCH/BOS -> FVG/OB
entry, tight structural SL, liquidity-pool TP (structure_lib.generate_signals).
Forward-simulate fills + SL/TP resolution + cost. Across assets and 30d windows."""
import sys, warnings, os
sys.path.insert(0, ".")
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
from concurrent.futures import ProcessPoolExecutor, as_completed
from backtesting.engine.data import load_data
from backtesting.structure_lib.swing import swing_points
from backtesting.structure_lib.labels import label_structure
from backtesting.structure_lib.sweep import detect_pools, detect_sweeps
from backtesting.structure_lib.fvg import detect_fvgs
from backtesting.structure_lib.ob import detect_order_blocks
from backtesting.structure_lib.trade_signals import generate_signals

FILL_WIN = 48      # bars to wait for limit fill (4h on 5m)
HOLD_CAP = 288     # max hold (1 day on 5m)
RISK_PCT = 0.005

ASSETS = {  # symbol: spread in price units (round-trip approx)
    "EURUSD": 0.00012, "GBPUSD": 0.00015, "AUDUSD": 0.00016, "USDCAD": 0.00018,
    "USDCHF": 0.00018, "EURGBP": 0.00018, "EURCHF": 0.00022, "AUDNZD": 0.00030,
    "AUDCAD": 0.00026, "AUDCHF": 0.00028, "CADCHF": 0.00028,
    "EURAUD": 0.00032, "EURCAD": 0.00030, "GBPAUD": 0.00035, "GBPCAD": 0.00035,
    "GBPCHF": 0.00035, "USDJPY": 0.014, "EURJPY": 0.017, "GBPJPY": 0.020,
    "AUDJPY": 0.017, "CADJPY": 0.019, "CHFJPY": 0.022, "XAUUSD": 0.30,
}
def pip_of(sym):
    return 0.1 if "XAU" in sym else 0.01 if "JPY" in sym else 0.0001
def gen_windows():
    s = pd.Timestamp("2025-03-01", tz="UTC"); e = pd.Timestamp("2026-06-23", tz="UTC")
    w=[]; c=s
    while c < e:
        n=c+pd.Timedelta(days=30); w.append((c.strftime("%Y-%m-%d"), min(n,e).strftime("%Y-%m-%d"))); c=n
    return w
WINDOWS = gen_windows()
OOS = "2026-05-24"

def simulate(sym, start, end, spread, min_rr=2.0):
    df = load_data(sym, tf="5", start=start, end=end)
    if df.empty or len(df) < 300:
        return None
    o = df.copy(); o["ts"] = pd.to_datetime(o["ts"]); o = o.set_index("ts").sort_index()
    sw, lv = swing_points(o, swing_length=3, causal=True)
    lab = label_structure(o, sw, lv)
    pools = detect_pools(o, sw, lv)
    sweeps = detect_sweeps(o, pools)
    fvgs = detect_fvgs(o)
    obs = detect_order_blocks(o, lab)
    sigs = generate_signals(o, lab, sweeps, fvgs, obs, pools, min_rr=min_rr)
    if not sigs:
        return dict(trades=0, R=[])
    high = o["high"].to_numpy(); low = o["low"].to_numpy(); close = o["close"].to_numpy()
    idx_of = {t: i for i, t in enumerate(o.index)}
    pip = pip_of(sym)
    rows = []
    for s in sigs:
        si = idx_of.get(s.signal_time)
        if si is None: continue
        e, sl, tp, d = s.entry, s.sl, s.tp, s.direction
        risk = abs(e - sl)
        if risk <= 0: continue
        fi = None
        for j in range(si + 1, min(si + 1 + FILL_WIN, len(o))):
            if low[j] <= e <= high[j]: fi = j; break
        if fi is None: continue
        cost_R = spread / risk
        res = None
        for j in range(fi, min(fi + HOLD_CAP, len(o))):
            if d == "long":
                if low[j] <= sl: res = -1.0; break
                if high[j] >= tp: res = (tp - e) / risk; break
            else:
                if high[j] >= sl: res = -1.0; break
                if low[j] <= tp: res = (e - tp) / risk; break
        if res is None:
            last = close[min(fi + HOLD_CAP, len(o)) - 1]
            res = ((last - e) if d == "long" else (e - last)) / risk
        hr = s.signal_time.hour
        sess = "asia" if hr < 7 else "london" if hr < 12 else "ny" if hr < 17 else "late"
        rows.append(dict(
            symbol=sym, window=start, direction=d, confidence=s.confidence,
            has_fvg=s.fvg is not None, has_ob=s.ob is not None,
            session=sess, risk_pips=risk / pip, planned_rr=s.rr_ratio,
            fill_time=o.index[fi].value, gross_R=res, cost_R=cost_R, R=res - cost_R,
        ))
    return rows

def one(args):
    sym, st, en, spread = args
    try:
        return simulate(sym, st, en, spread) or []
    except Exception:
        return []

def eq_stats(Rs):
    eq=1.0; peak=1.0; dd=0.0
    for r in Rs:
        eq*=(1+RISK_PCT*r); peak=max(peak,eq); dd=max(dd,(peak-eq)/peak)
    return (eq-1)*100, dd*100

def fstat(df, label):
    if len(df)==0: print(f"  {label:42} n=0"); return
    wr=100*(df.R>0).mean(); avgr=df.R.mean()
    # per (symbol,window) returns
    rets=[]; dds=[]
    for _,g in df.groupby(["symbol","window"]):
        ret,dd=eq_stats(g.R.tolist()); rets.append(ret); dds.append(dd)
    posw=sum(1 for x in rets if x>0)
    print(f"  {label:42} n={len(df):5} WR={wr:4.1f}% avgR={avgr:+.3f} "
          f"medRet/win={np.median(rets):+5.2f}% medDD={np.median(dds):4.1f}% posWin={posw}/{len(rets)} ret>=8%={sum(1 for x in rets if x>=8)}")

def main():
    tasks = [(s, st, en, sp) for s, sp in ASSETS.items() for (st, en) in WINDOWS]
    allrows = []
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as ex:
        for f in as_completed([ex.submit(one, t) for t in tasks]):
            allrows.extend(f.result())
    df = pd.DataFrame(allrows)
    df.to_parquet("/private/tmp/claude-501/-Users-yegor-Documents-Acore-Development-trader-trading-journal/457425e4-476d-430a-a71f-8650093935d1/scratchpad/ict_signals.parquet")
    print(f"total mechanical signals (filled): {len(df)}")
    print("="*100)
    print("FILTER SWEEP — hunting Yegor's selection (target: WR up, avgR>0, ret>=8%, dd<3%)")
    print("="*100)
    fstat(df, "ALL (baseline)")
    fstat(df[df.confidence=='high'], "confidence=high")
    fstat(df[df.has_fvg], "has_fvg")
    fstat(df[df.has_fvg & df.has_ob], "has_fvg & has_ob")
    fstat(df[df.session.isin(['london','ny'])], "session london/ny")
    fstat(df[df.risk_pips>=8], "risk>=8 pips (kill spread drag)")
    fstat(df[df.risk_pips>=15], "risk>=15 pips")
    fstat(df[df.planned_rr>=3], "planned_rr>=3")
    print("  --- combined (Yegor-informed) ---")
    f1 = df[(df.confidence=='high') & df.session.isin(['london','ny']) & (df.risk_pips>=8)]
    fstat(f1, "high + london/ny + risk>=8")
    f2 = f1[f1.has_fvg]
    fstat(f2, "  + has_fvg")
    f3 = df[(df.confidence=='high') & df.session.isin(['london','ny']) & (df.risk_pips>=15) & df.has_fvg & (df.planned_rr>=3)]
    fstat(f3, "high+ldn/ny+risk>=15+fvg+rr>=3")
    print()
    print("="*100)
    print("BASKET — ONE account trades all 22 pairs, trades merged chronologically per 30d window")
    print("="*100)
    def basket(fdf, label):
        print(f"  -- {label} --")
        print(f"  {'window':<12}{'trades':>7}{'WR%':>7}{'ret%':>8}{'maxDD%':>8}")
        rets=[]; dds=[]; passes=0
        for st,en in WINDOWS:
            g=fdf[fdf.window==st].sort_values("fill_time")
            if len(g)==0: continue
            eq=1.0; peak=1.0; dd=0.0
            for r in g.R: eq*=(1+RISK_PCT*r); peak=max(peak,eq); dd=max(dd,(peak-eq)/peak)
            ret=(eq-1)*100; ddp=dd*100; rets.append(ret); dds.append(ddp)
            if ret>=8 and ddp<3: passes+=1
            tag="OOS " if st==OOS else ""
            print(f"  {tag+st[2:]:<12}{len(g):>7}{100*(g.R>0).mean():>7.1f}{ret:>8.2f}{ddp:>8.2f}")
        print(f"  SUMMARY: medRet={np.median(rets):+.2f}% meanRet={np.mean(rets):+.2f}% worst={min(rets):+.2f}% "
              f"medDD={np.median(dds):.2f}% worstDD={max(dds):.2f}% | windows>=8%&dd<3%: {passes}/{len(rets)}")
        print()
    basket(df[(df.risk_pips>=8) & df.session.isin(['london','ny'])], "risk>=8 + london/ny")
    basket(df[(df.risk_pips>=8) & (df.confidence=='high') & df.session.isin(['london','ny'])], "risk>=8 + high-conf + london/ny")
    basket(df[(df.risk_pips>=10) & df.session.isin(['london','ny'])], "risk>=10 + london/ny")
    basket(df[df.risk_pips>=8], "risk>=8 (all sessions)")
    return

    print("=" * 96)
    print("  ICT SEQUENCE (sweep->CHoCH/BOS->FVG/OB, structural SL, liquidity TP)  costs on, min_rr=2")
    print("=" * 96)
    # per-window pooled across assets
    print(f"  {'window':<13}{'trades':>7}{'fillN':>7}{'WR%':>7}{'avgR':>7}{'ret%/pair':>11}{'ddMean%':>9}{'ddWorst%':>10}")
    allR=[]; wrows=[]
    for st, en in WINDOWS:
        recs=[res[(s,st)] for s,_ in ASSETS.items() if (s,st) in res and res[(s,st)] and "err" not in res[(s,st)]]
        Rs=[x for r in recs for x in r["R"]]; t=sum(r["trades"] for r in recs)
        if not Rs:
            print(f"  {('OOS ' if st==OOS else '')+st[2:]:<13}{t:>7}{0:>7}{'-':>7}{'-':>7}{'-':>11}{'-':>9}{'-':>10}"); continue
        rets=[]; dds=[]
        for r in recs:
            if r["R"]:
                ret,dd=equity_stats(r["R"]); rets.append(ret); dds.append(dd)
        wr=100*np.mean([x>0 for x in Rs]); avgr=np.mean(Rs)
        retm=np.mean(rets) if rets else 0; ddm=np.mean(dds) if dds else 0; ddw=max(dds) if dds else 0
        allR+=Rs; wrows.append((retm,ddw))
        tag="OOS " if st==OOS else ""
        print(f"  {tag+st[2:]:<13}{t:>7}{len(Rs):>7}{wr:>7.1f}{avgr:>7.3f}{retm:>11.2f}{ddm:>9.2f}{ddw:>10.2f}")
    print("-"*96)
    if allR:
        rt=[r[0] for r in wrows]; dw=[r[1] for r in wrows]
        print(f"  pooled: trades={len(allR)}  WR={100*np.mean([x>0 for x in allR]):.1f}%  avgR={np.mean(allR):+.3f}")
        print(f"  ret%/pair-window: median={np.median(rt):.2f} mean={np.mean(rt):.2f} worst={min(rt):.2f} best={max(rt):.2f}")
        print(f"  ddWorst: median={np.median(dw):.2f} worst={max(dw):.2f}")
        print(f"  windows positive: {sum(1 for x in rt if x>0)}/{len(rt)}  ret>=8%: {sum(1 for x in rt if x>=8)}  ret>=4%: {sum(1 for x in rt if x>=4)}")
    print()
    print("  === per-asset pooled (all windows) ===")
    for s,_ in ASSETS.items():
        Rs=[x for st,en in WINDOWS if (s,st) in res and res[(s,st)] and "err" not in res[(s,st)] for x in res[(s,st)]["R"]]
        if not Rs: continue
        print(f"  {s:8} n={len(Rs):4} WR={100*np.mean([x>0 for x in Rs]):5.1f}%  avgR={np.mean(Rs):+.3f}")

if __name__ == "__main__":
    main()
