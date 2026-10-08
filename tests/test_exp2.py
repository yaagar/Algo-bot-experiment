import datetime as dt

import numpy as np
import pandas as pd

from src.backtest import Events
from src.exp2.c1 import run_c1
from src.exp2.engine import Costs, Engine, Order, Position, Swap, friday_close_ns, friday_cutoff, london_ns
from src.exp2.market import M1, rsi, wilder
from src.exp2.strategies import S2Box, S3Donchian, S5AsianHours

MIN = 60 * 10**9
T0 = pd.Timestamp("2024-01-10 08:00", tz="UTC").value        # a Wednesday, London = UTC in winter


def m1(rows, spread=0.25, t0=T0):
    """rows: list of (open, high, low, close), one per minute from t0."""
    a = np.array(rows, dtype=float)
    return M1(t0 + np.arange(len(rows)) * MIN, a[:, 0], a[:, 1], a[:, 2], a[:, 3], np.full(len(rows), spread))


def engine(m, events=()):
    return Engine(m, Events(list(events)), Costs(), Swap())


def pos(d, entry, stop, target, forced, t=T0):
    return Position(Order(d, t, None), t, entry, entry, 0.25, stop, target, 0.1, forced)


# --- indicators --------------------------------------------------------------------------

def test_wilder_seeds_with_simple_average_then_smooths():
    out = wilder([1, 2, 3, 4], 3)
    assert np.isnan(out[:2]).all() and out[2] == 2.0 and out[3] == (2.0 * 2 + 4) / 3


def test_rsi_extremes():
    assert rsi(np.arange(10.0), 2)[-1] == 100.0          # only up moves
    assert rsi(np.arange(10.0)[::-1], 2)[-1] == 0.0       # only down moves


# --- exits -----------------------------------------------------------------------------------

def test_long_target_and_short_stop_on_ask():
    m = m1([(100, 101, 99.5, 100.5), (100.5, 103, 100, 102.5)])
    assert engine(m).walk(pos(1, 100.25, 99, 102, T0 + 99 * MIN), T0, T0 + 2 * MIN)[1:] == (102.0, "target")
    # short stop 101.1: bid high 101.0 < stop, but ask = 101.0 + 0.25 >= stop
    assert engine(m).walk(pos(-1, 100, 101.1, 95, T0 + 99 * MIN), T0, T0 + 1 * MIN)[1:] == (101.1, "stop")


def test_same_minute_stop_and_target_takes_stop():
    m = m1([(100, 110, 90, 100)])
    assert engine(m).walk(pos(1, 100.25, 95, 105, T0 + 99 * MIN), T0, T0 + MIN)[2] == "stop"


def test_forced_exit_at_first_minute_at_or_after_time():
    m = m1([(100, 100.5, 99.5, 100)] * 5)
    ex = engine(m).walk(pos(-1, 100, 120, 80, T0 + 3 * MIN), T0, T0 + 5 * MIN)
    assert ex == (T0 + 3 * MIN, 100.25, "time")          # short closes at ask


def test_weekend_rules():
    wed = pd.Timestamp("2024-01-10 12:00", tz="UTC").value
    assert friday_close_ns(wed) == london_ns(dt.date(2024, 1, 12), 20 * 60)
    assert friday_cutoff(pd.Timestamp("2024-01-12 16:00", tz="UTC").value)
    assert not friday_cutoff(pd.Timestamp("2024-01-12 15:59", tz="UTC").value)


def test_swap_wednesday_night_counts_three():
    # long held from Wed 2024-01-10 12:00 UTC to Thu 12:00 UTC: crosses the Wednesday rollover
    t_in = pd.Timestamp("2024-01-10 12:00", tz="UTC").value
    t_out = pd.Timestamp("2024-01-11 12:00", tz="UTC").value
    m = m1([(2000, 2001, 1999, 2000)] * 2, t0=t_in)
    e = engine(m)
    p = Position(Order(1, t_in, None), t_in, 2000, 2000, 0.25, 1990, None, 1.0, t_out)
    usd, nights = e.swap_for(p, t_out)
    assert nights == 3 and round(usd, 2) == round(2000 * 100 * 1.0 * -0.0566 / 360 * 3, 2)


# --- strategy rules (synthetic bars) -----------------------------------------------------------

class FakeMarket:
    def __init__(self, bars, days=None, m1=None):
        self.bars = {"H1": bars, "H4": bars}
        self.days = days
        self.m1 = m1


