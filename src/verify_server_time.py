"""Phase 2: prove the broker server-time rule in src/timeutils.py (spec §8).

Two independent checks on M1 gold data, 2022 onward:

1. Daily break: gold stops trading 17:00-18:00 New York every weekday. If
   server = New York + 7 h, trading must resume at 01:00 server time on every
   day of the year, including the weeks when the US and Europe have changed
   clocks on different dates.
2. NFP spike: on each US jobs-report day the biggest 1-minute move should land
   on the 08:30 New York minute. We find the spike minute in server time and
   test which clock rule turns it into 08:30 New York. Includes NFP days that
   fall in the US/EU clock-mismatch weeks, which separate the rules cleanly.

Run:  .venv/Scripts/python -m src.verify_server_time
Writes results/phase2/server_time_nfp.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src.calendar_events import OUT as CALENDAR_PATH
from src.config import PROJECT_ROOT
from src.timeutils import NEW_YORK, server_to_utc

M1_PATH = PROJECT_ROOT / "data" / "raw" / "XAUUSD.sim_M1.parquet"
OUT_DIR = PROJECT_ROOT / "results" / "phase2"
FROM = pd.Timestamp("2022-01-01")
SPIKE_MULTIPLE = 3

# Candidate rules for the server clock: name -> function(naive server times) -> UTC
RULES = {
    "New York + 7h (US DST)": server_to_utc,
    "EU DST (UTC+2/+3 on EU dates)": lambda s: pd.Series(s).dt.tz_localize(
        "Europe/Athens", ambiguous="NaT", nonexistent="NaT").dt.tz_convert("UTC"),
    "fixed UTC+2": lambda s: (pd.Series(s) - pd.Timedelta(hours=2)).dt.tz_localize("UTC"),
    "fixed UTC+3": lambda s: (pd.Series(s) - pd.Timedelta(hours=3)).dt.tz_localize("UTC"),
}


def load_m1():
    m1 = pd.read_parquet(M1_PATH)
    m1 = m1[m1.time_server >= FROM].reset_index(drop=True)
    m1["abs_ret"] = (m1.close / m1.open - 1).abs()
    return m1


def daily_break_check(m1):
    """Server time at which trading resumes after each weekday's daily break."""
    gap = m1.time_server.diff()
    resume = m1.loc[(gap >= pd.Timedelta(minutes=30)) & (gap < pd.Timedelta(hours=12)), "time_server"]
    resume = resume[resume.dt.dayofweek < 5]          # skip Sunday reopen
    counts = resume.dt.strftime("%H:%M").value_counts()
    print("== Check 1: daily break — server time trading resumes (weekdays, 2022+)")
    for hhmm, n in counts.head(6).items():
        print(f"  {hhmm}  {n:5} days")
    # The broker reopens a few minutes after 18:00 New York, so accept 01:00-01:10 server
    in_window = resume.dt.strftime("%H:%M").between("01:00", "01:10")
    share = in_window.mean()
    print(f"  -> {share:.1%} of days resume 01:00-01:10 server (= just after 18:00 New York under NY+7h)")
    # The weeks where US and EU clocks disagree are the real test
    ny = server_to_utc(resume).dt.tz_convert(NEW_YORK)
    eu_offset = resume.dt.tz_localize("Europe/Athens", ambiguous="NaT", nonexistent="NaT")
    mismatch = (ny.dt.tz_localize(None) - resume).dt.total_seconds().values != \
               (eu_offset.dt.tz_convert(NEW_YORK).dt.tz_localize(None) - resume).dt.total_seconds().values
    print(f"  US/EU mismatch-week days: {mismatch.sum()}, of which resume 01:00-01:10: {in_window[mismatch].sum()}"
          "  (an EU-DST server would resume at 00:0x or 02:0x on these days)")
    return share


