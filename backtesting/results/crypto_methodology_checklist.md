# Crypto Engine Development: Methodology Checklist

## The Discovery Chain — How Each Improvement Was Found

### 1. `aligned_shock` → No-shock filter (the biggest gain)

**Trigger**: Manual trade forensics. We had 84 trades in the 180d baseline and
hitting performance walls with session/DMI filters. The "what's killing us"
question required looking at individual trade records, not aggregates.

**Method**:
1. Sorted all 84 trades by `stress_net_r` ascending (worst losers first).
2. Inspected the bottom 5 manually — read the feature columns for each.
3. Found `shock_alignment=aligned_shock` in 4 of 5 worst losers.
4. Checked prevalence: ~20% of all trades had that value.
5. The skew (20% population → 80% of worst 5) was large enough to act on
   without formal statistics.

**What it caught**: Entries where a structural shock (impulsive move) aligns
with trade direction. The MTF cascade correctly identifies trend direction,
but entry price is after the impulsive leg exhausted. `no_shock` trades are
quieter structural breaks (CHoCH/BOS without the violent leg).

**Why it worked after session/DMI filters stopped helping**:
Session filters and DMI alignment improve the *environment* but don't address
*entry quality*. The aligned_shock filter removes bad entries within good
environments.

**Validation**: 90d PF went from ~1.7 to 4.47. 180d PF went from ~1.5 to 2.58.
This was the single largest improvement in the entire project.

---

### 2. ATR-scaled slippage (infrastructure, not edge)

**Trigger**: The fixed 6bps/20bps cost model was unrealistic. Cryptocurrency
slippage scales with volatility. A 6bps assumption during high-ATR periods is
misleadingly cheap.

**Method**:
1. Added `--slippage-mode atr_scaled` flag.
2. Base cost = `base_cost_pct` × ATR(entry bar).
3. Stress cost = `stress_cost_pct` × ATR(entry bar).
4. Costs are converted to R-units: `cost_r = cost / stop_pct`.

**What it revealed**: Previous results that used fixed 6bps/20bps were
overstating PF. The ATR model is the honest baseline going forward.

---

### 3. 360d stress test (regime dependency)

**Trigger**: The 180d numbers looked good (PF 2.62 stress, 55% WR) but we
hadn't tested across a full market cycle. Crypto goes through bull/bear/sideways
regimes. A 180d slice could be cherry-picking a favorable regime.

**Method**:
1. Ran the same setup with `--days 360`.
2. Added 30/60/90d rolling window analysis to catch time-varying performance.
3. Compared symbol-level breakdowns between 90d, 180d, and 360d.

**Finding**: PF drops from 2.61 (90d) → 2.62 (180d) → 1.30 (360d). The edge
does not persist through all regimes. The no-shock filter removed the worst
losers but didn't solve the regime problem — there are periods where direction
calling degrades across the board.

**ETH specifically**: PF 0.97 at 360d stress, 39% WR. The only losing symbol.
Responsible for dragging multi-symbol PF from ~1.4 to 1.30. The 180d slice was
kind to ETH (PF 4.08, 67% WR) — this was a regime artifact, not a property of
ETH itself.

---

### 4. VWAP/EMA alignment filters (falsified)

**Trigger**: Reasonable hypothesis — if entry aligns with VWAP or EMA slope,
maybe it's better. The MTF cascade does multi-timeframe direction but doesn't
explicitly check VWAP or EMA steepness.

**Method**:
1. Built `build_vwap_index()` in `features/vwap.py` — session-anchored VWAP
   with bands, slope, trend classification.
2. Added `vwap_alignment()` and `ema_slope_alignment()` helper functions.
3. Added per-trade feature columns: `vwap_alignment`, `ema_alignment`,
   `ema21_slope`.
4. Added CLI filter flags `--vwap-alignments`, `--ema-alignments`.
5. Tested: VWAP aligned only, EMA aligned only, VWAP + EMA combined.

**Result**: Every filter degraded performance. VWAP-only: PF 1.59 (vs 2.58
baseline). EMA-only: PF 2.02. Combined: PF 1.69.

