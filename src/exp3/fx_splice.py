"""FX history splice (Experiment 3 Change Log v1.1 — data-source addition, no rule change).

The broker's FX history starts 2025-05-20 (server day), and that first day is partial. Before it we use
MetaQuotes-Demo prices:
  1. MetaQuotes H1 bars (UTC, converted with its European-DST clock — see pull_data.py).
  2. Daily bars REBUILT from those H1 bars at the broker's day boundary (New York 17:00), because
     MetaQuotes' own D1 bars close at New York 18:00 for ~4 weeks a year (spec §4 rule).
  3. Checks on the overlap (every full broker day to 2026-09-30): the rebuilt daily bars vs the broker's,
     median and max difference of open/high/low/close.
  4. Splice: MetaQuotes before the broker's first FULL day, the broker's own data from then on.
     Spreads before the splice = the broker's open-hour p75 estimate (flagged estimated); all costs are FTMO's.
Output: data/processed/exp3/spliced/<symbol>_{D1,H1}.parquet and results/exp3/fx_splice_check.md.

Run:  .venv/Scripts/python -m src.exp3.fx_splice
"""
import json

import numpy as np
import pandas as pd

from src.data_access import read_prices
from src.exp3.markets import PROCESSED, RESULTS, SPECS_PATH
from src.timeutils import utc_to_server

FX = {"EURUSD.sim": ("EURUSD", 0.0001), "USDJPY.sim": ("USDJPY", 0.01), "AUDUSD.sim": ("AUDUSD", 0.0001)}
START = pd.Timestamp("2022-01-01", tz="UTC")
OVERLAP_END = pd.Timestamp("2026-10-01", tz="UTC")
SPLICED = PROCESSED / "spliced"
PRICE = ["open", "high", "low", "close"]


def read(path):
    return read_prices(None, None, START, None, path=path).reset_index(drop=True)


def daily_from_h1(h1):
    """Daily bars from H1 grouped by broker day (server date = New York + 7 h -> day ends 17:00 New York)."""
    day = utc_to_server(h1.time_utc).dt.date.to_numpy()
    g = h1.groupby(day, sort=True)
    first = g.time_utc.first()
    # bar time = broker midnight of that day, in UTC (17:00 New York the evening before)
    open_utc = (pd.to_datetime(pd.Series(first.index)) - pd.Timedelta(hours=7)).dt.tz_localize(
        "America/New_York").dt.tz_convert("UTC")
    return pd.DataFrame({"time_utc": open_utc.to_numpy(), "server_date": first.index,
                         "open": g.open.first().to_numpy(), "high": g.high.max().to_numpy(),
                         "low": g.low.min().to_numpy(), "close": g.close.last().to_numpy(),
                         "first_h1_utc": first.to_numpy()})


def first_full_day(h1):
    """First broker day whose H1 bars start in the day's first hour (the broker's first day is partial)."""
    d = daily_from_h1(h1)
    full = d[(d.first_h1_utc - d.time_utc) <= pd.Timedelta(hours=1)]
    return full.iloc[0]


