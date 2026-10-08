"""Experiment 4 data: one market's M1, H1 and H4 bars for one period, with trading days and clocks.

Plain-English flow (spec §2-§3, Change Log v1.1):
  * all prices come through src/data_access.py (2022+ only), for a window [start, end) — warm-ups
    never reach outside the period because nothing outside it is loaded (spec §6);
  * H1 bars: gold = the broker's H1 bars; US500 = built from M1 at :30 New York (09:30-10:30, ...);
  * H4 bars: MT5-style 4-hour blocks of broker server time, built from the finest bars we have
    (gold H1, US500 M1). A block counts as finished only at its nominal end (block start + 4 h),
    never earlier, so a data hole can't leak "no more bars are coming";
  * every H1 bar gets its trading day (gold: London date; US500: 18:00 New York the evening before
    to 17:00, labelled by the New York date it ends on) and "minutes since day start" of its close.
Weekend-dated bars (gold's Sunday-evening hour) belong to no trading day but still feed the
indicators, like any real bar.
"""
import copy
from dataclasses import dataclass

import numpy as np
import pandas as pd
import yaml

from src.backtest import Events
from src.calendar_events import OUT as CALENDAR_PATH
from src.config import PROJECT_ROOT
from src.data_access import PROCESSED, read_prices
from src.exp2.market import M1, m1_arrays, to_ns
from src.timeutils import utc_to_server

CONFIG_PATH = PROJECT_ROOT / "config" / "exp4.yaml"
RESULTS = PROJECT_ROOT / "results" / "exp4"
COLS = ["time_utc", "open", "high", "low", "close", "spread_used", "spread_estimated"]
NS_MIN = 60 * 10**9
NS_HOUR = 60 * NS_MIN


# --- configuration ------------------------------------------------------------------------------

def load_config(path=CONFIG_PATH):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def variant_config(cfg, name):
    """The main configuration with one pre-declared variant's overrides applied (spec §7)."""
    out = copy.deepcopy(cfg)
    for key, value in cfg["variants"][name].items():
        if isinstance(value, dict):
            out[key].update(value)
        else:
            out[key] = value
    out["variant"] = name
    return out


def hhmm(text):
    h, m = text.split(":")
    return int(h) * 60 + int(m)


def period(cfg, name):
    p = cfg["periods"][name]
    return pd.Timestamp(p["start"], tz="UTC"), (pd.Timestamp(p["end"], tz="UTC") if p["end"] else None)


# --- clock --------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Clock:
    """A market's local clock and trading day (Change Log v1.1 item 4)."""
    tz: str
    start_min: int              # day start, local minutes after midnight (gold 0, US500 18:00 = 1080)

    def minute(self, text):
        """Minutes since day start of a local "HH:MM" (the day start itself = 0)."""
        return (hhmm(text) - self.start_min) % 1440

    def at(self, day, text):
        """UTC ns of local time "HH:MM" on trading day `day` (times at/after an evening start = the evening before)."""
        mins = hhmm(text)
        date = pd.Timestamp(day)
        if self.start_min > 0 and mins >= self.start_min:
            date -= pd.Timedelta(days=1)
        return int((date + pd.Timedelta(minutes=mins)).tz_localize(self.tz).value)

    def day_and_minute(self, t_close_ns):
        """Trading day (weekday dates only, else NaT) and minutes-since-day-start of each bar CLOSE."""
        local = pd.to_datetime(np.asarray(t_close_ns) - 1, utc=True).tz_convert(self.tz)   # -1 ns: a close at
        lm = local.hour * 60 + local.minute                                                # midnight is the old day
        minute = ((lm - self.start_min) % 1440) + 1
        shift = pd.Timedelta(minutes=(1440 - self.start_min) % 1440)
        day = (local.tz_localize(None) + shift).normalize()
        day = day.where(day.dayofweek < 5)
        return day, np.asarray(minute)


# --- bars ---------------------------------------------------------------------------------------

