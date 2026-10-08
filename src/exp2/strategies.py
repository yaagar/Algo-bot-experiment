"""The five Experiment 2 strategies (spec §2), rules exactly as written — no tuning.

Each strategy is called by the engine at the CLOSE of bar i with data up to bar i only:
  signal(i)          -> Order or None   (only asked when flat)
  exit_signal(i, p)  -> True to exit at the next bar's open
S5 is clock-based and provides schedule() instead.
"""
import numpy as np
import pandas as pd

from src.exp2.engine import NS_MIN, Order, london_ns
from src.exp2.market import atr, rsi, sma
from src.strategy_asian import Params as AsianParams, compute_box
from src.timeutils import LONDON, NEW_YORK

WINDOW_FROM, WINDOW_TO = 7 * 60, 16 * 60        # signal candles closing 07:00-16:00 London
TIME_EXIT = 20 * 60                               # 20:00 London


class S1Asian:
    """Experiment 1 §5 Asian breakout, under Experiment 2's common settings."""
    name = "S1"

    def __init__(self, market, tf="H1", box_end="07:00"):
        self.tf, self.bars = tf, market.bars[tf]
        self.minutes = 15 if tf == "M15" else 60
        h, m = map(int, box_end.split(":"))
        self.p = AsianParams(box_end=h * 60 + m)
        self.decisions = []
        self.boxes = self._boxes(market.m1)
        self.done_dates = set()

    def _boxes(self, m1):
        t = pd.to_datetime(m1.t, utc=True).tz_convert(LONDON)
        minute = (t.hour * 60 + t.minute).to_numpy()
        dates = t.date
        boxes = {}
        inside = minute < self.p.box_end
        df = pd.DataFrame({"date": dates[inside], "minute": minute[inside], "h": m1.h[inside], "l": m1.l[inside],
                           "s": m1.s[inside]})
        for d, g in df.groupby("date"):
            box, why = compute_box(g.minute.to_numpy(), g.h.to_numpy(), g.l.to_numpy(), g.s.to_numpy(), self.p)
            boxes[d] = box
            box_ns = london_ns(d, self.p.box_end)
            self.decisions.append((box_ns, "box", (round(box.high, 3), round(box.low, 3)) if box else why, box_ns))
        return boxes

    def signal(self, i):
        b = self.bars
        close_min, d = b.close_london_min[i], b.close_london_date[i]
        open_min = close_min - self.minutes
        if d in self.done_dates or open_min < self.p.box_end or close_min > self.p.entry_end or close_min < self.minutes:
            return None
        box = self.boxes.get(d)
        if box is None:
            return None
        c = b.close[i]
        direction = 1 if c > box.high else (-1 if c < box.low else 0)
        if direction == 0:
            return None
        self.done_dates.add(d)                         # first breakout is the day's only signal
        edge = box.low if direction > 0 else box.high
        return Order(direction, int(b.t_close[i]), lambda price, spread, e=edge: e, target_r=1.5,
                     time_exit_ns=london_ns(d, TIME_EXIT), info={"box_high": box.high, "box_low": box.low})

    def exit_signal(self, i, pos):
        return False


class S2Box:
    """Wick rejection at the previous broker day's high (PDH) / low (PDL), H1."""
    name = "S2"

    def __init__(self, market, wick_ratio=2.0):
        self.bars = b = market.bars["H1"]
        prev = market.days.shift(1)                    # previous broker trading day
        self.pdh = b.server_date.map(prev.high).to_numpy(dtype=float)
        self.pdl = b.server_date.map(prev.low).to_numpy(dtype=float)
        self.ratio = wick_ratio
        self.used = set()                              # (London date, level)

    def signal(self, i):
        b = self.bars
        if not (WINDOW_FROM <= b.close_london_min[i] <= WINDOW_TO) or np.isnan(self.pdh[i]):
            return None
        o, h, l, c = b.open[i], b.high[i], b.low[i], b.close[i]
        body, rng = abs(c - o), h - l
        upper, lower = h - max(o, c), min(o, c) - l
        sell = h >= self.pdh[i] and c < self.pdh[i] and upper >= self.ratio * body and upper >= 0.5 * rng
        buy = l <= self.pdl[i] and c > self.pdl[i] and lower >= self.ratio * body and lower >= 0.5 * rng
        if sell == buy:                                # neither, or (very rare) both at once
            return None
        d = b.close_london_date[i]
        level = "PDH" if sell else "PDL"
        if (d, level) in self.used:
            return None
        self.used.add((d, level))
        if sell:     # stop beyond the wick tip, plus the spread at entry
            rule = lambda price, spread, tip=h: tip + spread
        else:
            rule = lambda price, spread, tip=l: tip - spread
        return Order(-1 if sell else 1, int(b.t_close[i]), rule, target_r=1.5, time_exit_ns=london_ns(d, TIME_EXIT),
                     info={"level": level, "PDH": self.pdh[i], "PDL": self.pdl[i], "signal_high": h, "signal_low": l})

    def exit_signal(self, i, pos):
        return False


