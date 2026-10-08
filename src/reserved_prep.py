"""Reserved period 2010-2021 — data preparation only (Yash's one-time confirmation, 2026-10-08).

No backtest, signal, trade, return, price change or volatility is reported. Steps:
  calendar  - extend the news calendar to 2010-2021 (option a) and cross-check it with Forex Factory
  gold      - integrity of the gold bars already on disk: bars per year, gaps, server offset per year
  download  - H1/M1 for the other Experiment 3 markets: broker first, MetaQuotes-Demo where it has none
  symbols   - the same integrity checks on the downloads, NY 17:00 daily rebuild, overlap check
  login     - reconnect to the FTMO trial terminal and print the account it is logged in to

Server offset uses the Phase 2 NFP method, timing only: on each jobs-report day the minute with the
largest move inside +-2 h of 08:30 New York is located, and only its TIME is kept and reported.

Run:  .venv/Scripts/python -m src.reserved_prep <step> --purpose "..." --confirm "..."
Reports: results/reserved_prep/*.md (Markdown only)
"""
import argparse

import numpy as np
import pandas as pd

from src import calendar_events as ce
from src.config import PROJECT_ROOT
from src.data_access import read_prices
from src.exp3 import pull_data
from src.exp3.fx_splice import daily_from_h1
from src.timeutils import NEW_YORK

OUT = PROJECT_ROOT / "results" / "reserved_prep"
START, END = pd.Timestamp("2010-01-01", tz="UTC"), pd.Timestamp("2022-01-01", tz="UTC")
GAP_LIMIT = {"M1": pd.Timedelta(minutes=30), "H1": pd.Timedelta(hours=2)}
SPIKE_MULTIPLE = 3                     # Phase 2: the release minute must stand out 3x from a typical minute


# --- integrity checks (no prices reported) --------------------------------------------------

def unexplained_gaps(times_utc, tf):
    """Gaps longer than GAP_LIMIT that are not the weekend or the 17:00-18:00 New York daily break."""
    t = pd.Series(times_utc).reset_index(drop=True)
    gap = t.diff()
    start_ny, end_ny = t.shift().dt.tz_convert(NEW_YORK), t.dt.tz_convert(NEW_YORK)
    weekend = (start_ny.dt.dayofweek == 4) & end_ny.dt.dayofweek.isin([6, 0]) & (gap < pd.Timedelta(days=3.5))
    daily_break = ((start_ny.dt.hour >= 15) & (start_ny.dt.hour < 18) & (gap <= pd.Timedelta(hours=3)))
    big = (gap > GAP_LIMIT[tf]) & ~weekend & ~daily_break
    return pd.DataFrame({"start_utc": t.shift()[big], "hours": gap[big].dt.total_seconds() / 3600})


def year_table(bars, tf):
    """Bars, broker days, missing weekdays and unexplained gaps per calendar year (UTC)."""
    day = (bars.time_utc.dt.tz_convert(NEW_YORK) + pd.Timedelta(hours=7)).dt.date   # broker day (NY 17:00)
    gaps = unexplained_gaps(bars.time_utc, tf)
    rows = []
    for year, part in bars.groupby(bars.time_utc.dt.year):
        weekdays = pd.bdate_range(f"{year}-01-01", f"{year}-12-31")
        weekdays = {d.date() for d in weekdays if (d.month, d.day) not in ((1, 1), (12, 25))}
        present = set(day[part.index])
        g = gaps[gaps.start_utc.dt.year == year]
        rows.append({"year": year, "bars": len(part), "days": len(present),
                     "missing_weekdays": len(weekdays - present), "gaps": len(g),
                     "gap_hours": round(g.hours.sum(), 1),
                     "largest_gap": f"{g.hours.max():.1f} h on {g.loc[g.hours.idxmax(), 'start_utc']:%Y-%m-%d}" if len(g) else "-"})
    return pd.DataFrame(rows)


