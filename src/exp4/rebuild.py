"""Independent rebuild of Experiment 4's signals, gates and forecast (spec §7, leak safety).

Written straight from the spec and Change Log v1.1, sharing NO code with src/exp4/signals.py,
src/exp4/data.py or the Experiment 2 engine/indicators: plain Python loops, its own bar building
(local-clock flooring with zoneinfo instead of UTC offsets), its own SMA / Wilder ATR, the
statistics module for σ and medians. Input = the same raw price frames (M1, and gold's broker H1).
Output: one row per H1 bar close with the four scores, gates and F. The runner checks it matches
the engine's table on every bar.
"""
import math
import statistics
from bisect import bisect_left, bisect_right
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd

NY = ZoneInfo("America/New_York")
UTC = timezone.utc
NS = 10**9


def ns_list(times):
    """UTC times -> integer nanoseconds (whatever unit the file stored them in)."""
    return [int(x) for x in pd.Series(times).dt.tz_convert(None).astype("datetime64[ns]").astype("int64")]


def local(t_ns, tz):
    return datetime.fromtimestamp(t_ns // NS, tz)          # whole seconds: no float rounding noise


def to_ns(dt):
    return int(round(dt.timestamp())) * NS


def minutes(text):
    h, m = text.split(":")
    return int(h) * 60 + int(m)


def build_h1(m1, h1_broker, offset_30):
    """List of bars (t_open, t_close, high, low, close). US500: :30 New York bars from M1."""
    if not offset_30:
        t = ns_list(h1_broker.time_utc)
        return [(t[i], t[i] + 3600 * NS, h, l, c) for i, (h, l, c) in
                enumerate(zip(h1_broker.high.tolist(), h1_broker.low.tolist(), h1_broker.close.tolist()))]
    bars, cur = [], None
    for t, h, l, c in zip(ns_list(m1.time_utc), m1.high.tolist(), m1.low.tolist(), m1.close.tolist()):
        ny = local(t, NY)
        start = ny.replace(minute=30, second=0) if ny.minute >= 30 else (ny - timedelta(hours=1)).replace(minute=30, second=0)
        key = to_ns(start)
        if cur is None or cur[0] != key:
            if cur:
                bars.append(tuple(cur))
            cur = [key, key + 3600 * NS, h, l, c]
        else:
            cur[2], cur[3], cur[4] = max(cur[2], h), min(cur[3], l), c
    bars.append(tuple(cur))
    return bars


def build_h4(times_ns, highs, lows, closes):
    """Broker-server 4-hour blocks (server = New York + 7 h); close time = block start + 4 h."""
    out, cur = [], None
    for t, h, l, c in zip(times_ns, highs, lows, closes):
        server = local(t, NY).replace(tzinfo=None) + timedelta(hours=7)
        block = server.replace(hour=server.hour - server.hour % 4, minute=0, second=0)
        start_ns = to_ns((block - timedelta(hours=7)).replace(tzinfo=NY))
        if cur is None or cur[0] != start_ns:
            if cur:
                out.append(tuple(cur))
            cur = [start_ns, h, l, c]
        else:
            cur[1], cur[2], cur[3] = max(cur[1], h), min(cur[2], l), c
    out.append(tuple(cur))
    return [(s + 4 * 3600 * NS, h, l, c) for s, h, l, c in out]       # (t_close, high, low, close)


def sma_list(x, n):
    return [sum(x[i - n + 1:i + 1]) / n if i >= n - 1 else math.nan for i in range(len(x))]


def wilder_atr(high, low, close, n):
    tr = [high[0] - low[0]] + [max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
                               for i in range(1, len(high))]
    out = [math.nan] * len(tr)
    if len(tr) >= n:
        out[n - 1] = sum(tr[:n]) / n
        for i in range(n, len(tr)):
            out[i] = (out[i - 1] * (n - 1) + tr[i]) / n
    return out


class Day:
    def __init__(self, d):
        self.date, self.bars = d, []


def rebuild(mcfg, cfg, m1, h1_broker=None):
    tz = ZoneInfo(mcfg["tz"])
    start = minutes(mcfg["day_start"])
    sc, gc = cfg["signals"], cfg["gates"]
    use_gates = cfg.get("use_gates", True)
    use = set(cfg.get("use_signals", ["A", "B", "C", "D"]))

    m1_t, m1_h, m1_l, m1_c = ns_list(m1.time_utc), m1.high.tolist(), m1.low.tolist(), m1.close.tolist()
    bars = build_h1(m1, h1_broker, mcfg["h1_source"] != "broker")
    if mcfg["h1_source"] == "broker":
        h4 = build_h4(ns_list(h1_broker.time_utc), h1_broker.high.tolist(), h1_broker.low.tolist(), h1_broker.close.tolist())
    else:
        h4 = build_h4(m1_t, m1_h, m1_l, m1_c)

    def since_start(text):
        return (minutes(text) - start) % 1440

    def utc_at(d, text):
        mins = minutes(text)
        day = d - timedelta(days=1) if (start > 0 and mins >= start) else d
        return to_ns(datetime(day.year, day.month, day.day, mins // 60, mins % 60, tzinfo=tz))

    def last_price_before(t):
        j = bisect_left(m1_t, t) - 1
        return m1_c[j] if j >= 0 else math.nan

    # trading day and minutes-since-start of every bar close
    days, by_date, rows = [], {}, []
    for i, (t_open, t_close, h, l, c) in enumerate(bars):
        lc = local(t_close, tz)
        mins = (lc.hour * 60 + lc.minute - start) % 1440 or 1440
        just_before = local(t_close - NS, tz)
        d = just_before.date() + (timedelta(days=1) if start > 0 and just_before.hour * 60 + just_before.minute >= start else timedelta(0))
        if d.weekday() >= 5:
            d = None
        if d is not None and d not in by_date:
            by_date[d] = Day(d)
            days.append(by_date[d])
        if d is not None:
            by_date[d].bars.append(i)
        rows.append({"t_close": t_close, "day": d, "m": mins, "h": h, "l": l, "c": c})
    k_of = {day.date: k for k, day in enumerate(days)}

    closes = [r["c"] for r in rows]
    atr14 = wilder_atr([r["h"] for r in rows], [r["l"] for r in rows], closes, sc["d_atr"])
    sma_h1 = sma_list(closes, sc["d_sma"])
    h4_close_t = [b[0] for b in h4]
    h4_sma = sma_list([b[3] for b in h4], sc["c_sma"])
    h4_atr = wilder_atr([b[1] for b in h4], [b[2] for b in h4], [b[3] for b in h4], sc["c_atr"])

    m_range_end, m_flat = since_start(mcfg["range"]["end"]), since_start(mcfg["flat_by"])
    m_bto = since_start(mcfg["b_to"])
    m_ws, m_we = since_start(mcfg["window"]["start"]), since_start(mcfg["window"]["end"])

    # per-day quantities: range, momentum, daily close
    for k, day in enumerate(days):
        a, b = bisect_left(m1_t, utc_at(day.date, mcfg["range"]["start"])), bisect_left(m1_t, utc_at(day.date, mcfg["range"]["end"]))
        day.hi = max(m1_h[a:b]) if b > a else math.nan
        day.lo = min(m1_l[a:b]) if b > a else math.nan
        day.mom = (last_price_before(utc_at(day.date, mcfg["b_to"])) /
                   last_price_before(utc_at(days[k - 1].date, mcfg["b_from"])) - 1) if k > 0 else math.nan
        day.close = rows[day.bars[-1]]["c"]

    # raw values and activity per bar
    for i, r in enumerate(rows):
        r.update({"A": None, "B": None, "C": None, "D": None})
        if r["day"] is None:
            continue
        day, m = by_date[r["day"]], r["m"]
        if m_range_end <= m <= m_flat and day.hi - day.lo > 0:
            height = day.hi - day.lo
            r["A"] = (r["c"] - day.hi) / height if r["c"] > day.hi else (r["c"] - day.lo) / height if r["c"] < day.lo else 0.0
        if m_bto <= m <= m_flat and not math.isnan(day.mom):
            r["B"] = day.mom
        j = bisect_right(h4_close_t, r["t_close"]) - 1
        if j >= 0 and not math.isnan(h4_sma[j]) and not math.isnan(h4_atr[j]):
            r["C"] = (r["c"] - h4_sma[j]) / h4_atr[j]
        if not math.isnan(sma_h1[i]) and not math.isnan(atr14[i]):
            r["D"] = -(r["c"] - sma_h1[i]) / atr14[i]

    # σ per day from the previous 60 trading days' samples (B: one per day)
    n = sc["sigma_days"]
    samples = {s: [[rows[i][s] for i in day.bars if rows[i][s] is not None] for day in days] for s in "ACD"}
    samples["B"] = [[day.mom] if not math.isnan(day.mom) else [] for day in days]
    sigma = {s: [statistics.stdev(sum(samples[s][k - n:k], [])) if k >= n and len(sum(samples[s][k - n:k], [])) > 1
                 else math.nan for k in range(len(days))] for s in "ABCD"}

    # efficiency from completed days
    ne = gc["efficiency_days"]
    eff = []
    for k in range(len(days)):
        if k < ne + 1:
            eff.append(math.nan)
            continue
        c = [days[x].close for x in range(k - 1 - ne, k)]
        path = sum(abs(c[x] - c[x - 1]) for x in range(1, len(c)))
        eff.append(abs(c[-1] - c[0]) / path if path > 0 else math.nan)

    # shock: average H1 range so far today vs median of the same at the same time over 60 days
    so_far = {}
    for day in days:
        total, pts = 0.0, []
        for cnt, i in enumerate(day.bars, 1):
            total += rows[i]["h"] - rows[i]["l"]
            pts.append((rows[i]["m"], total / cnt))
            so_far[i] = total / cnt
        day.curve_m, day.curve_v = [p[0] for p in pts], [p[1] for p in pts]
    ns = gc["shock_days"]

    out = []
    for i, r in enumerate(rows):
        rec = {"t_close": r["t_close"], "in_day": r["day"] is not None}
        if r["day"] is None:
            rec.update({f"score_{s}": 0.0 for s in "ABCD"}, F=0.0, efficiency=math.nan, shock_ratio=math.nan, in_window=False)
            out.append(rec)
            continue
        k = k_of[r["day"]]
        e = eff[k]
        trending, ranging = (e >= gc["efficiency_trend"]), (e < gc["efficiency_trend"])    # NaN: both False
        for s in "ABCD":
            sg = sigma[s][k]
            v = r[s]
            score = max(-1.0, min(1.0, v / (sc["sigma_mult"] * sg))) if (v is not None and sg > 0) else 0.0
            if s not in use or (use_gates and not (ranging if s == "D" else trending)):
                score = 0.0
            rec[f"score_{s}"] = score
        rec["F"] = (rec["score_A"] + rec["score_B"] + rec["score_C"] + rec["score_D"]) / 4
        ratio = math.nan
        if k >= ns:
            vals = []
            for day in days[k - ns:k]:
                j = bisect_right(day.curve_m, r["m"]) - 1
                if j >= 0:
                    vals.append(day.curve_v[j])
            if vals:
                ratio = so_far[i] / statistics.median(vals)
        rec.update(efficiency=e, shock_ratio=ratio, in_window=m_ws <= r["m"] < m_we)
        out.append(rec)
    return pd.DataFrame(out)


def compare(engine_table, rebuilt, tol=1e-9):
    """Every bar must match: same bar closes, scores, F, efficiency, shock ratio, window flag."""
    e = engine_table.reset_index(drop=True)
    r = rebuilt.reset_index(drop=True)
    report = {"bars_engine": len(e), "bars_rebuild": len(r)}
    if len(e) != len(r) or not (e.t_close.to_numpy() == r.t_close.to_numpy()).all():
        report["match"] = False
        report["problem"] = "different bar sets"
        return report
    worst = {}
    for col in ["score_A", "score_B", "score_C", "score_D", "F", "efficiency", "shock_ratio"]:
        a, b = e[col].to_numpy(dtype=float), r[col].to_numpy(dtype=float)
        both_nan = (pd.isna(a) & pd.isna(b))
        diff = abs(a - b)
        diff[both_nan] = 0.0
        diff[pd.isna(diff)] = math.inf                     # NaN on one side only
        worst[col] = float(diff.max())
    report["max_abs_diff"] = worst
    report["window_flag_mismatches"] = int((e.in_window.to_numpy() != r.in_window.to_numpy()).sum())
    report["match"] = all(v <= tol for v in worst.values()) and report["window_flag_mismatches"] == 0
    return report