class S3Donchian:
    """Turtle-style channel breakout: 20-bar entry, 10-bar exit, 2 x ATR(20) initial stop on H4 (Experiment 2).
    Experiment 3 runs the same code on daily bars with 55/20: S3Donchian(market, 55, 20, tf="D1")."""
    name = "S3"

    def __init__(self, market, channel=20, exit_channel=10, tf="H4"):
        self.bars = b = market.bars[tf]
        hi, lo = b.high, b.low
        self.up = hi.shift(1).rolling(channel, min_periods=channel).max().to_numpy()
        self.dn = lo.shift(1).rolling(channel, min_periods=channel).min().to_numpy()
        self.ex_up = hi.shift(1).rolling(exit_channel, min_periods=exit_channel).max().to_numpy()
        self.ex_dn = lo.shift(1).rolling(exit_channel, min_periods=exit_channel).min().to_numpy()
        self.atr = atr(hi.to_numpy(), lo.to_numpy(), b.close.to_numpy(), 20)

    def signal(self, i):
        c, a = self.bars.close[i], self.atr[i]
        if np.isnan(self.up[i]) or np.isnan(a):
            return None
        direction = 1 if c > self.up[i] else (-1 if c < self.dn[i] else 0)
        if direction == 0:
            return None
        return Order(direction, int(self.bars.t_close[i]), lambda price, spread, d=direction, a=a: price - d * 2 * a,
                     info={"channel_high": self.up[i], "channel_low": self.dn[i], "atr20": a})

    def exit_signal(self, i, pos):
        c = self.bars.close[i]
        if pos.order.direction > 0:
            return not np.isnan(self.ex_dn[i]) and c < self.ex_dn[i]
        return not np.isnan(self.ex_up[i]) and c > self.ex_up[i]


class S4RSI2:
    """Connors RSI(2) pullback on H1: trade dips in the direction of the 200-bar trend."""
    name = "S4"

    def __init__(self, market, buy_below=10, sell_above=90):
        self.bars = b = market.bars["H1"]
        c = b.close.to_numpy()
        self.sma200, self.rsi2 = sma(c, 200), rsi(c, 2)
        self.atr14 = atr(b.high.to_numpy(), b.low.to_numpy(), c, 14)
        self.buy_below, self.sell_above = buy_below, sell_above

    def signal(self, i):
        b = self.bars
        if not (WINDOW_FROM <= b.close_london_min[i] <= WINDOW_TO):
            return None
        c, s, r, a = b.close[i], self.sma200[i], self.rsi2[i], self.atr14[i]
        if np.isnan(s) or np.isnan(r) or np.isnan(a):
            return None
        direction = 1 if (c > s and r < self.buy_below) else (-1 if (c < s and r > self.sell_above) else 0)
        if direction == 0:
            return None
        return Order(direction, int(b.t_close[i]), lambda price, spread, d=direction, a=a: price - d * 2 * a,
                     time_exit_ns=london_ns(b.close_london_date[i], TIME_EXIT),
                     info={"sma200": s, "rsi2": r, "atr14": a})

    def exit_signal(self, i, pos):
        r = self.rsi2[i]
        return r > 70 if pos.order.direction > 0 else r < 30


class S5AsianHours:
    """Long gold from 18:00 New York (new trading day) to 03:00 New York, Sunday-Thursday evenings."""
    name = "S5"

    def __init__(self, market, events, exit_hour_ny=3):
        h1 = market.bars["H1"]
        self.atr_close_ns = h1.t_close.to_numpy()
        self.atr14 = atr(h1.high.to_numpy(), h1.low.to_numpy(), h1.close.to_numpy(), 14)
        self.first, self.last = int(market.m1.t[0]), int(market.m1.t[-1])
        self.events, self.exit_hour = events, exit_hour_ny

    def schedule(self):
        first = pd.Timestamp(self.first, tz="UTC").tz_convert(NEW_YORK).normalize()
        last = pd.Timestamp(self.last, tz="UTC").tz_convert(NEW_YORK).normalize()
        for day in pd.date_range(first.tz_localize(None), last.tz_localize(None), freq="D"):
            if day.dayofweek not in (6, 0, 1, 2, 3):          # Sunday-Thursday evenings
                continue
            entry = pd.Timestamp(day).tz_localize(NEW_YORK) + pd.Timedelta(hours=18)
            exit_ = pd.Timestamp(day + pd.Timedelta(days=1)).tz_localize(NEW_YORK) + pd.Timedelta(hours=self.exit_hour)
            e_ns, x_ns = int(entry.tz_convert("UTC").value), int(exit_.tz_convert("UTC").value)
            if e_ns < self.first or x_ns > self.last:
                continue
            k = int(np.searchsorted(self.atr_close_ns, e_ns, "right")) - 1     # last H1 bar closed by 18:00
            a = self.atr14[k] if k >= 0 else np.nan
            info = {"atr14": a}
            if np.isnan(a):
                info["skip"] = "ATR warm-up"
            else:
                i = int(np.searchsorted(self.events.t, e_ns, "left"))
                if i < len(self.events.t) and self.events.t[i] <= x_ns:
                    info["skip"] = "high-impact event inside holding window"
            yield (Order(1, e_ns, lambda price, spread, a=a: price - 2 * a, time_exit_ns=x_ns, info=info), e_ns)
