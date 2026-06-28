"""Capture mechanical ICT signals with RICH causal features for meta-labeling.
Forex-only (clean universe). Capped workers so the Mac doesn't roast.
Output: scratchpad/meta_signals.parquet  (one row per filled signal + realized R)."""
import sys, warnings, os
sys.path.insert(0, ".")
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
from concurrent.futures import ProcessPoolExecutor, as_completed
from backtesting.engine.data import load_data
from backtesting.features.core import atr as f_atr, adx as f_adx, regime_from_adx
from backtesting.structure_lib.swing import swing_points
from backtesting.structure_lib.labels import label_structure
from backtesting.structure_lib.sweep import detect_pools, detect_sweeps
from backtesting.structure_lib.fvg import detect_fvgs
from backtesting.structure_lib.ob import detect_order_blocks
from backtesting.structure_lib.trade_signals import generate_signals

OUT = "/private/tmp/claude-501/-Users-yegor-Documents-Acore-Development-trader-trading-journal/457425e4-476d-430a-a71f-8650093935d1/scratchpad/meta_signals.parquet"
FILL_WIN, HOLD_CAP = 48, 288
WORKERS = 5  # of 8 cores — leave headroom, calm the fans

ASSETS = {
    "EURUSD":0.00012,"GBPUSD":0.00015,"AUDUSD":0.00016,"USDCAD":0.00018,"USDCHF":0.00018,
    "EURGBP":0.00018,"EURCHF":0.00022,"AUDNZD":0.00030,"AUDCAD":0.00026,"AUDCHF":0.00028,
    "CADCHF":0.00028,"EURAUD":0.00032,"EURCAD":0.00030,"GBPAUD":0.00035,"GBPCAD":0.00035,
    "GBPCHF":0.00035,"USDJPY":0.014,"EURJPY":0.017,"GBPJPY":0.020,"AUDJPY":0.017,
    "CADJPY":0.019,"CHFJPY":0.022,
}
def pip_of(s): return 0.01 if "JPY" in s else 0.0001
def windows():
    s=pd.Timestamp("2025-03-01",tz="UTC"); e=pd.Timestamp("2026-06-23",tz="UTC"); w=[];c=s
    while c<e: n=c+pd.Timedelta(days=30); w.append((c.strftime("%Y-%m-%d"),min(n,e).strftime("%Y-%m-%d")));c=n
    return w
WINDOWS=windows()

