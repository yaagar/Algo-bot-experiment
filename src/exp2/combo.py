"""Combination engine (spec §6 + Change Log): several strategies, ONE account, netting.

All strategies' events go on one timeline. The account holds one gold position at a time:
it is "busy" from a strategy's signal until that position closes (including the wait for
the next-bar fill). A signal from any strategy while busy is skipped and counted.
Events at the same timestamp: exits first, then fills, then new signals; ties between
strategies follow the priority order given (S1, S3, S5).

Uses Engine's own fill / stop / target / cost / swap code unchanged, so a combination of
ONE strategy reproduces that strategy's standalone run exactly (tested).
"""
import heapq
import itertools

import numpy as np

from src.exp2.engine import LONG_BREAK_NS, Result

EXIT, FILL, SIGNAL = 0, 1, 2


def friday_deadline_unreachable(eng, pos, t):
    """Same rule as the single-strategy engine: if the market won't trade again before the Friday
    20:00 London deadline (holiday early close, e.g. Good Friday), exit at the last price before t.
    Holiday closures are published in advance, so this uses no unknown future prices."""
    if not pos.forced_is_friday or pos.forced_ns < t:
        return None
    m = eng.m1
    j = int(np.searchsorted(m.t, t, "left"))
    if 0 < j < len(m.t) and m.t[j] - pos.forced_ns > LONG_BREAK_NS:      # (end of data is not a market close)
        k = j - 1
        price = m.c[k] if pos.order.direction > 0 else m.c[k] + m.s[k] * eng.costs.spread_mult
        return int(m.t[k]), float(price), "friday close (market closed early)"
    return None


def run_combo(eng, strategies):
    """strategies: ordered dict name -> strategy object (order = tie priority)."""
    res = Result()
    skipped = {n: 0 for n in strategies}
    heap, seq = [], itertools.count()
    for prio, (name, s) in enumerate(strategies.items()):
        if hasattr(s, "schedule"):
            for order, entry_ns in s.schedule():
                heapq.heappush(heap, (entry_ns, SIGNAL, prio, next(seq), "timed", name, (order, entry_ns)))
        else:
            for i, t in enumerate(s.bars.t_close.to_numpy()):
                heapq.heappush(heap, (int(t), SIGNAL, prio, next(seq), "close", name, i))
    prio_of = {n: k for k, n in enumerate(strategies)}
    pos, owner, busy, walked = None, None, None, None

    def close(ex):
        nonlocal pos, owner, busy
        eng.close(pos, *ex, res)
        res.trades[-1]["strategy"] = owner
        pos, owner, busy = None, None, None

    while heap:
        t, phase, prio, _, kind, name, payload = heapq.heappop(heap)
        if pos is not None and t > walked:                       # stops, targets, forced exits up to t
            ex = eng.walk(pos, walked, t)
            if ex:
                close(ex)
            else:
                walked = t
                ex = friday_deadline_unreachable(eng, pos, t)
                if ex:
                    close(ex)
        s = strategies[name]

        if kind == "exit_open":
            if pos is not None and owner == name and pos is payload:
                b = s.bars
                i = payload.exit_bar
                if pos.forced_ns <= t:                         # a forced exit at the same time comes first
                    close(eng.walk(pos, t, t + 1))
                else:
                    close(eng.exit_at_open(pos, int(b.t_open[i]), b.open[i], b.spread[i]))
        elif kind == "fill":
            order, i = payload
            b = s.bars
            pos = eng.open_position(order, int(b.t_open[i]), b.open[i], b.spread[i], res)
            if pos is None:
                busy = None
            else:
                owner, walked = name, int(b.t_open[i])
        elif kind == "timed":
            order, entry_ns = payload
            res.decisions.append((order.signal_ns, "signal", (order.direction,), order.signal_ns))
            if order.info.get("skip"):
                eng._block(res, order.signal_ns, order.info["skip"])
            elif busy is not None:
                skipped[name] += 1
            else:
                m = eng.m1
                k = int(np.searchsorted(m.t, entry_ns, "left"))
                if k >= len(m.t) or m.t[k] - entry_ns > 60 * 60 * 10**9:
                    eng._block(res, entry_ns, "no price within 60 min of entry time")
                else:
                    pos = eng.open_position(order, int(m.t[k]), m.o[k], m.s[k], res)
                    if pos is not None:
                        owner, busy, walked = name, name, int(m.t[k])
        else:                                                   # a bar of strategy `name` closed
            i, b = payload, s.bars
            has_next = i + 1 < len(b)
            if pos is not None and owner == name:
                if not pos.exit_next_open and s.exit_signal(i, pos):
                    pos.exit_next_open = True
                    if has_next:
                        pos.exit_bar = i + 1
                        heapq.heappush(heap, (int(b.t_open[i + 1]), EXIT, prio_of[name], next(seq), "exit_open", name, pos))
                if s.signal(i) is not None:
                    skipped[name] += 1
            elif busy is not None:
                if s.signal(i) is not None:
                    skipped[name] += 1
            else:
                order = s.signal(i)
                if order is not None and has_next:
                    res.decisions.append((t, "signal", (order.direction,), t))
                    busy = name
                    heapq.heappush(heap, (int(b.t_open[i + 1]), FILL, prio_of[name], next(seq), "fill", name, (order, i + 1)))

    if pos is not None:                                          # data ended with a trade open
        ex = eng.walk(pos, walked, int(eng.m1.t[-1]) + 1) or eng.end_of_data(pos)
        close(ex)
    res.skipped_by_strategy = skipped
    return res
