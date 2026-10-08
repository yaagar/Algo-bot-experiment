"""USD high-impact economic calendar (spec §8, v1.2), stored in UTC.

One FIXED event list for the whole experiment (2022 -> now), from official sources:

  FOMC decision (14:00 NY), press conference (14:30), minutes (14:00)  - federalreserve.gov
  NFP, CPI, PPI, PCE, GDP, retail sales (08:30 NY)                     - FRED API release dates
  ISM manufacturing (1st business day), ISM services (3rd), 10:00 NY   - rule-based

BEA's published schedule overrides the 08:30 assumption for GDP/PCE where it
gives a time (e.g. 2026-01-22 PCE at 10:00). The Forex Factory dataset is used
only to cross-check these dates/times for 2022 -> Apr 2025.

FRED needs a free API key: set FRED_API_KEY in the environment or put a line
FRED_API_KEY=... in the project's .env file (git-ignored). Never in code.

Run:  .venv/Scripts/python -m src.calendar_events
"""
import json
import os
import re

import pandas as pd
import requests
from pandas.tseries.holiday import USFederalHolidayCalendar

from src.config import PROJECT_ROOT
from src.data_access import check_window, read_forex_factory
from src.timeutils import NEW_YORK

RAW = PROJECT_ROOT / "data" / "raw" / "calendar"
OUT = PROJECT_ROOT / "data" / "processed" / "calendar_usd_high.parquet"
FROM = pd.Timestamp("2022-01-01")
TO = pd.Timestamp("2026-12-31")
FF_LAST_DAY = pd.Timestamp("2025-04-07")

# FRED release ids -> our event names (all published 08:30 New York)
FRED_RELEASES = {
    "NFP": 50,            # Employment Situation
    "CPI": 10,            # Consumer Price Index
    "PPI": 46,            # Producer Price Index
    "PCE": 54,            # Personal Income and Outlays
    "GDP": 53,            # Gross Domestic Product
    "Retail sales": 9,    # Advance Monthly Sales for Retail and Food Services
}
FRED_URL = "https://api.stlouisfed.org/fred/release/dates"
FRED_VINTAGE_URL = "https://api.stlouisfed.org/fred/series/vintagedates"
# Not-seasonally-adjusted key series: they get new data only on real release
# days, not on seasonal-factor revision days (used to filter FRED's date list)
FRED_KEY_SERIES = {"NFP": "PAYNSA", "CPI": "CPIAUCNS", "PPI": "PPIACO",
                   "PCE": "PCEPI", "GDP": "GDPC1", "Retail sales": "RSXFSN"}

# Our event -> Forex Factory event names, for the cross-check only
FF_NAMES = {
    "FOMC decision": ["Federal Funds Rate"],
    "FOMC press conference": ["FOMC Press Conference"],
    "FOMC minutes": ["FOMC Meeting Minutes"],
    "NFP": ["Non-Farm Employment Change"],
    "CPI": ["CPI m/m", "Core CPI m/m"],
    "PPI": ["PPI m/m", "Core PPI m/m"],
    "PCE": ["Core PCE Price Index m/m"],
    "GDP": ["Advance GDP q/q", "Prelim GDP q/q", "Final GDP q/q"],
    "Retail sales": ["Retail Sales m/m", "Core Retail Sales m/m"],
    "ISM manufacturing": ["ISM Manufacturing PMI"],
    "ISM services": ["ISM Services PMI"],
}


def ny_to_utc(date, hhmm):
    return pd.Timestamp(f"{pd.Timestamp(date):%Y-%m-%d} {hhmm}").tz_localize(NEW_YORK).tz_convert("UTC")


def make_rows(event, dates, hhmm, source):
    return pd.DataFrame({
        "event": event,
        "date": [pd.Timestamp(d).date() for d in dates],
        "time_utc": [ny_to_utc(d, hhmm) for d in dates],
        "source": source,
    })


# --- FOMC (federalreserve.gov) -------------------------------------------------------

