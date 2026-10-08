"""Phase 5 — Bot B (Claude filter) on the Claude window, 2026-07-01 -> 2026-10-07 (spec §6, v1.6).

Bot B = plain Bot A + two Claude calls (src/claude_filter.py, locked prompts):
  * morning, 07:00 London, every weekday with a valid box: TRADE_DAY / NO_TRADE_DAY;
  * veto, at the signal candle's close, for each A signal that passed A's own filters
    (news blackout, minimum lot) on a TRADE_DAY: TAKE / VETO.
Claude can only remove trades. Compared on identical dates with A, C1 (random entry,
200 seeds) and C2 (A's trades with the same NUMBER of trades removed at random, 1,000
seeds), for M15 and H1 under the three cost cases. 20% of calls are re-asked to measure
the flip rate.

Choices fixed before any result (see the report header): the 6-month-window part of the
§11 overall rule can't be evaluated on a 3-month window and is shown as n/a; the
"average month" check uses the window's length (99 days = 3.25 months) because October
is partial; C2 removes the same count of trades that Claude removed (NO_TRADE_DAY + VETO).

Run:  .venv/Scripts/python -m src.run_phase5 --sample     (5 calls + token estimate)
      .venv/Scripts/python -m src.run_phase5 --full
"""
import argparse
import dataclasses
import json
import random
import time

import numpy as np
import pandas as pd

from src import claude_filter, metrics
from src.backtest import Entry, Events, bot_a_chooser, build_days, load_bars, run, trades_frame
from src.calendar_events import OUT as CALENDAR_PATH
from src.claude_inputs import load_headlines, morning_input, veto_input, with_close_time
from src.config import PROJECT_ROOT, load_settings
from src.run_phase3 import TFS, account_from, cost_cases, fmt_money, run_c1
from src.run_phase4 import london_window
from src.strategy_asian import Params, compute_box
from src.timeutils import LONDON

OUT = PROJECT_ROOT / "results" / "phase5"
FIRST, LAST = "2026-07-01", "2026-10-07"
WINDOW_MONTHS = 99 / 30.4375
CASES = ["base", "spread x1.5", "commission 0.0025%"]
C2_SEEDS = 1000
RECHECK_SEED = 20261008


class Setup:
    def __init__(self):
        s = load_settings()
        self.settings = s
        self.symbol = s["mt5"]["symbol"]
        self.meta = json.loads((PROJECT_ROOT / "data" / "raw" / f"{self.symbol}_metadata.json").read_text())
        self.start, self.end = london_window(FIRST, LAST)
        m1 = load_bars(self.symbol, "M1", self.start, self.end, self.end)
        bars = {tf: load_bars(self.symbol, tf, self.start, self.end, self.end) for tf in TFS}
        self.days = {tf: build_days(m1, bars[tf], self.meta["point"]) for tf in TFS}
        hist_from = self.start - pd.Timedelta(days=14)          # H1 history for the first 48 candles
        self.h1 = with_close_time(load_bars(self.symbol, "H1", hist_from, self.end, self.end), 60)
        self.m15 = with_close_time(bars["M15"], 15)
        self.calendar = pd.read_parquet(CALENDAR_PATH)
        self.events = Events(self.calendar.time_utc)
        self.headlines = load_headlines()
        self.p = Params.from_settings(s)
        self.acct = account_from(s, self.meta)
        self.costs = cost_cases(s)
        self.months = metrics.all_months(FIRST, LAST)

    def london(self, date, minute):
        return (pd.Timestamp(date).tz_localize(LONDON) + pd.Timedelta(minutes=int(minute))).tz_convert("UTC")

    def box(self, day):
        return compute_box(day.m1_min, day.m1_h, day.m1_l, day.m1_s, self.p)[0]

    def morning_text(self, day):
        box = self.box(day)
        t = self.london(day.date, self.p.box_end)
        return morning_input(t, box, self.h1, self.m15, self.calendar, self.headlines,
                             self.london(day.date, self.p.time_exit))

    def veto_text(self, day, entry):
        t = pd.Timestamp(entry.signal_time_ns, tz="UTC")
        return veto_input(t, self.box(day), entry.direction, self.h1, self.m15, self.calendar, self.headlines)