def nfp_timing(m1, nfp_days, tf="M1"):
    """Per NFP day: where the release-minute spike lands. Timing only.

    The window is set in SERVER time (release + 0.5 h to + 4.5 h, i.e. any clock from UTC+1 to UTC+4),
    so it does not depend on the clock rule being tested. With H1 bars (no M1 history) the spike is
    the 08:00-09:00 New York hour instead of the 08:30 minute.
    """
    bar = pd.Timedelta(minutes=1 if tf == "M1" else 60)
    rows = []
    t = m1.time_server
    for day in nfp_days:
        release = ce.ny_to_utc(day, "08:30").floor(bar)
        naive = release.tz_localize(None)
        win = m1[(t >= naive + pd.Timedelta(hours=0.5)) & (t < naive + pd.Timedelta(hours=4.5))]
        if len(win) < (30 if tf == "M1" else 3):
            rows.append({"date": day, "status": "no data"})
            continue
        size = (win.close / win.open - 1).abs()          # used only to locate the spike minute
        i = size.idxmax()
        clear = size[i] >= (SPIKE_MULTIPLE if tf == "M1" else 1.5) * size.median()
        lag = (win.time_utc[i] - release).total_seconds() / 60          # after our current UTC conversion
        minutes = (win.time_server[i] - naive).total_seconds() / 60     # server clock vs the real release
        offset = round(minutes / 60) if clear and abs(minutes - 60 * round(minutes / 60)) <= 1 else np.nan
        rows.append({"date": day, "status": "clear" if clear else "unclear",
                     "on_time": bool(clear and 0 <= lag <= (1 if tf == "M1" else 0)), "server_offset_h": offset,
                     "us_summer": bool(pd.Timestamp(day).tz_localize(NEW_YORK).dst())})
    return pd.DataFrame(rows)


def daily_break_resume(bars, by_month=False):
    """Modal server time at which trading resumes after the weekday daily break (Phase 2 check 1)."""
    t = bars.time_server.reset_index(drop=True)
    gap = t.diff()
    resume = t[(gap >= pd.Timedelta(minutes=30)) & (gap < pd.Timedelta(hours=12)) & (t.dt.dayofweek < 5)]
    summer = resume.dt.tz_localize(NEW_YORK, ambiguous="NaT", nonexistent="NaT").map(
        lambda x: bool(x.dst()) if pd.notna(x) else None)
    key = resume.dt.strftime("%Y-%m") if by_month else resume.dt.year
    rows = []
    for k, r in resume.groupby(key):
        mode = lambda s: (s.dt.floor("10min").dt.strftime("%H:%M").mode().iloc[0] if len(s) else "-")
        ny = bars.time_utc.reset_index(drop=True)[r.index].dt.tz_convert(NEW_YORK).dt.tz_localize(None)
        share = (ny.dt.strftime("%H:%M").between("18:00", "18:10")).mean()
        rows.append({"period": k, "resume_server_US_summer": mode(r[summer[r.index] == True]),
                     "resume_server_US_winter": mode(r[summer[r.index] == False]),
                     "resume_NY_after_conversion": mode(ny), "share_18:00-18:10_NY": f"{share:.0%}"})
    return pd.DataFrame(rows)


def offset_table(timing):
    rows = []
    for year, g in timing.groupby(pd.to_datetime(timing.date).dt.year):
        clear = g[g.status == "clear"].astype({"us_summer": bool, "on_time": bool})
        counts = lambda s: ", ".join(f"+{v:g} ({n})" for v, n in s.dropna().value_counts().sort_index().items()) or "-"
        rows.append({"year": year, "nfp_days": len(g), "clear_spikes": len(clear),
                     "spike_at_08:30_NY": f"{int(clear.on_time.sum())}/{len(clear)}",
                     "server_UTC+_US_summer (days)": counts(clear[clear.us_summer].server_offset_h),
                     "server_UTC+_US_winter (days)": counts(clear[~clear.us_summer].server_offset_h)})
    return pd.DataFrame(rows)


def md(df):
    cols = list(df.columns)
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(lines)


