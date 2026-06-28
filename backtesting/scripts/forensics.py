"""Per-trade forensics — reconstruct each reviewed trade as interpretable price action.
30 candles before + the trade + the path after. Builds the 'second brain' records and the
direction-accuracy breakdown. NOT statistics on aggregates — one trade at a time, with reasons.
See skill: trade-forensics.  Output: data/forensics/records.parquet + findings to stdout."""
import sys, json, glob, os; sys.path.insert(0, ".")
import numpy as np, pandas as pd
from backtesting.engine.data import load_data

SESS = glob.glob("pine-review/data/review_sessions/*.json")
PRE = 30      # candles of context before entry
POST_CAP = 200  # bars to follow the path if no exit recorded
OUT = "data/forensics"

def parse_tags(t):
    out = {}
    for x in t.get("reason_tags", []) or []:
        if ":" in str(x): k, v = str(x).split(":", 1); out[k] = v
    return out

def load_trades():
    rows = []
    for fp in SESS:
        try: d = json.load(open(fp))
        except Exception: continue
        sym = d.get("symbol"); tf = str(d.get("timeframe") or "5")
        for t in d.get("trades", []):
            if t.get("source") != "manual": continue
            e = t.get("manual_entry_price") or t.get("entry_price")
            sl = t.get("manual_stop_loss") or t.get("stop_loss")
            tp = t.get("manual_take_profit") or t.get("take_profit")
            et = t.get("entry_time"); out = t.get("outcome")
            d_ = t.get("manual_direction") or t.get("direction")
            if not (e and sl and tp and et) or out not in ("win","loss"): continue
            tg = parse_tags(t)
            rows.append(dict(symbol=sym, tf=tf, entry_time=int(et), direction=d_,
                entry=float(e), sl=float(sl), tp=float(tp),
                exit_time=int(t.get("manual_exit_time") or t.get("exit_time") or 0),
                outcome=out, trigger=tg.get("trigger","?"), session=tg.get("session","?"),
                htf_bias=tg.get("htf_bias","?"), notes=(t.get("notes") or "")[:160]))
    return rows

