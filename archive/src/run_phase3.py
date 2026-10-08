"""Phase 3: Bot A + C1 on the DEVELOPMENT period only (2022-2025).

Runs, for M15 and H1:
  * Bot A under three cost cases (base, 1.5x spread, 0.0025% commission)
  * C1 random entry, 200 seeds, under the same three cost cases
  * robustness nudges for A (box end 06:30 / 07:30, target 1.3R / 1.7R) — reported, never selected
  * the future-scramble leak test (20 random cut times)
and writes results/phase3/ (report, trade lists, hand-check trades, plots).

Run:  .venv/Scripts/python -m src.run_phase3
"""
import dataclasses
import json
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src import leak_test, metrics
from src.backtest import (Account, Costs, Events, bot_a_chooser, build_days, dev_window, holdout_start,
                          load_bars, run, trades_frame)
from src.calendar_events import OUT as CALENDAR_PATH
from src.config import PROJECT_ROOT, load_settings
from src.controls import c1_chooser
from src.strategy_asian import Params, hhmm_to_minutes
from src.timeutils import LONDON, utc_to_server

OUT = PROJECT_ROOT / "results" / "phase3"
TFS = {"M15": 15, "H1": 60}


def cost_cases(settings):
    c = settings["costs"]
    base = Costs(1.0, c["commission_pct_per_side"])
    return {"base": base,
            "spread x1.5": Costs(c["spread_stress_multiplier"], c["commission_pct_per_side"]),
            "commission 0.0025%": Costs(1.0, c["commission_pct_per_side_stress"])}


def account_from(settings, meta):
    a, r = settings["account"], settings["risk"]
    return Account(initial_balance=a["initial_balance"], risk_per_trade=r["risk_per_trade_usd"],
                   daily_stop=r["daily_stop_usd"], kill_switch_dd=r["kill_switch_drawdown_usd"],
                   contract_size=meta["contract_size"], volume_step=meta["volume_step"],
                   volume_min=meta["volume_min"])


def run_c1(days_m15, a_trades, p, costs, acct, events, seeds):
    """200 C1 runs on the days A traded, with A's stop distance per day."""
    r_by_date = dict(zip(a_trades.date, a_trades.stop_distance))
    days = [d for d in days_m15 if d.date in r_by_date]
    chooser = c1_chooser(r_by_date, events)
    return [trades_frame(run(days, chooser, p, costs, acct, events, rng=np.random.default_rng(s)))
            for s in range(seeds)]


def fmt_money(x):
    return f"${x:,.0f}"