CALENDAR_PATH_2010_2021 = ce.RESERVED_OUT


def reserved_nfp_days():
    cal = pd.read_parquet(CALENDAR_PATH_2010_2021)
    return sorted(cal[cal.event == "NFP"].date.unique())


# --- steps ----------------------------------------------------------------------------------

def step_calendar(purpose, confirm):
    cal, meetings = ce.build_reserved(ce.fred_key(), purpose, confirm)
    cal.to_parquet(ce.RESERVED_OUT, index=False)
    ff = ce.load_forex_factory_usd_high(ce.RESERVED_FROM, ce.RESERVED_TO + pd.Timedelta(days=1), purpose, confirm,
                                        high_only=False)
    check = ce.cross_check_with_forex_factory(cal, ff, ce.RESERVED_FROM, ce.RESERVED_TO, ce.FF_NAMES_RESERVED)

    detail = []
    for event, names in ce.FF_NAMES_RESERVED.items():
        ours = cal[cal.event == event]
        theirs = ff[ff.event.isin(names)]
        for d in sorted(set(ours.date) - set(theirs.date)):
            detail.append((event, d, "ours only", ours[ours.date == d].time_utc.iloc[0].tz_convert(NEW_YORK).strftime("%H:%M"), "-"))
        for d in sorted(set(theirs.date) - set(ours.date)):
            ft = theirs[theirs.date == d].time_utc.dropna()
            detail.append((event, d, "FF only", "-", ft.iloc[0].tz_convert(NEW_YORK).strftime("%H:%M") if len(ft) else "no time"))
        exact = theirs[theirs.time_status == "exact"].drop_duplicates("date").set_index("date").time_utc
        for r in ours[ours.date.isin(exact.index)].itertuples():
            if r.time_utc != exact[r.date]:
                detail.append((event, r.date, "time differs", r.time_utc.tz_convert(NEW_YORK).strftime("%H:%M"),
                               exact[r.date].tz_convert(NEW_YORK).strftime("%H:%M")))
    detail = pd.DataFrame(detail, columns=["event", "date", "kind", "ours_NY", "FF_NY"])

    jan = []                       # does "ISM one business day later in January" hold before 2022?
    for year in range(2010, 2022):
        m = pd.Timestamp(f"{year}-01-01")
        for event, n, names in (("ISM manufacturing", 1, ce.FF_NAMES["ISM manufacturing"]),
                                ("ISM services", 3, ce.FF_NAMES_RESERVED["ISM services"])):
            ffd = sorted(d for d in ff[ff.event.isin(names)].date if d.year == year and d.month == 1)
            jan.append({"year": year, "event": event, "FF": ", ".join(map(str, ffd)) or "-",
                        "nth_business_day": ce.nth_business_day(m, n).date(),
                        "one_later": ce.nth_business_day(m, n + 1).date(),
                        "rule_holds": bool(ffd) and ffd[0] == ce.nth_business_day(m, n + 1).date()})
    jan = pd.DataFrame(jan)

    per_year = cal.groupby([pd.to_datetime(cal.date).dt.year, "event"]).size().unstack(fill_value=0)
    sources = cal[cal.event == "FOMC decision"].source.value_counts()
    L = ["# News calendar 2010-2021 (option a) — build and Forex Factory cross-check", "",
         f"Saved: `data/processed/calendar_usd_high_2010_2021.parquet` ({len(cal)} events, "
         f"{cal.date.min()} to {cal.date.max()}). The 2022+ calendar file is unchanged.", "",
         "## Events per year", "", md(per_year.T.reset_index()), "",
         "## FOMC statement time source", "", md(sources.rename_axis("source").reset_index()), "",
         f"Fed pages list {len(meetings)} meetings/calls/votes; {meetings.statement_path.notna().sum()} have a statement, "
         f"{meetings.presser_path.notna().sum()} a press conference.", "",
         "## Cross-check with Forex Factory (2010-2021, USD rows of any impact level)", "", md(check), "",
         "time_checked = days where FF kept an exact time; ~half of FF rows lost their time.", "",
         "## ISM in January: one business day later?", "", md(jan), "",
         "## Every mismatch", "", md(detail) if len(detail) else "None."]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "calendar_check.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(check.to_string(index=False))
    print(f"mismatch rows: {len(detail)}; January rule holds {int(jan.rule_holds.sum())}/{len(jan)}")


