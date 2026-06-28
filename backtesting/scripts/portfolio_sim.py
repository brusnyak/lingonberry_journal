"""Portfolio-level prop simulator: concurrency cap + per-currency cap + daily-loss
circuit breaker + compounding risk. Attacks worst-window DD (the binding constraint)
structurally so base risk can rise toward the 8%/<3% target. Sweeps risk/caps."""
import sys; sys.path.insert(0, ".")
import heapq, numpy as np, pandas as pd
from collections import Counter

P="/private/tmp/claude-501/-Users-yegor-Documents-Acore-Development-trader-trading-journal/457425e4-476d-430a-a71f-8650093935d1/scratchpad/meta_signals.parquet"
df=pd.read_parquet(P)
wins=sorted(df.window.unique())
DAY=86_400_000_000_000  # ns/day

def sim_window(g, risk, maxopen, ccycap, daily_stop):
    g=g.sort_values("fill_time")
    eq=1.0; peak=1.0; dd=0.0
    openh=[]; ccy=Counter(); day=None; day_start=eq
    def realize(until):
        nonlocal eq,peak,dd
        while openh and openh[0][0]<=until:
            et,R,risk_amt,b,q=heapq.heappop(openh)
            eq+=risk_amt*R; ccy[b]-=1; ccy[q]-=1
            peak=max(peak,eq); dd=max(dd,(peak-eq)/peak)
    for _,t in g.iterrows():
        ft=t.fill_time; realize(ft)
        d=ft//DAY
        if d!=day: day=d; day_start=eq
        if daily_stop<1 and (eq-day_start)/day_start<=-daily_stop: continue  # day blocked
        if len(openh)>=maxopen: continue
        if ccy[t.base]>=ccycap or ccy[t.quote]>=ccycap: continue
        ra=risk*eq
        heapq.heappush(openh,(int(t.exit_time),float(t.R),ra,t.base,t.quote))
        ccy[t.base]+=1; ccy[t.quote]+=1
    realize(10**30)  # close all at window end
    return (eq-1)*100, dd*100

def sweep(fdf, label):
    print(f"\n### {label}  (n={len(fdf)})")
    print(f"  {'risk':>5}{'maxO':>5}{'ccy':>4}{'dStop':>6} | {'medRet':>7}{'meanRet':>8}{'worstRet':>9}{'medDD':>6}{'worstDD':>8}{'+win':>6}{'pass':>5}")
    best=[]
    for risk in (0.005,0.0075,0.01,0.0125,0.015):
        for maxopen in (3,5,8,99):
            for ccycap in (2,3,99):
                for dstop in (0.015,0.02,0.99):
                    rets=[];dds=[]
                    for w in wins:
                        g=fdf[fdf.window==w]
                        if len(g)==0: continue
                        r,dv=sim_window(g,risk,maxopen,ccycap,dstop); rets.append(r); dds.append(dv)
                    if not rets: continue
                    medr=np.median(rets); worstdd=max(dds); meddd=np.median(dds)
                    posw=sum(x>0 for x in rets); npass=sum(r>=8 and d<3 for r,d in zip(rets,dds))
                    best.append((medr,worstdd,meddd,np.mean(rets),min(rets),posw,npass,risk,maxopen,ccycap,dstop))
    # best-achievable median return under each worst-window-DD ceiling = the frontier
    print("  -- FRONTIER: max median return achievable under each worst-window-DD ceiling --")
    print(f"  {'DDceil':>7} | {'risk':>5}{'maxO':>5}{'ccy':>4}{'dStop':>6} | {'medRet':>7}{'meanRet':>8}{'worstRet':>9}{'worstDD':>8}{'+win':>6}")
    for ceil in (3.0, 5.0, 8.0, 10.0):
        cands=[b for b in best if b[1]<ceil]
        if not cands: print(f"  {ceil:>6.0f}% | (none)"); continue
        cands.sort(key=lambda b:-b[0]); b=cands[0]
        medr,wdd,mdd,meanr,worst,posw,npass,risk,mo,cc,ds=b
        print(f"  {ceil:>6.0f}% | {risk:>5.3f}{mo:>5}{cc:>4}{ds:>6.2f} | {medr:>7.2f}{meanr:>8.2f}{worst:>9.2f}{wdd:>8.2f}{posw:>5}/16")

HQ=(df.risk_pips>=8)&(df.htf_agree==1)&(df.has_fvg==1)&(df.disp>=0.8)&df.hour.between(12,16)
sweep(df[HQ], "HQ: fvg+disp>=0.8+NY+htf  (5m+15m stacked)")
sweep(df[(df.risk_pips>=8)&(df.htf_agree==1)&(df.disp>=0.8)&df.hour.between(12,16)], "HQ no-fvg-req (5m+15m)")
sweep(df[(df.risk_pips>=8)&df.hour.between(7,16)&(df.htf_agree==1)], "base+htf (5m+15m, context)")
