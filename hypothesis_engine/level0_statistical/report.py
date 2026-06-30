"""
Reporting for Level 0 statistical scanner.

Produces:
  1. Per-pocket detailed stats
  2. Summary table of significant pockets (ci excludes zero)
  3. CSV export
"""

from __future__ import annotations


def pocket_summary(result: dict) -> str:
    """One-line summary of a pocket scan result."""
    if "error" in result:
        return f"{result.get('symbol','?')} {result.get('tf','?')}: ERROR — {result['error']}"

    sessions = result.get("sessions", {})
    total_pockets = sum(len(v) for v in sessions.values())
    sig_pockets = _count_significant(result)
    return (
        f"{result['symbol']:<8} {result['tf']:>3}m  "
        f"{result['bars']:>6} bars  "
        f"{result['start']} - {result['end']}  "
        f"{total_pockets:>3} pockets  "
        f"{sig_pockets:>3} significant"
    )


def _count_significant(result: dict) -> int:
    """Count pockets where CI excludes zero and t > 2."""
    count = 0
    for sname, sdata in result.get("sessions", {}).items():
        for key, stats in sdata.items():
            if not stats.get("ci_contains_zero", True) and abs(stats.get("t_stat", 0)) > 1.96:
                count += 1
    return count


POCKET_HEADER = (
    f"{'Symbol':<8} {'TF':>3} {'Session':<12} {'Dir':<5} "
    f"{'Horizon':>7} {'N':>6} {'MeanRet':>9} {'WR':>6} "
    f"{'PF':>6} {'t_stat':>7} {'CI_low':>9} {'CI_high':>9} {'Sig':>4}"
)


def pocket_row(symbol: str, tf: str, session: str, direction: str,
               horizon: int, stats: dict) -> str:
    """Single row in the results table."""
    sig = "YES" if (not stats.get("ci_contains_zero", True)
                    and abs(stats.get("t_stat", 0)) > 1.96) else ""
    return (
        f"{symbol:<8} {tf:>3} {session:<12} {direction:<5} "
        f"{horizon:>7} {stats['n']:>6} {stats['mean_ret']:>9.6f} "
        f"{stats['win_rate']:>6.1%} {stats['profit_factor']:>6.2f} "
        f"{stats['t_stat']:>7.2f} {stats['ci_low']:>9.6f} "
        f"{stats['ci_high']:>9.6f} {sig:>4}"
    )


def format_results(results: list[dict], min_pockets: int = 0) -> str:
    """Format all scan results into a readable table."""
    lines = []
    lines.append("=" * 100)
    lines.append("LEVEL 0 — STATISTICAL POCKET SCAN")
    lines.append("=" * 100)

    for result in results:
        if "error" in result:
            lines.append(pocket_summary(result))
            continue

        summary = pocket_summary(result)
        sessions = result.get("sessions", {})
        pocket_count = sum(len(v) for v in sessions.values())
        if pocket_count < min_pockets:
            continue

        lines.append("")
        lines.append(summary)
        lines.append(POCKET_HEADER)
        lines.append("-" * 100)

        for sname in sorted(sessions.keys()):
            for key in sorted(sessions[sname].keys()):
                dir_h = key.split("_")
                direction = dir_h[0]
                horizon = dir_h[1] if len(dir_h) > 1 else "?"
                stats = sessions[sname][key]
                lines.append(pocket_row(
                    result["symbol"], result["tf"],
                    sname, direction, int(horizon) if horizon.isdigit() else 0,
                    stats,
                ))

    lines.append("")
    lines.append("=" * 100)
    total_sig = sum(_count_significant(r) for r in results if "error" not in r)
    total_pock = sum(sum(len(v) for v in r.get("sessions", {}).values())
                     for r in results if "error" not in r)
    lines.append(f"Total pockets: {total_pock}, Significant: {total_sig}")
    lines.append("=" * 100)
    return "\n".join(lines)
