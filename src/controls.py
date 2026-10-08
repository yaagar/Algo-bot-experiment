"""C1 — random-entry control (spec §2, clarified in v1.3).

Same days as Bot A's trades (per timeframe), same $50 risk, same exits
(1.5R target, 20:00 London time exit). Only the entry is random: a random
direction at the open of a random M15 bar in the entry window, avoiding news
blackouts. The stop distance is A's stop distance on that day.
"""
import numpy as np

from src.backtest import Entry


def c1_chooser(a_stop_distance_by_date, events):
    """Entry chooser for C1. Needs days built with M15 candles."""
    def choose(day, box, p, rng):
        r_dist = a_stop_distance_by_date.get(day.date)
        if r_dist is None:
            return None, "not a Bot A trade day"
        in_window = (day.c_min >= p.box_end) & (day.c_min < p.entry_end)
        allowed = [j for j in np.flatnonzero(in_window)
                   if not events.within(int(day.c_t[j]), p.news_blackout_minutes)]
        if not allowed:
            return None, "no M15 bar outside blackout"
        j = int(rng.choice(allowed))
        direction = int(rng.choice([-1, 1]))
        return Entry(direction, j, int(day.c_t[j]), stop_distance=r_dist), None
    return choose
