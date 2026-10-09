"""Experiment 7 pattern definitions (spec §2-§3): trend -> tight box -> breakout on gold.

Plain-English flow for one M15 bar b (decided at its close, using only bars closed by then):
  1. Box: walk back from the bar before b while the bars' combined high-low stays <= 1.5 x ATR(14, H1).
     A run of >= 6 bars is the box. Without one, the 6 bars before b act as a stand-in edge so a
     "break" can still be seen and counted as blocked by "no box".
  2. Candidate: b closes above the edge (up) or below it (down). Everything else is ignored.
  3. Checks: H1 trend structure (3 rising swing highs and lows), t-stat of the 48-bar slope,
     box present, false breaks inside the box, choppiness, box height, cost guard, news, hours.
  4. If all pass, the setup's entry (next M15 open + spread), stop and 2R target are planned.
Nothing after the fill is computed here: no exits, no P&L (src/exp7/system.py trades the setups).
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

M15 = pd.Timedelta(minutes=15)
H1 = pd.Timedelta(hours=1)

# Block reasons in reporting order (a setup's "first" reason is the first that fails in this order).
REASONS = ["no_trend", "weak_tstat", "no_box", "false_breaks", "choppy", "box_too_tall",
           "cost_guard", "news", "hours"]


# --- Bars and indicators ------------------------------------------------------------------

def m15_from_m1(m1):
    """M15 bars (UTC, labelled by open time) from M1 bars; only 15-min blocks that have M1 data."""
    block = m1.time_utc.dt.floor("15min")
    g = m1.groupby(block, sort=True)
    out = pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(), "close": g.close.last()})
    return out.rename_axis("time_utc").reset_index()


def true_range(high, low, close):
    prev = np.r_[np.nan, close[:-1]]
    tr = np.fmax(high - low, np.fmax(np.abs(high - prev), np.abs(low - prev)))
    tr[0] = high[0] - low[0]
    return tr


def wilder_atr(high, low, close, n):
    """ATR with Wilder smoothing (alpha = 1/n); NaN until n bars exist."""
    tr = pd.Series(true_range(high, low, close))
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean().to_numpy()


def choppiness(high, low, close, n):
    """Choppiness Index = 100 x log10(sum of n true ranges / (n-bar high - n-bar low)) / log10(n)."""
    tr = pd.Series(true_range(high, low, close)).rolling(n).sum()
    span = pd.Series(high).rolling(n).max() - pd.Series(low).rolling(n).min()
    return (100 * np.log10(tr / span) / np.log10(n)).to_numpy()


def slope_tstat(close, n):
    """t-statistic of the OLS slope of the last n closes against 0..n-1 (NaN until n bars)."""
    out = np.full(len(close), np.nan)
    if len(close) < n:
        return out
    y = np.lib.stride_tricks.sliding_window_view(close, n)
    x = np.arange(n) - (n - 1) / 2
    sxx = (x ** 2).sum()
    slope = (y - y.mean(axis=1, keepdims=True)) @ x / sxx
    resid = y - y.mean(axis=1, keepdims=True) - slope[:, None] * x
    se = np.sqrt((resid ** 2).sum(axis=1) / (n - 2) / sxx)
    with np.errstate(divide="ignore", invalid="ignore"):
        out[n - 1:] = slope / se
    return out


def swing_points(high, low):
    """Swing high at i: high[i] above the 2 bars before and not below the 2 after (lows mirrored).

    Ties go to the earlier bar, so a flat double top gives one swing, not two.
    A swing at i is only known at the close of bar i + 2.
    """
    n = len(high)
    sh, sl = np.zeros(n, bool), np.zeros(n, bool)
    for i in range(2, n - 2):
        sh[i] = high[i] > high[i - 1] and high[i] > high[i - 2] and high[i] >= high[i + 1] and high[i] >= high[i + 2]
        sl[i] = low[i] < low[i - 1] and low[i] < low[i - 2] and low[i] <= low[i + 1] and low[i] <= low[i + 2]
    return sh, sl


def trend_structure(high, low, swings=3):
    """Per H1 bar k (at its close): +1 if the last `swings` confirmed swing highs AND lows are
    strictly rising, -1 if both strictly falling, else 0."""
    sh, sl = swing_points(high, low)
    out = np.zeros(len(high), int)
    highs, lows = [], []
    for k in range(len(high)):
        i = k - 2                                   # the swing confirmed at this bar's close
        if i >= 0:
            if sh[i]:
                highs.append(high[i])
            if sl[i]:
                lows.append(low[i])
        if len(highs) >= swings and len(lows) >= swings:
            h, lo = np.diff(highs[-swings:]), np.diff(lows[-swings:])
            out[k] = 1 if (h > 0).all() and (lo > 0).all() else -1 if (h < 0).all() and (lo < 0).all() else 0
    return out


# --- H1 context ------------------------------------------------------------------------------

@dataclass
class H1Context:
    close_ns: np.ndarray     # close time of each H1 bar
    trend: np.ndarray        # +1 / -1 / 0
    tstat: np.ndarray
    atr: np.ndarray

    def last_closed(self, t_ns):
        """Index of the last H1 bar closed at or before t (-1 if none)."""
        return int(np.searchsorted(self.close_ns, t_ns, side="right")) - 1


def h1_context(h1, cfg):
    h, lo, c = (h1[k].to_numpy(float) for k in ("high", "low", "close"))
    close_ns = (h1.time_utc + H1).dt.tz_convert(None).to_numpy().astype("datetime64[ns]").astype(np.int64)
    return H1Context(close_ns, trend_structure(h, lo, cfg["trend_swings"]),
                     slope_tstat(c, cfg["tstat_bars"]), wilder_atr(h, lo, c, cfg["atr_bars"]))


# --- Boxes -----------------------------------------------------------------------------------

def run_start(high, low, end, max_range, gap_before):
    """Earliest bar s such that bars s..end have combined high-low <= max_range and no gap between
    them (end+1 if even bar `end` alone is wider). gap_before[i]: a > 30 min gap precedes bar i."""
    hi, lo = high[end], low[end]
    if not hi - lo <= max_range:
        return end + 1
    s = end
    while s > 0 and not gap_before[s]:
        nh, nl = max(hi, high[s - 1]), min(lo, low[s - 1])
        if nh - nl > max_range:
            break
        hi, lo, s = nh, nl, s - 1
    return s


def false_breaks(high, low, close, s, e, min_bars):
    """Bars inside box s..e that closed outside the box edge formed by the earlier box bars
    (once at least `min_bars` earlier bars exist) and a later box bar closed back inside it."""
    count = 0
    for k in range(s + min_bars, e + 1):
        hi, lo = high[s:k].max(), low[s:k].min()
        if lo <= close[k] <= hi:
            continue
        back = close[k + 1:e + 1]
        if ((back >= lo) & (back <= hi)).any():
            count += 1
    return count


def place_stop(entry, mid, atr_m15, direction, cfg):
    """Box midpoint, but at least 1 x ATR(14, M15) from entry; then pushed $0.50 beyond a round
    $10 level if it lands within $0.50 of one."""
    min_dist = cfg["stop_min_atr_m15"] * atr_m15
    stop = min(mid, entry - min_dist) if direction > 0 else max(mid, entry + min_dist)
    step, buf = cfg["round_level"], cfg["round_buffer"]
    level = round(stop / step) * step
    if abs(stop - level) <= buf:
        stop = level - buf if direction > 0 else level + buf
    return stop


# --- Scan ------------------------------------------------------------------------------------

def _to_ns(times):
    return pd.Series(times).dt.tz_convert(None).to_numpy().astype("datetime64[ns]").astype(np.int64)


def scan(m15, ctx, events, spread_frac_by_server_hour, cfg):
    """Every candidate breakout with its block flags, plus the planned entry/stop/2R target and the
    M2 inputs. `bar` = index of the breakout (decision) bar in m15; the fill is bar + 1.

    m15: M15 bars (UTC, open-time labels, bid prices). ctx: H1Context. events: src.backtest.Events.
    spread_frac_by_server_hour: 24 tick-p75 spreads as fractions of price. Returns one row per candidate.
    """
    from src.timeutils import LONDON, utc_to_server

    h, lo, c, o = (m15[k].to_numpy(float) for k in ("high", "low", "close", "open"))
    n = len(m15)
    open_ns = _to_ns(m15.time_utc)
    close_ns = open_ns + M15.value
    gap_before = np.r_[False, np.diff(open_ns) > M15.value + cfg["box_max_gap_min"] * 60 * 10**9]
    london = m15.time_utc.dt.tz_convert(LONDON)
    london_min = (london.dt.hour * 60 + london.dt.minute).to_numpy()
    server_hour = utc_to_server(m15.time_utc).dt.hour.to_numpy()
    atr_m15 = wilder_atr(h, lo, c, cfg["atr_bars"])
    chop = choppiness(h, lo, c, cfg["chop_bars"])
    t0, t1 = (int(x[:2]) * 60 + int(x[3:]) for x in cfg["entry_hours_london"])
    nb = cfg["box_min_bars"]

    h1_idx = np.searchsorted(ctx.close_ns, close_ns, side="right") - 1      # last H1 bar closed by bar close
    max_range = np.where(h1_idx >= 0, cfg["box_max_range_atr_h1"] * ctx.atr[np.maximum(h1_idx, 0)], np.nan)

    rows = []
    for b in range(nb, n - 1):
        k = h1_idx[b]
        if k < 0 or not max_range[b] == max_range[b] or not ctx.tstat[k] == ctx.tstat[k]:
            continue                                              # H1 warm-up
        s = run_start(h, lo, b - 1, max_range[b], gap_before)
        has_box = b - s >= nb
        first = s if has_box else b - nb
        edge_hi, edge_lo = h[first:b].max(), lo[first:b].min()
        direction = 1 if c[b] > edge_hi else -1 if c[b] < edge_lo else 0
        if direction == 0:
            continue

        f = b + 1                                                 # fill bar
        spread = spread_frac_by_server_hour[server_hour[f]] * o[f]
        entry = o[f] + (spread if direction > 0 else 0.0)
        flags = dict.fromkeys(REASONS, False)
        flags["no_trend"] = ctx.trend[k] != direction
        flags["weak_tstat"] = not ctx.tstat[k] * direction >= cfg["tstat_min"]
        flags["no_box"] = not has_box
        flags["choppy"] = not chop[b] <= cfg["chop_max"]
        flags["news"] = events.within(open_ns[f], cfg["news_blackout_min"])
        flags["hours"] = not t0 <= london_min[f] < t1
        row = dict(bar=b, time_utc=m15.time_utc.iat[b], fill_time_utc=m15.time_utc.iat[f], direction=direction,
                   spread=spread, entry=entry, box_bars=b - s if has_box else 0, tstat=ctx.tstat[k],
                   atr_h1=ctx.atr[k], atr_m15=atr_m15[b])
        if has_box:
            mid = (edge_hi + edge_lo) / 2
            flags["false_breaks"] = false_breaks(h, lo, c, s, b - 1, nb) > cfg["max_false_breaks"]
            flags["box_too_tall"] = edge_hi - edge_lo > cfg["box_max_height_atr_m15"] * atr_m15[b]
            stop = place_stop(entry, mid, atr_m15[b], direction, cfg)
            stop_dist = abs(entry - stop)
            flags["cost_guard"] = not spread <= cfg["cost_guard_max_spread_frac"] * stop_dist
            row.update(box_high=edge_hi, box_low=edge_lo, box_mid=mid, stop=stop, stop_dist=stop_dist,
                       target=entry + direction * cfg["target_r"] * stop_dist)
        failed = [r for r in REASONS if flags[r]]
        row.update({f"x_{r}": v for r, v in flags.items()}, first_block=failed[0] if failed else "",
                   qualifies=not failed)
        rows.append(row)
    columns = ["bar", "time_utc", "fill_time_utc", "direction", "spread", "entry", "box_bars", "tstat", "atr_h1",
               "atr_m15", "box_high", "box_low", "box_mid", "stop", "stop_dist", "target",
               *(f"x_{r}" for r in REASONS), "first_block", "qualifies"]
    return pd.DataFrame(rows, columns=columns)