def h1_from_broker(h1, point):
    t = to_ns(h1.time_utc)
    return pd.DataFrame({"t_open": t, "t_close": t + NS_HOUR, "open": h1.open.values, "high": h1.high.values,
                         "low": h1.low.values, "close": h1.close.values, "spread": h1.spread_used.values * point})


def h1_from_m1(m1, point, offset_min):
    """H1 bars from M1 starting `offset_min` past each UTC hour (New York is a whole hour from UTC,
    so 30 here = :30 New York). A bar is stamped with its nominal open/close, even if its first
    minutes are empty (e.g. 17:30-18:30 New York only has prices from the 18:00 reopen)."""
    t = to_ns(m1.time_utc)
    off = offset_min * NS_MIN
    bucket = (t - off) // NS_HOUR * NS_HOUR + off
    g = pd.DataFrame({"b": bucket, "open": m1.open.values, "high": m1.high.values, "low": m1.low.values,
                      "close": m1.close.values, "spread": m1.spread_used.values * point}).groupby("b", sort=True)
    out = pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(),
                        "close": g.close.last(), "spread": g.spread.first()}).reset_index(names="t_open")
    out.insert(1, "t_close", out.t_open + NS_HOUR)
    return out


def h4_blocks(frame):
    """MT5-style H4 bars from finer bars (columns time_utc, high, low, close): 4-hour blocks of
    broker server time. t_close = nominal block end, so a block is used only once it is over."""
    server = utc_to_server(frame.time_utc)
    block = server.dt.floor("4h")
    t = to_ns(frame.time_utc)
    t_open = t - (server - block).to_numpy().astype("timedelta64[ns]").astype(np.int64)
    g = pd.DataFrame({"b": block.values, "t_open": t_open, "high": frame.high.values, "low": frame.low.values,
                      "close": frame.close.values}).groupby("b", sort=True)
    out = pd.DataFrame({"t_open": g.t_open.first(), "high": g.high.max(), "low": g.low.min(),
                        "close": g.close.last()}).reset_index(drop=True)
    out["t_close"] = out.t_open + 4 * NS_HOUR
    return out


# --- one market ---------------------------------------------------------------------------------

@dataclass
class MarketData:
    name: str
    cfg: dict              # the market's config block
    clock: Clock
    m1: M1                 # engine price path (stops, forced exits)
    h1: pd.DataFrame       # decision bars + day (Timestamp/NaT), day_idx (-1 = none), m (minutes since day start)
    h4: pd.DataFrame
    days: list             # trading days present, in order


def load_frames(mcfg, start, end):
    """(M1, broker H1 or None) for [start, end), through the data lock."""
    read = lambda tf, f: read_prices(mcfg["symbol"], tf, start, end, columns=COLS,
                                     path=PROCESSED / f).reset_index(drop=True)
    return read("M1", mcfg["m1_file"]), (read("H1", mcfg["h1_file"]) if mcfg["h1_file"] else None)


def build_market(name, mcfg, m1_df, h1_df=None):
    point = mcfg["point"]
    if mcfg["h1_source"] == "broker":
        h1 = h1_from_broker(h1_df, point)
        h4 = h4_blocks(h1_df)
    else:
        h1 = h1_from_m1(m1_df, point, offset_min=30)
        h4 = h4_blocks(m1_df)
    clock = Clock(mcfg["tz"], hhmm(mcfg["day_start"]))
    day, minute = clock.day_and_minute(h1.t_close.to_numpy())
    h1["day"], h1["m"] = day.values, minute
    days = sorted(h1.day.dropna().unique())
    index = {d: k for k, d in enumerate(days)}
    h1["day_idx"] = h1.day.map(index).fillna(-1).astype(int)
    return MarketData(name, mcfg, clock, m1_arrays(m1_df, point), h1, h4, [pd.Timestamp(d) for d in days])


def load_market(cfg, name, period_name="development"):
    start, end = period(cfg, period_name)
    mcfg = cfg["markets"][name]
    return build_market(name, mcfg, *load_frames(mcfg, start, end))


def load_events():
    return Events(pd.read_parquet(CALENDAR_PATH).time_utc)
