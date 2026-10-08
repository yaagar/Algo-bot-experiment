"""USD high-impact economic calendar (spec §8), stored in UTC.

Sources:
  * 2022 -> 2025-04-07: public Forex Factory dataset (Hugging Face, Ehsanrs2).
  * After that: official schedules — Fed FOMC calendar, BEA (GDP, PCE).
    BLS (NFP, CPI, PPI, JOLTS) blocks automated access; see coverage notes.

Two repairs to the Forex Factory file (both found in Phase 2):
  1. Timezone label: times are Tehran wall-clock, but the file tags summers
     2023+ as +04:30 although Iran dropped daylight saving in 2023. We ignore
     the tag and re-apply the real Tehran rule from the timezone database.
  2. Missing times: ~half the USD high-impact rows show 00:00 (Forex Factory
     prints the time only on the first event of a group; the scraper lost it).
     For scheduled releases we fill the official New York release time from
     SCHEDULED_NY_TIME and mark time_status="filled". Events with no fixed
     time (speeches, elections) stay time_status="unknown".

Run:  .venv/Scripts/python -m src.calendar_events
"""
import re

import pandas as pd

from src.config import PROJECT_ROOT
from src.timeutils import NEW_YORK

RAW = PROJECT_ROOT / "data" / "raw" / "calendar"
OUT = PROJECT_ROOT / "data" / "processed" / "calendar_usd_high.parquet"
FROM = pd.Timestamp("2022-01-01")
FF_LAST_DAY = pd.Timestamp("2025-04-07")
MISSING_TIME_MARKERS = ("00:00:00", "23:59:59")

# Official New York release times for scheduled USD releases.
SCHEDULED_NY_TIME = {
    **dict.fromkeys([
        "Non-Farm Employment Change", "Unemployment Rate", "Average Hourly Earnings m/m",
        "CPI m/m", "CPI y/y", "Core CPI m/m", "PPI m/m", "Core PPI m/m",
        "Retail Sales m/m", "Core Retail Sales m/m", "Unemployment Claims",
        "Core PCE Price Index m/m", "Employment Cost Index q/q",
        "Advance GDP q/q", "Prelim GDP q/q", "Final GDP q/q",
        "Empire State Manufacturing Index", "Philly Fed Manufacturing Index",
        "Durable Goods Orders m/m", "Core Durable Goods Orders m/m",
    ], "08:30"),
    **dict.fromkeys(["Flash Manufacturing PMI", "Flash Services PMI"], "09:45"),
    **dict.fromkeys([
        "ISM Manufacturing PMI", "ISM Services PMI", "JOLTS Job Openings",
        "CB Consumer Confidence", "Prelim UoM Consumer Sentiment",
        "Revised UoM Consumer Sentiment", "Prelim UoM Inflation Expectations",
    ], "10:00"),
    **dict.fromkeys([
        "FOMC Statement", "Federal Funds Rate", "FOMC Economic Projections",
        "FOMC Meeting Minutes",
    ], "14:00"),
}


def ny_to_utc(date, hhmm):
    return pd.Timestamp(f"{pd.Timestamp(date):%Y-%m-%d} {hhmm}").tz_localize(NEW_YORK).tz_convert("UTC")


# --- Forex Factory -------------------------------------------------------------

def load_forex_factory_usd_high():
    df = pd.read_csv(RAW / "forex_factory_cache.csv")
    df = df[(df.Currency == "USD") & df.Impact.str.startswith("High")].copy()
    wall = df.DateTime.str[:19]                       # Tehran wall-clock, tag dropped
    df = df[pd.to_datetime(wall) >= FROM]
    wall = df.DateTime.str[:19]
    missing = wall.str[11:].isin(MISSING_TIME_MARKERS)

    exact_utc = (pd.to_datetime(wall).dt.tz_localize("Asia/Tehran", ambiguous="NaT", nonexistent="NaT")
                 .dt.tz_convert("UTC"))
    out = pd.DataFrame({
        "event": df.Event.values,
        "date": pd.to_datetime(wall.str[:10]).dt.date.values,
        "actual": df.Actual.values,
        "forecast": df.Forecast.values,
        "source": "forex_factory",
    })
    out["time_utc"] = exact_utc.where(~missing).reset_index(drop=True)   # keeps the UTC tz
    out["time_status"] = ["exact" if not m else "unknown" for m in missing]
    for i in out.index[missing.values]:
        hhmm = SCHEDULED_NY_TIME.get(out.at[i, "event"])
        if hhmm:
            out.at[i, "time_utc"] = ny_to_utc(out.at[i, "date"], hhmm)
            out.at[i, "time_status"] = "filled"
    # For exact rows, the New York date is the true release date
    exact = out.time_status == "exact"
    out.loc[exact, "date"] = pd.to_datetime(out.loc[exact, "time_utc"]).dt.tz_convert(NEW_YORK).dt.date
    return out