def nfp_check(m1):
    cal = pd.read_parquet(CALENDAR_PATH)   # official NFP dates (FRED), 2022 -> now
    nfp_days = cal[(cal.event == "NFP") & (cal.time_utc < pd.Timestamp.now(tz="UTC"))].date.drop_duplicates()
    nfp_days = [d for d in nfp_days if pd.Timestamp(d) >= FROM]

    rows = []
    for day in nfp_days:
        # NFP is between 14:30 and 16:30 server under every candidate rule; look at 13:00-18:00 server
        win = m1[(m1.time_server >= pd.Timestamp(day) + pd.Timedelta(hours=13)) &
                 (m1.time_server < pd.Timestamp(day) + pd.Timedelta(hours=18))]
        if win.empty:
            continue
        typical = win.abs_ret.median()
        row = {"date": day}
        for name, rule in RULES.items():
            ny = rule(win.time_server).dt.tz_convert(NEW_YORK).dt.strftime("%H:%M").values
            at_release = win.abs_ret[(ny == "08:30") | (ny == "08:31")]
            # The 08:30 minute (or the next, if the print lands late) must be a clear spike
            row[name] = bool(len(at_release)) and at_release.max() >= SPIKE_MULTIPLE * typical
        ny_day = pd.Timestamp(day).tz_localize(NEW_YORK)
        row["us_summer"] = bool(ny_day.dst())
        row["us_eu_mismatch"] = bool(ny_day.dst()) != bool(pd.Timestamp(day).tz_localize("Europe/Athens").dst())
        rows.append(row)
    table = pd.DataFrame(rows)

    print(f"\n== Check 2: is 08:30 New York (after conversion) a spike >= {SPIKE_MULTIPLE}x a typical minute?")
    print(f"  NFP days tested: {len(table)}  (summer {table.us_summer.sum()}, winter {(~table.us_summer).sum()}, "
          f"US/EU mismatch weeks {table.us_eu_mismatch.sum()})")
    print(f"  {'rule':32} {'all':>5} {'summer':>7} {'winter':>7} {'mismatch':>9}")
    for name in RULES:
        s = table[name]
        print(f"  {name:32} {s.mean():5.0%} {s[table.us_summer].mean():7.0%} "
              f"{s[~table.us_summer].mean():7.0%} {s[table.us_eu_mismatch].mean():9.0%}")
    return table


def nfp_plot(m1, table):
    """Average |1-min return| around 08:30 New York, summer vs winter, after conversion."""
    m1 = m1.copy()
    m1["ny"] = server_to_utc(m1.time_server).dt.tz_convert(NEW_YORK)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    for summer, label in [(True, "US summer time (server UTC+3)"), (False, "US winter time (server UTC+2)")]:
        curves = []
        for day in table[table.us_summer == summer].date:
            t0 = pd.Timestamp(f"{day} 08:30", tz=NEW_YORK)
            w = m1[(m1.ny >= t0 - pd.Timedelta(minutes=30)) & (m1.ny <= t0 + pd.Timedelta(minutes=30))]
            minutes = ((w.ny - t0).dt.total_seconds() // 60).astype(int)
            curves.append(pd.Series(w.abs_ret.values * 1e4, index=minutes.values))
        avg = pd.concat(curves, axis=1).mean(axis=1).sort_index()
        ax.plot(avg.index, avg.values, marker=".", label=f"{label}, n={len(curves)}")
    ax.axvline(0, color="grey", ls="--", lw=1)
    ax.set_xlabel("minutes from 08:30 New York (after converting server time -> UTC -> New York)")
    ax.set_ylabel("average |1-min return| (basis points)")
    ax.set_title("Gold M1 around US NFP releases, 2022-2026")
    ax.legend()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / "server_time_nfp.png"
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    print(f"\n  plot saved: {path.relative_to(PROJECT_ROOT)}")


def main():
    m1 = load_m1()
    daily_break_check(m1)
    table = nfp_check(m1)
    nfp_plot(m1, table)


if __name__ == "__main__":
    main()