def main():
    t_start = time.time()
    settings = load_settings()
    symbol = settings["mt5"]["symbol"]
    meta = json.loads((PROJECT_ROOT / "data" / "raw" / f"{symbol}_metadata.json").read_text())
    point = meta["point"]
    start, end = dev_window(settings)
    hold = holdout_start(settings)
    print(f"Development window (UTC): {start} -> {end}  | holdout starts {hold} (not loaded)")

    m1 = load_bars(symbol, "M1", start, end, hold)
    bars = {tf: load_bars(symbol, tf, start, end, hold) for tf in TFS}
    events = Events(pd.read_parquet(CALENDAR_PATH).time_utc)
    p = Params.from_settings(settings)
    acct = account_from(settings, meta)
    seeds = settings["controls"]["c1_random_entry_seeds"]
    days = {tf: build_days(m1, bars[tf], point) for tf in TFS}
    months = metrics.all_months(settings["periods"]["development"]["start"],
                                settings["periods"]["development"]["end"])
    OUT.mkdir(parents=True, exist_ok=True)

    results, c1_nets, base_trades, c1_base = {}, {}, {}, {}
    for tf, tf_min in TFS.items():
        for case, costs in cost_cases(settings).items():
            a = trades_frame(run(days[tf], bot_a_chooser(tf_min), p, costs, acct, events))
            s = metrics.summarize(a, months, acct.initial_balance)
            c1 = run_c1(days["M15"], a, p, costs, acct, events, seeds)
            nets = [float(t.net_pnl.sum()) if len(t) else 0.0 for t in c1]
            pct = metrics.c1_percentile(s["net_profit"], nets)
            passed, checks = metrics.strategy_verdict(s, pct)
            results[(tf, case)] = {"summary": s, "c1_pct": pct, "passed": passed, "checks": checks,
                                   "c1_median": float(np.median(nets)), "c1_p5": float(np.percentile(nets, 5)),
                                   "c1_p95": float(np.percentile(nets, 95))}
            c1_nets[(tf, case)] = nets
            if case == "base":
                base_trades[tf], c1_base[tf] = a, c1
            print(f"{tf:3} {case:18} A: {s['trades']:4} trades, net {fmt_money(s['net_profit']):>8}, "
                  f"beats {pct:5.1%} of C1  -> {'PASS' if passed else 'FAIL'}   ({time.time() - t_start:.0f}s)")

    # INFORMATION ONLY: same runs with the kill switch disabled (not a spec verdict)
    no_kill = dataclasses.replace(acct, kill_switch_dd=float("inf"))
    info_no_kill = {}
    for tf, tf_min in TFS.items():
        a = trades_frame(run(days[tf], bot_a_chooser(tf_min), p, cost_cases(settings)["base"], no_kill, events))
        s = metrics.summarize(a, months, acct.initial_balance)
        c1 = run_c1(days["M15"], a, p, cost_cases(settings)["base"], no_kill, events, seeds)
        nets = [float(t.net_pnl.sum()) if len(t) else 0.0 for t in c1]
        info_no_kill[tf] = {"summary": s, "c1_pct": metrics.c1_percentile(s["net_profit"], nets),
                            "c1_median": float(np.median(nets))}
        print(f"{tf:3} [info, no kill switch] A: {s['trades']} trades, net {fmt_money(s['net_profit'])}, "
              f"beats {info_no_kill[tf]['c1_pct']:.1%} of C1")

    # Robustness nudges (A only, base costs) — reported, never selected
    nudges = []
    variants = {"box end 06:30": {"box_end": hhmm_to_minutes("06:30")},
                "box end 07:30": {"box_end": hhmm_to_minutes("07:30")},
                "target 1.3R": {"take_profit_r": 1.3}, "target 1.7R": {"take_profit_r": 1.7}}
    base_costs = cost_cases(settings)["base"]
    for tf, tf_min in TFS.items():
        base_net = results[(tf, "base")]["summary"]["net_profit"]
        for name, change in variants.items():
            v = trades_frame(run(days[tf], bot_a_chooser(tf_min), dataclasses.replace(p, **change),
                                 base_costs, acct, events))
            s = metrics.summarize(v, months, acct.initial_balance)
            collapse = (base_net > 0 and s["net_profit"] < 0.5 * base_net)
            nudges.append({"tf": tf, "variant": name, "trades": s["trades"], "net_profit": s["net_profit"],
                           "avg_month": s["avg_month"], "max_dd_usd": s["max_dd_usd"],
                           "vs_base": s["net_profit"] - base_net, "profit_collapses": collapse})
    nudges = pd.DataFrame(nudges)
    print(f"nudges done ({time.time() - t_start:.0f}s)")

    # Future-scramble leak test
    leaks = {tf: leak_test.run_test(m1, bars[tf], tf_min, point, p, base_costs, acct, events)
             for tf, tf_min in TFS.items()}
    for tf, df in leaks.items():
        print(f"leak test {tf}: {df.identical_before_cut.sum()}/{len(df)} cut times identical before the cut")
    print(f"leak test done ({time.time() - t_start:.0f}s)")

    write_outputs(results, nudges, leaks, base_trades, c1_base, c1_nets, months, p, acct, start, end, info_no_kill)
    print(f"done in {time.time() - t_start:.0f}s -> {OUT.relative_to(PROJECT_ROOT)}")


# --- Outputs -------------------------------------------------------------------------------

def with_times(t):
    """Add London date and MT5 server-time columns for hand-checking."""
    t = t.copy()
    for col in ("signal_time", "entry_time", "exit_time"):
        t[f"{col}_server"] = utc_to_server(t[f"{col}_utc"]).dt.strftime("%Y-%m-%d %H:%M")
        t[f"{col}_utc"] = t[f"{col}_utc"].dt.strftime("%Y-%m-%d %H:%M")
    return t


