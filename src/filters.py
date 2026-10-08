"""Candidate filter tags for Bot A trades (spec v1.4, §12 Phase 4b).

Definitions are fixed here BEFORE any 4b result was seen:

  narrow_box  : today's Asian box width (high - low of M1 bars 00:00-07:00 London,
                the same box Bot A uses) < median width of the PRIOR 20 London
                weekdays that had box data (today excluded). Median split, no threshold search.
  trend_up    : at box time (07:00 London) the broker's current daily candle is still
                open, so use COMPLETED broker days only: latest completed daily close
                > average of the last 20 completed daily closes. A broker day = server
                calendar day (ends 17:00 New York); its close = last M1 close of that day.
  with_trend  : long when trend_up, short when not trend_up.
  event_day   : the London trade date has an FOMC decision, CPI or NFP release.

Tags needing 20 days of history are None until that history exists inside the
loaded data (2021 and earlier are reserved for Phase 4c and are not loaded).
"""
import numpy as np
import pandas as pd

from src.timeutils import LONDON, utc_to_server

LOOKBACK = 20
EVENT_DAY_EVENTS = ("FOMC decision", "CPI", "NFP")


def box_widths(m1, box_start_min=0, box_end_min=420):
    """Asian box width per London weekday from M1 bars (time_utc, high, low)."""
    london = m1.time_utc.dt.tz_convert(LONDON)
    minute = london.dt.hour * 60 + london.dt.minute
    inside = (minute >= box_start_min) & (minute < box_end_min) & (london.dt.dayofweek < 5)
    g = m1[inside].groupby(london[inside].dt.date)
    return (g.high.max() - g.low.min()).rename("box_width")


def narrow_box_tags(widths):
    """True / False / None per date: width below the median of the prior 20 days."""
    prior_median = widths.shift(1).rolling(LOOKBACK, min_periods=LOOKBACK).median()
    tags = widths < prior_median
    return tags.where(prior_median.notna(), None)


def daily_closes(m1):
    """Close of each broker (server) day = last M1 close of that server calendar date."""
    server_date = utc_to_server(m1.time_utc).dt.date
    return m1.groupby(server_date.values).close.last().rename("daily_close")


def trend_up_tags(trade_dates, closes):
    """For each London trade date: latest COMPLETED daily close > its 20-day average.

    Completed = server dates strictly before the trade's London date (at 07:00 London
    the server day with that date has started but not finished).
    """
    closes = closes.sort_index()
    sma = closes.rolling(LOOKBACK, min_periods=LOOKBACK).mean()
    out = {}
    for d in trade_dates:
        i = closes.index.searchsorted(d, side="left") - 1      # last server date < d
        if i < 0 or np.isnan(sma.iloc[i]):
            out[d] = None
        else:
            out[d] = bool(closes.iloc[i] > sma.iloc[i])
    return pd.Series(out)


def event_days(calendar):
    return set(calendar[calendar.event.isin(EVENT_DAY_EVENTS)].date)


def tag_trades(trades, m1, calendar):
    """Add year, quarter and the candidate-filter tags to a Bot A trade list."""
    t = trades.copy()
    dates = pd.to_datetime(t.date)
    t["year"], t["quarter"] = dates.dt.year, dates.dt.year.astype(str) + "-Q" + dates.dt.quarter.astype(str)
    narrow = narrow_box_tags(box_widths(m1))
    t["narrow_box"] = [narrow.get(d) for d in t.date]
    trend = trend_up_tags(list(t.date), daily_closes(m1))
    t["trend_up"] = [trend.get(d) for d in t.date]
    t["with_trend"] = [None if up is None else (dirn == "LONG") == up for dirn, up in zip(t.direction, t.trend_up)]
    ev = event_days(calendar)
    t["event_day"] = [d in ev for d in t.date]
    return t


# Candidate filters, fixed in advance: name -> (tag column, value of trades KEPT)
CANDIDATES = {
    "narrow box only": ("narrow_box", True),
    "with-trend only": ("with_trend", True),
    "skip FOMC/CPI/NFP days": ("event_day", False),
}


def with_trend_chooser(base_chooser, trend_up_by_date):
    """A + with-trend (adopted in spec v1.5): take Bot A's signal only if it goes with
    the daily trend. No trend reading yet (under 20 completed days) = no trade."""
    def choose(day, box, p, rng=None):
        entry, why = base_chooser(day, box, p, rng)
        if entry is None:
            return None, why
        up = trend_up_by_date.get(day.date)
        if up is None:
            return None, "trend unknown"
        if (entry.direction > 0) != up:
            return None, "against trend"
        return entry, None
    return choose