def check_fill_table_against_exact_rows(ff):
    """Every event we fill must, on the rows where FF kept the time, really be at that NY time."""
    exact = ff[ff.time_status == "exact"].copy()
    exact["ny"] = pd.to_datetime(exact.time_utc).dt.tz_convert(NEW_YORK).dt.strftime("%H:%M")
    report = []
    for event, hhmm in SCHEDULED_NY_TIME.items():
        rows = exact[exact.event == event]
        if len(rows):
            report.append((event, hhmm, len(rows), (rows.ny == hhmm).mean()))
    return pd.DataFrame(report, columns=["event", "filled_ny_time", "exact_rows", "share_matching"])


# --- Official schedules (after Forex Factory ends) -------------------------------

def load_fomc():
    """FOMC statement (14:00 NY, last meeting day) and minutes release dates."""
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " | ", (RAW / "fomc_calendars.html").read_text(encoding="utf-8")))
    rows = []
    for block in re.split(r"(?=\b20\d\d FOMC Meetings)", text)[1:]:
        year = int(block[:4])
        for m in re.finditer(r"\| ([A-Z][a-z]+(?:/[A-Z][a-z]+)?) \| \| \| (\d+)-(\d+)(\*?) \|", block):
            month_name, last_day, sep = m.group(1).split("/")[-1], m.group(3), m.group(4)
            day = pd.to_datetime(f"{month_name} {last_day} {year}", format="%B %d %Y", errors="coerce")
            if pd.isna(day):
                day = pd.to_datetime(f"{month_name} {last_day} {year}", format="%b %d %Y", errors="coerce")
            if pd.isna(day):
                continue
            rows.append(("FOMC Statement", day.date()))
            rows.append(("Federal Funds Rate", day.date()))
            if sep:
                rows.append(("FOMC Economic Projections", day.date()))
        for released in re.findall(r"\(Released ([A-Z][a-z]+ \d{1,2}, \d{4})\)", block):
            rows.append(("FOMC Meeting Minutes", pd.to_datetime(released).date()))
    out = pd.DataFrame(rows, columns=["event", "date"]).drop_duplicates()
    out["time_utc"] = [ny_to_utc(d, "14:00") for d in out.date]
    out["time_status"] = "official"
    out["source"] = "federalreserve.gov"
    return out


BEA_EVENTS = {r"^GDP \(Advance Estimate\)": "Advance GDP q/q",
              r"^GDP \(Second Estimate\)": "Prelim GDP q/q",
              r"^GDP \(Third Estimate\)": "Final GDP q/q",
              r"^Personal Income and Outlays": "Core PCE Price Index m/m"}


def load_bea(year):
    """BEA's 'full schedule' page (shows the current year only)."""
    html = (RAW / "bea_schedule_full.html").read_text(encoding="utf-8")
    rows = []
    for date_s, time_s, title in re.findall(
            r'release-date">([^<]+)</div>\s*<small[^>]*>([^<]+)</small>.*?release-title[^>]*>([^<]+)</td>', html, flags=re.S):
        for pattern, event in BEA_EVENTS.items():
            if re.search(pattern, title.strip()):
                day = pd.to_datetime(f"{date_s.strip()} {year}")
                hhmm = pd.to_datetime(time_s.strip()).strftime("%H:%M")
                rows.append((event, day.date(), ny_to_utc(day, hhmm), title.strip()))
    out = pd.DataFrame(rows, columns=["event", "date", "time_utc", "detail"])
    out["time_status"] = "official"
    out["source"] = "bea.gov"
    return out


def build():
    ff = load_forex_factory_usd_high()
    fomc = load_fomc()
    bea = load_bea(2026)
    after_ff = lambda d: d[pd.to_datetime(d.date) > FF_LAST_DAY]
    cal = pd.concat([ff, after_ff(fomc), after_ff(bea)], ignore_index=True)
    cal["time_utc"] = pd.to_datetime(cal.time_utc, utc=True)
    cal = cal.sort_values(["date", "time_utc"]).reset_index(drop=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    cal.to_parquet(OUT, index=False)
    return ff, cal


def main():
    ff, cal = build()
    print("== Fill-table check (rows where Forex Factory kept the time)")
    print(check_fill_table_against_exact_rows(ff).to_string(index=False))
    print("\n== Calendar coverage (USD high impact)")
    print(cal.groupby(["source", "time_status"]).size().to_string())
    print("\n  by year/source:")
    print(cal.groupby([pd.to_datetime(cal.date).dt.year, "source"]).size().unstack(fill_value=0).to_string())
    print(f"\n  saved: {OUT.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
