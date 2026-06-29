"""Go/no-go signal scan: do the macro features have a SIGN-STABLE directional
pulse on forward returns? (lvl 1.5 — decides whether modeling is worth it)

Kill criterion (Yegor): a feature survives only if its correlation with forward
return is the SAME SIGN in BOTH halves of history. Sign-flip across halves =
regime artifact (the yen-trend trap), not an edge. Magnitude is secondary;
stability is the gate. Economic-prior column flags whether the sign even makes
sense (rising rate-diff / rising VIX should push EURUSD DOWN).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from daily_engine.data import build_dataset


def _spearman(x: pd.Series, y: pd.Series) -> float:
    if len(x) < 10:
        return float("nan")
    # Spearman = Pearson on ranks (avoids the scipy dependency).
    return float(x.rank().corr(y.rank()))

HORIZONS = [1, 3, 5, 10]
# Economic prior: expected sign of corr(feature, forward EURUSD return).
# US tightening / risk-off => stronger USD => EURUSD down => negative.
PRIOR = {
    "rate_diff": -1, "d_rate_diff": -1, "us2y_mom": -1,
    "slope": +1, "d_slope": +1, "vix": -1, "d_vix": -1,
}


def add_features(ds: pd.DataFrame) -> pd.DataFrame:
    f = ds.copy()
    f["d_rate_diff"] = f["rate_diff"].diff(5)
    f["d_slope"] = f["slope"].diff(5)
    f["d_vix"] = f["vix"].diff(5)
    return f


def scan(symbol: str = "EURUSD") -> pd.DataFrame:
    ds = add_features(build_dataset(symbol))
    feats = ["rate_diff", "d_rate_diff", "us2y_mom", "slope", "d_slope", "vix", "d_vix"]

    mid = len(ds) // 2
    rows = []
    for h in HORIZONS:
        fwd = ds["close"].shift(-h) / ds["close"] - 1.0
        for feat in feats:
            x = ds[feat]
            m = x.notna() & fwd.notna()
            xa, ya = x[m], fwd[m]
            half = ds.index[m] >= ds.index[mid]
            full = _spearman(xa, ya)
            early = _spearman(xa[~half], ya[~half])
            late = _spearman(xa[half], ya[half])
            sign_stable = np.sign(early) == np.sign(late) and abs(early) > 0.03 and abs(late) > 0.03
            prior_ok = np.sign(full) == PRIOR[feat]
            rows.append(dict(
                h=h, feature=feat,
                full=round(full, 3), early=round(early, 3), late=round(late, 3),
                stable=sign_stable, prior_ok=prior_ok,
            ))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    import sys
    sym = sys.argv[1] if len(sys.argv) > 1 else "EURUSD"
    df = scan(sym)

    # baseline drift
    ds = build_dataset(sym)
    for h in HORIZONS:
        up = ((ds["close"].shift(-h) / ds["close"] - 1.0) > 0).mean()
        print(f"baseline up-rate h={h:2d}: {up:.3f}")

    print(f"\n=== {sym} feature vs forward-return Spearman (sign-stability scan) ===")
    print(df.to_string(index=False))

    survivors = df[df["stable"] & df["prior_ok"]]
    print(f"\nSIGN-STABLE + economically-coherent cells: {len(survivors)} / {len(df)}")
    if len(survivors):
        print(survivors.to_string(index=False))
    else:
        print(">>> NO survivor. Daily macro bias on this pair fails the kill criterion.")
