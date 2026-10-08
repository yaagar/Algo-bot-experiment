"""Experiment 4 unit checks on synthetic inputs (no price files needed)."""
from types import SimpleNamespace

import numpy as np
import pandas as pd

from src.exp4.data import Clock, h1_from_m1, load_config, variant_config
from src.exp4.signals import efficiency_by_day
from src.exp4.system import E4Strategy

NS_H = 3600 * 10**9


def utc_ns(text):
    return pd.Timestamp(text, tz="UTC").value


def test_config_matches_locked_spec_numbers():
    cfg = load_config()
    t, g, s = cfg["trading"], cfg["gates"], cfg["signals"]
    assert (t["entry_threshold"], t["exit_threshold"], t["full_size_forecast"], t["stop_atr"]) == (0.30, 0.10, 0.60, 1.5)
    assert (t["max_entries_per_day"], t["news_blackout_min"]) == (3, 5)
    assert (g["efficiency_days"], g["efficiency_trend"], g["shock_mult"], g["shock_days"]) == (10, 0.30, 3.0, 60)
    assert (s["sigma_days"], s["sigma_mult"], s["c_sma"], s["c_atr"], s["d_sma"], s["d_atr"]) == (60, 2.0, 20, 20, 20, 14)
    v = variant_config(cfg, "stop_2.0")
    assert v["trading"]["stop_atr"] == 2.0 and v["trading"]["entry_threshold"] == 0.30 and cfg["trading"]["stop_atr"] == 1.5


def test_us500_day_starts_18_00_new_york_the_evening_before():
    clk = Clock("America/New_York", 18 * 60)
    # Monday 2024-03-04: 18:00 NY Sunday = 23:00 UTC Sunday (winter)
    assert clk.at(pd.Timestamp("2024-03-04"), "18:00") == utc_ns("2024-03-03 23:00")
    assert clk.at(pd.Timestamp("2024-03-04"), "09:30") == utc_ns("2024-03-04 14:30")
    day, minute = clk.day_and_minute(np.array([utc_ns("2024-03-03 23:30"), utc_ns("2024-03-04 14:30")]))
    assert list(day) == [pd.Timestamp("2024-03-04")] * 2
    assert list(minute) == [30, 930]                     # 18:30 and 09:30 NY, minutes since 18:00


def test_gold_day_is_the_london_date_and_weekends_have_no_day():
    clk = Clock("Europe/London", 0)
    day, minute = clk.day_and_minute(np.array([utc_ns("2024-07-01 00:00"), utc_ns("2024-07-01 06:00"),
                                               utc_ns("2024-06-30 23:00")]))
    # 00:00 UTC = 01:00 London Monday (summer time)
    assert day[0] == pd.Timestamp("2024-07-01") and minute[0] == 60
    assert day[1] == pd.Timestamp("2024-07-01") and minute[1] == 7 * 60     # the 06:00-07:00 London bar
    assert minute[2] == 1440 and pd.isna(day[2])        # closes at midnight -> Sunday's last minute, no day


def test_us500_h1_bars_start_at_half_past():
    t = pd.date_range("2024-03-04 14:00", periods=120, freq="1min", tz="UTC")     # 09:00-10:59 NY
    m1 = pd.DataFrame({"time_utc": t, "open": 1.0, "high": np.arange(120.0), "low": 0.0,
                       "close": np.arange(120.0), "spread_used": 5})
    bars = h1_from_m1(m1, 0.1, offset_min=30)
    assert list(pd.to_datetime(bars.t_open, utc=True).dt.strftime("%H:%M")) == ["13:30", "14:30", "15:30"]
    assert bars.close.tolist() == [29.0, 89.0, 119.0] and bars.high.tolist() == [29.0, 89.0, 119.0]


def test_efficiency_uses_completed_days_only():
    closes = np.array([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 99.0])
    eff = efficiency_by_day(closes, 10)
    assert np.isnan(eff[10]) and eff[11] == 1.0          # day 11 sees days 0..10 only, not its own 99


def test_exit_on_sign_flip_or_weak_forecast():
    table = pd.DataFrame({"F": [0.5, 0.2, 0.09, -0.3], "t_close": [1, 2, 3, 4], "day_idx": 0,
                          "in_window": True, "shock_ok": True, "atr14": 1.0, "trending": True, "ranging": False,
                          **{f"score_{s}": 0.0 for s in "ABCD"}, "efficiency": 0.5, "shock_ratio": 1.0})
    mk = SimpleNamespace(h1=table, days=[pd.Timestamp("2024-03-04")], cfg={"flat_by": "20:00"},
                         clock=Clock("Europe/London", 0))
    strat = E4Strategy(mk, table, load_config(), SimpleNamespace(within=lambda t, m: False))
    long_pos = SimpleNamespace(order=SimpleNamespace(direction=1))
    assert [strat.exit_signal(i, long_pos) for i in range(4)] == [False, False, True, True]
    assert strat.signal(0).direction == 1 and strat.signal(0).info["size"] == 0.5 / 0.6
    assert strat.signal(1) is None                      # |F| < 0.30: no entry
