"""Performance metrics (spec §10) and the pass/fail rule (spec §11)."""
import numpy as np
import pandas as pd

from src import ftmo_rules


def all_months(start_date, end_date):
    return pd.period_range(pd.Timestamp(start_date), pd.Timestamp(end_date), freq="M")


def monthly_pnl(trades, months):
    if trades.empty:
        return pd.Series(0.0, index=months)
    by = trades.groupby(pd.to_datetime(trades.date).dt.to_period("M")).net_pnl.sum()
    return by.reindex(months, fill_value=0.0)


def longest_losing_streak(pnl):
    best = run = 0
    for x in pnl:
        run = run + 1 if x < 0 else 0
        best = max(best, run)
    return best


def max_drawdown(trades, initial):
    """Largest drop from the closed-balance peak to the lowest equity (incl. floating)."""
    if trades.empty:
        return 0.0, 0.0
    peak_before = np.maximum.accumulate(np.r_[initial, trades.balance_after.to_numpy()[:-1]])
    peak_before = np.maximum(peak_before, initial)
    low = (trades.balance_before + trades.floating_min).to_numpy()
    dd = peak_before - low
    i = int(np.argmax(dd))
    return float(dd[i]), float(dd[i] / peak_before[i])


def summarize(trades, months, initial=10_000.0):
    m = monthly_pnl(trades, months)
    windows = [int((m.iloc[i:i + 6] > 0).sum()) for i in range(len(m) - 5)]
    dd_usd, dd_pct = max_drawdown(trades, initial)
    ftmo = ftmo_rules.evaluate(trades, initial)
    n = len(trades)
    day_pnl = trades.groupby("date").net_pnl.sum() if n else pd.Series(dtype=float)
    return {
        "trades": n,
        "win_rate": float((trades.net_pnl > 0).mean()) if n else 0.0,
        "avg_r": float(trades.r_multiple.mean()) if n else 0.0,
        "expectancy_usd": float(trades.net_pnl.mean()) if n else 0.0,
        "net_profit": float(trades.net_pnl.sum()) if n else 0.0,
        "pct_months_profitable": float((m > 0).mean()),
        "avg_month": float(m.mean()),
        "worst_month": float(m.min()), "worst_month_label": str(m.idxmin()),
        "worst_day": float(day_pnl.min()) if n else 0.0,
        "max_dd_usd": dd_usd, "max_dd_pct": dd_pct,
        "longest_losing_streak": longest_losing_streak(trades.net_pnl) if n else 0,
        "min_profitable_in_6m_window": min(windows) if windows else 0,
        "ftmo_breached": ftmo["breached"], "ftmo_breach": (ftmo["breach_rule"], ftmo["breach_date"]),
        "ftmo_phase1_passed": ftmo["phase1_passed"], "ftmo_phase2_passed": ftmo["phase2_passed"],
        "ftmo_flagged_exits": int(trades.ftmo_flagged_exit.sum()) if n else 0,
        "monthly": m,
    }


def c1_percentile(a_net, c1_nets):
    """Share of C1 runs whose net profit is strictly below A's."""
    c1 = np.asarray(c1_nets)
    return float((c1 < a_net).mean())


def strategy_verdict(s, c1_pct):
    """spec §11: all four must hold."""
    checks = {
        "avg net profit >= $100/month": s["avg_month"] >= 100,
        ">= 4 profitable months in every 6-month window": s["min_profitable_in_6m_window"] >= 4,
        "no FTMO breach": not s["ftmo_breached"],
        "beats >= 90% of C1 runs": c1_pct >= 0.90,
    }
    return all(checks.values()), checks