def step_gold(purpose, confirm):
    nfp = reserved_nfp_days()
    L = ["# Gold (XAUUSD.sim) 2010-2021 — integrity checks (already downloaded; not re-downloaded)", "",
         "Gaps = longer than 30 min (M1) / 2 h (H1), not a weekend or the 17:00-18:00 New York break. "
         "Missing weekdays exclude 1 Jan and 25 Dec.", ""]
    for tf in ("H1", "M15", "M1"):
        cols = ["time_utc", "time_server", "open", "close"] if tf == "M1" else ["time_utc"]
        bars = read_prices("XAUUSD.sim", tf, START, END, columns=cols, purpose=purpose, confirm=confirm).reset_index(drop=True)
        L += [f"## {tf}: {len(bars)} bars, first {bars.time_utc.min()}", "",
              md(year_table(bars, "M1" if tf == "M15" else tf)), ""]
        if tf == "M1":
            timing = nfp_timing(bars, nfp)
            L += ["## Daily break: server time trading resumes (NY+7h rule -> 01:00 all year; "
                  "fixed UTC+2 -> 00:00 in US summer, 01:00 in winter)", "", md(daily_break_resume(bars)), "",
                  "### 2021 by month", "", md(daily_break_resume(bars[bars.time_server.dt.year == 2021], by_month=True)), ""]
            L += ["## Server clock per year (NFP spike timing). NY+7h rule = UTC+3 in US summer, UTC+2 in US winter. "
                  "spike_at_08:30_NY = spike lands on 08:30-08:31 New York after our current UTC conversion", "",
                  md(offset_table(timing)), ""]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "gold_integrity.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


# MetaQuotes-Demo only where the broker has no 2010-2021 history (found by the broker download:
# no FX before 2025, Nasdaq 100 only from 2014-09-15). Nasdaq is pulled for the whole period so
# 2014-09 to 2021 can be checked against the broker.
METAQUOTES_MARKETS = ("Nasdaq 100", "EURUSD", "USDJPY", "AUDUSD")


def step_download(purpose, confirm, source):
    markets = METAQUOTES_MARKETS if source == "metaquotes" else pull_data.RESERVED_MARKETS
    pull_data.pull_reserved(purpose, confirm, source, markets=markets)


OVERLAP_NAMES = {"US100": ("US100", "NAS100", "USTEC", "NDX100")}


def overlap_table(broker, mq):
    """Per year: common H1 hours and the share whose closes agree within 0.05%, for MetaQuotes shifts -1/0/+1 h."""
    b = broker.drop_duplicates("time_utc").set_index("time_utc").close
    rows = []
    for year in sorted(b.index.year.unique()):
        row = {"year": year}
        for shift in (-1, 0, 1):
            m = mq.assign(time_utc=mq.time_utc + pd.Timedelta(hours=shift)).drop_duplicates("time_utc").set_index("time_utc").close
            j = pd.concat([b[b.index.year == year].rename("b"), m.rename("m")], axis=1, join="inner")
            agree = ((j.b - j.m).abs() <= 0.0005 * j.b).mean() if len(j) else np.nan
            row[f"shift {shift:+d}h: common / agree"] = f"{len(j)} / {agree:.0%}" if len(j) else "0 / -"
        rows.append(row)
    return pd.DataFrame(rows)


