"""Bot A — Asian Range Breakout rules (spec §5).

Pure decision functions. Each one only looks at the bars it is handed, and the
backtester only hands it bars that have already closed (spec §9.1).
All clock times here are Europe/London minutes-of-day (e.g. 07:00 -> 420).
"""
from dataclasses import dataclass

import numpy as np


def hhmm_to_minutes(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


@dataclass(frozen=True)
class Params:
    box_start: int = hhmm_to_minutes("00:00")
    box_end: int = hhmm_to_minutes("07:00")        # entry window starts here too
    entry_end: int = hhmm_to_minutes("16:00")
    time_exit: int = hhmm_to_minutes("20:00")
    take_profit_r: float = 1.5
    min_box_to_median_spread: float = 5.0
    max_box_gap_minutes: int = 30
    news_blackout_minutes: int = 30

    @classmethod
    def from_settings(cls, s):
        a = s["strategy_asian"]
        return cls(box_start=hhmm_to_minutes(a["box_start"]), box_end=hhmm_to_minutes(a["box_end"]),
                   entry_end=hhmm_to_minutes(a["entry_window_end"]), time_exit=hhmm_to_minutes(a["time_exit"]),
                   take_profit_r=float(a["take_profit_r"]),
                   min_box_to_median_spread=float(a["min_box_to_median_spread"]),
                   max_box_gap_minutes=int(a["max_box_gap_minutes"]),
                   news_blackout_minutes=int(a["news_blackout_minutes"]))


@dataclass(frozen=True)
class Box:
    high: float
    low: float
    median_spread: float

    @property
    def height(self):
        return self.high - self.low


def compute_box(minute, high, low, spread_px, p):
    """The Asian box from M1 bars that opened between box_start and box_end.

    Returns (Box, None) or (None, skip_reason). Skips (spec §5.2):
      - no bars, or a hole in the data longer than max_box_gap_minutes
        (including at the start or end of the box period);
      - box height < min_box_to_median_spread x median spread during the box.
    """
    inside = (minute >= p.box_start) & (minute < p.box_end)
    if not inside.any():
        return None, "no data in box"
    m = minute[inside]
    # gap = minutes with no bar; consecutive M1 bars have 0 missing minutes between them
    edges = np.concatenate(([p.box_start - 1], m, [p.box_end]))
    if (np.diff(edges) - 1).max() > p.max_box_gap_minutes:
        return None, "box data gap > 30 min"
    box = Box(high=float(high[inside].max()), low=float(low[inside].min()),
              median_spread=float(np.median(spread_px[inside])))
    if box.height < p.min_box_to_median_spread * box.median_spread:
        return None, "box < 5x median spread"
    return box, None


def find_breakout(candle_minute, candle_close, tf_minutes, box, p):
    """First candle in the entry window that CLOSES beyond the box (spec §5.4).

    Candles are checked one at a time in order — exactly what a live bot sees
    at each candle close. Returns (index, direction) with +1 = long, -1 = short,
    or None. A candle counts if it opens at/after box_end and closes by entry_end.
    """
    for i in range(len(candle_minute)):
        opens, closes_at = candle_minute[i], candle_minute[i] + tf_minutes
        if opens < p.box_end or closes_at > p.entry_end:
            continue
        if candle_close[i] > box.high:
            return i, +1
        if candle_close[i] < box.low:
            return i, -1
    return None
