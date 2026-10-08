"""Backtester (spec §5, §9).

Walks forward one London trading day at a time. For each day:
  1. at box_end, build the Asian box from M1 bars that have already closed;
  2. an entry chooser picks the trade (Bot A: first breakout candle; C1: random);
  3. the fill is at the next candle's open, paying the spread (buy at ask, sell at bid);
  4. the exit is simulated on M1 bars after the fill (stop / target / 20:00);
  5. account rules (our kill switch, FTMO checks) are applied in date order.
Every decision is logged with the time it was made and the newest data it saw.

Prices in the data are BID (what MT5 charts show). ask = bid + spread.
"""
import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.config import PROJECT_ROOT, commission_usd
from src.data_access import read_prices
from src.strategy_asian import Params, compute_box, find_breakout
from src.timeutils import LONDON

PROCESSED = PROJECT_ROOT / "data" / "processed"
TF_MINUTES = {"M1": 1, "M15": 15, "H1": 60}
NS_PER_MIN = 60 * 10**9


@dataclass(frozen=True)
class Costs:
    spread_mult: float = 1.0               # 1.5 for the spread stress (fills only)
    commission_pct_per_side: float = 0.0007


@dataclass(frozen=True)
class Account:
    initial_balance: float = 10_000.0
    risk_per_trade: float = 50.0
    daily_stop: float = 150.0
    kill_switch_dd: float = 600.0
    contract_size: float = 100.0
    volume_step: float = 0.01
    volume_min: float = 0.01
    volume_max: float = 10.0


# --- Data ---------------------------------------------------------------------------

def dev_window(settings):
    """[start, end) of the development period in UTC, from London calendar dates."""
    period = settings["periods"]["development"]
    start = pd.Timestamp(str(period["start"])).tz_localize(LONDON).tz_convert("UTC")
    end = (pd.Timestamp(str(period["end"])) + pd.Timedelta(days=1)).tz_localize(LONDON).tz_convert("UTC")
    return start, end


def holdout_start(settings):
    return pd.Timestamp(str(settings["periods"]["holdout"]["start"])).tz_localize(LONDON).tz_convert("UTC")


def load_bars(symbol, tf, start, end, holdout_from, purpose=None, confirm=None):
    """Bars with start <= time_utc < end. Refuses any window that reaches the holdout, and
    (via src/data_access.py) any window before 2022-01-01 unless confirmed."""
    if end > holdout_from:
        raise ValueError(f"window end {end} reaches into the holdout period ({holdout_from}) — not allowed")
    cols = ["time_utc", "open", "high", "low", "close", "spread_used", "spread_estimated"]
    bars = read_prices(symbol, tf, start, end, columns=cols, purpose=purpose, confirm=confirm).reset_index(drop=True)
    assert bars.time_utc.max() < holdout_from
    return bars


@dataclass
class Day:
    """One London trading day: M1 bars (00:00-21:00 London) and the strategy candles."""
    date: object
    m1_t: np.ndarray        # int64 UTC ns of bar open
    m1_min: np.ndarray      # London minute of day
    m1_o: np.ndarray
    m1_h: np.ndarray
    m1_l: np.ndarray
    m1_c: np.ndarray
    m1_s: np.ndarray        # spread in price units
    m1_est: np.ndarray      # spread estimated?
    c_t: np.ndarray
    c_min: np.ndarray
    c_o: np.ndarray
    c_c: np.ndarray
    c_s: np.ndarray


def _split_by_day(bars, point):
    london = bars.time_utc.dt.tz_convert(LONDON)
    minute = (london.dt.hour * 60 + london.dt.minute).to_numpy()
    keep = (london.dt.dayofweek < 5).to_numpy() & (minute < 21 * 60)
    dates = london.dt.date.to_numpy()[keep]
    arrays = {
        "t": bars.time_utc.dt.tz_convert(None).to_numpy().astype("datetime64[ns]").astype(np.int64)[keep],
        "min": minute[keep],
        "o": bars.open.to_numpy()[keep], "h": bars.high.to_numpy()[keep],
        "l": bars.low.to_numpy()[keep], "c": bars.close.to_numpy()[keep],
        "s": bars.spread_used.to_numpy()[keep] * point,
        "est": bars.spread_estimated.to_numpy()[keep],
    }
    out = {}
    if len(dates) == 0:
        return out
    cut = np.flatnonzero(dates[1:] != dates[:-1]) + 1
    for lo, hi in zip(np.r_[0, cut], np.r_[cut, len(dates)]):
        out[dates[lo]] = {k: v[lo:hi] for k, v in arrays.items()}
    return out


def build_days(m1, candles, point):
    m1_days, c_days = _split_by_day(m1, point), _split_by_day(candles, point)
    days = []
    for d in sorted(m1_days):
        a, c = m1_days[d], c_days.get(d)
        if c is None:
            continue
        days.append(Day(d, a["t"], a["min"], a["o"], a["h"], a["l"], a["c"], a["s"], a["est"],
                        c["t"], c["min"], c["o"], c["c"], c["s"]))
    return days