def weekly_open_table(server_times):
    """Per year: server time of the week's first bar minus Sunday 17:00 New York (in UTC), US winter / summer."""
    t = pd.Series(server_times).reset_index(drop=True)
    first = t[t.diff() > pd.Timedelta(hours=24)]
    sunday = first.dt.normalize() - pd.to_timedelta((first.dt.dayofweek + 1) % 7, unit="D")
    ny_open = (sunday + pd.Timedelta(hours=17)).dt.tz_localize(NEW_YORK)
    hours = ((first - ny_open.dt.tz_convert("UTC").dt.tz_localize(None)).dt.total_seconds() / 3600).round()
    summer = ny_open.map(lambda x: bool(x.dst()))
    rows = []
    for year, h in hours.groupby(first.dt.year):
        mode = lambda x: f"+{x.mode().iloc[0]:g} ({(x == x.mode().iloc[0]).sum()}/{len(x)})" if len(x) else "-"
        rows.append({"year": year, "US winter": mode(h[~summer[h.index]]), "US summer": mode(h[summer[h.index]])})
    return pd.DataFrame(rows)


def clock_summary(offsets):
    """'+2 all year' style summary of an offset table: per year, the US-summer / US-winter clock."""
    parts = [f"{r.year}: {r['server_UTC+_US_summer (days)'].split(' ')[0]}/{r['server_UTC+_US_winter (days)'].split(' ')[0]}"
             for _, r in offsets.iterrows()]
    return "; ".join(parts)


def step_symbols(purpose, confirm):
    """Integrity of the 2010-2021 downloads, per market and source. Prices are never reported."""
    nfp = reserved_nfp_days()
    root = pull_data.RESERVED_PROCESSED
    load = lambda path, cols=None: read_prices(None, None, START, END, columns=cols, purpose=purpose,
                                               confirm=confirm, path=path).reset_index(drop=True)
    summary, L = [], ["# Other markets 2010-2021 — download integrity (no prices or returns reported)", "",
                      "Gaps = longer than 30 min (M1) / 2 h (H1), not a weekend or a break starting 15:00-18:00 New York. "
                      "Clock = server UTC offset found from NFP spike timing (US summer / US winter).", ""]
    for source in ("broker", "metaquotes"):
        for h1_path in sorted((root / source).glob("*_H1.parquet")):
            symbol = h1_path.name[:-len("_H1.parquet")]
            m1_path = h1_path.with_name(f"{symbol}_M1.parquet")
            h1 = load(h1_path, ["time_utc", "time_server"])
            m1 = load(m1_path, ["time_utc", "time_server", "open", "close"]) if m1_path.exists() else None
            L += [f"## {symbol} ({source})", ""]
            rec = {"symbol": symbol, "source": source, "H1_first": f"{h1.time_server.min():%Y-%m-%d}", "H1_bars": len(h1)}
            L += ["### H1", "", md(year_table(h1, "H1")), ""]
            if m1 is None:                                # no M1 history: clock from the NFP hour on H1
                offsets = offset_table(nfp_timing(load(h1_path, ["time_utc", "time_server", "open", "close"]), nfp, "H1"))
                rec.update({"M1_first": "none", "clock": clock_summary(offsets)})
                L += ["### Clock per year (NFP hour on H1; no M1 history before 2022)", "", md(offsets), ""]
                L += ["### Week open: server time minus Sunday 17:00 New York (UTC), hours (weeks)", "",
                      "Same in every year = the week opens at server midnight with a clock that follows summer time. "
                      "Fixed UTC+2 would show +2 all year. This cannot separate European from US summer-time dates.", "",
                      md(weekly_open_table(load(h1_path, ["time_server"]).time_server)), ""]
            else:
                yt = year_table(m1, "M1")
                offsets = offset_table(nfp_timing(m1, nfp))
                rec.update({"M1_first": f"{m1.time_server.min():%Y-%m-%d}", "M1_bars": len(m1),
                            "M1_gaps": int(yt.gaps.sum()), "M1_missing_weekdays": int(yt.missing_weekdays.sum()),
                            "clock": clock_summary(offsets)})
                L += ["### M1", "", md(yt), "", "### Clock per year (NFP spike timing)", "", md(offsets), "",
                      "### Daily break (M1): resume time", "", md(daily_break_resume(m1)), ""]
            if source == "metaquotes":                    # days rebuilt at the New York 17:00 boundary
                h1_full = load(h1_path)
                d1 = daily_from_h1(h1_full)
                d1.to_parquet(h1_path.with_name(f"{symbol}_D1_ny17.parquet"), index=False)
                weekend = int((pd.to_datetime(d1.server_date).dt.dayofweek >= 5).sum())
                rec["D1_rebuilt"] = len(d1)
                L += [f"Daily bars rebuilt at New York 17:00: {len(d1)} (weekend-dated: {weekend}).", ""]
            summary.append(rec)
    for broker_h1 in sorted((root / "broker").glob("*_H1.parquet")):     # overlap: both sources, same market
        stem = broker_h1.name.split(".")[0]
        mq = [p for p in (root / "metaquotes").glob("*_H1.parquet") if p.name.split("_")[0] in OVERLAP_NAMES.get(stem, ())]
        if mq:
            L += [f"## Overlap {broker_h1.name[:-11]} (broker) vs {mq[0].name[:-11]} (MetaQuotes), H1", "",
                  "Share of common hours whose closes agree within 0.05%, with MetaQuotes shifted by -1/0/+1 h "
                  "(on each source's current UTC conversion). The best shift shows any clock difference.", "",
                  md(overlap_table(load(broker_h1, ["time_utc", "close"]), load(mq[0], ["time_utc", "close"]))), ""]
    summary = pd.DataFrame(summary)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "markets_integrity.md").write_text("\n".join(L[:4] + ["## Summary", "", md(summary.fillna("-")), ""] + L[4:]) + "\n",
                                              encoding="utf-8")
    print(summary.drop(columns=["clock"], errors="ignore").to_string(index=False))


