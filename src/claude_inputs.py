"""Build what Claude sees for a decision (spec §6.1, v1.3) — and nothing else.

Everything is built only from data available at the decision time T:
  * price action, ANONYMISED: the last 48 completed H1 candles and today's completed M15
    candles, as (price - box_mid) / box_height (so the box runs from -0.5 to +0.5),
    plus H1 ATR(14) in the same units. Candles carry weekday + London time of day only:
    no dates, years, symbol name or absolute prices;
  * the signal (veto calls): direction, stop -1R, target +1.5R;
  * scheduled USD events: upcoming (name, impact, minutes until) and already released
    today (name, minutes since). No actual or forecast values (v1.3);
  * headlines first seen between T-12h and T-15min, shown as "3h ago". Headlines whose
    only topic is "gold" must also contain a market word (v1.3). Exact duplicate titles
    are shown once.
"""
import json
import re
from glob import glob

import numpy as np
import pandas as pd

from src.config import PROJECT_ROOT
from src.timeutils import LONDON

GKG_DIR = PROJECT_ROOT / "data" / "raw" / "gdelt_gkg"
GOLD_MARKET_WORDS = re.compile(r"\b(?:price|prices|ounce|bullion|futures|xau|rally|falls|drops|rises|record)\b", re.I)
H1_CANDLES = 48
ATR_PERIOD = 14
HEADLINE_WINDOW = pd.Timedelta(hours=12)
HEADLINE_DELAY = pd.Timedelta(minutes=15)


def load_headlines():
    rows = []
    for f in sorted(glob(str(GKG_DIR / "*.jsonl"))):
        for line in open(f, encoding="utf-8").read().splitlines()[1:]:
            r = json.loads(line)
            rows.append((r["available_at_utc"], r["title"], r["topics"]))
    h = pd.DataFrame(rows, columns=["available_at", "title", "topics"])
    h["available_at"] = pd.to_datetime(h.available_at, utc=True)
    gold_only = h.topics.apply(lambda t: t == ["gold"])
    keep = ~gold_only | h.title.str.contains(GOLD_MARKET_WORDS)
    h = h[keep].sort_values("available_at")
    h["key"] = h.title.str.lower().str.strip()          # show each title once (earliest copy)
    return h.drop_duplicates("key").drop(columns="key").reset_index(drop=True)


def ago(delta):
    minutes = int(delta.total_seconds() // 60)
    return f"{minutes}m ago" if minutes < 60 else f"{round(minutes / 60)}h ago"


def headlines_block(headlines, t):
    w = headlines[(headlines.available_at <= t - HEADLINE_DELAY) & (headlines.available_at > t - HEADLINE_WINDOW)]
    w = w.sort_values("available_at", ascending=False)
    lines = [f"- [{ago(t - a)}] {title}" for a, title in zip(w.available_at, w.title)]
    return f"Recent headlines ({len(lines)}, newest first):\n" + ("\n".join(lines) if lines else "- none")


def events_block(calendar, t, until):
    """Upcoming events between t and `until`, plus events already released today (London)."""
    today = t.tz_convert(LONDON).date()
    c = calendar.copy()
    c["london_date"] = c.time_utc.dt.tz_convert(LONDON).dt.date
    upcoming = c[(c.time_utc > t) & (c.time_utc <= until)].sort_values("time_utc")
    released = c[(c.time_utc <= t) & (c.london_date == today)].sort_values("time_utc")
    up = [f"- {r.event} (high impact) in {int((r.time_utc - t).total_seconds() // 60)} min" for r in upcoming.itertuples()]
    done = [f"- {r.event} (high impact) released {int((t - r.time_utc).total_seconds() // 60)} min ago" for r in released.itertuples()]
    return ("Scheduled high-impact US events still to come:\n" + ("\n".join(up) if up else "- none") +
            "\nEvents already released today:\n" + ("\n".join(done) if done else "- none"))


def rel(x, mid, height):
    return (x - mid) / height


def candles_block(bars, label, t, box, n=None, today_only=False):
    """Completed candles (close time <= t), relative to the box."""
    done = bars[bars.close_time <= t]
    if today_only:
        done = done[done.time_utc.dt.tz_convert(LONDON).dt.date == t.tz_convert(LONDON).date()]
    if n:
        done = done.tail(n)
    mid, height = (box.high + box.low) / 2, box.high - box.low
    lines = []
    for r in done.itertuples():
        lt = r.time_utc.tz_convert(LONDON)
        o, h, l, c = (rel(v, mid, height) for v in (r.open, r.high, r.low, r.close))
        lines.append(f"{lt:%a %H:%M} {o:+.3f} {h:+.3f} {l:+.3f} {c:+.3f}")
    return f"{label} ({len(lines)}; weekday + London open time, then open high low close):\n" + "\n".join(lines)


def atr_in_box_units(h1, t, box):
    done = h1[h1.close_time <= t].tail(ATR_PERIOD + 1)
    prev_close = done.close.shift(1)
    tr = pd.concat([done.high - done.low, (done.high - prev_close).abs(), (done.low - prev_close).abs()], axis=1).max(axis=1)
    return float(tr.iloc[1:].mean() / (box.high - box.low))


def with_close_time(bars, minutes):
    bars = bars.copy()
    bars["close_time"] = bars.time_utc + pd.Timedelta(minutes=minutes)
    return bars


def price_block(h1, m15, t, box):
    return (f"Price action relative to today's overnight box (box = -0.500 to +0.500):\n"
            f"H1 ATR({ATR_PERIOD}) = {atr_in_box_units(h1, t, box):.3f} box heights\n\n"
            + candles_block(h1, "Recent hourly candles", t, box, n=H1_CANDLES) + "\n\n"
            + candles_block(m15, "Today's 15-minute candles", t, box, today_only=True))


def morning_input(t, box, h1, m15, calendar, headlines, day_end):
    return "\n\n".join([
        f"Decision time: {t.tz_convert(LONDON):%A} {t.tz_convert(LONDON):%H:%M} London (start of the trading session).",
        price_block(h1, m15, t, box),
        events_block(calendar, t, day_end),
        headlines_block(headlines, t),
        "Is today a TRADE_DAY or a NO_TRADE_DAY?"])


def veto_input(t, box, direction, h1, m15, calendar, headlines):
    side = "LONG" if direction > 0 else "SHORT"
    return "\n\n".join([
        f"Decision time: {t.tz_convert(LONDON):%A} {t.tz_convert(LONDON):%H:%M} London.",
        f"Signal: {side}. The last 15-minute/hourly candle closed {'above' if direction > 0 else 'below'} the box. "
        f"Entry at the next candle's open. Stop = -1.0R (opposite box edge), target = +1.5R. "
        f"Closed by 20:00 London at the latest.",
        price_block(h1, m15, t, box),
        events_block(calendar, t, t + pd.Timedelta(hours=6)),
        headlines_block(headlines, t),
        "TAKE or VETO this trade?"])
