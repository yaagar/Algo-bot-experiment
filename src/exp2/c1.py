"""C1 — random direction (spec §5, clarified in v1.0).

For every real trade: same entry time, same entry quote and spread, same stop distance,
same exit time — but a random direction. The C1 trade closes at its stop or at the real
trade's exit time, whichever comes first (no profit target). Costs and swap as usual.
Tests whether the strategy's direction calls beat a coin flip.
"""
import numpy as np

from src.exp2.engine import Order, Position, Result


def run_c1(engine, real_trades, seed):
    rng = np.random.default_rng(seed)
    res = Result()
    for t in real_trades.itertuples():
        d = int(rng.choice([-1, 1]))
        spread = t.entry_spread                       # already includes any stress multiplier
        price = t.entry_bid + spread if d > 0 else t.entry_bid
        stop = price - d * t.stop_distance
        order = Order(d, int(t.signal_ns), None)
        pos = Position(order, int(t.entry_ns), price, t.entry_bid, spread, stop, None,
                       engine.risk / (t.stop_distance * engine.cs), forced_ns=int(t.exit_ns))
        ex = engine.walk(pos, int(t.entry_ns), int(t.exit_ns) + 1)
        if ex is None:                                # no M1 bar at/after the exit time
            continue
        engine.close(pos, *ex, res)
    return res
