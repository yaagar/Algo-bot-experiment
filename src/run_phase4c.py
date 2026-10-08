"""Phase 4c — ONE-TIME filter confirmation on 2010-2021 (spec v1.5, §12).

Bots: A, and A + with-trend (adopted in v1.5). For M15 and H1:
  * official §11 verdicts, kill switch ON, three cost cases, C1 (200 seeds) each;
  * kill switch OFF runs, three cost cases, results per year in $ and R —
    the v1.5 decision rule is judged on A + with-trend, kill switch off, base costs:
    expectancy >= +0.10R per trade after costs AND profitable in >= 8 of 12 years;
  * C1 for the kill-switch-off base runs;
  * 2026 holdout period: A vs A + with-trend side by side — INFORMATION ONLY.
Spreads 2010-2021 use the 2026-based estimate (harsher than reality).
Run once.

Run:  .venv/Scripts/python -m src.run_phase4c
"""
import dataclasses
import json
import time

import numpy as np
import pandas as pd

from src import metrics
from src.backtest import Events, bot_a_chooser, build_days, load_bars, run, trades_frame
from src.calendar_events import OUT as CALENDAR_PATH
from src.config import PROJECT_ROOT, load_settings
from src.filters import daily_closes, trend_up_tags, with_trend_chooser
from src.run_phase3 import TFS, account_from, cost_cases, fmt_money, run_c1, with_times
from src.run_phase4 import london_window
from src.strategy_asian import Params

OUT = PROJECT_ROOT / "results" / "phase4c"
FIRST, LAST = "2010-01-01", "2021-12-31"
YEARS = list(range(2010, 2022))
MIN_R, MIN_YEARS = 0.10, 8
CASES = ["base", "spread x1.5", "commission 0.0025%"]


def add_net_r(t, contract):
    if len(t):
        t = t.copy()
        t["net_r"] = t.net_pnl / (t.stop_distance * t.lots * contract)
    return t


def per_year(t):
    rows = {}
    for y in YEARS:
        g = t[pd.to_datetime(t.date).dt.year == y] if len(t) else t
        rows[y] = {"n": len(g), "net": float(g.net_pnl.sum()) if len(g) else 0.0,
                   "exp": float(g.net_pnl.mean()) if len(g) else float("nan"),
                   "exp_r": float(g.net_r.mean()) if len(g) else float("nan"),
                   "win": float((g.net_pnl > 0).mean()) if len(g) else float("nan")}
    return rows


def overall(t):
    n = len(t)
    return {"n": n, "net": float(t.net_pnl.sum()) if n else 0.0, "exp": float(t.net_pnl.mean()) if n else float("nan"),
            "exp_r": float(t.net_r.mean()) if n else float("nan"), "gross_r": float(t.r_multiple.mean()) if n else float("nan")}


