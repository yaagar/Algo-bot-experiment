"""Experiment 6 portfolio engine (spec §5-§6, Change Log v1.1-v1.3).

Plain English: one account holds up to 18 positions. Time moves hour by hour through every market's
H1 bars. At each broker-day close (17:00 New York) we first charge swap on everything held over the
rollover, then read each market's forecast, size the whole portfolio and, where the change is
bigger than the buffer, place an order. Orders fill at the open of the 10:00 New York H1 bar on the
next weekday (or the first bar after it if the market is shut): buys pay the tick-p75 spread of that
hour, every fill pays commission. Every H1 bar the account's worst-case equity (lows for longs,
highs + spread for shorts) is checked against the FTMO limits.

Accounting (v1.3 d): netting by average price; a reduction realises its P/L and its share of the
accrued swap into the balance; commission leaves the balance at the fill.
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.ftmo_rules import PortfolioLimits
from src.exp6.signals import apply_buffer, market_signals, size_targets

NS_HOUR = 3600 * 10**9
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


def ny_time_ns(dates, hour):
    """UTC ns of `hour`:00 New York on each date (datetime64[D])."""
    ts = pd.to_datetime(np.asarray(dates)) + pd.Timedelta(hours=hour)
    return ts.tz_localize("America/New_York").tz_convert("UTC").as_unit("ns").asi8


def next_weekday(dates):
    d = pd.to_datetime(np.asarray(dates))
    step = np.where(d.dayofweek == 4, 3, np.where(d.dayofweek == 5, 2, 1))
    return (d + pd.to_timedelta(step, unit="D")).to_numpy().astype("datetime64[D]")


class Account:
    def __init__(self, n, capital):
        self.balance = float(capital)
        self.lots, self.avg, self.swap = np.zeros(n), np.zeros(n), np.zeros(n)

    def fill(self, i, new_lots, price, usd_ppu, commission):
        q = self.lots[i]
        d = new_lots - q
        self.balance -= commission
        if q != 0 and np.sign(d) != np.sign(q):                      # reducing or flipping
            closed = min(abs(d), abs(q))
            self.balance += np.sign(q) * closed * (price - self.avg[i]) * usd_ppu
            share = self.swap[i] * closed / abs(q)
            self.balance += share
            self.swap[i] -= share
        if new_lots == 0:
            self.avg[i] = 0.0
        elif q == 0 or np.sign(new_lots) != np.sign(q):
            self.avg[i] = price                                       # fresh position (or the flipped rest)
        elif abs(new_lots) > abs(q):
            self.avg[i] = (abs(q) * self.avg[i] + abs(d) * price) / abs(new_lots)
        self.lots[i] = new_lots

    def floating(self, marks, usd_ppu):
        held = self.lots != 0                                         # markets with no price yet hold nothing
        return float(np.sum(((marks - self.avg) * self.lots * usd_ppu)[held]))


@dataclass
class Result:
    decisions: list = field(default_factory=list)     # leak-test log: tuples, time first
    fills: list = field(default_factory=list)         # dicts
    daily: list = field(default_factory=list)         # dicts per broker day (equity at the close etc.)
    limits: PortfolioLimits = None


def commission_usd(cls, lots, notional_usd, cfg):
    c = cfg["commission"][cls]
    per_side = lots * c["usd_per_lot"] if "usd_per_lot" in c else notional_usd * c["pct"] / 100
    return per_side * cfg["execution"]["commission_mult"]


def run(u, cfg, f_override=None):
    sc, ex = cfg["sizing"], cfg["execution"]
    mk = u.markets
    n = len(mk)
    groups = np.array([cfg["classes"][m.cls] for m in mk])
    sig = [market_signals(m, cfg["signal"]["lookbacks"], sc["vol_days"], cfg.get("long_only", False)) for m in mk]
    if f_override is not None:
        for i, m in enumerate(mk):
            sig[i]["f"] = f_override[m.symbol]
    triple = [WEEKDAYS.index(cfg["triple_swap_day"][m.cls]) for m in mk]

    # broker days of the portfolio and their close times
    days = np.unique(np.concatenate([m.days for m in mk]))
    t_dec = ny_time_ns(days, ex["rollover_hour_ny"])
    t_fill = ny_time_ns(next_weekday(days), ex["fill_hour_ny"])
    day_of_dec = dict(zip(t_dec.tolist(), range(len(days))))

    # daily $ change per lot (rows = portfolio days), for the covariance
    dollar = np.zeros((len(days), n))
    for i, m in enumerate(mk):
        pos = np.searchsorted(days, m.days)
        chg = np.r_[0.0, np.diff(m.day_close)]
        usd = np.array([u.conv.usd_per(m.profit_ccy, t) for t in ny_time_ns(m.days, ex["rollover_hour_ny"])])
        dollar[pos, i] = chg * m.contract * usd

    events = np.unique(np.concatenate([t_dec] + [m.t for m in mk]))
    ptr = np.zeros(n, dtype=int)
    hour_of = [((pd.to_datetime(m.t, utc=True).tz_convert("America/New_York").hour + 7) % 24).to_numpy() for m in mk]
    last_close = np.full(n, np.nan)
    last_hour = np.zeros(n, dtype=int)
    acct = Account(n, sc["capital"])
    limits = PortfolioLimits(cfg["ftmo"]["initial"], cfg["ftmo"]["daily_loss_pct"], cfg["ftmo"]["max_loss_pct"],
                             cfg["ftmo"]["reset_tz"])
    res = Result(limits=limits)
    pending = {}                                                     # i -> (lots, not before ns, decision day)
    slip = np.array([ex["slippage_ticks"] * m.tick for m in mk])

    def usd_ppu_now(t):
        return np.array([m.contract * u.conv.usd_per(m.profit_ccy, t) for m in mk])

    def marks_close(spread_hour):
        sp = np.array([m.spread_by_hour[h] for m, h in zip(mk, spread_hour)]) * ex["spread_mult"]
        return np.where(acct.lots < 0, last_close + sp, last_close)

    for t in events:
        t = int(t)
        limits.new_time(t, acct.balance)
        if t in day_of_dec:
            k_day = day_of_dec[t]
            D = days[k_day]
            usd_ppu = usd_ppu_now(t)
            # 1. swap for positions held over this rollover (Mon-Fri broker days; triple per class)
            wd = pd.Timestamp(D).dayofweek
            for i in np.flatnonzero(acct.lots):
                pct = u.swaps[mk[i].symbol][0 if acct.lots[i] > 0 else 1]
                charge_mult = ex["swap_charge_mult"] if pct < 0 else 1.0
                mult = 3 if wd == triple[i] else 1
                acct.swap[i] += abs(acct.lots[i]) * last_close[i] * usd_ppu[i] * pct / 100 / cfg["swap_days_per_year"] * mult * charge_mult
            # 2. forecasts and sizing from data up to this close
            rows = [s.iloc[max(int(np.searchsorted(m.days, D, "right")) - 1, 0)] for m, s in zip(mk, sig)]
            f = np.array([r.f for r in rows])
            sigma = np.array([r.sigma for r in rows])
            tradeable = np.array([bool(r.tradeable) and np.isfinite(last_close[i]) for i, r in enumerate(rows)])
            f = np.where(tradeable, f, 0.0)
            notional = np.abs(last_close) * usd_ppu
            equity = acct.balance + acct.floating(marks_close(last_hour), usd_ppu) + acct.swap.sum()
            window = dollar[max(0, k_day - sc["cov_days"] + 1):k_day + 1]
            cov = np.cov(window, rowvar=False, ddof=1) if len(window) >= sc["cov_days"] else np.zeros((n, n))
            target, full_unit, scaler = size_targets(f, np.nan_to_num(sigma, nan=1.0), usd_ppu, np.nan_to_num(notional),
                                                     groups, tradeable, cov, equity, sc)
            new = apply_buffer(acct.lots.copy(), target, full_unit, sc["buffer"])
            for i in range(n):
                if new[i] != acct.lots[i]:
                    pending[i] = (new[i], int(t_fill[k_day]), k_day)
                else:
                    pending.pop(i, None)
                res.decisions.append((t, "dec", mk[i].symbol, round(float(f[i]), 6), round(float(target[i]), 6),
                                      round(float(new[i]), 6)))
            margin = float(np.sum(np.abs(acct.lots) * notional)) / sc["leverage"]
            res.daily.append({"day": D, "t": t, "equity": equity, "balance": acct.balance, "scaler": scaler,
                              "margin_used": margin, "n_tradeable": int(tradeable.sum()),
                              **{f"f_{m.symbol}": f[i] for i, m in enumerate(mk)},
                              **{f"target_{m.symbol}": target[i] for i, m in enumerate(mk)}})
            res.decisions.append((t, "eq", round(equity, 4)))

        # 3. bars opening now: fills at the open, then worst-case equity over the bar
        usd_ppu = usd_ppu_now(t)
        worst = last_close.copy()
        any_bar = False
        for i, m in enumerate(mk):
            j = ptr[i]
            if j >= len(m.t) or m.t[j] != t:
                if np.isfinite(last_close[i]) and acct.lots[i] < 0:
                    worst[i] = last_close[i] + m.spread_by_hour[last_hour[i]] * ex["spread_mult"]
                continue
            any_bar = True
            hr = hour_of[i][j]
            spread = m.spread_by_hour[hr] * ex["spread_mult"]
            if i in pending and t >= pending[i][1]:
                new_lots, _, k_day = pending.pop(i)
                d = new_lots - acct.lots[i]
                price = m.o[j] + spread + slip[i] if d > 0 else m.o[j] - slip[i]
                comm = commission_usd(m.cls, abs(d), abs(d) * price * usd_ppu[i], cfg)
                swap_before = acct.swap[i]
                acct.fill(i, new_lots, price, usd_ppu[i], comm)
                res.fills.append({"symbol": m.symbol, "t": t, "decision_day": days[k_day], "lots_before": new_lots - d,
                                  "lots_after": new_lots, "price": price, "bid_open": m.o[j], "spread": spread,
                                  "commission_usd": comm, "swap_accrued_before": swap_before})
                res.decisions.append((t, "fill", m.symbol, round(float(new_lots), 6), round(float(price), 8)))
            worst[i] = m.l[j] if acct.lots[i] > 0 else (m.h[j] + spread if acct.lots[i] < 0 else m.c[j])
            last_close[i], last_hour[i] = m.c[j], hr
            ptr[i] = j + 1
        if any_bar:
            eq_low = acct.balance + float(np.sum(np.where(acct.lots != 0, (worst - acct.avg) * acct.lots * usd_ppu, 0.0))) + acct.swap.sum()
            limits.check(t, eq_low)
    res.decisions.extend((b[0], "breach", b[1], round(b[2], 4)) for b in limits.breaches)
    return res, sig
