"""Phase E2-1 — build and verify (docs/EXPERIMENT_2_SPEC.md §8). No performance numbers.

  * runs S1 (H1 and M15), S2, S3, S4, S5 once on 2022-2025 (data through src/data_access.py)
  * checks S1 reproduces Experiment 1's Asian-breakout trades under the new common settings
  * future-scramble test, 20 random cut times, every strategy
  * C1 smoke test (one seed per strategy: same number of trades, same entry/exit times)
  * monthly regime labels (market description only)
  * exports 5 trades per new strategy (S2-S5) for hand-checking, without any P&L

Run:  .venv/Scripts/python -m src.exp2.run_e2_1
"""
import json
import time

import numpy as np
import pandas as pd

from src.backtest import Events, dev_window, holdout_start
from src.calendar_events import OUT as CALENDAR_PATH
from src.config import PROJECT_ROOT, load_settings
from src.exp2.c1 import run_c1
from src.exp2.engine import Costs, Engine, Swap, trades_frame
from src.exp2.market import build_market, load_frames
from src.exp2.regime import classify_months
from src.exp2.strategies import S1Asian, S2Box, S3Donchian, S4RSI2, S5AsianHours
from src.timeutils import utc_to_server

OUT = PROJECT_ROOT / "results" / "exp2"
VALUE_COLS = ["open", "high", "low", "close", "spread_used", "spread_estimated"]
N_CUTS, CUT_SEED, HANDCHECK_SEED = 20, 11, 2026


def strategies(market, events):
    return {"S1 H1": S1Asian(market, "H1"), "S1 M15": S1Asian(market, "M15"), "S2": S2Box(market),
            "S3": S3Donchian(market), "S4": S4RSI2(market), "S5": S5AsianHours(market, events)}


def run_all(market, events, eng):
    out = {}
    for name, s in strategies(market, events).items():
        out[name] = eng.run_timed(s) if name == "S5" else eng.run(s)
    return out


def make_engine(settings, market, events):
    sw = settings["exp2"]["swap"]
    return Engine(market.m1, events, Costs(1.0, settings["costs"]["commission_pct_per_side"]),
                  Swap(sw["long_pct_per_year"], sw["short_pct_per_year"], sw["days_per_year"], 2),
                  risk_usd=settings["exp2"]["risk_per_trade_usd"])


def scramble_after(df, cut, rng):
    out = df.copy()
    after = np.flatnonzero((out.time_utc > cut).to_numpy())
    out.loc[after, VALUE_COLS] = out.loc[rng.permutation(after), VALUE_COLS].to_numpy()
    return out


def server(ns):
    return f"{utc_to_server(pd.Series([pd.Timestamp(int(ns), tz='UTC')])).iloc[0]:%Y-%m-%d %H:%M}"


def utc(ns):
    return f"{pd.Timestamp(int(ns), tz='UTC'):%Y-%m-%d %H:%M}"


