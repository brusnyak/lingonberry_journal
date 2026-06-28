"""Meta-labeling (Lopez de Prado) on mechanical ICT signals.
Secondary model filters which primary signals to take. Expanding walk-forward
(train on strictly-earlier 30d windows, predict later) = purged, no leakage.
Compares meta-filter vs the simple risk>=8+london/ny hand-rule on identical OOS windows."""
import sys; sys.path.insert(0, ".")
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

P="/private/tmp/claude-501/-Users-yegor-Documents-Acore-Development-trader-trading-journal/457425e4-476d-430a-a71f-8650093935d1/scratchpad/meta_signals.parquet"
RISK=0.005; MIN_TRAIN=4
FEATS=["dirv","conf_high","has_fvg","has_ob","hour","risk_pips","planned_rr","atr_norm",
       "adx","is_range","is_trend","disp","fvg_atr","sweep_to_shift","htf_agree","is_jpy","is_cross"]

df=pd.read_parquet(P)
wins=sorted(df.window.unique())   # chronological 30d windows
print(f"signals={len(df)} windows={len(wins)} base WR={100*df.win.mean():.1f}% avgR={df.R.mean():+.3f}")

def basket_eq(g):
    g=g.sort_values("fill_time"); eq=peak=1.0; dd=0.0
    for r in g.R: eq*=(1+RISK*r); peak=max(peak,eq); dd=max(dd,(peak-eq)/peak)
    return (eq-1)*100, dd*100

# ---- expanding walk-forward meta-labeling ----
oos=df.copy(); oos["proba"]=np.nan
for wi in range(MIN_TRAIN, len(wins)):
    tr=df[df.window.isin(wins[:wi])]; te_mask=df.window==wins[wi]
    m=HistGradientBoostingClassifier(max_depth=3,learning_rate=0.05,max_iter=300,
        l2_regularization=1.0,min_samples_leaf=40,random_state=0)
    m.fit(tr[FEATS], tr.win)
    oos.loc[te_mask,"proba"]=m.predict_proba(df[te_mask][FEATS])[:,1]
    # train-derived threshold stored per window (top-30% of TRAIN scores -> leak-free)
    thr=np.quantile(m.predict_proba(tr[FEATS])[:,1], 0.70)
    oos.loc[te_mask,"thr_train"]=thr

ev=oos[oos.window.isin(wins[MIN_TRAIN:])].copy()   # OOS windows only
owins=wins[MIN_TRAIN:]
def report(mask,label):
    g=ev[mask]
    if len(g)==0: print(f"  {label:34} n=0"); return
    rets=[];dds=[]
    for w in owins:
        gg=g[g.window==w]
        if len(gg)==0: continue
        r,d=basket_eq(gg); rets.append(r); dds.append(d)
    print(f"  {label:34} n={len(g):5} WR={100*g.win.mean():4.1f}% avgR={g.R.mean():+.3f} "
          f"medRet={np.median(rets):+5.2f}% meanRet={np.mean(rets):+5.2f}% worst={min(rets):+5.2f}% "
          f"medDD={np.median(dds):4.2f}% worstDD={max(dds):4.2f}% +win={sum(r>0 for r in rets)}/{len(rets)} "
          f"pass(>=8&dd<3)={sum(r>=8 and d<3 for r,d in zip(rets,dds))}")

print("\n=== BASELINES (same OOS windows) ===")
report(ev.index.notna(), "ALL signals")
report((ev.risk_pips>=8)&ev.hour.between(7,16), "hand-rule risk>=8 + london/ny")
print("\n=== META-FILTER (proba threshold sweep, OOS) ===")
for thr in [0.30,0.35,0.40,0.45,0.50]:
    report(ev.proba>=thr, f"proba>={thr:.2f}")
print("\n=== META-FILTER (train-derived top-30%, leak-free) ===")
report(ev.proba>=ev.thr_train, "proba>=train top-30%")
print("\n=== META + hand-rule combined ===")
report((ev.proba>=0.40)&(ev.risk_pips>=8), "proba>=0.40 & risk>=8")

# feature importance (permutation on a final model, quick)
from sklearn.inspection import permutation_importance
m=HistGradientBoostingClassifier(max_depth=3,learning_rate=0.05,max_iter=300,l2_regularization=1.0,
    min_samples_leaf=40,random_state=0).fit(df[df.window.isin(wins[:-3])][FEATS], df[df.window.isin(wins[:-3])].win)
te=df[df.window.isin(wins[-3:])]
imp=permutation_importance(m,te[FEATS],te.win,n_repeats=5,random_state=0,n_jobs=1)
print("\n=== feature importance (permutation, OOS) ===")
for i in np.argsort(imp.importances_mean)[::-1][:10]:
    print(f"  {FEATS[i]:16} {imp.importances_mean[i]:+.4f}")
