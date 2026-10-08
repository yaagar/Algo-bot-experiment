"""Phase E3-2 — run and report (docs/EXPERIMENT_3_SPEC.md §5-6) -> results/exp3/report.md.

  0. re-checks on the final data (FX spliced): independent signal/trade check and the 20-cut scramble test
  1. R statistics per market and for the equal-risk portfolio (base costs)
  2. C1 random direction, 200 seeds, portfolio total R
  3. stresses: 1.5x spread, 2x commission, 1.5x swap charges
  4. diversification: portfolio max drawdown vs the average single-market one; monthly R correlations
  5. FTMO Swing tradeability at $25 and $50 risk with real lots
  6. the §6 verdict

Run:  .venv/Scripts/python -m src.exp3.run_e3_2
"""
import time

import numpy as np
import pandas as pd

from src.exp2.c1 import run_c1
from src.exp2.engine import trades_frame
from src.exp3.data import build_market, load_frames, load_specs, make_engine, strategy
from src.exp3.evaluate import FULL_YEARS, ftmo_sim, r_stats
from src.exp3.markets import RESULTS
from src.exp3.run_e3_1 import N_CUTS, independent_check, leak_test

C1_SEEDS = 200
STRESSES = {"1.5x spread": {"spread_mult": 1.5}, "2x commission": {"commission_mult": 2.0},
            "1.5x swap charges": {"swap_charge_mult": 1.5}}


def run_all(specs, frames, **cost):
    out, engines = {}, {}
    for s in specs:
        m = build_market(*frames[s["symbol"]], s["point"])
        engines[s["symbol"]] = eng = make_engine(s, m, **cost)
        out[s["symbol"]] = eng.run(strategy(m))
    return out, engines


def fmt_r(x):
    return f"{x:+.2f}"