def handcheck(base_trades, p, n_each=5, seed=2026):
    rng = np.random.default_rng(seed)
    rows = []
    for tf, t in base_trades.items():
        pick = t.iloc[np.sort(rng.choice(len(t), size=min(n_each, len(t)), replace=False))]
        for _, r in pick.iterrows():
            box_start = pd.Timestamp(r.date).tz_localize(LONDON) + pd.Timedelta(minutes=p.box_start)
            box_end = pd.Timestamp(r.date).tz_localize(LONDON) + pd.Timedelta(minutes=p.box_end)
            to_utc = lambda x: x.tz_convert("UTC")
            to_srv = lambda x: utc_to_server(pd.Series([x.tz_convert("UTC")])).iloc[0]
            rows.append({
                "timeframe": tf, "london_date": str(r.date), "direction": r.direction,
                "box_utc": f"{to_utc(box_start):%H:%M}-{to_utc(box_end):%H:%M}",
                "box_server": f"{to_srv(box_start):%H:%M}-{to_srv(box_end):%H:%M}",
                "box_high": round(r.box_high, 2), "box_low": round(r.box_low, 2),
                "signal_close_utc": f"{r.signal_time_utc:%Y-%m-%d %H:%M}",
                "signal_close_server": f"{utc_to_server(pd.Series([r.signal_time_utc])).iloc[0]:%Y-%m-%d %H:%M}",
                "entry_utc": f"{r.entry_time_utc:%Y-%m-%d %H:%M}",
                "entry_server": f"{utc_to_server(pd.Series([r.entry_time_utc])).iloc[0]:%Y-%m-%d %H:%M}",
                "entry_bid_open": round(r.entry_bid, 2), "spread_paid": round(r.spread_at_entry, 3),
                "spread_estimated": r.spread_estimated, "entry_price": round(r.entry_price, 3),
                "stop": round(r.stop, 3), "target": round(r.target, 3), "lots": r.lots,
                "exit_utc": f"{r.exit_time_utc:%Y-%m-%d %H:%M}",
                "exit_server": f"{utc_to_server(pd.Series([r.exit_time_utc])).iloc[0]:%Y-%m-%d %H:%M}",
                "exit_price": round(r.exit_price, 3), "exit_reason": r.exit_reason,
                "result_R": round(r.r_multiple, 2), "net_pnl_usd": round(r.net_pnl, 2),
            })
    return pd.DataFrame(rows)


def equity_plot(base_trades, c1_base, acct):
    fig, axes = plt.subplots(1, len(base_trades), figsize=(13, 4.5), sharey=True)
    for ax, (tf, a) in zip(np.atleast_1d(axes), base_trades.items()):
        dates = pd.to_datetime(sorted(set(a.date)))
        curves = []
        for t in c1_base[tf]:
            daily = t.groupby(pd.to_datetime(t.date)).net_pnl.sum().reindex(dates, fill_value=0) if len(t) \
                else pd.Series(0.0, index=dates)
            curves.append(daily.cumsum().to_numpy())
        curves = np.array(curves)
        ax.fill_between(dates, np.percentile(curves, 5, axis=0), np.percentile(curves, 95, axis=0),
                        color="grey", alpha=0.3, label="C1 random entry, 5-95%")
        ax.plot(dates, np.median(curves, axis=0), color="grey", lw=1, label="C1 median")
        a_daily = a.groupby(pd.to_datetime(a.date)).net_pnl.sum().reindex(dates, fill_value=0).cumsum()
        ax.plot(dates, a_daily, color="tab:blue", lw=1.6, label="Bot A")
        ax.axhline(0, color="black", lw=0.6)
        ax.set_title(f"{tf} — cumulative net P&L, base costs (2022-2025)")
        ax.set_ylabel("USD")
        ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "equity_A_vs_C1.png", dpi=120)