def fomc_dates():
    """(last meeting day list, minutes release day list) from the saved Fed calendar page."""
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " | ", (RAW / "fomc_calendars.html").read_text(encoding="utf-8")))
    decisions, minutes = [], []
    for block in re.split(r"(?=\b20\d\d FOMC Meetings)", text)[1:]:
        year = int(block[:4])
        if year < FROM.year:              # skip reserved-period years before parsing
            continue
        for m in re.finditer(r"\| ([A-Z][a-z]+(?:/[A-Z][a-z]+)?) \| \| \| (\d+)-(\d+)\*? \|", block):
            month_name = m.group(1).split("/")[-1]       # "Apr/May" meetings end in May
            for fmt in ("%B %d %Y", "%b %d %Y"):
                day = pd.to_datetime(f"{month_name} {m.group(3)} {year}", format=fmt, errors="coerce")
                if not pd.isna(day):
                    decisions.append(day)
                    break
        minutes += [pd.to_datetime(s) for s in re.findall(r"\(Released ([A-Z][a-z]+ \d{1,2}, \d{4})\)", block)]
    return sorted(set(decisions)), sorted(set(minutes))


def fomc_events():
    decisions, minutes = fomc_dates()
    return pd.concat([
        make_rows("FOMC decision", decisions, "14:00", "federalreserve.gov"),
        make_rows("FOMC press conference", decisions, "14:30", "federalreserve.gov"),
        make_rows("FOMC minutes", minutes, "14:00", "federalreserve.gov"),
    ])


# --- ISM (rule-based) --------------------------------------------------------------

def nth_business_day(month_start, n):
    """n-th US business day (Mon-Fri, not a federal holiday) of the month."""
    holidays = USFederalHolidayCalendar().holidays(month_start, month_start + pd.offsets.MonthEnd(0))
    days = pd.bdate_range(month_start, month_start + pd.offsets.MonthEnd(0), freq="C", holidays=holidays)
    return days[n - 1]


def ism_events(start=FROM, end=TO):
    """ISM manufacturing = 1st business day, services = 3rd, at 10:00 NY.

    Exception: in January ISM publishes one business day later (seen in all
    four Januaries 2022-2025 in the Forex Factory cross-check). Before 2018 Januaries
    followed the plain rule (Forex Factory 2010-2017), so the shift starts in 2018 (Yash, 2026-10-08).
    """
    months = pd.date_range(start, end, freq="MS")
    january_shift = lambda m: 1 if m.month == 1 and m.year >= 2018 else 0
    return pd.concat([
        make_rows("ISM manufacturing", [nth_business_day(m, 1 + january_shift(m)) for m in months],
                  "10:00", "rule: 1st business day (2nd in Jan from 2018)"),
        make_rows("ISM services", [nth_business_day(m, 3 + january_shift(m)) for m in months],
                  "10:00", "rule: 3rd business day (4th in Jan from 2018)"),
    ])


# --- FRED release dates -------------------------------------------------------------

def fred_key():
    key = os.environ.get("FRED_API_KEY")
    env_file = PROJECT_ROOT / ".env"
    if not key and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("FRED_API_KEY="):
                key = line.split("=", 1)[1].strip()
    return key


def fred_release_dates(release_id, key, start=FROM, end=TO):
    params = {"release_id": release_id, "api_key": key, "file_type": "json",
              "realtime_start": f"{start:%Y-%m-%d}", "realtime_end": "9999-12-31",
              "include_release_dates_with_no_data": "true", "sort_order": "asc", "limit": 10000}
    r = requests.get(FRED_URL, params=params, timeout=60)
    r.raise_for_status()
    dates = pd.to_datetime([d["date"] for d in r.json()["release_dates"]])
    return [d for d in dates if start <= d <= end]


def fred_vintage_dates(series_id, key, start=FROM):
    params = {"series_id": series_id, "api_key": key, "file_type": "json",
              "realtime_start": f"{start:%Y-%m-%d}", "limit": 10000}
    r = requests.get(FRED_VINTAGE_URL, params=params, timeout=60)
    r.raise_for_status()
    return set(pd.to_datetime(r.json()["vintage_dates"]))


def real_release_dates(release_dates, vintages, today, one_per_month=False):
    """Keep FRED release dates that are real data releases.

    FRED also lists revision-only days (seasonal-factor updates, benchmark
    previews, annual revisions). Rules:
      1. a past date must be a day the unadjusted key series got new data;
         future dates are kept as scheduled;
      2. one_per_month (retail sales only): keep the earliest date in a month,
         because the late-April annual revision also changes the unadjusted
         series. Not used elsewhere: e.g. Dec 2022 had two real PCE releases.
    """
    kept = sorted(d for d in release_dates if d > today or d in vintages)
    if one_per_month:
        first = {}
        for d in kept:
            first.setdefault((d.year, d.month), d)
        kept = sorted(first.values())
    return kept