def forensic(tr, df):
    ts = (df["ts"].astype("int64")//10**9).to_numpy()
    o,h,l,c = (df[k].to_numpy() for k in ("open","high","low","close"))
    v = df["volume"].to_numpy()
    i = int(np.argmin(np.abs(ts - tr["entry_time"])))
    if i < PRE or i >= len(df)-3: return None
    dirv = 1 if tr["direction"]=="long" else -1
    risk = abs(tr["entry"]-tr["sl"])
    pre_h, pre_l, pre_c, pre_v = h[i-PRE:i], l[i-PRE:i], c[i-PRE:i], v[i-PRE:i]
    rng = pre_h.max()-pre_l.min()
    atr = np.mean(h[i-PRE:i]-l[i-PRE:i]) or 1e-9
    if risk < 0.2*atr: return None  # degenerate/hindsight stop too tight to be a real trade
    # --- CONTEXT before ---
    trend = (pre_c[-1]-pre_c[0])/atr                       # >0 up, <0 down (in ATRs)
    # liquidity sweep: recent extreme took out the prior extreme then reversed back
    recent_hi = h[i-8:i].max(); prior_hi = h[i-PRE:i-8].max()
    recent_lo = l[i-8:i].min(); prior_lo = l[i-PRE:i-8].min()
    swept_high = recent_hi > prior_hi and c[i-1] < recent_hi - 0.1*atr
    swept_low  = recent_lo < prior_lo and c[i-1] > recent_lo + 0.1*atr
    swept_for_dir = int((dirv==1 and swept_low) or (dirv==-1 and swept_high))
    # premium/discount of entry within pre range (0=low,1=high)
    pos = (tr["entry"]-pre_l.min())/(rng or 1e-9)
    discount_ok = int((dirv==1 and pos<0.5) or (dirv==-1 and pos>0.5))
    # reversal/entry candle anatomy
    eb = i-1
    body = abs(c[eb]-o[eb]); cr = (h[eb]-l[eb]) or 1e-9
    body_frac = body/cr
    vol_spike = int(np.mean(v[i-2:i]) > 1.3*np.mean(pre_v[:-2]) if pre_v[:-2].mean()>0 else 0)
    # --- PATH after ---
    end = i + POST_CAP
    if tr["exit_time"]>0:
        j = int(np.searchsorted(ts, tr["exit_time"]))
        if j>i: end = min(end, j+5)
    mfe=mae=0.0; t_mfe=t_mae=0; reached1=adverse1=None
    rr_cap = abs(tr["tp"]-tr["entry"])/risk
    for k in range(i, min(end, len(df))):
        fav = (h[k]-tr["entry"])/risk if dirv==1 else (tr["entry"]-l[k])/risk
        adv = (l[k]-tr["entry"])/risk if dirv==1 else (tr["entry"]-h[k])/risk
        if fav>mfe: mfe=fav; t_mfe=k-i
        if adv<mae: mae=adv; t_mae=k-i
        if reached1 is None and mfe>=1.0: reached1=k-i
        if adverse1 is None and mae<=-1.0: adverse1=k-i
        if mae<=-1.0 or mfe>=rr_cap: break  # close at first barrier (real-trade horizon)
    direction_correct = int(reached1 is not None and (adverse1 is None or reached1<=adverse1))
    return dict(**{k:tr[k] for k in ("symbol","tf","direction","outcome","trigger","session","htf_bias","notes")},
        rr=abs(tr["tp"]-tr["entry"])/risk, trend_atr=round(trend,2), swept_liq=swept_for_dir,
        discount_ok=discount_ok, entry_pos=round(pos,2), body_frac=round(body_frac,2),
        vol_spike=vol_spike, mfe_R=round(mfe,2), mae_R=round(mae,2), t_mfe=t_mfe, t_mae=t_mae,
        reached_1R=int(reached1 is not None), direction_correct=direction_correct,
        adverse_first=int(adverse1 is not None and (reached1 is None or adverse1<reached1)))

def main():
    trades = load_trades(); print(f"reviewed trades: {len(trades)}")
    cache = {}
    recs = []
    for tr in trades:
        key=(tr["symbol"],tr["tf"])
        if key not in cache:
            try:
                df = load_data(tr["symbol"], tf=tr["tf"])
                cache[key] = df if not df.empty else None
            except Exception: cache[key]=None
        df = cache[key]
        if df is None: continue
        r = forensic(tr, df)
        if r: recs.append(r)
    f = pd.DataFrame(recs)
    if f.empty: print("no records (data symbols missing?)"); print("symbols:", {t['symbol'] for t in trades}); return
    os.makedirs(OUT, exist_ok=True); f.to_parquet(f"{OUT}/records.parquet")
    print(f"forensic records: {len(f)}  symbols: {sorted(f.symbol.unique())}\n")
    print("=== DIRECTION ACCURACY ===")
    print(f"  direction_correct (reached +1R before -1R): {100*f.direction_correct.mean():.0f}%")
    print(f"  adverse_first (went wrong way first):        {100*f.adverse_first.mean():.0f}%")
    print(f"  of LOSSES: {100*f[f.outcome=='loss'].adverse_first.mean():.0f}% went adverse-first "
          f"vs WINS {100*f[f.outcome=='win'].adverse_first.mean():.0f}%")
    print("\n=== WHAT SEPARATES correct-direction vs wrong (interpretable PA features) ===")
    feats=["swept_liq","discount_ok","vol_spike","body_frac","trend_atr","rr","mfe_R","mae_R","t_mfe"]
    g=f.groupby("direction_correct")[feats].mean()
    for ft in feats:
        if 1 in g.index and 0 in g.index:
            print(f"  {ft:14} correct={g.loc[1,ft]:+.2f}  wrong={g.loc[0,ft]:+.2f}")
    print("\n=== by trigger: direction accuracy ===")
    for t,gg in f.groupby("trigger"):
        if len(gg)>=8: print(f"  {t:16} n={len(gg):3} dir_correct={100*gg.direction_correct.mean():3.0f}%  mfe={gg.mfe_R.mean():.2f}R mae={gg.mae_R.mean():.2f}R")

if __name__=="__main__": main()