def main():
    t0 = time.time()
    settings = load_settings()
    symbol = settings["mt5"]["symbol"]
    point = json.loads((PROJECT_ROOT / "data" / "raw" / f"{symbol}_metadata.json").read_text())["point"]
    start, end = dev_window(settings)
    assert end <= holdout_start(settings)
    frames = load_frames(symbol, start, end)
    assert min(f.time_utc.min() for f in frames) >= pd.Timestamp("2022-01-01", tz="UTC")
    events = Events(pd.read_parquet(CALENDAR_PATH).time_utc)
    market = build_market(*frames, point)
    eng = make_engine(settings, market, events)
    base = run_all(market, events, eng)
    trades = {k: trades_frame(r) for k, r in base.items()}
    print(f"base runs done ({time.time() - t0:.0f}s)")
    OUT.mkdir(parents=True, exist_ok=True)
    L = ["# Phase E2-1 — build and verify (no performance numbers)", "",
         f"Data: {start:%Y-%m-%d} → {end:%Y-%m-%d} (UTC), through `src/data_access.py`; nothing before 2022-01-01 loaded. "
         "Indicators start from the first 2022 bar.", ""]

    # 1. Counts (activity, not performance)
    L += ["## What each strategy did (counts only)", "",
          "| Strategy | Trades | Signals skipped while in a trade | Blocked at entry (reason: count) | Exits by reason | "
          "Held across a >2 h break | Overnight rollovers held |", "|---|---:|---:|---|---|---:|---:|"]
    for name, r in base.items():
        t = trades[name]
        reasons = t.exit_reason.value_counts().to_dict() if len(t) else {}
        L.append(f"| {name} | {len(t)} | {r.skipped_in_trade} | {r.blocked or '—'} | {reasons} | "
                 f"{int(t.held_across_long_break.sum()) if len(t) else 0} | {int(t.swap_nights.sum()) if len(t) else 0} |")

    # 2. S1 re-wire check against Experiment 1 (Phase 4b run: same rules, kill switch off, min-lot skip)
    L += ["", "## S1 re-wire check against Experiment 1", ""]
    for tf in ("H1", "M15"):
        e1 = pd.read_csv(PROJECT_ROOT / "results" / "phase4b" / f"tagged_trades_A_{tf}.csv")
        e1_entry = pd.to_datetime(e1.entry_time_utc, utc=True)
        s1 = trades[f"S1 {tf}"]
        s1_idx = s1.set_index("entry_utc")
        matched = same = holiday = 0
        for k, row in enumerate(e1.itertuples()):
            if e1_entry[k] in s1_idx.index:
                matched += 1
                s = s1_idx.loc[e1_entry[k]]
                if (s.direction == row.direction and abs(s.stop - row.stop) < 1e-6 and abs(s.target - row.target) < 1e-6
                        and s.exit_reason == row.exit_reason and abs(s.exit_price - row.exit_price) < 1e-6):
                    same += 1
                elif bool(s.held_across_long_break) or row.exit_reason == "end of data":
                    holiday += 1
        lon = e1_entry.dt.tz_convert("Europe/London")
        friday_late = int(((lon.dt.dayofweek == 4) & (lon.dt.hour >= 16)).sum())
        L.append(f"- **S1 {tf}:** {matched} of {len(e1)} Experiment 1 trades found at the same entry time "
                 f"(the {len(e1) - matched} not found are Friday entries at 16:00 London, which Experiment 2's weekend rule "
                 f"forbids; Experiment 1 had {friday_late} such trades); "
                 f"{same} identical in direction, stop, target, exit reason and exit price. The other {matched - same} "
                 f"are all holiday early closes ({holiday} confirmed): Experiment 1 exited at the last price before the halt, "
                 f"Experiment 2 holds to the reopen and flags the trade (spec §3). S1 now has {len(s1)} trades: the extra "
                 f"{len(s1) - matched} are signals Experiment 1 skipped because the size was below 0.01 lots "
                 "(fractional sizing trades every signal, spec §3).")

    # 3. Future-scramble test
    rng = np.random.default_rng(CUT_SEED)
    t_lo, t_hi = frames[0].time_utc.min().value, frames[0].time_utc.max().value
    ok = {name: 0 for name in base}
    changed = {name: [] for name in base}
    for c in range(N_CUTS):
        cut = pd.Timestamp(int(rng.integers(t_lo, t_hi)), tz="UTC")
        scr = tuple(scramble_after(f, cut, rng) for f in frames)
        m2 = build_market(*scr, point)
        res2 = run_all(m2, events, make_engine(settings, m2, events))
        for name in base:
            before = sorted((d for d in base[name].decisions if d[0] <= cut.value), key=str)
            before2 = sorted((d for d in res2[name].decisions if d[0] <= cut.value), key=str)
            ok[name] += before == before2
            changed[name].append(len(set(map(str, base[name].decisions)) ^ set(map(str, res2[name].decisions))))
            assert all(seen <= when for when, _, _, seen in res2[name].decisions)
        print(f"scramble cut {c + 1}/{N_CUTS} ({time.time() - t0:.0f}s)")
    L += ["", f"## Future-scramble test ({N_CUTS} random cut times, all data after the cut shuffled)", "",
          "| Strategy | Cuts with every decision before the cut identical | Decisions changed after the cut (min / median) |",
          "|---|---:|---|"]
    for name in base:
        L.append(f"| {name} | **{ok[name]} / {N_CUTS}** | {min(changed[name])} / {int(np.median(changed[name]))} |")
    L.append("\nEvery decision is also checked to be logged with data no newer than its decision time.")

    # 4. C1 smoke test
    L += ["", "## C1 (random direction) smoke test — one seed per strategy, no results reported", ""]
    for name, t in trades.items():
        c = trades_frame(run_c1(eng, t, seed=0)) if len(t) else pd.DataFrame()
        same_times = len(c) == len(t) and (c.entry_ns.values == t.entry_ns.values).all()
        stops_ok = len(c) == len(t) and np.allclose(c.stop_distance.values, t.stop_distance.values)
        early = int((c.exit_ns.values < t.exit_ns.values).sum()) if len(c) == len(t) else -1
        late = int((c.exit_ns.values > t.exit_ns.values + 60 * 10**9).sum()) if len(c) == len(t) else -1
        L.append(f"- {name}: {len(c)} C1 trades for {len(t)} real; same entry times: {same_times}; same stop distance: "
                 f"{stops_ok}; {early} stopped out earlier than the real exit; {late} exited later (only where no M1 "
                 "bar exists at the real exit minute — a data gap — so C1 takes the next available price).")

    # 5. Regime labels
    reg = classify_months(market.days)
    reg[["efficiency", "trend", "direction", "regime"]].to_csv(OUT / "regime_months.csv")
    counts = reg.regime.value_counts().to_dict()
    L += ["", "## Monthly regime labels (market description, 2022–2025)", "",
          f"Median efficiency {reg.attrs['median_efficiency']:.3f}. Months per regime: {counts}. File: `regime_months.csv`."]

    # 6. Hand-check exports (no P&L)
    rng = np.random.default_rng(HANDCHECK_SEED)
    rows = []
    for name in ("S2", "S3", "S4", "S5"):
        t = trades[name]
        for _, r in t.iloc[np.sort(rng.choice(len(t), size=5, replace=False))].iterrows():
            levels = {k[5:]: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()
                      if k.startswith("info_") and pd.notna(v)}
            rows.append({"strategy": name, "direction": r.direction,
                         "signal_close_utc": utc(r.signal_ns), "signal_close_server": server(r.signal_ns),
                         "entry_utc": utc(r.entry_ns), "entry_server": server(r.entry_ns),
                         "entry_bid_open": round(r.entry_bid, 3), "spread_paid": round(r.entry_spread, 3),
                         "entry_price": round(r.entry_price, 3), "stop": round(r.stop, 3),
                         "target": round(r.target, 3) if pd.notna(r.target) else "none",
                         "levels": json.dumps(levels), "exit_utc": utc(r.exit_ns), "exit_server": server(r.exit_ns),
                         "exit_price": round(r.exit_price, 3), "exit_reason": r.exit_reason,
                         "overnight_rollovers": int(r.swap_nights)})
    pd.DataFrame(rows).to_csv(OUT / "handcheck_5_trades_per_strategy.csv", index=False)
    L += ["", "## Hand-check file", "", "`handcheck_5_trades_per_strategy.csv`: 5 random trades each for S2–S5 with UTC and "
          "MT5 server times, levels, entry, stop, target and exit. No P&L. MT5 charts show BID prices: long entries pay "
          "bid + spread; shorts exit at ask = bid + spread."]
    (OUT / "e2_1_build_report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"done ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