def fred_events(key, start=FROM, end=TO, raw_name="fred_release_dates.csv"):
    today = pd.Timestamp.now().normalize()
    raw, rows = [], []
    for event, release_id in FRED_RELEASES.items():
        dates = fred_release_dates(release_id, key, start, end)
        vintages = fred_vintage_dates(FRED_KEY_SERIES[event], key, start)
        kept = real_release_dates(dates, vintages, today, one_per_month=(event == "Retail sales"))
        raw.append(pd.DataFrame({"event": event, "date": dates, "kept": [d in kept for d in dates]}))
        rows.append(make_rows(event, kept, "08:30", "FRED"))
    pd.concat(raw).to_csv(RAW / raw_name, index=False)   # keep what we pulled
    return pd.concat(rows)


def bea_time_overrides():
    """BEA's own schedule page (current year): exact times for GDP and PCE releases."""
    html = (RAW / "bea_schedule_full.html").read_text(encoding="utf-8")
    patterns = {r"^GDP \(": "GDP", r"^Personal Income and Outlays": "PCE"}
    rows = []
    for date_s, time_s, title in re.findall(
            r'release-date">([^<]+)</div>\s*<small[^>]*>([^<]+)</small>.*?release-title[^>]*>([^<]+)</td>', html, flags=re.S):
        for pattern, event in patterns.items():
            if re.search(pattern, title.strip()):
                rows.append((event, pd.to_datetime(f"{date_s.strip()} 2026").date(),
                             pd.to_datetime(time_s.strip()).strftime("%H:%M")))
    return pd.DataFrame(rows, columns=["event", "date", "hhmm"]).drop_duplicates()


def apply_bea_times(cal):
    for _, o in bea_time_overrides().iterrows():
        hit = (cal.event == o.event) & (cal.date == o.date)
        cal.loc[hit, "time_utc"] = ny_to_utc(o.date, o.hhmm)
        cal.loc[hit, "source"] = cal.loc[hit, "source"] + " + bea.gov time"
    return cal


# --- Forex Factory (cross-check only, and the NFP server-time test) ---------------------

def load_forex_factory_usd_high(start=FROM, end=None, purpose=None, confirm=None, high_only=True):
    """USD high-impact rows from the Forex Factory file, start <= day < end (default 2022+).

    high_only=False keeps every impact level (2010-2021 check: FF rated e.g. PPI and PCE
    below "High" in those years, which says nothing about whether our dates are right).

    Fixes the file's wrong timezone tag (Iran dropped DST in 2023): times are
    Tehran wall-clock, re-labelled with the real Tehran rule. Rows whose time
    was lost (shown 00:00 / 23:59:59) get time_utc = NaT, time_status='unknown'.
    """
    df = read_forex_factory(RAW / "forex_factory_cache.csv", f"{start:%Y-%m-%d}",
                            f"{end:%Y-%m-%d}" if end is not None else None, purpose, confirm)
    df = df[(df.Currency == "USD") & (df.Impact.str.startswith("High") | (not high_only))]
    wall = df.DateTime.str[:19]
    df, wall = df[pd.to_datetime(wall) >= start], wall[pd.to_datetime(wall) >= start]
    missing = wall.str[11:].isin(("00:00:00", "23:59:59")).values
    utc = (pd.to_datetime(wall).dt.tz_localize("Asia/Tehran", ambiguous="NaT", nonexistent="NaT")
           .dt.tz_convert("UTC").reset_index(drop=True))
    out = pd.DataFrame({"event": df.Event.values, "date": pd.to_datetime(wall.str[:10]).dt.date.values,
                        "actual": df.Actual.values, "forecast": df.Forecast.values})
    out["time_utc"] = utc.where(~missing)
    out["time_status"] = ["unknown" if m else "exact" for m in missing]
    exact = out.time_status == "exact"
    out.loc[exact, "date"] = out.loc[exact, "time_utc"].dt.tz_convert(NEW_YORK).dt.date
    return out


