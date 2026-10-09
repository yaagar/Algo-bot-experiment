"""Experiment 7 random controls (spec v1.0 §5). Each control trade is simulated on its own (no
one-position interaction) on the same engine, with the same $ stop distance, 2R target, costs and
20:00 London exit as the real trade it stands in for.

C1: the real trade's fill time, random direction.
C2: a random M15 bar of the same period where the H1 trend condition holds (swing structure AND
    t-stat) and whose fill lands inside trading hours outside the news window; trend direction.
"""
import numpy as np
import pandas as pd

from src.exp2.engine import Order, trades_frame
from src.exp7.pattern import M15, h1_context
from src.exp7.system import make_engine, time_exit_ns
from src.exp2.market import to_ns
from src.timeutils import LONDON


class _Schedule:
    def __init__(self, items):
        self.items = items

    def schedule(self):
        return self.items


def _order(direction, signal_ns, fill_ns, stop_dist, cfg, tag):
    return Order(direction=direction, signal_ns=signal_ns,
                 stop_rule=lambda price, spread: price - direction * stop_dist, target_r=cfg["target_r"],
                 time_exit_ns=time_exit_ns(fill_ns, cfg["time_exit_london"]), info={"size": 1.0, "control": tag})


def run_orders(data, cfg, items, spread_mult=1.0):
    engine = make_engine(data, cfg, spread_mult)
    return trades_frame(engine.run_timed(_Schedule(items)))


def c1(data, trades, cfg, seed, spread_mult=1.0):
    """Real fill times and stop distances, random directions."""
    rng = np.random.default_rng(seed)
    dirs = rng.choice([-1, 1], size=len(trades))
    items = [(_order(int(d), int(t.signal_ns), int(t.entry_ns), float(t.stop_distance), cfg, "C1"), int(t.entry_ns))
             for d, t in zip(dirs, trades.itertuples())]
    return run_orders(data, cfg, items, spread_mult)


def trend_bars(data, cfg):
    """(decision bar index, trend direction) for every M15 bar whose close sees the H1 trend condition
    and whose next bar (the fill) is inside trading hours and outside the news window."""
    ctx = h1_context(data.h1, cfg)
    open_ns = to_ns(data.m15.time_utc)
    k = np.searchsorted(ctx.close_ns, open_ns + M15.value, side="right") - 1
    ok = k >= 0
    kk = np.maximum(k, 0)
    trend, t = ctx.trend[kk], ctx.tstat[kk]
    holds = ok & (trend != 0) & (trend * t >= cfg["tstat_min"])
    london = data.m15.time_utc.dt.tz_convert(LONDON)
    minute = (london.dt.hour * 60 + london.dt.minute).to_numpy()
    t0, t1 = (int(x[:2]) * 60 + int(x[3:]) for x in cfg["entry_hours_london"])
    fill_ok = np.zeros(len(open_ns), bool)
    fill_ok[:-1] = (t0 <= minute[1:]) & (minute[1:] < t1)
    fill_ok[:-1] &= [not data.events.within(int(x), cfg["news_blackout_min"]) for x in open_ns[1:]]
    bars = np.flatnonzero(holds & fill_ok)
    return bars, trend[bars]


def c2(data, trades, cfg, seed, eligible, spread_mult=1.0):
    """One trend-direction trade at a random eligible bar per real trade, same $ stop distance."""
    rng = np.random.default_rng(seed)
    bars, dirs = eligible
    pick = rng.integers(0, len(bars), size=len(trades))
    open_ns = to_ns(data.m15.time_utc)
    items = []
    for j, t in zip(pick, trades.itertuples()):
        b = bars[j]
        fill = int(open_ns[b + 1])
        items.append((_order(int(dirs[j]), int(open_ns[b] + M15.value), fill, float(t.stop_distance), cfg, "C2"), fill))
    return run_orders(data, cfg, items, spread_mult)