# --- Events ---------------------------------------------------------------------------

class Events:
    """Sorted USD event times (UTC ns) for blackout / FTMO-flag checks."""

    def __init__(self, times_utc):
        utc = pd.to_datetime(pd.Series(times_utc), utc=True).dt.tz_convert(None)
        self.t = np.sort(utc.to_numpy().astype("datetime64[ns]").astype(np.int64))

    def within(self, t_ns, minutes):
        """Is there an event within +-minutes of t (inclusive)?"""
        w = minutes * NS_PER_MIN
        i = np.searchsorted(self.t, t_ns - w, side="left")
        return i < len(self.t) and self.t[i] <= t_ns + w


# --- Trade mechanics ---------------------------------------------------------------------

def lots_for_risk(risk_usd, stop_distance, acct):
    """spec §5.9: floor_to_step($50 / (stop distance x contract size))."""
    raw = risk_usd / (stop_distance * acct.contract_size)
    lots = math.floor(raw / acct.volume_step + 1e-9) * acct.volume_step
    return round(min(lots, acct.volume_max), 2)


@dataclass
class Exit:
    index: int              # M1 row in the day of the exit bar
    time_ns: int
    price: float
    reason: str             # "stop" | "target" | "time" | "end of data"
    worst_price: float      # most adverse price seen while open (for floating P&L)


def simulate_exit(day, start, direction, entry, stop, target, p, spread_mult):
    """Walk M1 bars from the fill bar until stop, target or time exit.

    Long: stop/target trigger on BID (bar low/high). Short: they trigger on ASK
    (bid + spread). If one bar touches both, the stop is assumed first (spec §5.11).
    A stop gapped through fills at the bar open (worse); targets fill at the target.
    """
    o, h, l, c = day.m1_o[start:], day.m1_h[start:], day.m1_l[start:], day.m1_c[start:]
    s = day.m1_s[start:] * spread_mult
    minute = day.m1_min[start:]
    path = minute < p.time_exit
    n = int(path.sum()) if path.all() else int(np.argmax(~path))   # path = bars before 20:00
    if direction > 0:
        stop_hit, target_hit = l[:n] <= stop, h[:n] >= target
        adverse = l[:n]
    else:
        stop_hit, target_hit = h[:n] + s[:n] >= stop, l[:n] + s[:n] <= target
        adverse = h[:n] + s[:n]
    hit = stop_hit | target_hit
    if hit.any():
        k = int(np.argmax(hit))
        if stop_hit[k]:
            price = min(o[k], stop) if direction > 0 else max(o[k] + s[k], stop)
            worst = price
            reason = "stop"
        else:
            price, reason = target, "target"
            worst = adverse[k]
        if k > 0:                         # include the bars before the exit bar
            prior = adverse[:k]
            worst = min(prior.min(), worst) if direction > 0 else max(prior.max(), worst)
        return Exit(start + k, int(day.m1_t[start + k]), float(price), reason, float(worst))
    worst = (adverse.min() if direction > 0 else adverse.max()) if n else entry
    if n < len(o):                       # first bar at/after 20:00 London
        k = n
        price = o[k] if direction > 0 else o[k] + s[k]
        return Exit(start + k, int(day.m1_t[start + k]), float(price), "time", float(worst))
    if n == 0:
        return None
    k = n - 1
    price = c[k] if direction > 0 else c[k] + s[k]
    return Exit(start + k, int(day.m1_t[start + k]), float(price), "end of data", float(worst))


# --- Entry choosers ------------------------------------------------------------------------

@dataclass
class Entry:
    direction: int
    fill_index: int          # candle row of the fill
    signal_time_ns: int      # when the decision was made (signal candle close)
    stop_price: float = None     # Bot A: opposite box edge
    stop_distance: float = None  # C1: A's stop distance that day


def bot_a_chooser(tf_minutes):
    """Bot A: first candle closing beyond the box; fill at the next candle's open."""
    def choose(day, box, p, rng=None):
        found = find_breakout(day.c_min, day.c_c, tf_minutes, box, p)
        if found is None:
            return None, "no breakout"
        i, direction = found
        signal_close_ns = int(day.c_t[i]) + tf_minutes * NS_PER_MIN
        nxt = np.flatnonzero((day.c_t > day.c_t[i]) & (day.c_min <= p.entry_end))
        if len(nxt) == 0:
            return None, "no candle to fill before entry window end"
        j = int(nxt[0])
        stop = box.low if direction > 0 else box.high
        return Entry(direction, j, signal_close_ns, stop_price=stop), None
    return choose


# --- The account loop ------------------------------------------------------------------------

@dataclass
class RunResult:
    trades: list = field(default_factory=list)
    decisions: list = field(default_factory=list)   # (time_ns, kind, date, detail, data_seen_ns)
    days: list = field(default_factory=list)        # London dates considered
    kill_switch_date: object = None