def a_entries(S):
    """A's signals that passed A's own filters, per TF: {date: Entry}. Same across cost cases?"""
    out = {}
    no_kill = dataclasses.replace(S.acct, kill_switch_dd=float("inf"))
    for tf, tf_min in TFS.items():
        per_case = {}
        for case in CASES:
            res = run(S.days[tf], bot_a_chooser(tf_min), S.p, S.costs[case], no_kill, S.events)
            per_case[case] = {d[2] for d in res.decisions if d[1] == "entry"}
        dates = set().union(*per_case.values())
        chooser = bot_a_chooser(tf_min)
        out[tf] = {}
        for day in S.days[tf]:
            if day.date in dates:
                entry, _ = chooser(day, S.box(day), S.p)
                out[tf][day.date] = entry
    return out


def plan_calls(S):
    """Every primary call: morning per weekday with a valid box; veto per A entry (resolved later)."""
    mornings = [(day.date, S.morning_text(day)) for day in S.days["M15"] if S.box(day) is not None]
    return mornings


def sample(S):
    mornings = plan_calls(S)
    entries = a_entries(S)
    days_by_date = {tf: {d.date: d for d in S.days[tf]} for tf in TFS}
    picks = [("morning", mornings[5][1], {"date": str(mornings[5][0])}),
             ("morning", mornings[40][1], {"date": str(mornings[40][0])})]
    for tf, k in (("M15", 3), ("M15", 30), ("H1", 15)):
        date = sorted(entries[tf])[k]
        picks.append(("veto", S.veto_text(days_by_date[tf][date], entries[tf][date]), {"date": str(date), "tf": tf}))
    recs = []
    for kind, text, meta in picks:
        r = claude_filter.decide(kind, text, meta)
        recs.append(r)
        u = r["usage"]
        print(f"{kind:7} {meta}  -> {r['decision']:12} conf {r['confidence']}  in {u['input_tokens']}+cw {u['cache_creation_input_tokens']}"
              f"+cr {u['cache_read_input_tokens']} out {u['output_tokens']}  ${r['cost_usd']}  {r['seconds']}s  ({r['input_chars']} chars)")
    n_veto = sum(len(e) for e in entries.values())
    n_primary = len(mornings) + n_veto
    n_total = int(round(n_primary * 1.2))
    tok = np.mean([sum(r["usage"].values()) for r in recs])
    cost = np.mean([r["cost_usd"] or 0 for r in recs])
    secs = np.mean([r["seconds"] for r in recs])
    L = ["# Phase 5 — sample calls and run estimate", "",
         "| Call | Decision | Input tokens (new / cache write / cache read) | Output tokens | API-equivalent $ | Seconds |",
         "|---|---|---|---:|---:|---:|"]
    for (kind, _, meta), r in zip(picks, recs):
        u = r["usage"]
        L.append(f"| {kind} {meta} | {r['decision']} | {u['input_tokens']} / {u['cache_creation_input_tokens']} / "
                 f"{u['cache_read_input_tokens']} | {u['output_tokens']} | {r['cost_usd']} | {r['seconds']} |")
    L += ["", f"Planned calls: {len(mornings)} morning + up to {n_veto} veto (fewer if NO_TRADE_DAYs) = {n_primary}, "
              f"+20% recheck ≈ **{n_total} calls**.",
          f"Average per call: {tok:,.0f} tokens, ${cost:.3f} API-equivalent, {secs:.0f}s.",
          f"**Estimated total: ≈ {tok * n_total / 1e6:.2f}M tokens, ≈ ${cost * n_total:.0f} API-equivalent, "
          f"≈ {secs * n_total / 60:.0f} minutes of calls.**"]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "sample_calls.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L[-3:]).encode("ascii", "replace").decode())


# --- Full run ---------------------------------------------------------------------------------

class FailureGuard:
    """Stop the run after 3 failed calls in a row (e.g. a usage limit), instead of letting
    a wave of failures default to TAKE / TRADE_DAY. Failures aren't cached, so a re-run resumes."""
    def __init__(self):
        self.streak = 0

    def check(self, rec):
        self.streak = self.streak + 1 if rec["failed"] else 0
        if self.streak >= 3:
            raise SystemExit(f"3 Claude calls failed in a row (last: {rec['error']}). Stopping; re-run later to resume.")
        return rec


GUARD = FailureGuard()

