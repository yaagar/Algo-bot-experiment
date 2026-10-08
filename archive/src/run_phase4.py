"""Phase 4: ONE-TIME holdout run (spec §7, §12.4) — 2026-01-01 -> 2026-09-30.

Uses the Phase 3 engine, strategy, C1, FTMO and metrics code unchanged; only
the data window differs. Kill switch included. Run once; never re-run.

Reports: official §11 verdicts (M15, H1 x base / 1.5x spread / 0.0025% commission),
monthly P&L, an information-only run with the kill switch off, Bot A for
Jul-Sep 2026 (slice of the official run + standalone fresh account), C1
percentile, FTMO breach check and FTMO-flagged exits.

Run:  .venv/Scripts/python -m src.run_phase4
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
from src.run_phase3 import TFS, account_from, cost_cases, fmt_money, run_c1, with_times
from src.strategy_asian import Params
from src.timeutils import LONDON

OUT = PROJECT_ROOT / "results" / "phase4"
CLAUDE_WINDOW = (pd.Timestamp("2026-07-01").date(), pd.Timestamp("2026-09-30").date())


def london_window(start_date, end_date):
    """[start, end) in UTC for London calendar dates start..end inclusive."""
    start = pd.Timestamp(str(start_date)).tz_localize(LONDON).tz_convert("UTC")
    end = (pd.Timestamp(str(end_date)) + pd.Timedelta(days=1)).tz_localize(LONDON).tz_convert("UTC")
    return start, end


def slice_stats(t, months):
    """Trades, P&L, max drawdown and worst month for a slice of a trade list."""
    s = metrics.summarize(t, months)
    return {"trades": s["trades"], "net_profit": s["net_profit"], "max_dd_usd": s["max_dd_usd"],
            "worst_month": s["worst_month"], "worst_month_label": s["worst_month_label"],
            "ftmo_breached": s["ftmo_breached"], "ftmo_flagged_exits": s["ftmo_flagged_exits"]}


def main():
    t0 = time.time()
    settings = load_settings()
    symbol = settings["mt5"]["symbol"]
    meta = json.loads((PROJECT_ROOT / "data" / "raw" / f"{symbol}_metadata.json").read_text())
    point = meta["point"]
    period = settings["periods"]["holdout"]
    start, end = london_window(period["start"], period["end"])
    print(f"HOLDOUT window (UTC): {start} -> {end}")

    # load_bars refuses anything at/after its last argument: pass the holdout end so nothing later is read
    m1 = load_bars(symbol, "M1", start, end, end)
    bars = {tf: load_bars(symbol, tf, start, end, end) for tf in TFS}
    events = Events(pd.read_parquet(CALENDAR_PATH).time_utc)
    p = Params.from_settings(settings)
    acct = account_from(settings, meta)
    seeds = settings["controls"]["c1_random_entry_seeds"]
    days = {tf: build_days(m1, bars[tf], point) for tf in TFS}
    months = metrics.all_months(period["start"], period["end"])
    claude_months = metrics.all_months(*CLAUDE_WINDOW)
    OUT.mkdir(parents=True, exist_ok=True)

    official, kill_dates, base_trades = {}, {}, {}
    for tf, tf_min in TFS.items():
        for case, costs in cost_cases(settings).items():
            res = run(days[tf], bot_a_chooser(tf_min), p, costs, acct, events)
            a = trades_frame(res)
            s = metrics.summarize(a, months, acct.initial_balance)
            c1 = run_c1(days["M15"], a, p, costs, acct, events, seeds)
            nets = [float(t.net_pnl.sum()) if len(t) else 0.0 for t in c1]
            pct = metrics.c1_percentile(s["net_profit"], nets)
            passed, checks = metrics.strategy_verdict(s, pct)
            official[(tf, case)] = {"summary": s, "c1_pct": pct, "passed": passed, "checks": checks,
                                    "c1_p5": float(np.percentile(nets, 5)), "c1_median": float(np.median(nets)),
                                    "c1_p95": float(np.percentile(nets, 95)), "kill_switch": res.kill_switch_date}
            if case == "base":
                base_trades[tf] = a
            print(f"{tf:3} {case:18} A: {s['trades']:3} trades, net {fmt_money(s['net_profit']):>7}, "
                  f"beats {pct:5.1%} of C1, kill switch {res.kill_switch_date} -> {'PASS' if passed else 'FAIL'}"
                  f"   ({time.time() - t0:.0f}s)")

    # INFORMATION ONLY: kill switch off, base costs
    no_kill = dataclasses.replace(acct, kill_switch_dd=float("inf"))
    info = {}
    for tf, tf_min in TFS.items():
        a = trades_frame(run(days[tf], bot_a_chooser(tf_min), p, cost_cases(settings)["base"], no_kill, events))
        s = metrics.summarize(a, months, acct.initial_balance)
        c1 = run_c1(days["M15"], a, p, cost_cases(settings)["base"], no_kill, events, seeds)
        nets = [float(t.net_pnl.sum()) if len(t) else 0.0 for t in c1]
        info[tf] = {"summary": s, "c1_pct": metrics.c1_percentile(s["net_profit"], nets),
                    "c1_median": float(np.median(nets))}
        print(f"{tf:3} [info, no kill switch] A: {s['trades']} trades, net {fmt_money(s['net_profit'])}, "
              f"beats {info[tf]['c1_pct']:.1%} of C1")

    # Bot A, Jul-Sep 2026 (base costs): slice of the official run + standalone fresh account
    claude = {}
    for tf, tf_min in TFS.items():
        a = base_trades[tf]
        in_window = a[(a.date >= CLAUDE_WINDOW[0]) & (a.date <= CLAUDE_WINDOW[1])] if len(a) else a
        fresh_days = [d for d in days[tf] if CLAUDE_WINDOW[0] <= d.date <= CLAUDE_WINDOW[1]]
        fresh = trades_frame(run(fresh_days, bot_a_chooser(tf_min), p, cost_cases(settings)["base"], acct, events))
        claude[tf] = {"slice": slice_stats(in_window, claude_months), "fresh": slice_stats(fresh, claude_months)}
        if len(fresh):
            with_times(fresh).to_csv(OUT / f"trades_A_{tf}_jul_sep_fresh.csv", index=False)

    for tf, t in base_trades.items():
        if len(t):
            with_times(t).to_csv(OUT / f"trades_A_{tf}_holdout.csv", index=False)
    write_report(official, info, claude, start, end)
    print(f"done in {time.time() - t0:.0f}s -> {OUT.relative_to(PROJECT_ROOT)}")


def write_report(official, info, claude, start, end):
    cases = ["base", "spread x1.5", "commission 0.0025%"]
    L = ["# Phase 4 — HOLDOUT run (one time): 2026-01-01 → 2026-09-30", "",
         f"Window (UTC): {start} → {end}. Phase 3 code and rules unchanged, kill switch included. "
         "Real broker spreads throughout (recorded since 2025-12-17). Run once.", ""]
    for tf in TFS:
        S = [official[(tf, c)]["summary"] for c in cases]
        R = [official[(tf, c)] for c in cases]
        L += [f"## {tf} entry timeframe — official", "",
              "| Metric | base | spread ×1.5 | commission 0.0025% |", "|---|---:|---:|---:|"]
        row = lambda name, f: L.append(f"| {name} | " + " | ".join(f(s) for s in S) + " |")
        row("Trades", lambda s: f"{s['trades']}")
        row("Win rate", lambda s: f"{s['win_rate']:.1%}")
        row("Average R", lambda s: f"{s['avg_r']:+.3f}")
        row("Expectancy / trade", lambda s: f"${s['expectancy_usd']:+.2f}")
        row("Net profit", lambda s: fmt_money(s["net_profit"]))
        row("Average month", lambda s: fmt_money(s["avg_month"]))
        row("% months profitable", lambda s: f"{s['pct_months_profitable']:.0%}")
        row("Fewest profitable months in any 6-month window", lambda s: f"{s['min_profitable_in_6m_window']} / 6")
        row("Worst month", lambda s: f"{fmt_money(s['worst_month'])} ({s['worst_month_label']})")
        row("Worst day", lambda s: fmt_money(s["worst_day"]))
        row("Max drawdown", lambda s: f"{fmt_money(s['max_dd_usd'])} ({s['max_dd_pct']:.1%})")
        row("Longest losing streak", lambda s: f"{s['longest_losing_streak']}")
        row("FTMO breach", lambda s: "no" if not s["ftmo_breached"] else f"YES {s['ftmo_breach'][0]} on {s['ftmo_breach'][1]}")
        row("FTMO-flagged exits (±2 min of news)", lambda s: f"{s['ftmo_flagged_exits']}")
        L.append("| Kill switch triggered | " + " | ".join(str(r["kill_switch"] or "no") for r in R) + " |")
        L.append("| C1 net profit: 5% / median / 95% | " + " | ".join(
            f"{fmt_money(r['c1_p5'])} / {fmt_money(r['c1_median'])} / {fmt_money(r['c1_p95'])}" for r in R) + " |")
        L.append("| **A beats % of C1 runs** | " + " | ".join(f"**{r['c1_pct']:.1%}**" for r in R) + " |")
        L.append("| **Official verdict (§11)** | " + " | ".join(f"**{'PASS' if r['passed'] else 'FAIL'}**" for r in R) + " |")
        L += ["", "Checks per cost case:", "", "| Check | base | spread ×1.5 | commission 0.0025% |", "|---|---|---|---|"]
        for name in R[0]["checks"]:
            L.append(f"| {name} | " + " | ".join("✅" if r["checks"][name] else "❌" for r in R) + " |")
        L += ["", "Monthly net P&L (official run):", "", "| Month | base | spread ×1.5 | commission 0.0025% |",
              "|---|---:|---:|---:|"]
        for mth in S[0]["monthly"].index:
            L.append(f"| {mth} | " + " | ".join(fmt_money(s["monthly"][mth]) for s in S) + " |")
        L.append("")

    L += ["## Information only — kill switch disabled (NOT a verdict)", "",
          "Same rules and base costs, but the 6% kill switch never stops the strategy (C1 likewise).", "",
          "| TF | Trades | Net profit | Avg month | Fewest profitable in a 6-mo window | Max DD | FTMO breach | "
          "FTMO-flagged exits | A beats % of C1 | C1 median |", "|---|---:|---:|---:|---:|---:|---|---:|---:|---:|"]
    for tf, r in info.items():
        s = r["summary"]
        L.append(f"| {tf} | {s['trades']} | {fmt_money(s['net_profit'])} | {fmt_money(s['avg_month'])} | "
                 f"{s['min_profitable_in_6m_window']} / 6 | {fmt_money(s['max_dd_usd'])} ({s['max_dd_pct']:.1%}) | "
                 f"{'no' if not s['ftmo_breached'] else 'YES ' + str(s['ftmo_breach'][1])} | "
                 f"{s['ftmo_flagged_exits']} | {r['c1_pct']:.1%} | {fmt_money(r['c1_median'])} |")
    L += ["", "Monthly net P&L, information-only run:", "", "| Month | " + " | ".join(info) + " |",
          "|---|" + "---:|" * len(info)]
    first = next(iter(info.values()))["summary"]["monthly"]
    for mth in first.index:
        L.append(f"| {mth} | " + " | ".join(fmt_money(r["summary"]["monthly"][mth]) for r in info.values()) + " |")

    L += ["", "## Bot A, Jul–Sep 2026 (Bot B comparison window), base costs", "",
          "*Slice* = these months of the official holdout run (carries the kill-switch state from earlier in 2026). "
          "*Fresh* = a standalone run starting 2026-07-01 with a new $10,000 account — the setup Phase 5 compares B against.", "",
          "| TF | Version | Trades | Net P&L | Max drawdown | Worst month | FTMO breach | FTMO-flagged exits |",
          "|---|---|---:|---:|---:|---|---|---:|"]
    for tf, r in claude.items():
        for version in ("slice", "fresh"):
            s = r[version]
            L.append(f"| {tf} | {version} | {s['trades']} | {fmt_money(s['net_profit'])} | {fmt_money(s['max_dd_usd'])} | "
                     f"{fmt_money(s['worst_month'])} ({s['worst_month_label']}) | {'YES' if s['ftmo_breached'] else 'no'} | "
                     f"{s['ftmo_flagged_exits']} |")
    (OUT / "phase4_holdout_report.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
