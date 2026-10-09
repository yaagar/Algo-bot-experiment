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


# --- Portfolio level (Experiment 6 spec §2, Change Log v1.1 e) ----------------------------------
# The trade-list `evaluate` above stays for Experiment 1-4 code (src/metrics.py). Experiment 6 holds
# many positions for days, so limits are checked on the account's equity path instead:
#   equity = balance + floating P/L of ALL open positions + accrued swaps (commissions are already
#   taken from the balance at each fill); checked on every H1 bar's worst (high/low) equity.
#   Max daily loss: equity must stay above (balance at 00:00 Europe/Prague) - 5% of initial capital.
#   Max loss: equity must stay above 90% of initial capital, always.

class PortfolioLimits:
    def __init__(self, initial, daily_loss_pct=5.0, max_loss_pct=10.0, tz=PRAGUE):
        self.initial, self.tz = initial, tz
        self.daily_limit = initial * daily_loss_pct / 100
        self.floor = initial * (1 - max_loss_pct / 100)
        self.day, self.day_start_balance = None, None
        self.breaches = []                   # first breach per Prague day and rule: (time ns, rule, equity, limit)
        self.days = {}                       # Prague date -> {"start_balance", "min_equity"}

    def prague_date(self, t_ns):
        return pd.Timestamp(int(t_ns), tz="UTC").tz_convert(self.tz).date()

    def new_time(self, t_ns, balance):
        """Call first at every event time, BEFORE fills: snapshots the balance when a Prague day starts."""
        d = self.prague_date(t_ns)
        if d != self.day:
            self.day, self.day_start_balance = d, balance
            self.days[d] = {"start_balance": balance, "min_equity": None}

    def check(self, t_ns, equity_low):
        rec = self.days[self.day]
        rec["min_equity"] = equity_low if rec["min_equity"] is None else min(rec["min_equity"], equity_low)
        daily_floor = self.day_start_balance - self.daily_limit
        for rule, limit in (("max daily loss 5%", daily_floor), ("max loss 10%", self.floor)):
            key = (self.day, rule)
            if equity_low < limit and key not in rec.setdefault("breached", set()):
                rec["breached"].add(key)
                self.breaches.append((int(t_ns), rule, equity_low, limit))