def b_chooser(base, ntd_dates, veto_dates):
    def choose(day, box, p, rng=None):
        if day.date in ntd_dates:
            return None, "Claude: NO_TRADE_DAY"
        entry, why = base(day, box, p, rng)
        if entry is None:
            return None, why
        if day.date in veto_dates:
            return None, "Claude: VETO"
        return entry, None
    return choose


def c2_chooser(base, removed_dates):
    def choose(day, box, p, rng=None):
        if day.date in removed_dates:
            return None, "C2: randomly removed"
        return base(day, box, p, rng)
    return choose


def full(S):
    t0 = time.time()
    mornings = plan_calls(S)
    morning = {}
    for i, (date, text) in enumerate(mornings):
        morning[date] = GUARD.check(claude_filter.decide("morning", text, {"date": str(date)}))
        if i % 10 == 0:
            print(f"morning {i + 1}/{len(mornings)}  ({time.time() - t0:.0f}s)")
    ntd = {d for d, r in morning.items() if r["decision"] == "NO_TRADE_DAY"}

    entries = a_entries(S)
    days_by_date = {tf: {d.date: d for d in S.days[tf]} for tf in TFS}
    veto = {tf: {} for tf in TFS}
    for tf in TFS:
        todo = [d for d in sorted(entries[tf]) if d not in ntd]
        for i, date in enumerate(todo):
            veto[tf][date] = GUARD.check(claude_filter.decide("veto", S.veto_text(days_by_date[tf][date], entries[tf][date]),
                                                              {"date": str(date), "tf": tf}))
            if i % 10 == 0:
                print(f"veto {tf} {i + 1}/{len(todo)}  ({time.time() - t0:.0f}s)")
    vetoed = {tf: {d for d, r in veto[tf].items() if r["decision"] == "VETO"} for tf in TFS}

    # Consistency recheck: re-ask a random 20% of the primary calls
    primary = [("morning", text, {"date": str(d)}, morning[d]["decision"]) for d, text in mornings]
    primary += [("veto", S.veto_text(days_by_date[tf][d], entries[tf][d]), {"date": str(d), "tf": tf}, r["decision"])
                for tf in TFS for d, r in veto[tf].items()]
    rng = random.Random(RECHECK_SEED)
    picks = rng.sample(primary, k=round(len(primary) * S.settings["claude"]["consistency_recheck_fraction"]))
    rechecks = []
    for kind, text, meta, first in picks:
        r = GUARD.check(claude_filter.decide(kind, text, meta, recheck=True))
        rechecks.append({"kind": kind, **meta, "first": first, "second": r["decision"], "failed": r["failed"]})
    flips = [r for r in rechecks if not r["failed"] and r["first"] != r["second"]]
    flip_rate = len(flips) / max(1, sum(not r["failed"] for r in rechecks))
    print(f"recheck: {len(rechecks)} calls, flip rate {flip_rate:.1%}  ({time.time() - t0:.0f}s)")

    # Backtests on identical dates
    results = {}
    for tf, tf_min in TFS.items():
        base = bot_a_chooser(tf_min)
        for case in CASES:
            c, acct = S.costs[case], S.acct
            a = trades_frame(run(S.days[tf], base, S.p, c, acct, S.events))
            b = trades_frame(run(S.days[tf], b_chooser(base, ntd, vetoed[tf]), S.p, c, acct, S.events))
            sa, sb = metrics.summarize(a, S.months), metrics.summarize(b, S.months)
            c1 = [float(t.net_pnl.sum()) if len(t) else 0.0 for t in run_c1(S.days["M15"], a, S.p, c, acct, S.events, 200)]
            removed = len(a) - len(b)
            c2 = []
            for seed in range(C2_SEEDS):
                drop = set(random.Random(seed).sample(sorted(a.date), k=removed)) if removed else set()
                t = trades_frame(run(S.days[tf], c2_chooser(base, drop), S.p, c, acct, S.events))
                s2 = metrics.summarize(t, S.months)
                c2.append((s2["max_dd_usd"], s2["worst_month"]))
            c2 = np.array(c2)
            results[(tf, case)] = {"a": a, "b": b, "sa": sa, "sb": sb, "c1": c1, "c2": c2, "removed": removed}
            print(f"{tf} {case:18} A {len(a)} tr {fmt_money(sa['net_profit'])} | B {len(b)} tr {fmt_money(sb['net_profit'])} "
                  f"| removed {removed}  ({time.time() - t0:.0f}s)")
    write_report(S, morning, ntd, veto, vetoed, entries, rechecks, flip_rate, results)


