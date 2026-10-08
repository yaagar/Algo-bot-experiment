import datetime as dt

import numpy as np
import pandas as pd
import pytest

from src.backtest import (Account, Costs, Day, Events, bot_a_chooser, load_bars, lots_for_risk, run,
                          simulate_exit)
from src.strategy_asian import Box, Params, compute_box, find_breakout

P = Params()
ACCT = Account()
DATE = dt.date(2024, 1, 10)                     # winter: London = UTC
T0 = pd.Timestamp("2024-01-10 00:00", tz="UTC").value
MIN = 60 * 10**9


def make_day(m1_rows, candle_rows, spread=0.25):
    """m1_rows / candle_rows: list of (london_minute, open, high, low, close)."""
    def arr(rows, i):
        return np.array([r[i] for r in rows], dtype=float)
    m1_min = np.array([r[0] for r in m1_rows])
    c_min = np.array([r[0] for r in candle_rows])
    return Day(DATE, T0 + m1_min.astype(np.int64) * MIN, m1_min, arr(m1_rows, 1), arr(m1_rows, 2),
               arr(m1_rows, 3), arr(m1_rows, 4), np.full(len(m1_rows), spread), np.zeros(len(m1_rows), bool),
               T0 + c_min.astype(np.int64) * MIN, c_min, arr(candle_rows, 1), arr(candle_rows, 4),
               np.full(len(candle_rows), spread))


def box_rows(lo=2000.0, hi=2010.0):
    """Full 00:00-07:00 M1 box bars, ranging lo..hi."""
    return [(m, 2005, hi if m == 100 else 2006, lo if m == 200 else 2004, 2005) for m in range(0, 420)]


# --- sizing / box / breakout --------------------------------------------------------

def test_lots_floor_to_step():
    assert lots_for_risk(50, 2.0, ACCT) == 0.25
    assert lots_for_risk(50, 3.0, ACCT) == 0.16     # 0.1666 floored


def test_box_ok_and_skips():
    rows = box_rows()
    minute = np.array([r[0] for r in rows]); h = np.array([r[2] for r in rows], float)
    l = np.array([r[3] for r in rows], float); s = np.full(len(rows), 0.25)
    box, why = compute_box(minute, h, l, s, P)
    assert why is None and (box.high, box.low) == (2010, 2000)
    gap = (minute < 100) | (minute > 140)            # 40-minute hole
    assert compute_box(minute[gap], h[gap], l[gap], s[gap], P) == (None, "box data gap > 30 min")
    assert compute_box(minute, h, l, np.full(len(rows), 3.0), P)[1] == "box < 5x median spread"


def test_breakout_ignores_candles_outside_window():
    box = Box(high=2010, low=2000, median_spread=0.25)
    minute = np.array([405, 420, 435])                # 06:45 (before window), 07:00, 07:15
    close = np.array([2020, 2005, 1990])
    assert find_breakout(minute, close, 15, box, P) == (2, -1)
    late = np.array([945, 960]); assert find_breakout(late, np.array([2005, 2020]), 15, box, P) is None  # closes 16:15


# --- exits ------------------------------------------------------------------------------

def path_day(bars, spread=0.25):
    return make_day(bars, [(420, 2011, 0, 0, 2011)], spread)


def test_long_target():
    d = path_day([(480, 2011, 2012, 2010.5, 2011.5), (481, 2011.5, 2020, 2011, 2019)])
    ex = simulate_exit(d, 0, +1, 2011.25, 2000, 2028.125, P, 1.0)
    assert ex is None or ex.reason in ("time", "end of data")      # 2020 < target
    ex = simulate_exit(d, 0, +1, 2011.25, 2000, 2015, P, 1.0)
    assert (ex.reason, ex.price, ex.index) == ("target", 2015, 1)


def test_same_bar_stop_and_target_takes_stop():
    d = path_day([(480, 2011, 2030, 1990, 2011)])
    ex = simulate_exit(d, 0, +1, 2011.25, 2000, 2028, P, 1.0)
    assert (ex.reason, ex.price) == ("stop", 2000)


def test_gap_through_stop_fills_at_open():
    d = path_day([(480, 2011, 2012, 2010, 2011), (481, 1995, 1996, 1990, 1992)])
    ex = simulate_exit(d, 0, +1, 2011.25, 2000, 2028, P, 1.0)
    assert (ex.reason, ex.price) == ("stop", 1995)


def test_short_stop_triggers_on_ask_not_bid():
    # bid high 2009.9 < stop 2010, but ask = 2009.9 + 0.25 = 2010.15 >= stop
    d = path_day([(480, 2005, 2009.9, 2004, 2005)])
    ex = simulate_exit(d, 0, -1, 2005, 2010, 1997.5, P, 1.0)
    assert (ex.reason, ex.price) == ("stop", 2010)


def test_time_exit_at_2000_london_open():
    d = path_day([(1199, 2011, 2012, 2010, 2011), (1200, 2013, 2014, 2012, 2013)])
    ex = simulate_exit(d, 0, -1, 2011, 2030, 1980, P, 1.0)
    assert (ex.reason, ex.price) == ("time", 2013.25)      # short closes at ask


# --- events / holdout guard -------------------------------------------------------------

def test_event_window_inclusive():
    ev = Events([pd.Timestamp("2024-01-10 13:30", tz="UTC")])
    t = pd.Timestamp("2024-01-10 14:00", tz="UTC").value
    assert ev.within(t, 30) and not ev.within(t + MIN, 30)


def test_holdout_is_refused():
    with pytest.raises(ValueError):
        load_bars("XAUUSD.sim", "M15", pd.Timestamp("2025-12-01", tz="UTC"),
                  pd.Timestamp("2026-01-02", tz="UTC"), pd.Timestamp("2026-01-01", tz="UTC"))


# --- full day ---------------------------------------------------------------------------

def full_day():
    m1 = box_rows() + [(m, 2011, 2012, 2010.5, 2011.5) for m in range(420, 480)] + \
         [(m, 2012, 2030, 2011.5, 2029) for m in range(480, 482)]
    candles = [(420, 2005, 0, 0, 2009), (435, 2009, 0, 0, 2011), (450, 2011, 0, 0, 2011.5)]
    return make_day(m1, candles)


def test_bot_a_takes_breakout_and_hits_target():
    res = run([full_day()], bot_a_chooser(15), P, Costs(), ACCT, Events([]))
    t = res.trades[0]
    assert t["direction"] == "LONG" and t["entry_price"] == 2011.25       # 07:30 open + spread
    assert t["stop"] == 2000 and t["exit_reason"] == "target" and t["lots"] == 0.04
    assert all(seen <= when for when, _, _, _, seen in res.decisions)     # spec §9.5


def test_blackout_blocks_first_breakout_and_no_retry():
    ev = Events([pd.Timestamp("2024-01-10 07:45", tz="UTC")])            # 07:30 fill is within 30 min
    res = run([full_day()], bot_a_chooser(15), P, Costs(), ACCT, ev)
    assert res.trades == [] and any(k == "blocked" for _, k, _, _, _ in res.decisions)
