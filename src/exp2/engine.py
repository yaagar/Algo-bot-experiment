"""Experiment 2 engine: one strategy, one position at a time, common settings (spec §3).

Flow for candle strategies (S1-S4):
  at each bar CLOSE the strategy may ask to enter (when flat) or to exit (when in a trade);
  orders fill at the NEXT bar's open, paying the spread (buy at ask, sell at bid);
  while a trade is open, M1 bars decide stop / target hits (longs on bid, shorts on ask;
  a bar touching both = stop first) and forced exits (the strategy's time exit and the
  Friday 20:00 London close) happen at the first M1 bar at or after that time.
S5 (clock-based) uses `run_timed`: entry at the first M1 price at/after a scheduled time.

Entry filters (§3): news blackout +-30 min around the fill, no new entries from Friday 16:00
London, one position at a time (signals while in a trade are skipped and counted).
Size is fractional: lots = risk $ / (stop distance x contract size); results are in R.
Swap is charged per rollover held (broker midnight = 17:00 New York), x3 on Wednesday night.
Every decision is logged with the time it was made and the newest data it saw (spec §9).

Experiment 3 (daily, multi-market) reuses this engine with weekend_rule=False (swing account:
positions held over weekends, no Friday cutoff), an empty news calendar, a per-lot commission
for FX, and quote_per_usd for markets whose P&L currency is not USD (USDJPY: P&L in JPY).
Results stay in R, which is the same in any currency.
"""
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from src.config import commission_usd
from src.timeutils import LONDON, NEW_YORK, utc_to_server

NS_MIN = 60 * 10**9
NY_TZ = ZoneInfo(NEW_YORK)
LONG_BREAK_NS = 120 * NS_MIN
NO_FORCED_EXIT = np.iinfo(np.int64).max // 2      # weekend_rule=False and no time exit


@dataclass(frozen=True)
class Costs:
    spread_mult: float = 1.0
    commission_pct: float = 0.0007
    commission_per_lot_usd: float = 0.0     # FX: fixed $ per lot per side (Experiment 3)


@dataclass(frozen=True)
class Swap:
    long_pct: float = -5.66
    short_pct: float = -3.02
    days_per_year: int = 360
    triple_weekday: int = 2          # Wednesday (Mon=0)


@dataclass
class Order:
    direction: int                   # +1 long, -1 short
    signal_ns: int                   # decision time (bar close)
    stop_rule: object                # f(entry_price, entry_spread) -> stop price
    target_r: float = None           # e.g. 1.5, or None
    time_exit_ns: int = None         # absolute forced exit time, or None
    info: dict = field(default_factory=dict)


@dataclass
class Position:
    order: Order
    entry_ns: int
    entry_price: float
    entry_bid: float
    entry_spread: float
    stop: float
    target: float
    lots: float
    forced_ns: int
    forced_is_friday: bool = False      # the Friday 20:00 London deadline (weekend rule)
    exit_next_open: bool = False
    worst_gap_ns: int = 0


@dataclass
class Result:
    trades: list = field(default_factory=list)
    decisions: list = field(default_factory=list)    # (time_ns, kind, detail, data_seen_ns)
    skipped_in_trade: int = 0
    blocked: dict = field(default_factory=dict)


def london_ns(date, minute):
    return int((pd.Timestamp(date).tz_localize(LONDON) + pd.Timedelta(minutes=int(minute))).tz_convert("UTC").value)


def friday_close_ns(t_ns):
    """20:00 London on the Friday of the week containing t (spec §3 weekend rule)."""
    d = pd.Timestamp(int(t_ns), tz="UTC").tz_convert(LONDON)
    friday = (d + pd.Timedelta(days=(4 - d.dayofweek) % 7)).date()
    return london_ns(friday, 20 * 60)


def friday_cutoff(t_ns):
    """No new entries from Friday 16:00 London."""
    d = pd.Timestamp(int(t_ns), tz="UTC").tz_convert(LONDON)
    return d.dayofweek == 4 and d.hour * 60 + d.minute >= 16 * 60