def cross_check_with_forex_factory(cal, ff=None, start=FROM, end=FF_LAST_DAY, ff_names=FF_NAMES):
    """For 2022 -> Apr 2025 (or start -> end): do our dates (and times, where FF kept them) agree with FF?"""
    ff = load_forex_factory_usd_high() if ff is None else ff
    window = cal[(pd.to_datetime(cal.date) >= start) & (pd.to_datetime(cal.date) <= end)]
    rows = []
    for event, names in ff_names.items():
        ours = window[window.event == event]
        theirs = ff[ff.event.isin(names)]
        ff_dates = set(theirs.date)
        our_dates = set(ours.date)
        exact = theirs[theirs.time_status == "exact"].drop_duplicates("date").set_index("date").time_utc
        timed = ours[ours.date.isin(exact.index)]
        rows.append({
            "event": event,
            "ours": len(our_dates),
            "in_FF": len(our_dates & ff_dates),
            "FF_not_ours": len(ff_dates - our_dates),
            "time_checked": len(timed),
            "time_match": int(sum(timed.time_utc.values == exact.loc[timed.date].values)),
        })
    return pd.DataFrame(rows)


def build(key):
    parts = [fomc_events(), ism_events()]
    if key:
        parts.append(fred_events(key))
    cal = pd.concat(parts, ignore_index=True)
    cal = cal[(pd.to_datetime(cal.date) >= FROM) & (pd.to_datetime(cal.date) <= TO)]
    cal = apply_bea_times(cal)
    return cal.sort_values("time_utc").reset_index(drop=True)


# --- Reserved period 2010-2021 (option a; data preparation only) ------------------------
#
# Same sources and rules as above, plus the Fed's historical FOMC pages. Before 2022 the
# statement time changed (14:15 to 2011, 12:30 at press-conference meetings 2011-12, 14:00
# from 2013, plus unscheduled statements), so it is read per meeting from the Fed's own pages:
#   1. the statement page ("For release at 2:00 p.m."), else
#   2. the press-conference page ("Statement ... (Released <date> at 12:30 p.m.)"), else
#   3. the Fed's press-release feed posting time, rounded down to the quarter hour (flagged).
# Press-conference status = the meeting has a "Press Conference" link. Its start time is not
# printed on the Fed pages, so it is a rule: 14:15 after a midday statement (2011-12), else statement + 30 min.
# The 2009 page is read only for minutes released in January 2010.
# Output goes to its own file; the 2022+ calendar is untouched.

RESERVED_FROM = pd.Timestamp("2010-01-01")
RESERVED_TO = pd.Timestamp("2021-12-31")
RESERVED_OUT = PROJECT_ROOT / "data" / "processed" / "calendar_usd_high_2010_2021.parquet"
FED = "https://www.federalreserve.gov"
FED_RAW = RAW / "fed_2010_2021"
FED_FEED = "/json/ne-press.json"
# Older Forex Factory names for the same events, used only in the 2010-2021 cross-check
FF_NAMES_RESERVED = {**FF_NAMES,
                     "FOMC decision": ["Federal Funds Rate", "FOMC Statement"],
                     "ISM services": ["ISM Services PMI", "ISM Non-Manufacturing PMI"]}