def main():
    t0 = time.time()
    specs = load_specs()
    names = {s["symbol"]: s["market"] for s in specs}
    frames = {s["symbol"]: load_frames(s) for s in specs}
    base, engines = run_all(specs, frames)
    trades = {sym: trades_frame(r) for sym, r in base.items()}
    for sym, t in trades.items():
        t.insert(0, "symbol", sym)

    # 0. checks on the final data
    checks = {s["symbol"]: independent_check(s, *frames[s["symbol"]], base[s["symbol"]]) for s in specs}
    ok, _, changed = leak_test(specs, frames, base)
    print(f"checks done ({time.time() - t0:.0f}s)")

    # 1. R statistics
    port = pd.concat(trades.values(), ignore_index=True)
    stats = {sym: r_stats(t) for sym, t in trades.items()}
    ps = r_stats(port)

    # 2. C1
    c1_totals = []
    for seed in range(C1_SEEDS):
        c1_totals.append(sum(trades_frame(run_c1(engines[sym], t, seed)).net_r.sum() if len(t) else 0.0
                             for sym, t in trades.items()))
    c1_totals = np.array(c1_totals)
    beats = float((c1_totals < ps["total_r"]).mean())
    print(f"C1 done ({time.time() - t0:.0f}s)")

    # 3. stresses
    stress = {}
    for name, cost in STRESSES.items():
        res, _ = run_all(specs, frames, **cost)
        stress[name] = r_stats(pd.concat([trades_frame(r) for r in res.values()], ignore_index=True))

    # 4. diversification
    avg_single_dd = float(np.mean([stats[sym]["max_dd_r"] for sym in stats]))
    monthly = pd.DataFrame({names[sym]: stats[sym]["monthly"] for sym in stats})
    corr = monthly.corr()
    off = corr.where(~np.eye(len(corr), dtype=bool)).stack()

    # 5. FTMO
    d1s = {sym: frames[sym][0] for sym in frames}
    ftmo = {risk: ftmo_sim(trades, specs, d1s, risk) for risk in (25.0, 50.0)}

    # 6. verdict
    years_pos = sum(ps["per_year"].get(y, 0.0) > 0 for y in FULL_YEARS)
    edge = {"Expectancy >= +0.10R": ps["expectancy"] >= 0.10,
            "Positive total R in >= 3 of 2022-2025": years_pos >= 3,
            "Beats >= 90% of C1 runs": beats >= 0.90,
            "Positive under each stress": all(v["total_r"] > 0 for v in stress.values())}
    divers = ps["max_dd_r"] < avg_single_dd

    def tradeable(f):
        return {"avg >= $100/month": f["avg_month"] >= 100, ">= 4 of every 6 months profitable": f["min_profitable_in_6m"] >= 4,
                "no FTMO breach": f["daily_breach"] is None and f["total_breach"] is None,
                "margin never exceeded": f["max_margin_to_equity"] <= 1.0}
    trade_ok = {risk: tradeable(f) for risk, f in ftmo.items()}
    edge_pass = all(edge.values())
    trade_pass = any(all(v.values()) for v in trade_ok.values())
    overall = edge_pass and divers and trade_pass

    # --- report -------------------------------------------------------------------------------
    yes = lambda b: "yes" if b else "**no**"
    L = ["# Experiment 3 — multi-market daily Donchian 55/20 — results", "",
         "## Summary", "",
         f"One rule (Turtle System 2 on daily bars) run on {len(specs)} markets, 2022-01 to 2026-09, every trade risking "
         f"the same 1R. The portfolio made **{ps['trades']} trades, {fmt_r(ps['expectancy'])}R per trade, "
         f"{fmt_r(ps['total_r'])}R in total**, with a worst drawdown of {ps['max_dd_r']:.1f}R. "
         f"It beat {beats:.0%} of 200 random-direction runs. "
         f"**Verdict (§6): {'PASS (provisional — needs a paper forward test)' if overall else 'FAIL'}** — "
         f"edge {'passes' if edge_pass else 'fails'}, diversification {'works' if divers else 'does not work'}, "
         f"tradeable for Yash: {'yes' if trade_pass else 'no'}.", "",
         "FX before 2025-05-21 uses MetaQuotes-Demo prices with FTMO costs (Change Log v1.1). Swap is today's rate "
         "applied to all history (estimate); spreads before real recording are the open-hour 75th percentile (estimate).", "",
         "## §6 verdict", "", "| Test | Result | Pass |", "|---|---|---|",
         f"| Expectancy >= +0.10R | {fmt_r(ps['expectancy'])}R | {yes(edge['Expectancy >= +0.10R'])} |",
         f"| Positive R in >= 3 of 2022-2025 | {years_pos} of 4 ("
         + ", ".join(f"{y}: {fmt_r(ps['per_year'].get(y, 0.0))}" for y in FULL_YEARS)
         + f") | {yes(edge['Positive total R in >= 3 of 2022-2025'])} |",
         f"| Beats >= 90% of C1 | {beats:.1%} (C1 median {np.median(c1_totals):+.1f}R) | {yes(edge['Beats >= 90% of C1 runs'])} |",
         "| Positive under each stress | " + ", ".join(f"{k}: {fmt_r(v['total_r'])}R" for k, v in stress.items())
         + f" | {yes(edge['Positive under each stress'])} |",
         f"| Diversification: portfolio max DD < average single-market max DD | {ps['max_dd_r']:.1f}R vs {avg_single_dd:.1f}R | {yes(divers)} |"]
    for risk, f in ftmo.items():
        L.append(f"| Tradeable at {risk / 100:.2%} risk | " + "; ".join(f"{k}: {'ok' if v else 'fails'}" for k, v in trade_ok[risk].items())
                 + f" | {yes(all(trade_ok[risk].values()))} |")

    L += ["", "## Portfolio vs single markets (R, base costs)", "",
          "| Market | Trades | R/trade | Total R | % months + | Max DD (R) | Worst month (R) | "
          + " | ".join(str(y) for y in (2022, 2023, 2024, 2025, 2026)) + " |",
          "|---|---:|---:|---:|---:|---:|---:|" + "---:|" * 5]
    for sym, s in list(stats.items()) + [("Portfolio", ps)]:
        L.append(f"| {names.get(sym, '**Portfolio**')} | {s['trades']} | {fmt_r(s['expectancy'])} | {fmt_r(s['total_r'])} | "
                 f"{s['pct_months_profitable']:.0%} | {s['max_dd_r']:.1f} | {fmt_r(s['worst_month_r'])} | "
                 + " | ".join(fmt_r(s["per_year"].get(y, 0.0)) for y in (2022, 2023, 2024, 2025, 2026)) + " |")
    L.append(f"\nAverage single-market max drawdown {avg_single_dd:.1f}R. Monthly R correlation between markets: "
             f"mean {off.mean():+.2f}, range {off.min():+.2f} to {off.max():+.2f} (pairs counted twice). 2026 = Jan-Sep.")

    L += ["", "## FTMO Swing tradeability ($10k, real lots from `symbol_info`)", "",
          "| Risk per trade | Signals skipped (min lot) | Avg $/month | % months profitable | Min profitable in any 6 months | "
          "Worst month | Max DD $ | Worst day $ | FTMO breach | Max margin / equity (1:30) |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---|---:|"]
    for risk, f in ftmo.items():
        breach = ", ".join(x for x in (f"daily 5% on {f['daily_breach']}" if f["daily_breach"] else "",
                                       f"total 10% on {f['total_breach']}" if f["total_breach"] else "") if x) or "none"
        L.append(f"| ${risk:.0f} ({risk / 100:.2%}) | {f['skipped_min_lot']} / {f['signals']} ({f['pct_skipped']:.0%}) | "
                 f"${f['avg_month']:+.0f} | {f['pct_months_profitable']:.0%} | {f['min_profitable_in_6m']} / 6 | "
                 f"${f['worst_month']:+.0f} | ${f['max_dd_usd']:.0f} | ${f['worst_day_loss']:.0f} | {breach} | "
                 f"{f['max_margin_to_equity']:.2f} |")
    L += ["", "Daily loss is conservative: every open position is marked at its day's worst price (spec §5.5). "
          "Skipped signals are dropped without re-running later signals the engine skipped while that trade was open.",
          "", "## Monthly R correlation", "",
          "| | " + " | ".join(corr.columns) + " |", "|---|" + "---:|" * len(corr.columns),
          *[f"| {i} | " + " | ".join(f"{v:+.2f}" for v in row) + " |" for i, row in corr.round(2).iterrows()], "",
          "## Checks on the final data", "",
          "| Symbol | Independent check (trades identical) | Scramble test (cuts identical) | Decisions changed after cut (median) |",
          "|---|---|---|---:|"]
    for sym in base:
        c = checks[sym]
        L.append(f"| {sym} | {c['identical']} / {c['engine_trades']} {'pass' if c['pass'] else '**FAIL**'} | "
                 f"{ok[sym]} / {N_CUTS} | {int(np.median(changed[sym]))} |")
    L += ["", "## Notes", "",
          "- Stress '1.5x swap' multiplies swap charges only; swap credits are unchanged (a stress should not help).",
          "- '>= 4 of every 6 months' = every rolling 6-month window (as in Experiment 1).",
          "- Months and years are counted by trade exit (UTC). FTMO days = broker days (New York 17:00), "
          "not Prague midnight (1 hour apart).",
          "- Trades: `trades.csv`. C1 totals by seed: `c1_total_r_by_seed.csv`."]
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = port.copy()
    for c in ("signal", "entry", "exit"):
        out[f"{c}_utc"] = pd.to_datetime(out[f"{c}_ns"], utc=True)
    out.drop(columns=[c for c in out.columns if c.endswith("_ns")]).to_csv(RESULTS / "trades.csv", index=False)
    pd.DataFrame({"seed": range(C1_SEEDS), "total_r": c1_totals}).to_csv(RESULTS / "c1_total_r_by_seed.csv", index=False)
    (RESULTS / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"done ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
