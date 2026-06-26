"""
Performance metrics computed from a list of ClosedTrade.

All functions are pure — no side effects.
"""

from __future__ import annotations

import math
from typing import Sequence

from .orders import ClosedTrade, ExitReason


def compute(trades: Sequence[ClosedTrade], initial_equity: float = 10_000.0) -> dict:
    """
    Compute full performance report from a list of closed trades.

    Returns a flat dict suitable for printing or DataFrame insertion.
    """
    if not trades:
        return _empty_report(initial_equity)

    pnls = [t.pnl for t in trades]
    r_multiples = [t.r_multiple for t in trades]

    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    n = len(trades)

    win_rate = len(wins) / n if n else 0.0
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    profit_factor = sum(wins) / abs(sum(losses)) if losses else float("inf")
    expectancy = sum(pnls) / n if n else 0.0
    total_pnl = sum(pnls)
    avg_r = sum(r_multiples) / n if n else 0.0
    final_equity = initial_equity + total_pnl
    return_pct = total_pnl / initial_equity if initial_equity else 0.0
    payoff_ratio = (avg_win / abs(avg_loss)) if avg_loss else 0.0

    # Equity curve and drawdown
    equity_curve = _equity_curve(pnls, initial_equity)
    max_dd, max_dd_pct = _max_drawdown(equity_curve)
    durations_min = _durations_min(trades)

    # Exit breakdown
    exit_counts: dict[str, int] = {}
    for t in trades:
        key = t.exit_reason.value if hasattr(t.exit_reason, "value") else str(t.exit_reason)
        exit_counts[key] = exit_counts.get(key, 0) + 1

    # Consecutive stats
    max_consec_wins = _max_consecutive(pnls, positive=True)
    max_consec_losses = _max_consecutive(pnls, positive=False)

    # Sharpe (daily grouping, approximate)
    sharpe = _sharpe(trades)

    return {
        "trades": n,
        "win_rate": round(win_rate, 4),
        "profit_factor": round(profit_factor, 3),
        "expectancy": round(expectancy, 2),
        "total_pnl": round(total_pnl, 2),
        "final_equity": round(final_equity, 2),
        "return_pct": round(return_pct, 4),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "payoff_ratio": round(payoff_ratio, 3),
        "avg_r": round(avg_r, 3),
        "median_pnl": round(_median(pnls), 2),
        "best_trade": round(max(pnls), 2),
        "worst_trade": round(min(pnls), 2),
        "avg_duration_min": round(sum(durations_min) / len(durations_min), 1) if durations_min else 0.0,
        "median_duration_min": round(_median(durations_min), 1) if durations_min else 0.0,
        "max_drawdown": round(max_dd, 2),
        "max_drawdown_pct": round(max_dd_pct, 4),
        "sharpe": round(sharpe, 3),
        "max_consec_wins": max_consec_wins,
        "max_consec_losses": max_consec_losses,
        "exit_counts": exit_counts,
        "equity_curve": equity_curve,
        # Per-trade breakdown for analysis
        "trade_pnls": [round(p, 2) for p in pnls],
        "trade_r_multiples": [round(r, 3) for r in r_multiples],
    }


def _empty_report(initial_equity: float = 0.0) -> dict:
    return {
        "trades": 0,
        "win_rate": 0.0,
        "profit_factor": 0.0,
        "expectancy": 0.0,
        "total_pnl": 0.0,
        "final_equity": round(initial_equity, 2),
        "return_pct": 0.0,
        "avg_win": 0.0,
        "avg_loss": 0.0,
        "payoff_ratio": 0.0,
        "avg_r": 0.0,
        "median_pnl": 0.0,
        "best_trade": 0.0,
        "worst_trade": 0.0,
        "avg_duration_min": 0.0,
        "median_duration_min": 0.0,
        "max_drawdown": 0.0,
        "max_drawdown_pct": 0.0,
        "sharpe": 0.0,
        "max_consec_wins": 0,
        "max_consec_losses": 0,
        "exit_counts": {},
        "equity_curve": [initial_equity] if initial_equity else [],
        "trade_pnls": [],
        "trade_r_multiples": [],
    }


def _equity_curve(pnls: list[float], initial: float) -> list[float]:
    curve = [initial]
    for p in pnls:
        curve.append(curve[-1] + p)
    return curve


def _max_drawdown(equity_curve: list[float]) -> tuple[float, float]:
    """Returns (max_dd_abs, max_dd_pct)."""
    if len(equity_curve) < 2:
        return 0.0, 0.0
    peak = equity_curve[0]
    max_dd = 0.0
    max_dd_pct = 0.0
    for val in equity_curve:
        if val > peak:
            peak = val
        dd = peak - val
        dd_pct = dd / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
        if dd_pct > max_dd_pct:
            max_dd_pct = dd_pct
    return max_dd, max_dd_pct


def _max_consecutive(pnls: list[float], positive: bool) -> int:
    best = 0
    current = 0
    for p in pnls:
        if (p > 0) == positive:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    vals = sorted(values)
    mid = len(vals) // 2
    if len(vals) % 2:
        return float(vals[mid])
    return float((vals[mid - 1] + vals[mid]) / 2)


