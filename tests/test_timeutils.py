import pandas as pd

from src.timeutils import server_offset_hours, server_to_utc


def to_utc(server_str):
    return server_to_utc(pd.Series([pd.Timestamp(server_str)])).iloc[0]


def test_summer_nfp_is_1230_utc():
    # NFP 2024-07-05 08:30 New York (EDT, UTC-4) = 12:30 UTC; server shows 15:30
    assert to_utc("2024-07-05 15:30") == pd.Timestamp("2024-07-05 12:30", tz="UTC")


def test_winter_nfp_is_1330_utc():
    # NFP 2024-12-06 08:30 New York (EST, UTC-5) = 13:30 UTC; server shows 15:30
    assert to_utc("2024-12-06 15:30") == pd.Timestamp("2024-12-06 13:30", tz="UTC")


def test_follows_us_not_eu_clock_change():
    # 2023-11-03: Europe already on winter time (since Oct 29), US still on summer
    # time (until Nov 5). A US-based server must still be UTC+3 here.
    assert server_offset_hours(pd.Series([pd.Timestamp("2023-11-03 15:30")])).iloc[0] == 3
    assert server_offset_hours(pd.Series([pd.Timestamp("2023-11-07 15:30")])).iloc[0] == 2


def test_dst_switch_hour_becomes_nat_not_a_wrong_time():
    # Sunday 2024-03-10 02:30 New York doesn't exist (clocks jump 02:00 -> 03:00)
    assert pd.isna(to_utc("2024-03-10 09:30"))
