"""Future-scramble leak test (spec §9.2).

Pick a cut time T. Shuffle every bar after T (prices and spreads move to other
timestamps, so the future becomes nonsense). Re-run Bot A. Every decision made
at or before T must be exactly the same as in the normal run — if anything
changed, the strategy was peeking at the future. Repeated for 20 random T.
"""
import numpy as np
import pandas as pd

from src.backtest import bot_a_chooser, build_days, run

VALUE_COLS = ["open", "high", "low", "close", "spread_used", "spread_estimated"]


def scramble_after(bars, cut, rng):
    out = bars.copy()
    after = np.flatnonzero((out.time_utc > cut).to_numpy())
    shuffled = rng.permutation(after)
    out.loc[after, VALUE_COLS] = out.loc[shuffled, VALUE_COLS].to_numpy()
    return out


def decisions_until(res, cut_ns):
    return [d for d in res.decisions if d[0] <= cut_ns]


def run_test(m1, candles, tf_minutes, point, p, costs, acct, events, n_cuts=20, seed=9):
    rng = np.random.default_rng(seed)
    base = run(build_days(m1, candles, point), bot_a_chooser(tf_minutes), p, costs, acct, events)
    t0, t1 = m1.time_utc.min().value, m1.time_utc.max().value
    rows = []
    for _ in range(n_cuts):
        cut = pd.Timestamp(int(rng.integers(t0, t1)), tz="UTC")
        scr = run(build_days(scramble_after(m1, cut, rng), scramble_after(candles, cut, rng), point),
                  bot_a_chooser(tf_minutes), p, costs, acct, events)
        before_base, before_scr = decisions_until(base, cut.value), decisions_until(scr, cut.value)
        after_changed = len(set(base.decisions) ^ set(scr.decisions))
        rows.append({"cut_utc": cut, "decisions_before_cut": len(before_base),
                     "identical_before_cut": before_base == before_scr,
                     "decisions_changed_after_cut": after_changed})
    return pd.DataFrame(rows)