def step_reconvert(purpose, confirm):
    """Re-convert pre-2021 broker bars to UTC with the measured fixed UTC+2 clock (timeutils), from raw files.

    Gold: process_prices + spread_model (the estimated spread depends on the London hour of time_utc).
    Other broker markets: data/raw/reserved/broker -> data/processed/reserved/broker.
    2022+ gold rows must come out identical; checked here.
    """
    from src import process_prices, spread_model
    from src.data_access import read_full_file_for_data_prep
    after_2022 = lambda tf: pd.util.hash_pandas_object(
        read_prices("XAUUSD.sim", tf, END, None).reset_index(drop=True)).sum()
    before = {tf: after_2022(tf) for tf in ("H1", "M15", "M1")}
    process_prices.main(purpose, confirm)
    spread_model.main(purpose, confirm)
    unchanged = {tf: bool(after_2022(tf) == before[tf]) for tf in before}
    print("gold 2022+ rows unchanged:", unchanged)
    assert all(unchanged.values())
    for raw_path in sorted((pull_data.RESERVED_RAW / "broker").glob("*.parquet")):
        bars = pull_data.to_utc(read_full_file_for_data_prep(raw_path, purpose, confirm))
        bars.to_parquet(pull_data.RESERVED_PROCESSED / "broker" / raw_path.name, index=False)
        print("re-converted", raw_path.name)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("step", choices=["calendar", "gold", "download", "symbols", "reconvert", "login"])
    ap.add_argument("--source", choices=["broker", "metaquotes"], default="broker")
    ap.add_argument("--purpose")
    ap.add_argument("--confirm")
    a = ap.parse_args()
    if a.step == "calendar":
        step_calendar(a.purpose, a.confirm)
    elif a.step == "gold":
        step_gold(a.purpose, a.confirm)
    elif a.step == "download":
        step_download(a.purpose, a.confirm, a.source)
    elif a.step == "symbols":
        step_symbols(a.purpose, a.confirm)
    elif a.step == "reconvert":
        step_reconvert(a.purpose, a.confirm)
    elif a.step == "login":
        print(pull_data.confirm_broker_login())


if __name__ == "__main__":
    main()