def _durations_min(trades: Sequence[ClosedTrade]) -> list[float]:
    out = []
    for t in trades:
        try:
            delta = t.exit_time - t.entry_time
            out.append(float(delta.total_seconds() / 60))
        except Exception:
            continue
    return out


def _sharpe(trades: Sequence[ClosedTrade], risk_free: float = 0.0) -> float:
    """
    Approximate annualized Sharpe using per-trade R-multiples.
    Assumes ~252 trades/year for annualization (rough).
    """
    if len(trades) < 2:
        return 0.0
    rs = [t.r_multiple for t in trades]
    mean_r = sum(rs) / len(rs)
    variance = sum((r - mean_r) ** 2 for r in rs) / (len(rs) - 1)
    std_r = math.sqrt(variance) if variance > 0 else 0.0
    if std_r == 0:
        return 0.0
    return (mean_r - risk_free) / std_r * math.sqrt(252)


def summary_str(report: dict) -> str:
    """Human-readable one-page summary."""
    ec = report.get("equity_curve", [])
    final_eq = ec[-1] if ec else 0.0
    lines = [
        f"Trades:      {report['trades']}",
        f"Win rate:    {report['win_rate']:.1%}",
        f"Profit factor: {report['profit_factor']:.2f}",
        f"Payoff/RR:   {report.get('payoff_ratio', 0):.2f}",
        f"Expectancy:  ${report['expectancy']:.2f} / trade",
        f"Total PnL:   ${report['total_pnl']:.2f} ({report.get('return_pct', 0):.1%})  final equity: ${final_eq:.2f}",
        f"Avg R:       {report['avg_r']:.2f}R",
        f"Best/Worst:  ${report.get('best_trade', 0):.2f} / ${report.get('worst_trade', 0):.2f}",
        f"Max DD:      ${report['max_drawdown']:.2f} ({report['max_drawdown_pct']:.1%})",
        f"Avg hold:    {report.get('avg_duration_min', 0):.1f} min",
        f"Sharpe:      {report['sharpe']:.2f}",
        f"Consec W/L:  {report['max_consec_wins']} / {report['max_consec_losses']}",
        f"Exits:       {report['exit_counts']}",
    ]
    return "\n".join(lines)


def table_row(
    report: dict,
    label: str = "",
    tf: str = "",
    start: str = "",
    end: str = "",
) -> str:
    """
    Single-line table row with all key metrics.
    Format: Label | TF | Duration | T | WR | RR | PF | DD | PnL | Trade PnL list
    """
    # Duration bucket
    dur_days = 0
    if start and end:
        try:
            from datetime import datetime
            fmt = "%Y-%m-%d"
            dur_days = (datetime.strptime(end[:10], fmt) - datetime.strptime(start[:10], fmt)).days
        except Exception:
            pass
    if dur_days <= 0 and report.get("avg_duration_min", 0) and report.get("trades", 0):
        pass  # can't infer window duration from trade durations

    dur_bucket = (
        "90d" if dur_days >= 75 else
        "60d" if dur_days >= 45 else
        "30d" if dur_days >= 20 else
        f"{dur_days}d" if dur_days > 0 else
        "  —"
    )

    t = report.get("trades", 0)
    wr = report.get("win_rate", 0)
    rr = report.get("payoff_ratio", 0)
    pf = report.get("profit_factor", 0)
    dd = report.get("max_drawdown_pct", 0)
    pnl = report.get("total_pnl", 0)

    return (
        f"{label:<16} {tf:>4} {dur_bucket:>5}  "
        f"T={t:>3}  WR={wr:>5.1%}  RR={rr:>4.2f}  PF={pf:>5.2f}  "
        f"DD={dd:>5.1%}  PnL={pnl:>+8.2f}"
    )


def table_header() -> str:
    return (
        f"{'Label':<16} {'TF':>4} {'Dur':>5}  "
        f"{'T':>5}  {'WR':>8}  {'RR':>7}  {'PF':>8}  "
        f"{'DD':>8}  {'PnL':>12}"
    )


def print_table(rows: list[tuple[str, dict, str, str, str]], title: str = "") -> None:
    """
    Print a formatted table of backtest results.

    rows: list of (label, report_dict, tf, start, end)
    """
    if title:
        print(f"\n{'═'*80}")
        print(f"  {title}")
        print(f"{'═'*80}")
    print(table_header())
    print("─" * 80)
    for label, report, tf, start, end in rows:
        print(table_row(report, label=label, tf=tf, start=start, end=end))
        # Print per-trade PnL on next line if trades > 0
        pnls = report.get("trade_pnls", [])
        if pnls:
            pnl_str = "  ".join(f"{p:+.1f}" for p in pnls[:20])
            suffix = f"  …+{len(pnls)-20}" if len(pnls) > 20 else ""
            print(f"  trades: [{pnl_str}{suffix}]")
    print("─" * 80)