def cap(sym,start,end,spread,tf="5"):
    df=load_data(sym,tf=tf,start=start,end=end)
    if df.empty or len(df)<300: return []
    o=df.copy(); o["ts"]=pd.to_datetime(o["ts"]); o=o.set_index("ts").sort_index()
    hi=o["high"].to_numpy(); lo=o["low"].to_numpy(); cl=o["close"].to_numpy(); op=o["open"].to_numpy()
    atr=f_atr(hi,lo,cl,14); adx=f_adx(hi,lo,cl,14); reg=regime_from_adx(adx)
    sw,lv=swing_points(o,swing_length=3,causal=True)
    lab=label_structure(o,sw,lv); pools=detect_pools(o,sw,lv); sweeps=detect_sweeps(o,pools)
    fvgs=detect_fvgs(o); obs=detect_order_blocks(o,lab)
    sigs=generate_signals(o,lab,sweeps,fvgs,obs,pools,min_rr=1.5)
    if not sigs: return []
    # 4H momentum for HTF agreement
    d4=load_data(sym,tf="240",start=start,end=end)
    h4t=h4d=None
    if not d4.empty:
        d4=d4.copy(); d4["ts"]=pd.to_datetime(d4["ts"]); d4=d4.set_index("ts").sort_index()
        h4t=d4.index.asi8; h4d=np.sign(d4["close"]-d4["close"].shift(6)).fillna(0).to_numpy()
    idx={t:i for i,t in enumerate(o.index)}; pip=pip_of(sym); rows=[]
    for s in sigs:
        si=idx.get(s.signal_time);
        if si is None or atr[si]<=0 or not np.isfinite(atr[si]): continue
        e,sl,tp,d=s.entry,s.sl,s.tp,s.direction; risk=abs(e-sl)
        if risk<=0: continue
        fi=None
        for j in range(si+1,min(si+1+FILL_WIN,len(o))):
            if lo[j]<=e<=hi[j]: fi=j; break
        if fi is None: continue
        cost_R=spread/risk; pool_rr=abs(tp-e)/risk; maxfav=0.0
        sl_bar=tp_bar=None; capj=min(fi+HOLD_CAP,len(o))
        for j in range(fi,capj):  # single scan: SL bar, pool-TP bar, max favorable excursion
            if d=="long":
                if lo[j]<=sl: sl_bar=j; break
                fav=(hi[j]-e)/risk
            else:
                if hi[j]>=sl: sl_bar=j; break
                fav=(e-lo[j])/risk
            if fav>maxfav: maxfav=fav
            if tp_bar is None and fav>=pool_rr: tp_bar=j
        Rk=lambda k:(k if maxfav>=k else -1.0)-cost_R   # fixed R-target exit
        res=(pool_rr if maxfav>=pool_rr else -1.0)-cost_R  # nearest-pool exit (net)
        exit_bar = tp_bar if (tp_bar is not None and (sl_bar is None or tp_bar<=sl_bar)) else (sl_bar if sl_bar is not None else capj-1)
        exit_time = o.index[exit_bar].value
        dv=1 if d=="long" else -1
        # premium/discount: where entry sits in the recent dealing range (ICT core filter)
        k0=max(0,si-50); rlo=lo[k0:si+1].min(); rhi=hi[k0:si+1].max()
        epct=(e-rlo)/(rhi-rlo) if rhi>rlo else 0.5
        in_pd=int((dv==1 and epct<0.5) or (dv==-1 and epct>0.5))  # long@discount / short@premium
        h4=0
        if h4t is not None:
            k=int(np.searchsorted(h4t,s.signal_time.value,side="right"))-1
            if k>=0: h4=int(h4d[k])
        # sweep->shift speed
        swi=idx.get(s.sweep.sweep_time, si); b2s=max(0,si-swi)
        rows.append(dict(
            symbol=sym, window=start, fill_time=o.index[fi].value, dirv=dv,
            conf_high=int(s.confidence=="high"), has_fvg=int(s.fvg is not None), has_ob=int(s.ob is not None),
            hour=int(s.signal_time.hour), risk_pips=risk/pip, planned_rr=float(s.rr_ratio),
            atr_norm=risk/atr[si], adx=float(adx[si]), is_range=int(reg[si]=="range"), is_trend=int(reg[si]=="trend"),
            disp=abs(cl[si]-op[si])/atr[si], fvg_atr=((s.fvg.top-s.fvg.bottom)/atr[si]) if s.fvg else 0.0,
            sweep_to_shift=b2s, htf_agree=int(h4==dv), is_jpy=int("JPY" in sym), is_cross=int(not sym.endswith("USD") and not sym.startswith("USD")),
            R=res, win=int(res>0), R2=Rk(2), R3=Rk(3), R4=Rk(4), maxfav=maxfav,
            exit_time=exit_time, base=sym[:3], quote=sym[3:6], tf=tf,
            entry_pct=epct, in_pd=in_pd,
        ))
    return rows

def task(a):
    try: return cap(*a)
    except Exception: return []

TFS=["5","15"]
def main():
    tasks=[(s,st,en,sp,tf) for s,sp in ASSETS.items() for (st,en) in WINDOWS for tf in TFS]
    rows=[]
    with ProcessPoolExecutor(max_workers=WORKERS) as ex:
        for f in as_completed([ex.submit(task,t) for t in tasks]): rows.extend(f.result())
    df=pd.DataFrame(rows); df.to_parquet(OUT)
    print(f"captured {len(df)} signals, {df.symbol.nunique()} pairs -> {OUT}")
    print(f"base WR={100*df.win.mean():.1f}% avgR={df.R.mean():+.3f}")

if __name__=="__main__": main()
