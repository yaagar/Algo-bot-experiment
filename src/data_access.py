"""The ONLY place price data is read from disk — with a hard lock on the reserved period.

2010-2021 is reserved for Phase 4c (spec v1.4). Any read, download or data-prep step
whose window starts before 2022-01-01 is refused unless the caller passes:
  purpose  = what the access is for, and
  confirm  = CONFIRM_TEMPLATE filled in with TODAY's date and that purpose,
so a confirmation only works on the day it was written. Each confirmed use appends a
dated entry to results/data_access_log.md.

Standing grants (GRANTS) are the one exception: Yash confirmed, on a stated date, a fixed
pre-2022 window for one experiment and named data only. A caller passes grant="<name>";
anything outside that window or those data sets still needs the daily confirmation.
Every granted read is logged too.

Rows outside the requested window are filtered inside the Parquet read, so reserved
rows never reach memory unless the window was confirmed. tests/test_data_lock.py
fails if any other module reads price files or pulls MT5 history without this check.
"""
import datetime as dt
import getpass
import subprocess
import traceback

import pandas as pd

from src.config import PROJECT_ROOT

LOCK_BEFORE = pd.Timestamp("2022-01-01", tz="UTC")      # London midnight = UTC midnight in winter
ACCESS_LOG = PROJECT_ROOT / "results" / "data_access_log.md"
PROCESSED = PROJECT_ROOT / "data" / "processed"
RAW = PROJECT_ROOT / "data" / "raw"
CONFIRM_TEMPLATE = "I confirm one-time use of pre-2022 data on {date} for: {purpose}"
GRANTS = {
    "exp7": {
        "data": ("XAUUSD.sim", "USD calendar"),     # the calendar is needed for the news rule on the same dates
        "start": pd.Timestamp("2019-01-01", tz="UTC"),
        "confirmed": "I confirm use of pre-2022 XAUUSD data on 2026-10-09 for: Experiment 7 development period "
                     "2019-01-01 to 2021-12-31. 2010-01-01 to 2018-12-31 stays reserved as Exp 7's one-time final exam.",
    },
}


class ReservedDataLocked(PermissionError):
    pass


def _git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              cwd=PROJECT_ROOT, timeout=10).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _log_access(what, start, end, purpose, log_path):
    caller = next((f"{f.filename.split('src')[-1]}:{f.lineno}" for f in reversed(traceback.extract_stack()[:-3])
                   if "data_access" not in f.filename), "unknown")
    line = (f"| {dt.datetime.now():%Y-%m-%d %H:%M:%S} | {what} | {start} → {end} | {purpose} | "
            f"{caller} | {_git_commit()} | {getpass.getuser()} |\n")
    if not log_path.exists():
        log_path.write_text(
            "# Data access log — reserved period (before 2022-01-01)\n\n"
            "| When (local) | What | Window | Purpose | Caller | Git commit | User |\n|---|---|---|---|---|---|---|\n",
            encoding="utf-8")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line)


def check_window(start, end=None, what="price data", purpose=None, confirm=None, log_path=None,
                 grant=None, data=None):
    """Refuse a window that starts before 2022-01-01 unless confirmed today (or covered by a standing
    grant for this data set). start=None = everything."""
    start_ts = LOCK_BEFORE - pd.Timedelta(days=1) if start is None else pd.Timestamp(start)
    if start_ts.tzinfo is None:
        start_ts = start_ts.tz_localize("UTC")
    if start_ts >= LOCK_BEFORE:
        return
    g = GRANTS.get(grant)
    if g and start is not None and data in g["data"] and start_ts >= g["start"]:
        _log_access(what, start, end or "end", f"standing grant '{grant}': {g['confirmed']}", log_path or ACCESS_LOG)
        return
    expected = CONFIRM_TEMPLATE.format(date=dt.date.today().isoformat(), purpose=purpose)
    if not purpose or confirm != expected:
        raise ReservedDataLocked(
            f"Refused: {what} from {start or 'the beginning'} reaches the reserved period (before 2022-01-01). "
            f"Pass purpose=... and confirm='{CONFIRM_TEMPLATE}' with today's date "
            "(only after Yash approves the use).")
    _log_access(what, start or "beginning", end or "end", purpose, log_path or ACCESS_LOG)


def read_prices(symbol, tf, start, end, columns=None, purpose=None, confirm=None, path=None, log_path=None,
                grant=None):
    """Processed (UTC) bars with start <= time_utc < end, filtered inside the read."""
    check_window(start, end, f"{symbol} {tf} bars", purpose, confirm, log_path, grant, symbol)
    path = path or PROCESSED / f"{symbol}_{tf}.parquet"
    filters = []
    if start is not None:
        filters.append(("time_utc", ">=", pd.Timestamp(start)))
    if end is not None:
        filters.append(("time_utc", "<", pd.Timestamp(end)))
    return pd.read_parquet(path, columns=columns, filters=filters or None)


def read_full_file_for_data_prep(path, purpose=None, confirm=None, log_path=None):
    """Whole raw/processed file (data-prep steps that rewrite every row). Always reaches the reserved period."""
    check_window(None, None, f"full file {path.name}", purpose, confirm, log_path)
    return pd.read_parquet(path)


def read_forex_factory_from_2022(path):
    """The Forex Factory CSV, keeping only rows dated 2022 or later."""
    return read_forex_factory(path, "2022-01-01")


def read_forex_factory(path, start, end=None, purpose=None, confirm=None, log_path=None):
    """The Forex Factory CSV, keeping only rows dated start <= day < end (YYYY-MM-DD strings).

    The CSV can't be filtered on read, so it is read in chunks and rows outside the
    window are dropped from each chunk before anything else sees them.
    """
    check_window(start, end, "Forex Factory calendar", purpose, confirm, log_path)
    keep = []
    for chunk in pd.read_csv(path, chunksize=20_000):
        day = chunk.DateTime.str[:10]
        keep.append(chunk[(day >= start) & (day < end if end else True)])
    return pd.concat(keep, ignore_index=True)


def read_usd_events(start, end, grant=None, log_path=None):
    """USD event times (UTC) with start <= time < end: the 2022+ calendar, plus the 2010-2021 one
    when the window reaches before 2022 (same lock, data set "USD calendar")."""
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    check_window(start, end, "USD calendar", log_path=log_path, grant=grant, data="USD calendar")
    files = ["calendar_usd_high.parquet"] + (["calendar_usd_high_2010_2021.parquet"] if start < LOCK_BEFORE else [])
    times = pd.concat([pd.read_parquet(PROCESSED / f, columns=["time_utc"]).time_utc for f in files])
    return times[(times >= start) & (times < end)].drop_duplicates().sort_values().reset_index(drop=True)