def main():
    specs = json.loads(SPECS_PATH.read_text(encoding="utf-8"))
    SPLICED.mkdir(parents=True, exist_ok=True)
    L = ["# FX history splice check (Change Log v1.1)", "",
         "MetaQuotes-Demo server clock = European summer time (UTC+2/+3); converted to UTC with that rule. "
         "Daily bars rebuilt from its H1 at the New York 17:00 boundary. Overlap = every full broker day to 2026-09-30.", "",
         "| Symbol | Overlap days | H1 closes matched | H1 close diff median / max (pips) | Daily O/H/L/C diff median (pips) | "
         "Daily O/H/L/C diff max (pips) | MetaQuotes native D1 = NY 17:00 rebuild | Splice: broker from (UTC) | MetaQuotes days used |",
         "|---|---:|---:|---|---|---|---:|---|---:|"]
    for rec in specs["markets"]:
        sym = rec["symbol"]
        if sym not in FX:
            continue
        mq_sym, pip = FX[sym]
        b_h1, b_d1 = read(PROCESSED / f"{sym}_H1.parquet"), read(PROCESSED / f"{sym}_D1.parquet")
        m_h1 = read(PROCESSED / "metaquotes" / f"{mq_sym}_H1.parquet")
        m_d1_native = read(PROCESSED / "metaquotes" / f"{mq_sym}_D1.parquet")
        m_d1 = daily_from_h1(m_h1)

        splice = first_full_day(b_h1)                         # broker's first full day
        cut = splice.time_utc
        # overlap checks (full broker days only)
        bd = b_d1[(b_d1.time_utc >= cut) & (b_d1.time_utc + pd.Timedelta(days=1) <= OVERLAP_END)]
        j = bd.merge(m_d1, on="time_utc", suffixes=("_b", "_m"))
        diffs = np.abs(j[[f"{c}_b" for c in PRICE]].to_numpy() - j[[f"{c}_m" for c in PRICE]].to_numpy()) / pip
        hb = b_h1[(b_h1.time_utc >= cut) & (b_h1.time_utc < OVERLAP_END)].set_index("time_utc").close
        hm = m_h1.drop_duplicates("time_utc").set_index("time_utc").close
        hj = pd.concat([hb.rename("b"), hm.rename("m")], axis=1, join="inner")
        hd = (hj.b - hj.m).abs() / pip
        nat = m_d1_native.assign(server_date=m_d1_native.time_server.dt.date).merge(
            m_d1[["server_date"] + PRICE], on="server_date", suffixes=("", "_r"))
        native_same = np.isclose(nat[PRICE].to_numpy(), nat[[f"{c}_r" for c in PRICE]].to_numpy(), atol=1e-9).all(1)

        # splice: MetaQuotes before the cut, broker from the cut. MetaQuotes spreads are never used.
        est = int(rec["open_hour_p75_points"])
        pre_h1 = m_h1[m_h1.time_utc < cut][["time_utc"] + PRICE].assign(spread=0, spread_used=est, spread_estimated=True)
        pre_d1 = m_d1[m_d1.time_utc < cut][["time_utc"] + PRICE].assign(spread=0, spread_used=est, spread_estimated=True)
        cols = ["time_utc"] + PRICE + ["spread", "spread_used", "spread_estimated"]
        h1 = pd.concat([pre_h1, b_h1[b_h1.time_utc >= cut][cols]], ignore_index=True)
        d1 = pd.concat([pre_d1, b_d1[b_d1.time_utc >= cut][cols]], ignore_index=True)
        assert h1.time_utc.is_monotonic_increasing and d1.time_utc.is_monotonic_increasing
        h1["spread_used"] = h1.spread_used.astype("int64")
        d1["spread_used"] = d1.spread_used.astype("int64")
        h1.to_parquet(SPLICED / f"{sym}_H1.parquet", index=False)
        d1.to_parquet(SPLICED / f"{sym}_D1.parquet", index=False)

        rec.update({"data_dir": "spliced", "spliced_from_metaquotes_before_utc": str(cut),
                    "first_d1_utc": str(d1.time_utc.iloc[0]), "d1_bars": len(d1), "h1_bars": len(h1),
                    "d1_bars_estimated_pct": round(100 * d1.spread_estimated.mean(), 1),
                    "overlap_days": len(j),
                    "overlap_daily_diff_median_pips": dict(zip(PRICE, np.round(np.median(diffs, 0), 2).tolist())),
                    "overlap_daily_diff_max_pips": dict(zip(PRICE, np.round(diffs.max(0), 2).tolist()))})
        med, mx = np.median(diffs, 0), diffs.max(0)
        L.append(f"| {sym} | {len(j)} | {len(hj)} / {len(hb)} | {hd.median():.1f} / {hd.max():.1f} | "
                 f"{' / '.join(f'{v:.1f}' for v in med)} | {' / '.join(f'{v:.1f}' for v in mx)} | "
                 f"{native_same.sum()} / {len(nat)} | {cut:%Y-%m-%d %H:%M} | {int((m_d1.time_utc < cut).sum())} |")
        print(sym, "done")
    L += ["", "Days where MetaQuotes' native D1 differs from the NY 17:00 rebuild are the weeks when Europe and the "
          "US are on different summer-time settings (its day then ends at 18:00 New York); the rebuild is what is used."]
    SPECS_PATH.write_text(json.dumps(specs, indent=2), encoding="utf-8")
    (RESULTS / "fx_splice_check.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