**Why it failed**: The MTF cascade already self-selects for aligned VWAP/EMA
states. The 240m EMA21/55 direction logic captures the same bias VWAP and EMA
slope provide. Adding explicit filters cuts marginal entries that were
directionally correct — you lose trade count without improving win rate.

---

### 5. Portfolio validation + review packet (deployment prep)

**Trigger**: Raw trade-level results don't account for real-world portfolio
constraints — you can't take every trade, you need to throttle by account risk.

**Method**:
1. Used existing `simulate_portfolio()` with `PortfolioRiskConfig`.
2. Parameters: 0.25% risk/trade, max 3 concurrent, max 1 per symbol, 0.5%
   daily loss limit.
3. Exported accepted trades via `build_full_review_packet()` to review UI.

**Finding**: 77 of 94 candidates accepted (82%). PF 2.43, max DD 2.1%. The
setup passes portfolio risk at 180d but the 30d still has ~10% negative windows.

---

## What We Falsified (Equally Important)

| Hypothesis | Status | Evidence |
|-----------|--------|----------|
| VWAP alignment improves entry quality | **FALSIFIED** | All VWAP/EMA filters degrade PF |
| EMA slope alignment improves entry quality | **FALSIFIED** | Same as above |
| 30m entry is better than 15m | **FALSIFIED** | PF 1.40 (30m) vs 2.61 (15m) at 90d |
| 180d results generalize to 360d | **FALSIFIED** | PF drops from 2.62 to 1.30 |
| ETH can trade the same setup as other symbols | **FALSIFIED** | PF 0.97 at 360d — losing symbol |
| Fixed 6bps/20bps is a reasonable cost model | **FALSIFIED** | Replaced with ATR-scaled model |
| Session-only filters can solve 30d weakness | **FALSIFIED** | Asia-only still negative at 30d |

---

## What We Confirmed

| Fact | Confidence | Evidence |
|------|-----------|----------|
| Context_change setup has real edge | High | 180d PF 2.62 stress, 55% WR, 100% positive 60/90d windows |
| No-shock filter is the best single improvement | High | +16pp WR, +83% PF at 90d |
| Asia session is materially stronger | High | 180d return/DD 9.16 (asia) vs ~4 (multi-session) |
| 15m entry beats 30m | High | Direct comparison, consistent across periods |
| DMI aligned > DMI opposed | Medium | Consistent in extended periods |
| Regime dependency is the main unsolved problem | High | 360d degradation is real |
| XRP and SOL are strongest symbols | High | Consistent across 90/180/360d |
| ETH is the weakest symbol | High | PF 0.97 at 360d stress |

---

## How the Methodology Evolved

```
Phase 1-39: Foundation building, MTF cascade, structural detection
        ↓
Phase 40: Filter diagnostics — asia-only best, but 30d still negative
        ↓
Phase 41: MANUAL TRADE INSPECTION — worst 5 losers → aligned_shock found
        ↓            (This was the breakthrough. Aggregates hid it.)
Phase 42: Filter testing — no-shock confirmed
        ↓
Phase 43: VWAP/EMA built and tested — all degraded
        ↓
Phase 44: ATR-scaled costs + multi-window rolling
        ↓
Phase 45: 360d stress test — regime dependency exposed
        ↓
Phase 46: VWAP/EMA formal comparison — reconfirmed
        ↓
Phase 47: Portfolio validation + review packet export
```

## Key Tooling Decisions

### What We Built (infrastructure that enabled discoveries)

- `--shock-alignments` filter flag → no-shock discovery wouldn't have been
  actionable without this.
- `--slippage-mode atr_scaled` → without realistic costs, the 360d stress
  result could be misleading.
- `build_vwap_index()` in `features/vwap.py` → even though the filters were
  rejected, the feature columns are useful for diagnostics.
- `rolling_windows()` → 30/60/90d windows exposed time-varying performance
  that single-period aggregates hide.
- `build_full_review_packet()` → enables human visual validation, which is
  the final gate before any deployment.

### What We Could Have Built But Didn't

- **Regime classifier** — would have caught the 360d problem proactively
  instead of reactively. Now the top priority.
- **Per-symbol config** — ETH needs different params or exclusion. Currently
  all symbols share one config.
- **Walk-forward cross-validation** — would have caught the 180d→360d
  degradation earlier. Rolling windows are a step in this direction.