def verdict(r, flip_rate):
    sa, sb = r["sa"], r["sb"]
    c2_dd = float((sb["max_dd_usd"] < r["c2"][:, 0]).mean())
    c2_wm = float((sb["worst_month"] > r["c2"][:, 1]).mean())
    b_c1 = metrics.c1_percentile(sb["net_profit"], r["c1"])
    avg = sb["net_profit"] / WINDOW_MONTHS
    checks = {
        "B has lower max drawdown than A": sb["max_dd_usd"] < sa["max_dd_usd"],
        "B has a better worst month than A": sb["worst_month"] > sa["worst_month"],
        f"B beats ≥ 90% of C2 on drawdown ({c2_dd:.1%})": c2_dd >= 0.90,
        f"B beats ≥ 90% of C2 on worst month ({c2_wm:.1%})": c2_wm >= 0.90,
        f"B overall rule: average ≥ $100/month (window-adjusted: {fmt_money(avg)})": avg >= 100,
        "B overall rule: ≥ 4 profitable months in every 6-month window — n/a (3.25-month window)": None,
        "B overall rule: no FTMO breach": not sb["ftmo_breached"],
        f"B overall rule: beats ≥ 90% of C1 on net profit ({b_c1:.1%})": b_c1 >= 0.90,
        f"Consistency flip rate < 20% ({flip_rate:.1%})": flip_rate < 0.20,
    }
    return all(v for v in checks.values() if v is not None), checks


def usage_totals():
    recs = [json.loads(l) for l in open(claude_filter.LOG_PATH, encoding="utf-8")]
    keys = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
    tot = {k: sum(r["usage"][k] for r in recs) for k in keys}
    return len(recs), tot, sum(r["cost_usd"] or 0 for r in recs), sum(r["failed"] for r in recs)