def main(purpose, confirm):
    """Reads 2010-2021: refused unless Yash's one-time confirmation is passed (src/data_access.py)."""
    t0 = time.time()
    settings = load_settings()
    symbol = settings["mt5"]["symbol"]
    meta = json.loads((PROJECT_ROOT / "data" / "raw" / f"{symbol}_metadata.json").read_text())
    point, contract = meta["point"], meta["contract_size"]
    start, end = london_window(FIRST, LAST)
    print(f"4c window (UTC): {start} -> {end}")
    m1 = load_bars(symbol, "M1", start, end, end, purpose, confirm)   # nothing after 2021-12-31
    calendar = pd.read_parquet(CALENDAR_PATH)
    events = Events(calendar.time_utc)
    p = Params.from_settings(settings)
    acct = account_from(settings, meta)
    no_kill = dataclasses.replace(acct, kill_switch_dd=float("inf"))
    seeds = settings["controls"]["c1_random_entry_seeds"]
    months = metrics.all_months(FIRST, LAST)
    costs = cost_cases(settings)
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"events in calendar before 2022: {(calendar.time_utc < pd.Timestamp('2022-01-01', tz='UTC')).sum()}")

    days, bots = {}, {}
    for tf, tf_min in TFS.items():
        days[tf] = build_days(m1, load_bars(symbol, tf, start, end, end, purpose, confirm), point)
        trend = trend_up_tags([d.date for d in days[tf]], daily_closes(m1)).to_dict()
        bots[tf] = {"A": bot_a_chooser(tf_min), "A + with-trend": with_trend_chooser(bot_a_chooser(tf_min), trend)}

    official, nokill, c1_nokill = {}, {}, {}
    for tf in TFS:
        for bot, chooser in bots[tf].items():
            for case in CASES:
                res = run(days[tf], chooser, p, costs[case], acct, events)
                a = add_net_r(trades_frame(res), contract)
                s = metrics.summarize(a, months, acct.initial_balance)
                nets = [float(t.net_pnl.sum()) if len(t) else 0.0
                        for t in run_c1(days["M15"], a, p, costs[case], acct, events, seeds)] if len(a) else [0.0]
                pct = metrics.c1_percentile(s["net_profit"], nets)
                passed, checks = metrics.strategy_verdict(s, pct)
                official[(tf, bot, case)] = {"s": s, "pct": pct, "passed": passed, "checks": checks,
                                             "kill": res.kill_switch_date, "c1_median": float(np.median(nets))}
                k = add_net_r(trades_frame(run(days[tf], chooser, p, costs[case], no_kill, events)), contract)
                nokill[(tf, bot, case)] = k
                if case == "base":
                    k.pipe(with_times).to_csv(OUT / f"trades_{tf}_{bot.replace(' + ', '_').replace('-', '')}_nokill.csv",
                                             index=False)
                    nets_nk = [float(t.net_pnl.sum()) if len(t) else 0.0
                               for t in run_c1(days["M15"], k, p, costs[case], no_kill, events, seeds)]
                    c1_nokill[(tf, bot)] = {"pct": metrics.c1_percentile(float(k.net_pnl.sum()), nets_nk),
                                           "median": float(np.median(nets_nk))}
                print(f"{tf:3} {bot:15} {case:18} official: {s['trades']:4} tr, net {fmt_money(s['net_profit']):>7}, "
                      f"kill {res.kill_switch_date}, {'PASS' if passed else 'FAIL'} | no-kill: {len(k)} tr, "
                      f"net {fmt_money(k.net_pnl.sum()):>7}, {k.net_r.mean():+.3f}R   ({time.time() - t0:.0f}s)")

    info_2026 = run_2026(settings, symbol, meta, p, acct, events, costs)
    write_report(official, nokill, c1_nokill, info_2026)
    print(f"done in {time.time() - t0:.0f}s -> {OUT.relative_to(PROJECT_ROOT)}")


def run_2026(settings, symbol, meta, p, acct, events, costs):
    """INFORMATION ONLY: A vs A + with-trend on the 2026 holdout period (kill switch on, as Phase 4)."""
    period = settings["periods"]["holdout"]
    start, end = london_window(period["start"], period["end"])
    m1 = load_bars(symbol, "M1", start, end, end)
    # trend needs 20 completed daily closes before 2026-01-01: use late-2025 dev data (already seen)
    history = load_bars(symbol, "M1", pd.Timestamp("2025-11-01", tz="UTC"), start, start)
    closes = daily_closes(pd.concat([history, m1], ignore_index=True))
    months = metrics.all_months(period["start"], period["end"])
    out = {}
    for tf, tf_min in TFS.items():
        days = build_days(m1, load_bars(symbol, tf, start, end, end), meta["point"])
        trend = trend_up_tags([d.date for d in days], closes).to_dict()
        for bot, chooser in {"A": bot_a_chooser(tf_min),
                             "A + with-trend": with_trend_chooser(bot_a_chooser(tf_min), trend)}.items():
            for case in CASES:
                t = add_net_r(trades_frame(run(days, chooser, p, costs[case], acct, events)), meta["contract_size"])
                s = metrics.summarize(t, months, acct.initial_balance)
                out[(tf, bot, case)] = {"s": s, "exp_r": float(t.net_r.mean()) if len(t) else float("nan")}
    return out


