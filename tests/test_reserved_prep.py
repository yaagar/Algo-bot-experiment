"""2010-2021 data-prep helpers, on synthetic data only."""
import pandas as pd

from src.calendar_events import _hhmm
from src.reserved_prep import unexplained_gaps


def ny(s):
    return pd.Timestamp(s, tz="America/New_York").tz_convert("UTC")


def test_weekend_and_daily_break_are_not_gaps_but_a_midweek_hole_is():
    gaps = lambda *t: unexplained_gaps(pd.Series([ny(x) for x in t]), "M1")
    assert gaps("2015-06-05 16:58", "2015-06-07 18:00").empty          # Friday close -> Sunday open
    assert gaps("2015-06-08 16:59", "2015-06-08 18:00").empty          # daily break
    hole = gaps("2015-06-09 10:00", "2015-06-09 10:20", "2015-06-09 11:50")
    assert hole.hours.round(1).tolist() == [1.5]                       # 20 min is fine, 90 min is a gap


def test_fed_time_text_to_24h():
    assert _hhmm("2", "15", "p") == "14:15"
    assert _hhmm("12", "30", "p") == "12:30"
    assert _hhmm("8", "00", "a") == "08:00"
