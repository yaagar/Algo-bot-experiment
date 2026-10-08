import pandas as pd

from src.calendar_events import nth_business_day, real_release_dates, ism_events
from src.spread_model import apply_table


# --- spread estimate ------------------------------------------------------------

def bars(times, spreads):
    return pd.DataFrame({"time_utc": pd.to_datetime(times, utc=True), "spread": spreads})


TABLE = pd.Series({h: 250 for h in range(24)} | {22: 810})   # points by London hour


def test_old_bars_get_estimated_spread_for_their_london_hour():
    # 2023-07-03 21:30 UTC = 22:30 London (BST) -> rollover hour estimate 810
    out = apply_table(bars(["2023-07-03 21:30"], [0]), TABLE, pd.Timestamp("2025-12-17", tz="UTC"))
    assert out.spread_estimated.iloc[0] and out.spread_used.iloc[0] == 810


def test_real_spread_is_kept_after_cutoff():
    out = apply_table(bars(["2026-03-02 10:00"], [270]), TABLE, pd.Timestamp("2025-12-17", tz="UTC"))
    assert not out.spread_estimated.iloc[0] and out.spread_used.iloc[0] == 270


def test_zero_spread_after_cutoff_is_still_estimated():
    out = apply_table(bars(["2026-03-02 10:00"], [0]), TABLE, pd.Timestamp("2025-12-17", tz="UTC"))
    assert out.spread_estimated.iloc[0] and out.spread_used.iloc[0] == 250


# --- ISM rule ---------------------------------------------------------------------

def test_business_day_skips_weekend_and_holiday():
    # Sep 2025: Mon 1st is Labor Day -> 1st business day is Tue 2nd
    assert nth_business_day(pd.Timestamp("2025-09-01"), 1) == pd.Timestamp("2025-09-02")


def test_ism_january_is_one_business_day_later():
    ism = ism_events()
    jan = ism[(ism.event == "ISM manufacturing") & (pd.to_datetime(ism.date) == "2024-01-03")]
    assert len(jan) == 1     # 1st business day is Jan 2, ISM published Jan 3


# --- FRED revision filter ---------------------------------------------------------

def test_revision_only_days_are_dropped_future_days_kept():
    d = pd.to_datetime(["2024-02-09", "2024-02-13", "2026-12-10"])   # revision, real, future
    kept = real_release_dates(list(d), vintages={d[1]}, today=pd.Timestamp("2026-10-08"))
    assert kept == [d[1], d[2]]


def test_one_per_month_keeps_earliest():
    d = pd.to_datetime(["2024-04-15", "2024-04-23"])                   # real, annual revision
    kept = real_release_dates(list(d), vintages=set(d), today=pd.Timestamp("2026-10-08"), one_per_month=True)
    assert kept == [d[0]]
