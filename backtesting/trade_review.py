#!/usr/bin/env python3
"""
Trade review: MFE/MAE analysis + per-trade progression charts.

Two outputs:
  1. Summary chart: MFE/MAE scatter + exit distribution + equity curve
  2. Per-trade HTML: interactive candlestick review via lightweight JS

Usage:
    from backtesting.trade_review import TradeReviewer
    reviewer = TradeReviewer(result, price_df, entry_tf="15")
    reviewer.summary(save="backtesting/results/review_summary.png")
    reviewer.html_review(save="backtesting/results/review_trades.html")

Or from command line:
    python backtesting/trade_review.py  (runs built-in example)
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backtesting.engine.orders import ClosedTrade, Direction, ExitReason
from backtesting.engine.runner import BacktestResult


# ── MFE/MAE computation ───────────────────────────────────────────────────────

@dataclass
class TradeMFE:
    trade: ClosedTrade
    mfe_r: float    # max favorable excursion in R (multiples of initial risk)
    mae_r: float    # max adverse excursion in R
    duration_bars: int
    bars: Optional[pd.DataFrame] = field(default=None, repr=False)


def compute_mfe_mae(
    trades: list[ClosedTrade],
    price_df: pd.DataFrame,
) -> list[TradeMFE]:
    """
    Compute MFE/MAE for each trade in R multiples.
    price_df must have ts/datetime index + high/low/close columns.
    """
    if price_df.empty or not trades:
        return []

    df = price_df.copy()
    if "ts" in df.columns:
        df = df.set_index("ts")
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index, utc=True)
    df = df.sort_index()

    results = []
    for t in trades:
        entry_ts = pd.Timestamp(t.entry_time)
        exit_ts  = pd.Timestamp(t.exit_time)
        if entry_ts.tzinfo is None:
            entry_ts = entry_ts.tz_localize("UTC")
        if exit_ts.tzinfo is None:
            exit_ts = exit_ts.tz_localize("UTC")

        mask = (df.index >= entry_ts) & (df.index <= exit_ts)
        bars = df[mask]
        if bars.empty:
            continue

        risk = abs(t.entry_price - t.sl) if t.sl else 0
        if risk == 0:
            continue

        if t.direction == Direction.LONG:
            mfe = (bars["high"].max() - t.entry_price) / risk
            mae = (t.entry_price - bars["low"].min()) / risk
        else:
            mfe = (t.entry_price - bars["low"].min()) / risk
            mae = (bars["high"].max() - t.entry_price) / risk

        results.append(TradeMFE(
            trade=t,
            mfe_r=round(float(mfe), 3),
            mae_r=round(float(mae), 3),
            duration_bars=len(bars),
            bars=bars,
        ))
    return results


# ── Summary chart ─────────────────────────────────────────────────────────────

class TradeReviewer:
    def __init__(
        self,
        result: BacktestResult,
        price_df: pd.DataFrame,
        label: str = "",
    ):
        self.result = result
        self.price_df = price_df
        self.label = label
        self._mfe_mae = compute_mfe_mae(result.trades, price_df)

    def summary(self, save: Optional[str] = None, show: bool = False) -> None:
        """4-panel summary: MFE/MAE scatter, exit reasons, equity, MFE histogram."""
        trades = self.result.trades
        mfes = self._mfe_mae
        if not trades:
            print("No trades to review.")
            return

        fig, axes = plt.subplots(2, 2, figsize=(14, 9))
        fig.suptitle(f"Trade Review{' — ' + self.label if self.label else ''}", fontsize=13)

        # ── 1. MFE vs MAE scatter ─────────────────────────────────────────────
        ax = axes[0, 0]
        wins   = [m for m in mfes if m.trade.pnl > 0]
        losses = [m for m in mfes if m.trade.pnl <= 0]
        if wins:
            ax.scatter([m.mae_r for m in wins], [m.mfe_r for m in wins],
                       c="green", alpha=0.6, s=40, label="Win")
        if losses:
            ax.scatter([m.mae_r for m in losses], [m.mfe_r for m in losses],
                       c="red", alpha=0.6, s=40, label="Loss")
        # Reference lines: typical TP/SL
        ax.axhline(1.0, color="green", lw=0.8, ls="--", alpha=0.5, label="1R TP")
        ax.axvline(1.0, color="red",   lw=0.8, ls="--", alpha=0.5, label="1R SL")
        ax.set_xlabel("MAE (R)")
        ax.set_ylabel("MFE (R)")
        ax.set_title("MFE vs MAE per trade")
        ax.legend(fontsize=8)
        ax.set_xlim(left=0)
        ax.set_ylim(bottom=0)

        # Stats annotation
        if mfes:
            avg_mfe = np.mean([m.mfe_r for m in mfes])
            avg_mae = np.mean([m.mae_r for m in mfes])
            pct_mfe_gt1 = np.mean([m.mfe_r > 1 for m in mfes]) * 100
            pct_mae_lt1 = np.mean([m.mae_r < 1 for m in mfes]) * 100
            ax.text(0.02, 0.98,
                    f"avg MFE={avg_mfe:.2f}R  avg MAE={avg_mae:.2f}R\n"
                    f"MFE>1R: {pct_mfe_gt1:.0f}%  MAE<1R: {pct_mae_lt1:.0f}%",
                    transform=ax.transAxes, va="top", fontsize=8,
                    bbox=dict(boxstyle="round", fc="white", alpha=0.8))

        # ── 2. Exit reason distribution ───────────────────────────────────────
        ax = axes[0, 1]
        exit_counts = {}
        for t in trades:
            k = t.exit_reason.value if hasattr(t.exit_reason, "value") else str(t.exit_reason)
            exit_counts[k] = exit_counts.get(k, 0) + 1
        colors = {"sl": "#d32f2f", "tp1": "#388e3c", "tp2": "#1976d2",
                  "tp3": "#7b1fa2", "trail": "#f57c00", "eod": "#607d8b", "signal": "#455a64"}
        labels = list(exit_counts.keys())
        vals   = [exit_counts[k] for k in labels]
        clrs   = [colors.get(k, "#9e9e9e") for k in labels]
        bars_plot = ax.bar(labels, vals, color=clrs)
        for bar_rect, v in zip(bars_plot, vals):
            ax.text(bar_rect.get_x() + bar_rect.get_width() / 2, v + 0.3,
                    str(v), ha="center", va="bottom", fontsize=9)
        ax.set_title("Exit reasons")
        ax.set_ylabel("Count")

        # ── 3. Equity curve ───────────────────────────────────────────────────
        ax = axes[1, 0]
        eq = self.result.report.get("equity_curve", [])
        if eq:
            ax.plot(eq, color="#1565c0", lw=1.5)
            ax.axhline(eq[0], color="gray", lw=0.8, ls="--")
            ax.fill_between(range(len(eq)), eq[0], eq, alpha=0.1, color="#1565c0")
            rpt = self.result.report
            ax.set_title(f"Equity  PF={rpt.get('profit_factor',0):.2f}  "
                         f"WR={rpt.get('win_rate',0):.0%}  "
                         f"MaxDD={rpt.get('max_drawdown_pct',0):.1%}")
        ax.set_xlabel("Trade #")
        ax.set_ylabel("Equity ($)")

        # ── 4. MFE histogram + "money left on table" ─────────────────────────
        ax = axes[1, 1]
        if mfes:
            mfe_vals = [m.mfe_r for m in mfes]
            ax.hist(mfe_vals, bins=20, color="#43a047", alpha=0.7, edgecolor="white")
            ax.axvline(np.mean(mfe_vals), color="darkgreen", lw=1.5, ls="--",
                       label=f"avg={np.mean(mfe_vals):.2f}R")
            # Mark where TP1 is (from first trade that has tp1)
            for t in trades:
                if t.sl and t.tp1:
                    tp1_r = abs(t.tp1 - t.entry_price) / abs(t.entry_price - t.sl)
                    ax.axvline(tp1_r, color="blue", lw=1.2, ls=":",
                               label=f"TP1≈{tp1_r:.1f}R")
                    break
            ax.set_title("MFE distribution (R)")
            ax.set_xlabel("MFE (R)")
            ax.set_ylabel("Count")
            ax.legend(fontsize=8)

        plt.tight_layout()
        if save:
            Path(save).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save, dpi=150, bbox_inches="tight")
            print(f"Saved: {save}")
        if show:
            plt.show()
        plt.close()

    def html_review(self, save: str = "backtesting/results/trade_review.html",
                    max_trades: int = 50, lookback_bars: int = 40,
                    lookahead_bars: int = 20) -> None:
        """
        Generate self-contained HTML with per-trade candlestick charts.
        Uses pure JS/Canvas — no server needed, open in any browser.
        """
        mfes = self._mfe_mae[:max_trades]
        if not mfes:
            print("No trades to review.")
            return

        df = self.price_df.copy()
        if "ts" in df.columns:
            df = df.set_index("ts")
        df = df.sort_index().reset_index()

        trade_data = []
        for m in mfes:
            t = m.trade
            entry_ts = pd.Timestamp(t.entry_time)
            exit_ts  = pd.Timestamp(t.exit_time)

            # Find bar indices
            ts_col = df.columns[0]
            ts_series = pd.to_datetime(df[ts_col])
            entry_idx = (ts_series - entry_ts).abs().idxmin()
            exit_idx  = (ts_series - exit_ts).abs().idxmin()
            start_idx = max(0, entry_idx - lookback_bars)
            end_idx   = min(len(df) - 1, exit_idx + lookahead_bars)

            bars = df.iloc[start_idx:end_idx + 1]
            candles = [
                {
                    "t": str(row[ts_col])[:16],
                    "o": float(row["open"]),
                    "h": float(row["high"]),
                    "l": float(row["low"]),
                    "c": float(row["close"]),
                    "entry": entry_idx - start_idx == j,
                    "exit":  exit_idx - start_idx == j,
                }
                for j, (_, row) in enumerate(bars.iterrows())
            ]
            trade_data.append({
                "id": t.id,
                "dir": t.direction.value if hasattr(t.direction, "value") else str(t.direction),
                "entry": t.entry_price,
                "exit": t.exit_price,
                "sl": t.sl or 0,
                "tp1": t.tp1 or 0,
                "reason": t.exit_reason.value if hasattr(t.exit_reason, "value") else str(t.exit_reason),
                "pnl": round(t.pnl, 2),
                "r": round(t.r_multiple, 2),
                "mfe": m.mfe_r,
                "mae": m.mae_r,
                "label": t.label or "",
                "candles": candles,
            })

        import json
        trades_json = json.dumps(trade_data)

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Trade Review{' — ' + self.label if self.label else ''}</title>
<style>
  body{{font-family:monospace;background:#111;color:#ccc;margin:0;padding:8px}}
  h2{{color:#eee;margin:4px 0}}
  .controls{{display:flex;gap:8px;align-items:center;margin:8px 0;flex-wrap:wrap}}
  button{{background:#222;color:#ccc;border:1px solid #444;padding:4px 10px;cursor:pointer;border-radius:3px}}
  button:hover{{background:#333}} button.active{{background:#1a5f1a;color:#8f8}}
  .info{{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:4px;margin:6px 0}}
  .kv{{background:#1a1a1a;padding:4px 8px;border-radius:3px;font-size:12px}}
  .kv span{{color:#888;font-size:11px}} .win{{color:#4caf50}} .loss{{color:#ef5350}}
  canvas{{display:block;background:#0d0d0d;border:1px solid #333;width:100%;height:300px}}
  #nav{{display:flex;gap:6px;align-items:center;margin:6px 0}}
  #counter{{color:#888;font-size:12px}}
  .tag{{background:#333;border-radius:3px;padding:1px 5px;font-size:11px;color:#aaa}}
</style>
</head><body>
<h2>Trade Review{' — ' + self.label if self.label else ''} ({len(trade_data)} trades)</h2>
<div id="nav">
  <button onclick="prev()">◀ Prev</button>
  <button onclick="next()">Next ▶</button>
  <span id="counter"></span>
</div>
<div class="info" id="info"></div>
<canvas id="chart"></canvas>
<script>
const TRADES = {trades_json};
let idx = 0;

function draw() {{
  const t = TRADES[idx];
  document.getElementById("counter").textContent = (idx+1) + " / " + TRADES.length;
  const pnlClass = t.pnl >= 0 ? "win" : "loss";
  document.getElementById("info").innerHTML = [
    `<div class="kv"><span>ID</span><br>#${{t.id}} ${{t.label ? '<span class=tag>'+t.label+'</span>' : ''}}</div>`,
    `<div class="kv"><span>Dir</span><br>${{t.dir.toUpperCase()}}</div>`,
    `<div class="kv"><span>PnL</span><br><b class="${{pnlClass}}">${{t.pnl >= 0 ? '+' : ''}}${{t.pnl}}</b></div>`,
    `<div class="kv"><span>R-mult</span><br><b class="${{pnlClass}}">${{t.r >= 0 ? '+' : ''}}${{t.r}}R</b></div>`,
    `<div class="kv"><span>Reason</span><br>${{t.reason}}</div>`,
    `<div class="kv"><span>MFE/MAE</span><br>+${{t.mfe}}R / -${{t.mae}}R</div>`,
    `<div class="kv"><span>Entry/Exit</span><br>${{t.entry}} → ${{t.exit}}</div>`,
    `<div class="kv"><span>SL/TP1</span><br>${{t.sl}} / ${{t.tp1 || '—'}}</div>`,
  ].join('');

  const canvas = document.getElementById("chart");
  const ctx = canvas.getContext("2d");
  canvas.width = canvas.offsetWidth; canvas.height = 300;
  const W = canvas.width, H = canvas.height;
  const candles = t.candles;
  const highs = candles.map(c => c.h), lows = candles.map(c => c.l);
  const pmin = Math.min(...lows, t.sl || Infinity, t.tp1 || Infinity);
  const pmax = Math.max(...highs, t.sl || -Infinity, t.tp1 || -Infinity);
  const pad = (pmax - pmin) * 0.05;
  const lo = pmin - pad, hi = pmax + pad;
  const py = p => H - ((p - lo) / (hi - lo)) * (H - 20) - 10;
  const cw = Math.max(2, Math.floor((W - 20) / candles.length) - 1);
  const cx = i => 10 + i * (cw + 1) + cw / 2;
  ctx.clearRect(0, 0, W, H);

  // Horizontal reference lines
  const drawLine = (price, color, dash) => {{
    if (!price) return;
    ctx.strokeStyle = color; ctx.lineWidth = 1;
    ctx.setLineDash(dash || []);
    ctx.beginPath(); ctx.moveTo(0, py(price)); ctx.lineTo(W, py(price)); ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = color; ctx.font = "10px monospace";
    ctx.fillText(price.toFixed(5), 4, py(price) - 3);
  }};
  drawLine(t.entry, "#90caf9", [4,2]);
  drawLine(t.sl,    "#ef5350", [4,2]);
  drawLine(t.tp1,   "#66bb6a", [4,2]);

  // Candles
  candles.forEach((c, i) => {{
    const x = cx(i), open = py(c.o), close = py(c.c), high = py(c.h), low = py(c.l);
    const bull = c.c >= c.o;
    const color = c.entry ? "#2196f3" : c.exit ? "#ff9800" : bull ? "#26a69a" : "#ef5350";
    ctx.strokeStyle = color; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(x, high); ctx.lineTo(x, low); ctx.stroke();
    ctx.fillStyle = color;
    ctx.fillRect(x - cw/2, Math.min(open, close), cw, Math.max(1, Math.abs(close - open)));
  }});

  // Entry/exit markers
  candles.forEach((c, i) => {{
    if (c.entry || c.exit) {{
      const x = cx(i);
      ctx.fillStyle = c.entry ? "#2196f3" : "#ff9800";
      ctx.font = "11px sans-serif";
      ctx.fillText(c.entry ? "▲ ENTRY" : "● EXIT", x - 20, py(c.entry ? c.l : c.h) + (c.entry ? 14 : -4));
    }}
  }});

  // Time labels
  ctx.fillStyle = "#555"; ctx.font = "9px monospace";
  [0, Math.floor(candles.length/2), candles.length-1].forEach(i => {{
    if (candles[i]) ctx.fillText(candles[i].t, cx(i) - 28, H - 1);
  }});
}}

function next() {{ if (idx < TRADES.length-1) {{ idx++; draw(); }} }}
function prev() {{ if (idx > 0) {{ idx--; draw(); }} }}
document.addEventListener("keydown", e => {{
  if (e.key === "ArrowRight") next();
  if (e.key === "ArrowLeft") prev();
}});
draw();
window.addEventListener("resize", draw);
</script></body></html>"""

        Path(save).parent.mkdir(parents=True, exist_ok=True)
        Path(save).write_text(html)
        print(f"Saved: {save}  ({len(trade_data)} trades, open in browser)")


# ── CLI demo ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from backtesting.engine.data import load_data
    from backtesting.engine.runner import run
    from backtesting.engine.costs import ForexCosts
    from backtesting.strategies.tr_accumulation import TrAccumulation

    pair, tf = "EURUSD", "15"
    data = {tf: load_data(pair, tf=tf, start="2026-03-17", end="2026-05-23")}
    result = run(TrAccumulation(compress_ratio=0.65), data, entry_tf=tf, costs=ForexCosts())
    print(result.summary())

    reviewer = TradeReviewer(result, data[tf], label=f"{pair} {tf}m TrAccumulation")
    reviewer.summary(save="backtesting/results/review_summary.png", show=False)
    reviewer.html_review(save="backtesting/results/review_trades.html")