def server_date(t_ns):
    """Broker server calendar date (New York clock + 7 h) of a UTC time."""
    ny = datetime.fromtimestamp(t_ns / 1e9, tz=timezone.utc).astimezone(NY_TZ)
    return (ny.replace(tzinfo=None) + timedelta(hours=7)).date()


class Engine:
    def __init__(self, m1, events, costs, swap, risk_usd=50.0, contract=100.0, blackout_min=30,
                 weekend_rule=True, quote_per_usd=None):
        self.m1, self.events, self.costs, self.swap = m1, events, costs, swap
        self.risk, self.cs, self.blackout = risk_usd, contract, blackout_min
        self.weekend_rule = weekend_rule             # False = hold over weekends, no Friday cutoff
        self.quote_per_usd = quote_per_usd or (lambda price: 1.0)   # P&L currency units per US dollar

    # --- fills and exits ---------------------------------------------------------------------

    def open_position(self, order, fill_ns, bid, spread, res):
        if self.weekend_rule and friday_cutoff(fill_ns):
            return self._block(res, fill_ns, "after Friday 16:00 London")
        if self.events.within(fill_ns, self.blackout):
            return self._block(res, fill_ns, "news blackout")
        spread *= self.costs.spread_mult
        price = bid + spread if order.direction > 0 else bid
        stop = order.stop_rule(price, spread)
        r_dist = (price - stop) * order.direction
        if not r_dist > 0:
            return self._block(res, fill_ns, "entry beyond stop")
        target = price + order.direction * order.target_r * r_dist if order.target_r else None
        friday = friday_close_ns(fill_ns) if self.weekend_rule else NO_FORCED_EXIT
        forced = friday if order.time_exit_ns is None else min(friday, order.time_exit_ns)
        lots = self.risk / (r_dist * self.cs)
        res.decisions.append((fill_ns, "entry", (order.direction, round(price, 3), round(stop, 3)), fill_ns))
        return Position(order, fill_ns, price, bid, spread, stop, target, lots, forced,
                        forced_is_friday=self.weekend_rule and forced == friday)

    def _block(self, res, t_ns, why):
        res.blocked[why] = res.blocked.get(why, 0) + 1
        res.decisions.append((t_ns, "blocked", why, t_ns))
        return None

    def walk(self, pos, t_from, t_to):
        """Check stop/target/forced exit on M1 bars with t_from <= open < t_to. Returns (exit_ns, price, reason) or None."""
        m = self.m1
        a = int(np.searchsorted(m.t, t_from, "left"))
        b = int(np.searchsorted(m.t, t_to, "left"))
        lim = min(b, int(np.searchsorted(m.t, pos.forced_ns, "left")))
        if lim > a:
            gaps = np.diff(m.t[a:lim + 1]) if lim < len(m.t) else np.diff(m.t[a:lim])
            if len(gaps):
                pos.worst_gap_ns = max(pos.worst_gap_ns, int(gaps.max()))
            s = m.s[a:lim] * self.costs.spread_mult
            d = pos.order.direction
            if d > 0:
                stop_hit = m.l[a:lim] <= pos.stop
                tgt_hit = m.h[a:lim] >= pos.target if pos.target is not None else np.zeros(lim - a, bool)
            else:
                stop_hit = m.h[a:lim] + s >= pos.stop
                tgt_hit = m.l[a:lim] + s <= pos.target if pos.target is not None else np.zeros(lim - a, bool)
            hit = stop_hit | tgt_hit
            if hit.any():
                k = int(np.argmax(hit))
                if stop_hit[k]:                                   # same bar: stop first (§3)
                    o = m.o[a + k] if d > 0 else m.o[a + k] + s[k]
                    price = min(o, pos.stop) if d > 0 else max(o, pos.stop)   # gap through stop = worse fill
                    return int(m.t[a + k]), float(price), "stop"
                return int(m.t[a + k]), float(pos.target), "target"
        if t_from <= pos.forced_ns < t_to or (pos.forced_ns < t_from):
            k = int(np.searchsorted(m.t, pos.forced_ns, "left"))
            if pos.forced_is_friday and k > 0 and (k >= len(m.t) or m.t[k] - pos.forced_ns > LONG_BREAK_NS):
                # market already closed for the weekend (e.g. holiday early close): positions must be
                # closed BY Friday 20:00 London, so exit at the last price before the close
                j = k - 1
                price = m.c[j] if pos.order.direction > 0 else m.c[j] + m.s[j] * self.costs.spread_mult
                return int(m.t[j]), float(price), "friday close (market closed early)"
            if k < len(m.t):
                price = m.o[k] if pos.order.direction > 0 else m.o[k] + m.s[k] * self.costs.spread_mult
                own_exit = pos.order.time_exit_ns
                friday_first = pos.forced_is_friday and (own_exit is None or pos.forced_ns < own_exit)
                return int(m.t[k]), float(price), "friday close" if friday_first else "time"
        return None

    def end_of_data(self, pos):
        """Data ends with a trade open: close at the last M1 close (shorts pay the spread)."""
        m = self.m1
        price = m.c[-1] if pos.order.direction > 0 else m.c[-1] + m.s[-1] * self.costs.spread_mult
        return int(m.t[-1]), float(price), "end of data"

    def exit_at_open(self, pos, t_ns, bid, spread):
        price = bid if pos.order.direction > 0 else bid + spread * self.costs.spread_mult
        return t_ns, float(price), "exit signal"

    def close(self, pos, exit_ns, price, reason, res):
        d, cs = pos.order.direction, self.cs
        gross = d * (price - pos.entry_price) * pos.lots * cs
        comm = (commission_usd(pos.lots, pos.entry_price, cs, self.costs.commission_pct)
                + commission_usd(pos.lots, price, cs, self.costs.commission_pct)
                + pos.lots * self.costs.commission_per_lot_usd * (self.quote_per_usd(pos.entry_price)
                                                                  + self.quote_per_usd(price)))
        swap, nights = self.swap_for(pos, exit_ns)
        net = gross - comm + swap
        risk = (pos.entry_price - pos.stop) * d * pos.lots * cs
        res.trades.append({
            "direction": "LONG" if d > 0 else "SHORT",
            "signal_ns": pos.order.signal_ns, "entry_ns": pos.entry_ns, "exit_ns": exit_ns,
            "entry_price": pos.entry_price, "entry_bid": pos.entry_bid, "entry_spread": pos.entry_spread,
            "stop": pos.stop, "target": pos.target, "stop_distance": (pos.entry_price - pos.stop) * d,
            "lots": pos.lots, "exit_price": price, "exit_reason": reason,
            "gross_usd": gross, "commission_usd": comm, "swap_usd": swap, "swap_nights": nights,
            "net_usd": net, "net_r": net / risk, "gross_r": gross / risk,
            "held_across_long_break": pos.worst_gap_ns > LONG_BREAK_NS,
            "ftmo_flagged_exit": self.events.within(exit_ns, 2),
            **{f"info_{k}": v for k, v in pos.order.info.items()},
        })
        res.decisions.append((exit_ns + NS_MIN, "exit", (reason, round(price, 3)), exit_ns + NS_MIN))

    def swap_for(self, pos, exit_ns):
        """Swap for every broker rollover (server midnight = 17:00 New York) crossed while open."""
        first, last = server_date(pos.entry_ns), server_date(exit_ns)
        if first >= last:
            return 0.0, 0
        rate = (self.swap.long_pct if pos.order.direction > 0 else self.swap.short_pct) / 100 / self.swap.days_per_year
        total, nights, day = 0.0, 0, first
        while day < last:                    # one rollover per broker day boundary crossed
            if day.weekday() >= 5:           # Saturday/Sunday broker days: market shut, no rollover (the
                day += timedelta(days=1)     # triple day already pays for the weekend). Only matters when
                continue                     # a position is held over a weekend (Experiment 3).
            mult = 3 if day.weekday() == self.swap.triple_weekday else 1
            # price at the rollover = last M1 close before that server day ends (17:00 New York)
            roll = datetime.combine(day, time(17), tzinfo=NY_TZ)
            k = int(np.searchsorted(self.m1.t, int(roll.timestamp()) * 10**9, "left")) - 1
            total += self.m1.c[max(k, 0)] * self.cs * pos.lots * rate * mult
            nights += mult
            day += timedelta(days=1)
        return total, nights

    # --- candle strategies -------------------------------------------------------------------

    def run(self, strategy):
        b = strategy.bars
        t_open, t_close = b.t_open.to_numpy(), b.t_close.to_numpy()
        o, sp = b.open.to_numpy(), b.spread.to_numpy()
        res = Result()
        pos, pending = None, None
        n = len(b)
        for i in range(n):
            nxt = t_open[i + 1] if i + 1 < n else t_close[i]
            if pending is not None:                       # fill at this bar's open
                pos = self.open_position(pending, int(t_open[i]), o[i], sp[i], res)
                pending = None
            if pos is not None and pos.exit_next_open:
                if pos.forced_ns <= t_open[i]:            # forced exit came first (in the gap)
                    ex = self.walk(pos, int(pos.forced_ns), int(pos.forced_ns) + 1)
                else:
                    ex = self.exit_at_open(pos, int(t_open[i]), o[i], sp[i])
                self.close(pos, *ex, res)
                pos = None
            if pos is not None:
                ex = self.walk(pos, int(t_open[i]), int(nxt))
                if ex:
                    self.close(pos, *ex, res)
                    pos = None
            # --- bar i has closed: strategy decisions (data up to and including bar i) ---
            if pos is not None:
                if strategy.exit_signal(i, pos):
                    pos.exit_next_open = True
                    res.decisions.append((int(t_close[i]), "exit signal", None, int(t_close[i])))
                if strategy.signal(i) is not None:
                    res.skipped_in_trade += 1
            else:
                order = strategy.signal(i)
                if order is not None:
                    res.decisions.append((int(t_close[i]), "signal", (order.direction,), int(t_close[i])))
                    pending = order
        if pos is not None:                               # data ended with a trade open
            ex = self.walk(pos, int(pos.entry_ns), int(self.m1.t[-1]) + 1) or self.end_of_data(pos)
            self.close(pos, *ex, res)
        for d in getattr(strategy, "decisions", []):
            res.decisions.append(d)
        return res

    # --- clock-based strategy (S5) ------------------------------------------------------------

    def run_timed(self, strategy):
        res = Result()
        m = self.m1
        for order, entry_ns in strategy.schedule():
            res.decisions.append((order.signal_ns, "signal", (order.direction,), order.signal_ns))
            if order.info.get("skip"):
                self._block(res, order.signal_ns, order.info["skip"])
                continue
            k = int(np.searchsorted(m.t, entry_ns, "left"))
            if k >= len(m.t) or m.t[k] - entry_ns > 60 * NS_MIN:
                self._block(res, entry_ns, "no price within 60 min of entry time")
                continue
            pos = self.open_position(order, int(m.t[k]), m.o[k], m.s[k], res)
            if pos is None:
                continue
            ex = self.walk(pos, int(m.t[k]), int(pos.forced_ns) + 1)
            if ex:
                self.close(pos, *ex, res)
        return res


def trades_frame(res):
    t = pd.DataFrame(res.trades)
    if len(t):
        for c in ("signal", "entry", "exit"):
            t[f"{c}_utc"] = pd.to_datetime(t[f"{c}_ns"], utc=True)
    return t