def write_outputs(results, nudges, leaks, base_trades, c1_base, c1_nets, months, p, acct, start, end, info_no_kill):
    for tf, t in base_trades.items():
        with_times(t).to_csv(OUT / f"trades_A_{tf}.csv", index=False)
    hc = handcheck(base_trades, p)
    hc.to_csv(OUT / "handcheck_10_trades.csv", index=False)
    equity_plot(base_trades, c1_base, acct)
    pd.DataFrame({f"{tf}|{case}": v for (tf, case), v in c1_nets.items()}).to_csv(OUT / "c1_net_profit_by_seed.csv",
                                                                                index=False)
    nudges.to_csv(OUT / "robustness_nudges.csv", index=False)
    for tf, df in leaks.items():
        df.to_csv(OUT / f"leak_test_{tf}.csv", index=False)

    L = ["# Phase 3 — Bot A and C1 on the development period (2022–2025)", "",
         f"Window (UTC): {start} → {end}. Holdout not loaded (the loader refuses any window reaching 2026-01-01).",
         "Spreads before 2025-12-17 are **estimated** (spec v1.2). No parameters were changed based on results.", ""]
    for tf in TFS:
        L += [f"## {tf} entry timeframe", "",
              "| Metric | base | spread ×1.5 | commission 0.0025% |", "|---|---:|---:|---:|"]
        cases = ["base", "spread x1.5", "commission 0.0025%"]
        S = [results[(tf, c)]["summary"] for c in cases]
        R = [results[(tf, c)] for c in cases]
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
        row("FTMO Phase 1 / 2 target reached", lambda s: f"{s['ftmo_phase1_passed'] or 'no'} / {s['ftmo_phase2_passed'] or 'no'}")
        row("FTMO-flagged exits (±2 min of news)", lambda s: f"{s['ftmo_flagged_exits']}")
        L.append("| C1 net profit: 5% / median / 95% | " + " | ".join(
            f"{fmt_money(r['c1_p5'])} / {fmt_money(r['c1_median'])} / {fmt_money(r['c1_p95'])}" for r in R) + " |")
        L.append("| **A beats % of C1 runs** | " + " | ".join(f"**{r['c1_pct']:.1%}**" for r in R) + " |")
        L.append("| **Development verdict** | " + " | ".join(f"**{'PASS' if r['passed'] else 'FAIL'}**" for r in R) + " |")
        L += ["", "Pass/fail checks (base costs):", ""]
        L += [f"- {'✅' if ok else '❌'} {name}" for name, ok in results[(tf, "base")]["checks"].items()]
        m = results[(tf, "base")]["summary"]["monthly"]
        L += ["", "<details><summary>Monthly net P&L, base costs</summary>", "", "| Month | P&L |", "|---|---:|"]
        L += [f"| {k} | {fmt_money(v)} |" for k, v in m.items()]
        L += ["", "</details>", ""]
    L += ["## Information only — kill switch disabled (NOT a spec verdict)", "",
          "Same rules and base costs, but the 6% kill switch never stops the strategy (C1 likewise). "
          "Shown so the whole 2022–2025 period can be seen; the official results above keep the kill switch.", "",
          "| TF | Trades | Net profit | Avg month | Fewest profitable in a 6-mo window | Max DD | FTMO breach | A beats % of C1 | C1 median |",
          "|---|---:|---:|---:|---:|---:|---|---:|---:|"]
    for tf, r in info_no_kill.items():
        s = r["summary"]
        L.append(f"| {tf} | {s['trades']} | {fmt_money(s['net_profit'])} | {fmt_money(s['avg_month'])} | "
                 f"{s['min_profitable_in_6m_window']} / 6 | {fmt_money(s['max_dd_usd'])} ({s['max_dd_pct']:.1%}) | "
                 f"{'no' if not s['ftmo_breached'] else 'YES ' + str(s['ftmo_breach'][1])} | {r['c1_pct']:.1%} | "
                 f"{fmt_money(r['c1_median'])} |")
    L += [""]
    L += ["## Robustness nudges (A only, base costs — reported, not selected)", "",
          "Box-end variants move the start of the entry window with the box end. "
          "'Collapses' = net profit below half of the base run (only judged when base is profitable).", "",
          "| TF | Variant | Trades | Net profit | Avg month | Max DD | vs base | Collapses? |",
          "|---|---|---:|---:|---:|---:|---:|---|"]
    L += [f"| {r.tf} | {r.variant} | {r.trades} | {fmt_money(r.net_profit)} | {fmt_money(r.avg_month)} | "
          f"{fmt_money(r.max_dd_usd)} | {fmt_money(r.vs_base)} | {'YES' if r.profit_collapses else 'no'} |"
          for r in nudges.itertuples()]
    L += ["", "## Future-scramble leak test (20 random cut times per timeframe)", ""]
    for tf, df in leaks.items():
        ok = int(df.identical_before_cut.sum())
        L.append(f"- **{tf}: {ok} / {len(df)}** cut times with every decision before the cut identical "
                 f"(decisions changed after the cut: min {df.decisions_changed_after_cut.min()}, "
                 f"median {int(df.decisions_changed_after_cut.median())}).")
    L += ["", "## Files", "",
          "- `handcheck_10_trades.csv` — 10 random trades (5 M15, 5 H1) to check against MT5",
          "- `trades_A_M15.csv`, `trades_A_H1.csv` — every Bot A trade, base costs",
          "- `c1_net_profit_by_seed.csv`, `robustness_nudges.csv`, `leak_test_*.csv`",
          "- `equity_A_vs_C1.png`"]
    (OUT / "phase3_report.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