def write_report(S, morning, ntd, veto, vetoed, entries, rechecks, flip_rate, results):
    cfg = claude_filter.config()
    n_calls, tot, cost, failed = usage_totals()
    L = ["# Phase 5 — Bot B (Claude filter) vs Bot A, Claude window 2026-07-01 → 2026-10-07", "",
         f"Model `{cfg['model']}` (training-data cutoff Jun 2026), effort `{cfg['effort']}`, Claude Code CLI "
         f"{S.settings['claude']['cli_version']}, locked prompts veto_v1 / morning_v1. Plain Bot A (no trend filter). "
         "Kill switch on (official). Real broker spreads.", "",
         "**Choices fixed before any result:** the 6-month-window part of the §11 overall rule is n/a on a 3.25-month window "
         "and does not count; the $100/month check divides net profit by 3.25 months (October is partial); C2 removes the "
         "same number of A's trades as Claude removed (NO_TRADE_DAY + VETO), 1,000 seeds; C1 = 200 seeds on A's days.", ""]

    L += ["## §11 verdict — is B better than A?", "",
          "| TF | Cost case | A trades / net / max DD / worst month | B trades / net / max DD / worst month | Verdict |",
          "|---|---|---|---|---|"]
    details = []
    for (tf, case), r in results.items():
        ok, checks = verdict(r, flip_rate)
        sa, sb = r["sa"], r["sb"]
        fmt = lambda s: f"{s['trades']} / {fmt_money(s['net_profit'])} / {fmt_money(s['max_dd_usd'])} / {fmt_money(s['worst_month'])}"
        L.append(f"| {tf} | {case} | {fmt(sa)} | {fmt(sb)} | **{'B BETTER' if ok else 'not better'}** |")
        details.append((tf, case, checks))
    L += ["", "Checks per case:", ""]
    for tf, case, checks in details:
        L.append(f"**{tf}, {case}:** " + "; ".join(f"{'✅' if v else ('➖' if v is None else '❌')} {k}" for k, v in checks.items()))
        L.append("")

    L += ["## P&L of the trades Claude removed vs the ones it kept (A's actual results, official run)", "",
          "| TF | Cost case | Removed on NO_TRADE_DAYs | Vetoed | Kept (= B) |", "|---|---|---|---|---|"]
    for (tf, case), r in results.items():
        a = r["a"]
        cell = lambda t: "–" if len(t) == 0 else f"{len(t)} tr, {fmt_money(t.net_pnl.sum())}, ${t.net_pnl.mean():+.2f}/tr, {(t.net_pnl > 0).mean():.0%} won"
        on_ntd = a[a.date.isin(ntd)]
        vet = a[a.date.isin(vetoed[tf])]
        kept = a[~a.date.isin(ntd) & ~a.date.isin(vetoed[tf])]
        L.append(f"| {tf} | {case} | {cell(on_ntd)} | {cell(vet)} | {cell(kept)} |")

    base = {tf: results[(tf, "base")]["a"] for tf in TFS}
    L += ["", f"## NO_TRADE_DAYs: {len(ntd)} of {len(morning)} mornings", "",
          "| Date | Confidence | Claude's reason | A on M15 that day | A on H1 that day |", "|---|---:|---|---|---|"]
    for d in sorted(ntd):
        r = morning[d]
        a_day = lambda tf: ("no trade" if not len(base[tf][base[tf].date == d]) else
                            f"{base[tf][base[tf].date == d].direction.iloc[0]} {fmt_money(base[tf][base[tf].date == d].net_pnl.sum())}")
        L.append(f"| {d} | {r['confidence']} | {r['reason']} | {a_day('M15')} | {a_day('H1')} |")

    L += ["", "## Every veto, with Claude's reason", "",
          "| TF | Date | Signal | Confidence | Claude's reason | A's result for that trade (base) |", "|---|---|---|---:|---|---|"]
    for tf in TFS:
        for d in sorted(vetoed[tf]):
            r = veto[tf][d]
            t = base[tf][base[tf].date == d]
            res = f"{t.exit_reason.iloc[0]} {fmt_money(t.net_pnl.iloc[0])}" if len(t) else "not traded by A (kill switch / filters)"
            L.append(f"| {tf} | {d} | {'LONG' if entries[tf][d].direction > 0 else 'SHORT'} | {r['confidence']} | {r['reason']} | {res} |")
    takes = sum(r["decision"] == "TAKE" for tf in TFS for r in veto[tf].values())
    L += ["", f"Veto calls: {sum(len(v) for v in veto.values())} (TAKE {takes}, VETO {sum(len(v) for v in vetoed.values())})."]

    L += ["", "## Consistency recheck", "",
          f"{len(rechecks)} calls re-asked (20%, seed {RECHECK_SEED}). **Flip rate: {flip_rate:.1%}** "
          f"({sum(1 for r in rechecks if not r['failed'] and r['first'] != r['second'])} changed)."]
    for r in rechecks:
        if not r["failed"] and r["first"] != r["second"]:
            L.append(f"- {r['kind']} {r.get('tf', '')} {r['date']}: {r['first']} → {r['second']}")

    L += ["", "## Tokens and cost", "",
          f"Calls made: {n_calls} (failed and defaulted: {failed}). Tokens — new input {tot['input_tokens']:,}, cache write "
          f"{tot['cache_creation_input_tokens']:,}, cache read {tot['cache_read_input_tokens']:,}, output {tot['output_tokens']:,}; "
          f"**total {sum(tot.values()):,}**. API-equivalent cost ${cost:.2f} (billed to the Pro subscription, not an API key)."]

    L += ["", "## C1 and C2 reference (net profit / drawdown)", "",
          "| TF | Cost case | A beats % of C1 | B beats % of C1 | C2 max DD median | C2 worst month median |", "|---|---|---:|---:|---:|---:|"]
    for (tf, case), r in results.items():
        L.append(f"| {tf} | {case} | {metrics.c1_percentile(r['sa']['net_profit'], r['c1']):.1%} | "
                 f"{metrics.c1_percentile(r['sb']['net_profit'], r['c1']):.1%} | {fmt_money(np.median(r['c2'][:, 0]))} | "
                 f"{fmt_money(np.median(r['c2'][:, 1]))} |")
    L += ["", "Monthly net P&L, base costs (A / B):", "", "| Month | M15 A | M15 B | H1 A | H1 B |", "|---|---:|---:|---:|---:|"]
    for m in S.months:
        L.append(f"| {m} | " + " | ".join(fmt_money(results[(tf, 'base')][k]['monthly'][m]) for tf in TFS for k in ("sa", "sb")) + " |")
    (OUT / "phase5_report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"written {(OUT / 'phase5_report.md').relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true")
    ap.add_argument("--full", action="store_true")
    args = ap.parse_args()
    S = Setup()
    if args.sample:
        sample(S)
    if args.full:
        full(S)
