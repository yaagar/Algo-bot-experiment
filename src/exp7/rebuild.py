"""Experiment 7 independent rebuild (E7-1 check). Written from the spec text; imports nothing from
src/exp7/pattern.py, system.py, controls.py or any engine. It re-derives M15 bars, indicators,
setups, the one-position rule, entries, stops and 2R targets with its own (slower, loop-based) code.

Exits are worked out only to know when the bot is flat again (one position at a time); no exit
price, P&L or R is produced. The result must match the engine trade list exactly:
entry time, side, stop and target of every trade.

Deliberate differences from the main code (so shared mistakes can't hide): pandas resample for
M15, Wilder ATR seeded with a simple average, t-stat via least squares, explicit loops.
"""
import bisect
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

NY = ZoneInfo("America/New_York")
LON = ZoneInfo("Europe/London")
MIN15 = 15 * 60 * 10**9


def ns(ts):
    return int(pd.Timestamp(ts).value)


def m15_bars(m1):
    r = m1.set_index("time_utc")[["open", "high", "low", "close"]].resample("15min", label="left", closed="left")
    out = pd.DataFrame({"open": r.open.first(), "high": r.high.max(), "low": r.low.min(), "close": r.close.last()})
    return out.dropna().reset_index()


def wilder_atr_sma_seed(h, l, c, n):
    tr = [h[0] - l[0]] + [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(1, len(h))]
    out = [float("nan")] * len(h)
    if len(h) < n:
        return out
    out[n - 1] = sum(tr[:n]) / n
    for i in range(n, len(h)):
        out[i] = (out[i - 1] * (n - 1) + tr[i]) / n
    return out


def tstat_lstsq(closes):
    n = len(closes)
    X = np.column_stack([np.ones(n), np.arange(n)])
    coef, res, *_ = np.linalg.lstsq(X, closes, rcond=None)
    resid = closes - X @ coef
    s2 = resid @ resid / (n - 2)
    var_slope = s2 * np.linalg.inv(X.T @ X)[1, 1]
    return coef[1] / np.sqrt(var_slope) if var_slope > 0 else float("nan")


def server_hour(t_utc):
    ny = t_utc.astimezone(NY).replace(tzinfo=None)
    return (ny + timedelta(hours=7)).hour


def h1_state(h1, cfg):
    """Per H1 bar (at its close): trend (+1/-1/0), t-stat, ATR."""
    H, L, C = (h1[k].tolist() for k in ("high", "low", "close"))
    n = len(H)
    atr = wilder_atr_sma_seed(H, L, C, cfg["atr_bars"])
    trend, tst = [0] * n, [float("nan")] * n
    highs, lows = [], []
    for k in range(n):
        i = k - 2                                    # bar i becomes a confirmed swing at bar k's close
        if i >= 2:
            if H[i] > max(H[i - 2], H[i - 1]) and H[i] >= max(H[i + 1], H[i + 2]):
                highs.append(H[i])
            if L[i] < min(L[i - 2], L[i - 1]) and L[i] <= min(L[i + 1], L[i + 2]):
                lows.append(L[i])
        if len(highs) >= 3 and len(lows) >= 3:
            a, b = highs[-3:], lows[-3:]
            if a[0] < a[1] < a[2] and b[0] < b[1] < b[2]:
                trend[k] = 1
            elif a[0] > a[1] > a[2] and b[0] > b[1] > b[2]:
                trend[k] = -1
        if k >= cfg["tstat_bars"] - 1:
            tst[k] = tstat_lstsq(np.array(C[k - cfg["tstat_bars"] + 1:k + 1], float))
    close_ns = [ns(t) + 3600 * 10**9 for t in h1.time_utc]
    return close_ns, trend, tst, atr