def fed_page(path):
    """A Fed web page, downloaded once and kept in data/raw/calendar/fed_2010_2021/."""
    f = FED_RAW / path.strip("/").replace("/", "_")
    if not f.exists():
        FED_RAW.mkdir(parents=True, exist_ok=True)
        r = requests.get(FED + path, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
        r.raise_for_status()
        f.write_bytes(r.content)
    return f.read_bytes().decode("utf-8-sig", errors="replace")


def _plain(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def _hhmm(h, m, ampm):
    return f"{int(h) % 12 + (12 if ampm.lower() == 'p' else 0):02d}:{m}"


def fomc_meetings_reserved():
    """One row per 2010-2021 meeting/call listed on the Fed pages: label, statement link, presser, minutes."""
    segments = []
    for year in range(RESERVED_FROM.year - 1, 2021):
        html = fed_page(f"/monetarypolicy/fomchistorical{year}.htm")
        parts = re.split(r"<h5[^>]*>", html)[1:]
        for part in parts:
            head = re.match(r"\s*([^<]*?)\s*-\s*(20\d\d)\s*</h5>", part)
            if head:
                segments.append((head.group(1), part))
    cal_page = fed_page("/monetarypolicy/fomccalendars.htm")
    block = cal_page[cal_page.find("2021 FOMC Meetings"):]
    block = block[:block.find("FOMC Meetings", 30)] if block.find("FOMC Meetings", 30) > 0 else block
    for row in block.split('fomc-meeting"')[1:]:
        month = re.search(r"fomc-meeting__month[^>]*><strong>([^<]+)<", row)
        day = re.search(r"fomc-meeting__date[^>]*>([^<]+)<", row)
        if month and day:
            segments.append((f"{month.group(1)} {day.group(1).strip()} Meeting", row))

    rows = []
    for label, seg in segments:
        statement = (re.search(r'href="(/newsevents/press(?:releases)?/monetary/?(\d{8})a\.htm)"[^>]*>\s*Statement\s*<', seg)
                     or re.search(r'Statement:</strong>.*?href="(/newsevents/pressreleases/monetary(\d{8})a\.htm)"', seg, re.S))
        presser = re.search(r'href="(/monetarypolicy/fomcpresconf(\d{8})\.htm)"', seg)
        minutes = re.search(r"Minutes[^()]{0,80}\(Released ([A-Z][a-z]+\.? \d{1,2}, \d{4})(?: at (\d{1,2}):(\d\d) ?([ap])\.m\.)?",
                            _plain(seg))
        rows.append({
            "label": label.replace("  ", " "),
            "statement_path": statement.group(1) if statement else None,
            "statement_date": pd.Timestamp(statement.group(2)) if statement else None,
            "presser_path": presser.group(1) if presser else None,
            "minutes_date": pd.to_datetime(minutes.group(1).replace(".", "")) if minutes else None,
            "minutes_hhmm": _hhmm(*minutes.group(2, 3, 4)) if minutes and minutes.group(2) else "14:00",
        })
    return pd.DataFrame(rows)


def statement_time(row, feed):
    """(hh:mm New York, source) for one statement, by the priority in the section comment."""
    m = re.search(r"For release at (\d{1,2}):(\d\d) ?([ap])\.m\.", _plain(fed_page(row.statement_path)), re.I)
    if m:
        return _hhmm(*m.groups()), "Fed statement page"
    if isinstance(row.presser_path, str):
        m = re.search(r"Statement[^()]*\(Released [A-Za-z]+ \d{1,2}, \d{4} at (\d{1,2}):(\d\d) ?([ap])\.m\.\)",
                      _plain(fed_page(row.presser_path)))
        if m:
            return _hhmm(*m.groups()), "Fed press-conference page"
    posted = feed.get(f"{row.statement_date:%Y%m%d}")
    if posted is not None:
        return posted.floor("15min").strftime("%H:%M"), "Fed feed posting time, rounded down (approx.)"
    return None, "no time found"


def fomc_events_reserved():
    meetings = fomc_meetings_reserved()
    feed = {}
    for item in json.loads(fed_page(FED_FEED)):
        hit = re.search(r"monetary(\d{8})a\.htm$", item.get("l", ""))
        if hit and "FOMC statement" in item.get("t", "") and ":" in item["d"]:      # some carry no time
            feed[hit.group(1)] = pd.to_datetime(item["d"], format="%m/%d/%Y %I:%M:%S %p")
    rows = []
    for row in meetings[meetings.statement_path.notna()].itertuples():
        hhmm, source = statement_time(row, feed)
        rows.append(("FOMC decision", row.statement_date, hhmm, source))
        if isinstance(row.presser_path, str):
            h, m = map(int, hhmm.split(":"))
            presser = "14:15" if "12:00" <= hhmm < "13:00" else f"{h + (m + 30) // 60:02d}:{(m + 30) % 60:02d}"
            rows.append(("FOMC press conference", row.statement_date, presser,
                         "rule: 14:15 after a midday statement, else statement + 30 min"))
    for row in meetings[meetings.minutes_date.notna()].itertuples():
        rows.append(("FOMC minutes", row.minutes_date, row.minutes_hhmm, "Fed historical page"))
    events = pd.DataFrame(rows, columns=["event", "day", "hhmm", "source"]).drop_duplicates(["event", "day"])
    return pd.DataFrame({"event": events.event, "date": [d.date() for d in events.day],
                         "time_utc": [ny_to_utc(d, t) for d, t in zip(events.day, events.hhmm)],
                         "source": events.source}), meetings


# Fixes decided by Yash on 2026-10-08 after the first Forex Factory cross-check:
PPI_REVISION_DAYS = ["2010-02-16", "2011-02-14", "2012-02-14", "2017-02-10", "2019-02-12", "2020-02-14"]
FF_TIME_OVERRIDES = {          # Forex Factory times where our rule/assumption was wrong
    ("PCE", "2016-02-26"): "10:00", ("PCE", "2016-12-22"): "10:00", ("PCE", "2019-11-27"): "10:00",
    ("PCE", "2019-12-20"): "10:00", ("PCE", "2021-11-24"): "10:00",
    ("FOMC press conference", "2020-03-03"): "11:00",          # unscheduled meetings
    ("FOMC press conference", "2020-03-15"): "18:30",
}


def retail_sales_from_forex_factory(cal, ff):
    """Retail-sales months with no FRED date (key series has no vintages before 2013): Forex Factory's date."""
    have = {(d.year, d.month) for d in cal[cal.event == "Retail sales"].date}
    ff = ff[ff.event.isin(FF_NAMES["Retail sales"])].sort_values("date").drop_duplicates("date")
    rows = []
    for r in ff.itertuples():
        if (r.date.year, r.date.month) not in have:
            have.add((r.date.year, r.date.month))
            rows.append((r.date, r.time_utc if pd.notna(r.time_utc) else ny_to_utc(r.date, "08:30")))
    return pd.DataFrame({"event": "Retail sales", "date": [d for d, _ in rows], "time_utc": [t for _, t in rows],
                         "source": "Forex Factory"})


def build_reserved(key, purpose, confirm):
    """The 2010-2021 calendar (data preparation only). Returns (calendar, meetings table)."""
    check_window(RESERVED_FROM, RESERVED_TO, "news calendar 2010-2021 (Fed, FRED, ISM rule)", purpose, confirm)
    fomc, meetings = fomc_events_reserved()
    cal = pd.concat([fomc, ism_events(RESERVED_FROM, RESERVED_TO),
                     fred_events(key, RESERVED_FROM, RESERVED_TO, "fred_release_dates_2010_2021.csv")],
                    ignore_index=True)
    cal = cal[(pd.to_datetime(cal.date) >= RESERVED_FROM) & (pd.to_datetime(cal.date) <= RESERVED_TO)]
    ff = load_forex_factory_usd_high(RESERVED_FROM, RESERVED_TO + pd.Timedelta(days=1), purpose, confirm, high_only=False)
    cal = pd.concat([cal, retail_sales_from_forex_factory(cal, ff)], ignore_index=True)
    revision = (cal.event == "PPI") & pd.to_datetime(cal.date).isin(pd.to_datetime(PPI_REVISION_DAYS))
    cal = cal[~revision].reset_index(drop=True)
    for (event, day), hhmm in FF_TIME_OVERRIDES.items():
        hit = (cal.event == event) & (pd.to_datetime(cal.date) == pd.Timestamp(day))
        assert hit.sum() == 1, (event, day)
        cal.loc[hit, "time_utc"] = ny_to_utc(day, hhmm)
        cal.loc[hit, "source"] = cal.loc[hit, "source"] + " + Forex Factory time"
    return cal.sort_values("time_utc").reset_index(drop=True), meetings


def main():
    key = fred_key()
    cal = build(key)
    print("== Cross-check against Forex Factory, 2022-01 -> 2025-04")
    print(cross_check_with_forex_factory(cal).to_string(index=False))
    print("\n== Events per year")
    print(cal.groupby([pd.to_datetime(cal.date).dt.year, "event"]).size().unstack(fill_value=0).T.to_string())
    if not key:
        print("\nFRED_API_KEY not set: NFP/CPI/PPI/PCE/GDP/retail sales missing. Calendar NOT saved.")
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    cal.to_parquet(OUT, index=False)
    print(f"\nsaved: {OUT.relative_to(PROJECT_ROOT)}  ({len(cal)} events)")


if __name__ == "__main__":
    main()
