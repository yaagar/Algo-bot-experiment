"""FTMO 2-Step rule simulation (spec §3).

Works from the trade list: each trade carries the balance before it and the
worst floating P&L while it was open (from M1 bars), so equity including
floating losses can be checked against the limits.
"""
import pandas as pd

PRAGUE = "Europe/Prague"


def evaluate(trades, initial=10_000.0, max_daily_loss=500.0, max_loss=1_000.0,
             phase1_target=1_000.0, phase2_target=500.0, min_trading_days=4):
    out = {"breached": False, "breach_date": None, "breach_rule": None,
           "phase1_passed": None, "phase2_passed": None}
    if trades.empty:
        return out
    t = trades.copy()
    t["prague_day"] = t.entry_time_utc.dt.tz_convert(PRAGUE).dt.date
    t["equity_low"] = t.balance_before + t.floating_min

    # Max daily loss: equity incl. floating vs the start-of-day balance (Prague day)
    for day, g in t.groupby("prague_day"):
        if g.balance_before.iloc[0] - g.equity_low.min() >= max_daily_loss:
            out.update(breached=True, breach_date=day, breach_rule="max daily loss 5%")
            break
    # Max loss (static): equity may never go below initial - 10%
    below = t[t.equity_low < initial - max_loss]
    if len(below) and (out["breach_date"] is None or below.prague_day.iloc[0] < out["breach_date"]):
        out.update(breached=True, breach_date=below.prague_day.iloc[0], breach_rule="max loss 10%")

    # Profit targets: Phase 1 (+10%), then Phase 2 (+5%) on a fresh account, each >= 4 trading days
    out["phase1_passed"] = _target_date(t, phase1_target, min_trading_days)
    if out["phase1_passed"] is not None:
        rest = t[t.prague_day > out["phase1_passed"]]
        out["phase2_passed"] = _target_date(rest, phase2_target, min_trading_days)
    return out


def _target_date(t, target, min_days):
    pnl = t.net_pnl.cumsum()
    days = t.prague_day.rank(method="dense")
    hit = t[(pnl >= target) & (days >= min_days)]
    return hit.prague_day.iloc[0] if len(hit) else None
