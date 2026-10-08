"""Time conversions (spec §5, §8).

Broker server clock = New York clock + 7 hours. So the server shows midnight
when New York shows 17:00 (the daily rollover), and it changes summer/winter
time on the US dates: UTC+3 while the US is on daylight time, UTC+2 otherwise.
Verified in Phase 2 by src/verify_server_time.py (daily-break and NFP checks).
"""
import pandas as pd

NEW_YORK = "America/New_York"
LONDON = "Europe/London"
SERVER_MINUS_NEW_YORK = pd.Timedelta(hours=7)


def server_to_utc(server_times):
    """Naive broker-server times (Series) -> tz-aware UTC times.

    Shift back 7 h to get New York wall-clock time, then let the timezone
    database apply the correct US daylight-saving rule for that date.
    Times that don't exist / are ambiguous in New York (the DST switch hour,
    Sunday 02:00 NY, when gold is closed) become NaT so they can't hide.
    """
    new_york = pd.Series(server_times) - SERVER_MINUS_NEW_YORK
    localized = new_york.dt.tz_localize(NEW_YORK, ambiguous="NaT", nonexistent="NaT")
    return localized.dt.tz_convert("UTC")


def server_offset_hours(server_times):
    """The UTC offset of the server clock for each timestamp (2 or 3)."""
    utc = server_to_utc(server_times)
    return (pd.Series(server_times) - utc.dt.tz_localize(None)) / pd.Timedelta(hours=1)


def utc_to_london(utc_times):
    return pd.Series(utc_times).dt.tz_convert(LONDON)


def utc_to_new_york(utc_times):
    return pd.Series(utc_times).dt.tz_convert(NEW_YORK)