def setups_and_trades(m1, h1, event_times, spread_frac_path, cfg):
    """Engine-independent trade list: DataFrame(entry_ns, direction, stop, target)."""
    frac = [float("nan") if x is None else x
            for x in json.loads(open(spread_frac_path, encoding="utf-8").read())["p75_frac_by_server_hour"]]
    ev = sorted(ns(t) for t in event_times)
    b = m15_bars(m1)
    T = [ns(t) for t in b.time_utc]
    O, H, L, C = (b[k].tolist() for k in ("open", "high", "low", "close"))
    n = len(T)
    atr15 = wilder_atr_sma_seed(H, L, C, cfg["atr_bars"])
    h1_close, trend, tst, atr1 = h1_state(h1, cfg)
    nb, step, buf = cfg["box_min_bars"], cfg["round_level"], cfg["round_buffer"]
    t0, t1 = (int(x[:2]) * 60 + int(x[3:]) for x in cfg["entry_hours_london"])
    xh, xm = (int(x) for x in cfg["time_exit_london"].split(":"))

    m1t = [ns(t) for t in m1.time_utc]
    m1o, m1h, m1l = m1.open.tolist(), m1.high.tolist(), m1.low.tolist()
    m1_hour_frac = [frac[server_hour(t.to_pydatetime())] for t in m1.time_utc]

    def chop(i):
        if i < 14:
            return float("nan")
        trs = [max(H[j] - L[j], abs(H[j] - C[j - 1]), abs(L[j] - C[j - 1])) for j in range(i - 13, i + 1)]
        return 100 * np.log10(sum(trs) / (max(H[i - 13:i + 1]) - min(L[i - 13:i + 1]))) / np.log10(14)

    def news(t):
        j = bisect.bisect_left(ev, t - 5 * 60 * 10**9)
        return j < len(ev) and ev[j] <= t + 5 * 60 * 10**9

    def flat_again_ns(fill_i, d, entry, stop, target, exit_ns):
        """When the trade is over: first M1 bar (from the fill bar) touching stop/target, else the time exit."""
        k = bisect.bisect_left(m1t, T[fill_i])
        while k < len(m1t) and m1t[k] < exit_ns:
            s = m1_hour_frac[k] * m1o[k]
            if d > 0 and (m1l[k] <= stop or m1h[k] >= target):
                return m1t[k]
            if d < 0 and (m1h[k] + s >= stop or m1l[k] + s <= target):
                return m1t[k]
            k += 1
        return exit_ns

    trades, busy_until = [], -1
    for i in range(nb, n - 1):
        close_t = T[i] + MIN15
        k = bisect.bisect_right(h1_close, close_t) - 1
        if k < 0 or atr1[k] != atr1[k] or tst[k] != tst[k]:
            continue
        rng = cfg["box_max_range_atr_h1"] * atr1[k]
        s, hi, lo = i, None, None                    # grow the box backwards from bar i-1
        while s - 1 >= 0:
            j = s - 1
            nh = H[j] if hi is None else max(hi, H[j])
            nl = L[j] if lo is None else min(lo, L[j])
            if nh - nl > rng:
                break
            hi, lo, s = nh, nl, j
            gap_before_j = j == 0 or T[j] - T[j - 1] > MIN15 + 30 * 60 * 10**9
            if gap_before_j:
                break                                # a gap > 30 min before bar j: the run can't go further
        if i - s < nb:
            continue
        d = 1 if C[i] > hi else -1 if C[i] < lo else 0
        if d == 0 or trend[k] != d or not d * tst[k] >= cfg["tstat_min"]:
            continue
        fb = 0                                       # false breaks inside the box
        for q in range(s + nb, i):
            ph, pl = max(H[s:q]), min(L[s:q])
            if not pl <= C[q] <= ph and any(pl <= C[r] <= ph for r in range(q + 1, i)):
                fb += 1
        if fb > cfg["max_false_breaks"] or not chop(i) <= cfg["chop_max"] or hi - lo > cfg["box_max_height_atr_m15"] * atr15[i]:
            continue
        f = i + 1
        fill_utc = pd.Timestamp(T[f], tz="UTC").to_pydatetime()
        spread = frac[server_hour(fill_utc)] * O[f]
        entry = O[f] + (spread if d > 0 else 0.0)
        mid = (hi + lo) / 2
        stop = min(mid, entry - atr15[i]) if d > 0 else max(mid, entry + atr15[i])
        lvl = round(stop / step) * step
        if abs(stop - lvl) <= buf:
            stop = lvl - buf if d > 0 else lvl + buf
        dist = abs(entry - stop)
        if not spread <= cfg["cost_guard_max_spread_frac"] * dist or news(T[f]):
            continue
        lon = fill_utc.astimezone(LON)
        if not t0 <= lon.hour * 60 + lon.minute < t1:
            continue
        if busy_until >= T[i + 1]:                   # still in a trade at this decision (exit not before next bar)
            continue
        exit_ns = int(datetime(lon.year, lon.month, lon.day, xh, xm, tzinfo=LON).astimezone(timezone.utc).timestamp()) * 10**9
        target = entry + d * cfg["target_r"] * dist
        trades.append((T[f], d, stop, target))
        busy_until = flat_again_ns(f, d, entry, stop, target, exit_ns)
    return pd.DataFrame(trades, columns=["entry_ns", "direction", "stop", "target"])