def h1_bars(rows, start="2024-01-10 06:00"):
    t = pd.date_range(start, periods=len(rows), freq="h", tz="UTC")
    b = pd.DataFrame(rows, columns=["open", "high", "low", "close"])
    b["t_open"] = t.tz_convert(None).astype("datetime64[ns]").astype(np.int64)
    b["t_close"] = b.t_open + 60 * MIN
    lon = (t + pd.Timedelta(hours=1)).tz_convert("Europe/London")
    b["close_london_min"] = lon.hour * 60 + lon.minute
    b["close_london_date"] = lon.date
    b["server_date"] = [dt.date(2024, 1, 10)] * len(rows)
    b["spread"] = 0.25
    return b


def test_s2_sell_on_upper_wick_rejection_of_pdh():
    days = pd.DataFrame({"high": [2010.0, 0], "low": [1990.0, 0], "close": [2000.0, 0]},
                        index=[dt.date(2024, 1, 9), dt.date(2024, 1, 10)])
    # 07:00-08:00 London bar: high 2012 >= PDH 2010, close 2005 < PDH, upper wick 6 >= 2 x body 1, >= half the range
    s = S2Box(FakeMarket(h1_bars([(2004, 2005, 2003, 2004), (2004, 2012, 2003.5, 2005)]), days))
    assert s.signal(0) is None                     # closes 07:00 London, no rejection
    o = s.signal(1)
    assert o.direction == -1 and o.stop_rule(2005, 0.3) == 2012.3 and o.target_r == 1.5
    assert s.signal(1) is None                     # one trade per level per day


def test_s3_channel_excludes_current_bar():
    rows = [(100, 101, 99, 100)] * 20 + [(100, 105, 99, 104)]
    s = S3Donchian(FakeMarket(h1_bars(rows)))
    assert s.up[20] == 101                         # previous 20 bars only
    assert s.signal(20) is None or s.signal(20).direction == 1


def test_s5_sunday_evening_entry_and_exit_times():
    t = pd.date_range("2024-01-07 12:00", "2024-01-08 12:00", freq="min", tz="UTC")   # Sun-Mon
    m = M1(t.tz_convert(None).astype("datetime64[ns]").astype(np.int64).to_numpy(), *(np.full(len(t), 2000.0),) * 4,
           np.full(len(t), 0.3))
    h1 = h1_bars([(2000, 2001, 1999, 2000)] * 20, start="2024-01-06 20:00")
    s = S5AsianHours(FakeMarket(h1, m1=m), Events([]))
    order, entry = next(iter(s.schedule()))
    assert pd.Timestamp(entry, tz="UTC") == pd.Timestamp("2024-01-07 23:00", tz="UTC")        # 18:00 New York
    assert pd.Timestamp(order.time_exit_ns, tz="UTC") == pd.Timestamp("2024-01-08 08:00", tz="UTC")  # 03:00 NY


def test_c1_closes_at_real_exit_time_without_target():
    m = m1([(100, 100.4, 99.6, 100)] * 10)
    real = pd.DataFrame([{"signal_ns": T0, "entry_ns": T0, "exit_ns": T0 + 6 * MIN, "entry_bid": 100.0,
                          "entry_spread": 0.25, "stop_distance": 5.0}])
    t = run_c1(engine(m), real, seed=1).trades[0]
    assert t["exit_ns"] == T0 + 6 * MIN and t["exit_reason"] == "time"


def test_same_broker_day_has_no_swap():
    t_in = pd.Timestamp("2024-03-05 08:00", tz="UTC").value
    t_out = pd.Timestamp("2024-03-05 20:00", tz="UTC").value
    m = m1([(2000, 2001, 1999, 2000)] * 2, t0=t_in)
    p = Position(Order(1, t_in, None), t_in, 2000, 2000, 0.25, 1990, None, 1.0, t_out)
    assert engine(m).swap_for(p, t_out) == (0.0, 0)


def test_friday_early_close_exits_before_the_weekend():
    # Friday 2024-01-12: market data stops at 18:00 London, then resumes Sunday 23:00
    fri = pd.Timestamp("2024-01-12 17:58", tz="UTC").value
    t = np.r_[fri + np.arange(3) * MIN, pd.Timestamp("2024-01-14 23:00", tz="UTC").value]
    m = M1(t, *(np.full(4, 2000.0),) * 4, np.full(4, 0.3))
    p = Position(Order(1, fri, None), fri, 2000, 2000, 0.3, 1900, None, 0.1,
                 friday_close_ns(fri), forced_is_friday=True)
    ex = engine(m).walk(p, fri, t[-1] + 1)
    assert ex[0] == t[2] and ex[2] == "friday close (market closed early)"
