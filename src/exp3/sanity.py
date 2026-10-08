"""Independent re-computation of Experiment 3's signals and trades (spec §7, E3-1 sanity check).

Written straight from spec §2, sharing NO code with the strategy, indicators or engine:
channels with numpy sliding windows, ATR with its own Wilder loop, and a plain day-by-day
position loop. The engine's trades must match these exactly (times, directions, exit reasons)
and to rounding error (stop levels).
"""
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view


def prior_extreme(x, n, fn):
    """fn (max/min) of the n bars BEFORE each bar; NaN until n earlier bars exist."""
    out = np.full(len(x), np.nan)
    if len(x) > n:
        out[n:] = fn(sliding_window_view(x, n)[:-1], axis=1)
    return out


def wilder_atr(high, low, close, n=20):
    tr = np.empty(len(high))
    tr[0] = high[0] - low[0]
    for i in range(1, len(high)):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
    atr = np.full(len(high), np.nan)
    if len(high) >= n:
        atr[n - 1] = tr[:n].mean()
        for i in range(n, len(high)):
            atr[i] = (atr[i - 1] * (n - 1) + tr[i]) / n
    return atr


def signals(d1):
    """+1 / -1 / 0 per daily bar: close beyond the previous 55-day high / low (needs ATR ready)."""
    h, l, c = d1.high.to_numpy(), d1.low.to_numpy(), d1.close.to_numpy()
    hi55, lo55 = prior_extreme(h, 55, np.max), prior_extreme(l, 55, np.min)
    atr = wilder_atr(h, l, c)
    ready = ~np.isnan(hi55) & ~np.isnan(atr)
    sig = np.where(ready & (c > hi55), 1, np.where(ready & (c < lo55), -1, 0))
    return sig, atr


def exits(d1):
    """Long exit when close < previous 20-day low; short exit when close > previous 20-day high."""
    h, l, c = d1.high.to_numpy(), d1.low.to_numpy(), d1.close.to_numpy()
    lo20, hi20 = prior_extreme(l, 20, np.min), prior_extreme(h, 20, np.max)
    return c < lo20, c > hi20        # NaN comparisons are False


def simulate(d1, h1_t, h1_o, h1_h, h1_l, h1_s, t_open, d1_spread):
    """Day-by-day: enter at next open when flat; exit at next open on the 20-day rule, or at the
    first H1 bar touching the 2 x ATR stop (longs on bid lows, shorts on ask highs)."""
    sig, atr = signals(d1)
    long_exit, short_exit = exits(d1)
    trades, pos, pending, exit_next = [], None, None, False
    n = len(d1)
    for i in range(n):
        if pending is not None:
            d, k = pending
            price = d1.open.iat[i] + (d1_spread[i] if d > 0 else 0.0)
            pos = {"direction": d, "signal_bar": k, "entry_ns": int(t_open[i]), "entry_price": price,
                   "stop": price - d * 2 * atr[k]}
            pending = None
        if pos is not None and exit_next:
            trades.append({**pos, "exit_ns": int(t_open[i]), "exit_reason": "exit signal"})
            pos, exit_next = None, False
        if pos is not None:
            end = t_open[i + 1] if i + 1 < n else np.iinfo(np.int64).max
            a, b = np.searchsorted(h1_t, t_open[i]), np.searchsorted(h1_t, end)
            if pos["direction"] > 0:
                hit = np.flatnonzero(h1_l[a:b] <= pos["stop"])
            else:
                hit = np.flatnonzero(h1_h[a:b] + h1_s[a:b] >= pos["stop"])
            if len(hit):
                trades.append({**pos, "exit_ns": int(h1_t[a + hit[0]]), "exit_reason": "stop"})
                pos = None
        if pos is not None:
            if (long_exit[i] if pos["direction"] > 0 else short_exit[i]):
                exit_next = True
        elif sig[i] != 0:
            pending = (int(sig[i]), i)
    if pos is not None:
        trades.append({**pos, "exit_ns": int(h1_t[-1]), "exit_reason": "end of data"})
    return trades, sig


def compare(engine_trades, indep_trades, tol):
    """Number of trades whose entry, direction, exit and reason all match, plus the worst stop gap."""
    same, worst = 0, 0.0
    for e, x in zip(engine_trades.itertuples(), indep_trades):
        d = 1 if e.direction == "LONG" else -1
        if (e.entry_ns, d, e.exit_ns, e.exit_reason) == (x["entry_ns"], x["direction"], x["exit_ns"], x["exit_reason"]):
            same += 1
        worst = max(worst, abs(e.stop - x["stop"]))
    return same, worst, worst <= tol
