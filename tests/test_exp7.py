"""Experiment 7 unit checks on synthetic inputs (no price files)."""
import numpy as np
import pandas as pd
import pytest

from src.backtest import Events
from src.exp7.pattern import (choppiness, false_breaks, h1_context, place_stop, place_target, run_start,
                              scan, slope_tstat, swing_points, trend_structure)
from src.exp7.run import load_config

CFG = load_config()


def test_swing_needs_two_bars_each_side_and_ties_go_to_earlier_bar():
    high = np.array([1, 2, 5, 3, 2, 5, 5, 1, 0.5])
    low = np.array([1, 0, 2, 2, 2, 2, 2, 2, 2.0])
    sh, sl = swing_points(high, low)
    assert sh.tolist() == [0, 0, 1, 0, 0, 1, 0, 0, 0]
    assert sl.tolist() == [0] * 9                    # low[1] has only one bar on its left


def test_trend_uses_only_swings_confirmed_two_bars_later():
    # zig-zag with rising highs and lows: highs at 2, 6, 10; lows at 4, 8, 12
    high = np.array([1, 2, 5, 3, 2, 4, 7, 5, 4, 6, 9, 7, 6, 8, 9.5, 9.6])
    low = high - 1
    tr = trend_structure(high, low)
    assert tr[13] == 0 and tr[14] == 1               # 3rd rising swing low (bar 12) known at bar 14
    assert (trend_structure(-high, -high - 1)[14:] == -1).all()


def test_tstat_of_clean_line_is_huge_and_flat_is_nan_or_zero():
    up = np.arange(48.0) + np.sin(np.arange(48))
    assert slope_tstat(up, 48)[-1] > 20
    assert np.isnan(slope_tstat(up, 48)[:47]).all()


def test_choppiness_trending_low_ranging_high():
    trend = np.arange(30.0)
    assert choppiness(trend + 0.5, trend - 0.5, trend, 14)[-1] < 40
    flat = np.tile([0.0, 1.0], 15)
    assert choppiness(flat + 0.5, flat - 0.5, flat, 14)[-1] > 61.8


def test_run_start_extends_while_combined_range_fits():
    high = np.array([10, 5, 5.2, 5.1, 5.3])
    low = np.array([0, 4.9, 5.0, 4.95, 5.1])
    no_gap = np.zeros(5, bool)
    assert run_start(high, low, 4, 0.5, no_gap) == 1
    assert run_start(high, low, 4, 0.1, no_gap) == 5          # even the last bar alone is too wide
    assert run_start(high, low, 4, 0.5, np.array([0, 0, 0, 1, 0], bool)) == 3   # gap before bar 3 ends the run


def test_false_break_counts_only_closes_that_came_back():
    high = np.array([1.0] * 6 + [1.3, 1.0, 1.3, 1.3])
    low = np.zeros(10)
    close = np.array([0.5] * 6 + [1.2, 0.5, 1.2, 1.25])  # bar 6 came back (bar 7); bars 8, 9 never did
    assert false_breaks(high, low, close, 0, 9, 6) == 1


def test_stop_is_midpoint_or_one_atr_and_jumps_round_level():
    assert place_stop(2005.0, 2001.0, 2.0, 1, CFG) == 2001.0
    assert place_stop(2005.0, 2004.5, 2.0, 1, CFG) == 2003.0           # at least 1 ATR away
    assert place_stop(2012.0, 2010.3, 1.0, 1, CFG) == 2009.5           # near $2010 -> $0.50 below it
    assert place_stop(2008.0, 2010.4, 1.0, -1, CFG) == 2010.5          # short: $0.50 above it


def test_target_zone_round_level_and_2r_fallback():
    assert place_target(2003.0, 1.0, 1, np.array([1995.0]), CFG) == (2005.0, "2R_no_zone")
    assert place_target(2003.0, 1.0, 1, np.array([2006.0, 2009.0]), CFG) == (2006.0, "zone")
    assert place_target(2007.0, 1.0, 1, np.array([2013.0]), CFG) == (2009.5, "zone")   # $2010 in between
    assert place_target(2003.0, 2.0, 1, np.array([2004.0]), CFG) == (2007.0, "2R_zone_under_1R")
    assert place_target(2003.0, 1.0, -1, np.array([1996.0]), CFG) == (2000.5, "zone")    # short: before $2000


def synthetic(seed=0, days=80):
    rng = np.random.default_rng(seed)
    t = pd.date_range("2024-03-04", periods=days * 96, freq="15min", tz="UTC")
    t = t[t.dayofweek < 5]
    regime = np.repeat(rng.choice([0.0, 0.2, -0.2], size=len(t) // 200 + 1), 200)[:len(t)]
    close = 2000 + np.cumsum(regime + rng.normal(0, 0.6, len(t)))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + rng.uniform(0, 0.5, len(t))
    low = np.minimum(open_, close) - rng.uniform(0, 0.5, len(t))
    m15 = pd.DataFrame({"time_utc": t, "open": open_, "high": high, "low": low, "close": close})
    return m15


def h1_of(m15):
    g = m15.groupby(m15.time_utc.dt.floor("1h"))
    return pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(),
                         "close": g.close.last()}).rename_axis("time_utc").reset_index()


LOOSE = {"cost_guard_max_spread_frac": 99, "tstat_min": -1e9, "chop_max": 100, "max_false_breaks": 99, "box_max_height_atr_m15": 99}


def run_scan(m15, **over):
    cfg = {**CFG, "entry_hours_london": ["00:00", "23:59"], **over}
    events = Events(pd.Series([pd.Timestamp("2024-03-12 13:30", tz="UTC")]))
    return scan(m15, h1_context(h1_of(m15), cfg), events, np.full(24, 0.00015), cfg)


def test_some_setups_qualify_on_synthetic_trends():
    assert run_scan(synthetic()).qualifies.sum() > 0


@pytest.mark.parametrize("seed", [0, 1])
def test_future_scramble_does_not_change_earlier_setups(seed):
    m15 = synthetic(seed)
    cut = m15.time_utc.iloc[len(m15) * 2 // 3].floor("1h")
    scrambled = m15.copy()
    future = scrambled.time_utc >= cut
    rng = np.random.default_rng(99)
    for col in ("open", "high", "low", "close"):
        scrambled.loc[future, col] = rng.permutation(scrambled.loc[future, col].to_numpy()) + 50
    a, b = run_scan(m15, **LOOSE), run_scan(scrambled, **LOOSE)
    keep = lambda d: d[d.fill_time_utc < cut].reset_index(drop=True)
    pd.testing.assert_frame_equal(keep(a), keep(b), check_dtype=False)
    assert keep(a).qualifies.sum() > 5 and keep(a).target_kind.eq("zone").any()
