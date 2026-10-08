"""Market data for Experiment 2: bars, H4 bars, broker-day levels and indicators.

All price data comes through src/data_access.py (via backtest.load_bars), 2022+ only.
Indicators are causal: the value at bar i uses bars up to and including i, and the
series start from the first loaded bar (no reaching into 2021 for warm-up, spec §4).
ATR and RSI use Wilder smoothing (first value = simple average of the first n).
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.backtest import load_bars
from src.timeutils import LONDON, NEW_YORK, utc_to_server

NS_MIN = 60 * 10**9


def to_ns(times):
    return pd.Series(times).dt.tz_convert(None).to_numpy().astype("datetime64[ns]").astype(np.int64)


@dataclass
class M1:
    t: np.ndarray        # bar open, UTC ns
    o: np.ndarray
    h: np.ndarray
    l: np.ndarray
    c: np.ndarray
    s: np.ndarray        # spread, price units (base, before any stress multiplier)


def m1_arrays(m1, point):
    return M1(to_ns(m1.time_utc), m1.open.to_numpy(), m1.high.to_numpy(), m1.low.to_numpy(),
              m1.close.to_numpy(), m1.spread_used.to_numpy() * point)


def bar_frame(df, minutes, point):
    """Strategy bars with open/close times (UTC ns) and London / New York / server clocks."""
    b = pd.DataFrame({"time_utc": df.time_utc.values, "open": df.open.values, "high": df.high.values,
                      "low": df.low.values, "close": df.close.values, "spread": df.spread_used.values * point})
    b["time_utc"] = pd.to_datetime(b.time_utc, utc=True)
    b["t_open"] = to_ns(b.time_utc)
    b["t_close"] = b.t_open + minutes * NS_MIN
    return add_clocks(b)


def add_clocks(b):
    close_utc = pd.to_datetime(b.t_close, utc=True)
    lon = close_utc.dt.tz_convert(LONDON)
    b["close_london_min"] = (lon.dt.hour * 60 + lon.dt.minute).values
    b["close_london_date"] = lon.dt.date.values
    b["close_london_wday"] = lon.dt.dayofweek.values
    b["server_date"] = utc_to_server(b.time_utc).dt.date.values
    return b.reset_index(drop=True)


def h4_from_h1(h1):
    """MT5-style H4 bars: H1 bars grouped into 4-hour blocks of broker server time (00, 04, 08 ...)."""
    server = utc_to_server(h1.time_utc)
    key = server.dt.floor("4h")
    g = h1.groupby(key.values, sort=True)
    b = pd.DataFrame({"time_utc": pd.to_datetime(g.t_open.first().values, utc=True), "open": g.open.first().values,
                      "high": g.high.max().values, "low": g.low.min().values, "close": g.close.last().values,
                      "spread": g.spread.first().values,
                      "t_open": g.t_open.first().values, "t_close": g.t_close.last().values})
    return add_clocks(b)


def broker_days(h1):
    """Each broker (server) day's high, low and close."""
    g = h1.groupby("server_date", sort=True)
    return pd.DataFrame({"high": g.high.max(), "low": g.low.min(), "close": g.close.last()})


# --- indicators (causal) ----------------------------------------------------------------------

def wilder(x, n):
    """Wilder smoothing: first value = mean of the first n inputs, then avg = (prev*(n-1) + x) / n."""
    x = np.asarray(x, dtype=float)
    out = np.full(len(x), np.nan)
    valid = np.flatnonzero(~np.isnan(x))
    if len(valid) < n:
        return out
    start = valid[0]
    first = start + n - 1
    out[first] = x[start:first + 1].mean()
    for i in range(first + 1, len(x)):
        out[i] = (out[i - 1] * (n - 1) + x[i]) / n
    return out


def atr(high, low, close, n):
    prev = np.r_[np.nan, close[:-1]]
    tr = np.nanmax(np.vstack([high - low, np.abs(high - prev), np.abs(low - prev)]), axis=0)
    tr[0] = high[0] - low[0]
    return wilder(tr, n)


def rsi(close, n):
    delta = np.r_[np.nan, np.diff(close)]
    up, down = np.where(delta > 0, delta, 0.0), np.where(delta < 0, -delta, 0.0)
    up[0] = down[0] = np.nan
    au, ad = wilder(up, n), wilder(down, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = au / ad
        out = 100 - 100 / (1 + rs)
    out[(ad == 0) & (au > 0)] = 100.0
    out[(ad == 0) & (au == 0)] = 50.0
    return out


def sma(x, n):
    return pd.Series(x).rolling(n, min_periods=n).mean().to_numpy()


# --- loading -----------------------------------------------------------------------------------

@dataclass
class Market:
    m1: M1
    bars: dict             # "M15", "H1", "H4" -> DataFrame
    days: pd.DataFrame     # broker-day high/low/close


def build_market(m1_df, m15_df, h1_df, point):
    h1 = bar_frame(h1_df, 60, point)
    return Market(m1_arrays(m1_df, point),
                  {"M15": bar_frame(m15_df, 15, point), "H1": h1, "H4": h4_from_h1(h1)},
                  broker_days(h1))


def load_frames(symbol, start, end):
    """M1, M15, H1 frames for [start, end). 2022+ only (the data lock refuses earlier windows)."""
    return tuple(load_bars(symbol, tf, start, end, end) for tf in ("M1", "M15", "H1"))


def new_york_minute(t_ns):
    t = pd.Timestamp(int(t_ns), tz="UTC").tz_convert(NEW_YORK)
    return t.hour * 60 + t.minute