def write_report(official, nokill, c1_nokill, info_2026):
    L = ["# Phase 4c — filter confirmation on 2010–2021 (run once)", "",
         "Bots: **A** and **A + with-trend** (adopted in spec v1.5). Spreads before 2025-12-17 are the 2026-based "
         "estimate, which overstates costs when gold was cheaper (harsher test). Expectancy in R = net P&L ÷ the "
         "trade's initial risk in $.", ""]

    L += ["## Decision rule (spec v1.5) — A + with-trend, kill switch off, base costs", "",
          f"Continue only if expectancy ≥ **+{MIN_R:.2f}R** per trade after costs **and** profitable in ≥ **{MIN_YEARS} of 12** years "
          "(checked per timeframe).", "",
          "| TF | Trades | Expectancy (R, net) | Profitable years | Net P&L | Rule met? |", "|---|---:|---:|---:|---:|---|"]
    for tf in TFS:
        k = nokill[(tf, "A + with-trend", "base")]
        o, py = overall(k), per_year(k)
        good_years = sum(py[y]["net"] > 0 for y in YEARS)
        met = o["exp_r"] >= MIN_R and good_years >= MIN_YEARS
        L.append(f"| {tf} | {o['n']} | **{o['exp_r']:+.3f}R** | **{good_years} / 12** | {fmt_money(o['net'])} | "
                 f"**{'YES — continues' if met else 'NO — dropped'}** |")

    L += ["", "## Does the filter improve expectancy over plain A? (§12 4c — otherwise rejected)", "",
          "Kill switch off. Cells: expectancy per trade in R (net) / in $.", "",
          "| TF | Cost case | A | A + with-trend | Improves? |", "|---|---|---|---|---|"]
    for tf in TFS:
        for case in CASES:
            a, f = overall(nokill[(tf, "A", case)]), overall(nokill[(tf, "A + with-trend", case)])
            L.append(f"| {tf} | {case} | {a['exp_r']:+.3f}R / ${a['exp']:+.2f} | {f['exp_r']:+.3f}R / ${f['exp']:+.2f} | "
                     f"{'yes' if f['exp_r'] > a['exp_r'] else 'NO'} |")

    for tf in TFS:
        L += ["", f"## {tf} — per year, kill switch off", "",
              "Cells: trades / net P&L / expectancy ($) / expectancy (R).", "",
              "| Year | A base | A + with-trend base | A + with-trend spread ×1.5 | A + with-trend commission 0.0025% |",
              "|---|---|---|---|---|"]
        cols = [("A", "base"), ("A + with-trend", "base"), ("A + with-trend", "spread x1.5"),
                ("A + with-trend", "commission 0.0025%")]
        tables = [per_year(nokill[(tf, b, c)]) for b, c in cols]
        fmt = lambda r: "–" if r["n"] == 0 else f"{r['n']} / {fmt_money(r['net'])} / ${r['exp']:+.2f} / {r['exp_r']:+.3f}R"
        for y in YEARS:
            L.append(f"| {y} | " + " | ".join(fmt(t[y]) for t in tables) + " |")
        tot = [overall(nokill[(tf, b, c)]) for b, c in cols]
        L.append("| **All** | " + " | ".join(f"**{o['n']} / {fmt_money(o['net'])} / ${o['exp']:+.2f} / {o['exp_r']:+.3f}R**"
                                            for o in tot) + " |")
        L += ["", "C1 (kill switch off, base costs): " + "; ".join(
            f"{bot} beats {c1_nokill[(tf, bot)]['pct']:.1%} of C1 (C1 median {fmt_money(c1_nokill[(tf, bot)]['median'])})"
            for bot in ("A", "A + with-trend"))]

    L += ["", "## Official §11 verdicts (kill switch ON, 2010–2021)", "",
          "| TF | Bot | Cost case | Trades | Net | Avg month | Fewest profitable / 6-mo window | Max DD | FTMO breach | "
          "FTMO-flagged exits | Kill switch | Beats % of C1 | Verdict |",
          "|---|---|---|---:|---:|---:|---:|---:|---|---:|---|---:|---|"]
    for (tf, bot, case), r in official.items():
        s = r["s"]
        L.append(f"| {tf} | {bot} | {case} | {s['trades']} | {fmt_money(s['net_profit'])} | {fmt_money(s['avg_month'])} | "
                 f"{s['min_profitable_in_6m_window']} | {fmt_money(s['max_dd_usd'])} | "
                 f"{'no' if not s['ftmo_breached'] else 'YES ' + str(s['ftmo_breach'][1])} | {s['ftmo_flagged_exits']} | "
                 f"{r['kill'] or 'no'} | {r['pct']:.1%} | **{'PASS' if r['passed'] else 'FAIL'}** |")

    L += ["", "## 2026 holdout period — INFORMATION ONLY", "",
          "2026 has already been seen, so this can neither confirm nor reject the filter. Kill switch on, as in Phase 4. "
          "Plain A should equal the Phase 4 numbers (M15 62 trades / $572, H1 49 / $534 at base).", "",
          "| TF | Bot | Cost case | Trades | Net | Avg month | Expectancy (R) | Max DD | FTMO breach |",
          "|---|---|---|---:|---:|---:|---:|---:|---|"]
    for (tf, bot, case), r in info_2026.items():
        s = r["s"]
        L.append(f"| {tf} | {bot} | {case} | {s['trades']} | {fmt_money(s['net_profit'])} | {fmt_money(s['avg_month'])} | "
                 f"{r['exp_r']:+.3f}R | {fmt_money(s['max_dd_usd'])} | {'no' if not s['ftmo_breached'] else 'YES'} |")
    (OUT / "phase4c_report.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--purpose", required=True)
    ap.add_argument("--confirm", required=True)
    a = ap.parse_args()
    main(a.purpose, a.confirm)