def run(days, chooser, p, costs, acct, events, rng=None, label=""):
    res = RunResult()
    balance = peak = acct.initial_balance
    killed = False
    for day in days:
        res.days.append(day.date)
        box_ns = _london_ns(day, p.box_end)
        box, skip = compute_box(day.m1_min, day.m1_h, day.m1_l, day.m1_s, p)
        in_box = (day.m1_min >= p.box_start) & (day.m1_min < p.box_end)
        seen = int(day.m1_t[in_box].max()) + NS_PER_MIN if in_box.any() else box_ns
        res.decisions.append((box_ns, "box", day.date,
                              (round(box.high, 3), round(box.low, 3)) if box else skip, seen))
        if box is None:
            continue
        if killed:
            res.decisions.append((box_ns, "no trade", day.date, "kill switch active", seen))
            continue
        entry, why = chooser(day, box, p, rng)
        if entry is None:
            # "no breakout" is only certain once the entry window has closed
            window_end = _london_ns(day, p.entry_end)
            res.decisions.append((window_end, "no trade", day.date, why, window_end))
            continue
        j = entry.fill_index
        fill_ns = int(day.c_t[j])
        res.decisions.append((entry.signal_time_ns, "signal", day.date, entry.direction, entry.signal_time_ns))
        if events.within(fill_ns, p.news_blackout_minutes):
            res.decisions.append((fill_ns, "blocked", day.date, "news blackout", fill_ns))
            continue
        spread = day.c_s[j] * costs.spread_mult
        bid = day.c_o[j]
        entry_price = bid + spread if entry.direction > 0 else bid
        if entry.stop_price is not None:
            stop = entry.stop_price
        else:
            stop = entry_price - entry.direction * entry.stop_distance
        r_dist = (entry_price - stop) * entry.direction
        if r_dist <= 0:
            res.decisions.append((fill_ns, "blocked", day.date, "entry beyond stop", fill_ns))
            continue
        lots = lots_for_risk(acct.risk_per_trade, r_dist, acct)
        if lots < acct.volume_min:
            res.decisions.append((fill_ns, "blocked", day.date, "size below minimum", fill_ns))
            continue
        target = entry_price + entry.direction * p.take_profit_r * r_dist
        m1_start = int(np.searchsorted(day.m1_t, fill_ns, side="left"))
        ex = simulate_exit(day, m1_start, entry.direction, entry_price, stop, target, p, costs.spread_mult)
        if ex is None:
            res.decisions.append((fill_ns, "blocked", day.date, "no M1 data after fill", fill_ns))
            continue
        res.decisions.append((fill_ns, "entry", day.date,
                              (entry.direction, round(entry_price, 3), round(stop, 3), round(target, 3), lots), fill_ns))
        res.decisions.append((ex.time_ns + NS_PER_MIN, "exit", day.date, (ex.reason, round(ex.price, 3)),
                              ex.time_ns + NS_PER_MIN))

        cs = acct.contract_size
        gross = entry.direction * (ex.price - entry_price) * lots * cs
        comm_in = commission_usd(lots, entry_price, cs, costs.commission_pct_per_side)
        comm = comm_in + commission_usd(lots, ex.price, cs, costs.commission_pct_per_side)
        net = gross - comm
        floating_min = min(entry.direction * (ex.worst_price - entry_price) * lots * cs - comm_in, net)
        balance_before = balance
        balance += net
        res.trades.append({
            "date": day.date, "direction": "LONG" if entry.direction > 0 else "SHORT",
            "signal_time_utc": pd.Timestamp(entry.signal_time_ns, tz="UTC"),
            "entry_time_utc": pd.Timestamp(fill_ns, tz="UTC"), "entry_price": entry_price,
            "entry_bid": bid, "spread_at_entry": spread, "spread_estimated": bool(day.m1_est[min(m1_start, len(day.m1_est) - 1)]),
            "box_high": box.high, "box_low": box.low, "stop": stop, "target": target,
            "stop_distance": r_dist, "lots": lots,
            "exit_time_utc": pd.Timestamp(ex.time_ns, tz="UTC"), "exit_price": ex.price, "exit_reason": ex.reason,
            "r_multiple": entry.direction * (ex.price - entry_price) / r_dist,
            "gross_pnl": gross, "commission": comm, "net_pnl": net,
            "floating_min": floating_min, "balance_before": balance_before, "balance_after": balance,
            "ftmo_flagged_exit": events.within(ex.time_ns, 2),
        })
        # our kill switch (spec §4): equity 6% below its peak -> stop the strategy
        if peak - (balance_before + floating_min) >= acct.kill_switch_dd or peak - balance >= acct.kill_switch_dd:
            killed = True
            res.kill_switch_date = day.date
        peak = max(peak, balance)
    return res


def _london_ns(day, minute_of_day):
    t = pd.Timestamp(day.date).tz_localize(LONDON) + pd.Timedelta(minutes=int(minute_of_day))
    return int(t.tz_convert("UTC").value)


def trades_frame(res):
    return pd.DataFrame(res.trades)
