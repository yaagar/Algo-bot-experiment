"""Phase E2-2 — main comparison on 2022-2025 (docs/EXPERIMENT_2_SPEC.md §5, §7, §8).

All five strategies (S1 judged on H1; S1 M15 reported), in R, under base costs and the two
cost stresses, with C1 (200 seeds), the regime table, robustness nudges, per-year results,
a buy-and-hold reference, and the §7 "promising" verdict per strategy.

Fixed before any result (spec Change Log): collapse = nudge expectancy below half of the
base expectancy (or <= 0); C1 compared on total R at base costs.

Run:  .venv/Scripts/python -m src.exp2.run_e2_2
"""
import json
import time

import numpy as np
import pandas as pd

from src.backtest import Events, dev_window, holdout_start
from src.calendar_events import OUT as CALENDAR_PATH
from src.config import PROJECT_ROOT, load_settings
from src.exp2.c1 import run_c1
from src.exp2.engine import Costs, trades_frame
from src.exp2.market import build_market, load_frames
from src.exp2.regime import classify_months
from src.exp2.run_e2_1 import make_engine
from src.exp2.strategies import S1Asian, S2Box, S3Donchian, S4RSI2, S5AsianHours
from src.timeutils import LONDON

OUT = PROJECT_ROOT / "results" / "exp2"
YEARS = [2022, 2023, 2024, 2025]
MONTHS = pd.period_range("2022-01", "2025-12", freq="M")
STRATS = ["S1 H1", "S1 M15", "S2", "S3", "S4", "S5"]
JUDGED = ["S1 H1", "S2", "S3", "S4", "S5"]
RISK_USD = 50.0          # fractional sizing: every trade risks exactly this (config exp2.risk_per_trade_usd)


def build(name, market, events, nudge=None):
    nudge = nudge or {}
    if name.startswith("S1"):
        return S1Asian(market, name.split()[1], **nudge)
    return {"S2": lambda: S2Box(market, **nudge), "S3": lambda: S3Donchian(market, **nudge),
            "S4": lambda: S4RSI2(market, **nudge), "S5": lambda: S5AsianHours(market, events, **nudge)}[name]()


NUDGES = {
    "S1 H1": {"box end 06:30": {"box_end": "06:30"}, "box end 07:30": {"box_end": "07:30"}},
    "S1 M15": {"box end 06:30": {"box_end": "06:30"}, "box end 07:30": {"box_end": "07:30"}},
    "S2": {"wick ratio 1.5": {"wick_ratio": 1.5}, "wick ratio 2.5": {"wick_ratio": 2.5}},
    "S3": {"channel 16": {"channel": 16}, "channel 24": {"channel": 24}},
    "S4": {"RSI 5 / 95": {"buy_below": 5, "sell_above": 95}, "RSI 15 / 85": {"buy_below": 15, "sell_above": 85}},
    "S5": {"exit 02:00 NY": {"exit_hour_ny": 2}, "exit 04:00 NY": {"exit_hour_ny": 4}},
}


def run_one(eng, strat, name):
    return trades_frame(eng.run_timed(strat) if name == "S5" else eng.run(strat))


def entry_london(t):
    return pd.to_datetime(t.entry_ns, utc=True).dt.tz_convert(LONDON)


def stats(t):
    """Everything in R (1R = the trade's initial risk)."""
    if len(t) == 0:
        return {"n": 0, "exp": float("nan"), "total": 0.0, "win": float("nan"), "dd": 0.0,
                "pct_months": 0.0, "worst_month": 0.0, "years": {y: (0, 0.0, float("nan")) for y in YEARS},
                "monthly": pd.Series(0.0, index=MONTHS)}
    lon = entry_london(t)
    t = t.assign(year=lon.dt.year.values, month=lon.dt.tz_localize(None).dt.to_period("M").values)
    by_exit = t.sort_values("exit_ns").net_r.cumsum().to_numpy()
    peak = np.maximum.accumulate(np.r_[0.0, by_exit])[1:]
    monthly = t.groupby("month").net_r.sum().reindex(MONTHS, fill_value=0.0)
    years = {y: (int((t.year == y).sum()), float(t.net_r[t.year == y].sum()),
                 float(t.net_r[t.year == y].mean()) if (t.year == y).any() else float("nan")) for y in YEARS}
    return {"n": len(t), "exp": float(t.net_r.mean()), "total": float(t.net_r.sum()), "win": float((t.net_r > 0).mean()),
            "dd": float((peak - by_exit).max()), "pct_months": float((monthly > 0).mean()),
            "worst_month": float(monthly.min()), "years": years, "monthly": monthly,
            "flagged": int(t.ftmo_flagged_exit.sum()), "long_break": int(t.held_across_long_break.sum()),
            "nights": int(t.swap_nights.sum()), "swap_r": float(t.swap_usd.sum() / RISK_USD)}


def main():
    t0 = time.time()
    settings = load_settings()
    symbol = settings["mt5"]["symbol"]
    point = json.loads((PROJECT_ROOT / "data" / "raw" / f"{symbol}_metadata.json").read_text())["point"]
    start, end = dev_window(settings)
    assert end <= holdout_start(settings)
    market = build_market(*load_frames(symbol, start, end), point)
    events = Events(pd.read_parquet(CALENDAR_PATH).time_utc)
    c = settings["costs"]
    cases = {"base": Costs(1.0, c["commission_pct_per_side"]),
             "spread x1.5": Costs(c["spread_stress_multiplier"], c["commission_pct_per_side"]),
             "commission 0.0025%": Costs(1.0, c["commission_pct_per_side_stress"])}
    engines = {k: make_engine(settings, market, events) for k in cases}
    for k, eng in engines.items():
        eng.costs = cases[k]

    # 1. Base and stress runs
    trades, S = {}, {}
    for name in STRATS:
        for case, eng in engines.items():
            t = run_one(eng, build(name, market, events), name)
            trades[(name, case)], S[(name, case)] = t, stats(t)
        print(f"{name}: runs done ({time.time() - t0:.0f}s)")
    OUT.mkdir(parents=True, exist_ok=True)
    for name in STRATS:
        trades[(name, "base")].to_csv(OUT / f"e2_2_trades_{name.replace(' ', '_')}.csv", index=False)

    # 2. C1, 200 seeds, base costs
    seeds = settings["exp2"]["c1_seeds"]
    c1 = {}
    for name in STRATS:
        tot = [float(trades_frame(run_c1(engines["base"], trades[(name, "base")], s)).net_r.sum()) for s in range(seeds)]
        c1[name] = np.array(tot)
        print(f"{name}: C1 done ({time.time() - t0:.0f}s)")
    pd.DataFrame(c1).to_csv(OUT / "e2_2_c1_total_r_by_seed.csv", index=False)

    # 3. Nudges, base costs
    nudge = {}
    for name in STRATS:
        for label, kw in NUDGES[name].items():
            nudge[(name, label)] = stats(run_one(engines["base"], build(name, market, events, kw), name))
    print(f"nudges done ({time.time() - t0:.0f}s)")

    # 4. Regimes and buy-and-hold
    reg = classify_months(market.days)
    days = market.days.copy()
    days.index = pd.to_datetime(days.index)
    yearly_close = days.close.groupby(days.index.year).last()
    first_close = float(days.close.iloc[0])

    write_report(S, c1, nudge, reg, yearly_close, first_close, settings)
    print(f"done ({time.time() - t0:.0f}s)")


def verdict(name, S, c1, nudge):
    b = S[(name, "base")]
    pct = float((c1[name] < b["total"]).mean())
    years_pos = sum(b["years"][y][1] > 0 for y in YEARS)
    collapses = [label for (n, label), s in nudge.items() if n == name and (s["exp"] <= 0 or s["exp"] < 0.5 * b["exp"])]
    checks = {
        f"expectancy ≥ +0.10R ({b['exp']:+.3f}R)": b["exp"] >= 0.10,
        f"positive total R in ≥ 3 of 4 years ({years_pos}/4)": years_pos >= 3,
        f"beats ≥ 90% of C1 on total R ({pct:.1%})": pct >= 0.90,
        f"positive expectancy at 1.5× spread ({S[(name, 'spread x1.5')]['exp']:+.3f}R)": S[(name, "spread x1.5")]["exp"] > 0,
        f"positive expectancy at 0.0025% commission ({S[(name, 'commission 0.0025%')]['exp']:+.3f}R)":
            S[(name, "commission 0.0025%")]["exp"] > 0,
        f"no collapse under nudges ({', '.join(collapses) or 'none'})": b["exp"] > 0 and not collapses,
    }
    return all(checks.values()), checks, pct


def write_report(S, c1, nudge, reg, yearly_close, first_close, settings):
    f = lambda x: f"{x:+.3f}"
    L = ["# Experiment 2 — E2-2 main comparison, 2022–2025", "",
         "All results in **R** (1R = the trade's initial risk; fractional size, every signal traded). Base costs unless "
         "stated: real spread from 2025-12-17, estimated hourly 75th percentile before; commission 0.0007% per side; swap "
         "from the broker's current rates (estimate). Data 2022+ only, through the data lock. S1 is judged on H1; M15 is "
         "reported for reference (spec §2).", "",
         "Fixed before any result: a nudge **collapses** if its expectancy falls below half of the base expectancy or to "
         "≤ 0 (Change Log clarification 4); C1 is compared on total R at base costs.", ""]

    L += ["## Verdicts (spec §7: a strategy is \"promising\" only if all six checks pass)", "",
          "| Strategy | Trades | Expectancy | Total R | Promising? |", "|---|---:|---:|---:|---|"]
    details = {}
    for name in STRATS:
        ok, checks, pct = verdict(name, S, c1, nudge)
        details[name] = checks
        b = S[(name, "base")]
        tag = ("**YES**" if ok else "no") if name in JUDGED else ("(reference: " + ("would pass" if ok else "would fail") + ")")
        L.append(f"| {name} | {b['n']} | {f(b['exp'])}R | {b['total']:+.1f}R | {tag} |")
    L += [""]
    for name in STRATS:
        L.append(f"**{name}:** " + "; ".join(f"{'✅' if v else '❌'} {k}" for k, v in details[name].items()))
        L.append("")

    L += ["## Main results, base costs", "",
          "| Strategy | Trades | Win rate | Expectancy | Total R | Max drawdown | % months profitable | Worst month | "
          "C1: 5% / median / 95% total R | Beats % of C1 | FTMO-flagged exits | Held over >2 h break | Swap |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|"]
    for name in STRATS:
        b = S[(name, "base")]
        q = np.percentile(c1[name], [5, 50, 95])
        L.append(f"| {name} | {b['n']} | {b['win']:.0%} | {f(b['exp'])}R | {b['total']:+.1f}R | {b['dd']:.1f}R | "
                 f"{b['pct_months']:.0%} | {b['worst_month']:+.1f}R | {q[0]:+.1f} / {q[1]:+.1f} / {q[2]:+.1f} | "
                 f"{(c1[name] < b['total']).mean():.1%} | {b['flagged']} | {b['long_break']} | "
                 f"{b['swap_r']:+.1f}R ({b['nights']} nights) |")

    L += ["", "## Per year, base costs (trades / total R / expectancy)", "",
          "| Strategy | " + " | ".join(map(str, YEARS)) + " |", "|---|" + "---|" * len(YEARS)]
    for name in STRATS:
        y = S[(name, "base")]["years"]
        L.append(f"| {name} | " + " | ".join(f"{y[k][0]} / {y[k][1]:+.1f}R / {y[k][2]:+.3f}R" for k in YEARS) + " |")

    L += ["", "## Cost stresses (expectancy / total R)", "",
          "| Strategy | Base | 1.5× spread | 0.0025% commission |", "|---|---|---|---|"]
    for name in STRATS:
        L.append(f"| {name} | " + " | ".join(f"{f(S[(name, c)]['exp'])}R / {S[(name, c)]['total']:+.1f}R"
                                            for c in ("base", "spread x1.5", "commission 0.0025%")) + " |")

    L += ["", "## Robustness nudges, base costs (reported, never selected)", "",
          "| Strategy | Variant | Trades | Expectancy | Total R | vs base expectancy | Collapses? |", "|---|---|---:|---:|---:|---:|---|"]
    for (name, label), s in nudge.items():
        b = S[(name, "base")]["exp"]
        col = s["exp"] <= 0 or s["exp"] < 0.5 * b
        L.append(f"| {name} | {label} | {s['n']} | {f(s['exp'])}R | {s['total']:+.1f}R | {s['exp'] - b:+.3f}R | "
                 f"{'**YES**' if col else 'no'} |")

    L += ["", "## Regime table — total R per month type, base costs", "",
          f"Months 2022–2025 labelled from broker-day closes: efficiency = |month change| ÷ sum of |daily changes|; above the "
          f"median ({reg.attrs['median_efficiency']:.3f}) = trending. Months: " +
          ", ".join(f"{k} {v}" for k, v in reg.regime.value_counts().items()) + ".", "",
          "| Strategy | Trending up | Trending down | Ranging up | Ranging down | All trending | All ranging | All up | All down |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    lab = reg.regime.reindex(MONTHS)
    for name in STRATS:
        m = S[(name, "base")]["monthly"]
        cell = lambda mask: f"{m[mask.values].sum():+.1f}R ({mask.sum()} mo)"
        L.append(f"| {name} | " + " | ".join(cell(lab == k) for k in ("trending up", "trending down", "ranging up", "ranging down"))
                 + f" | {cell(lab.str.startswith('trending'))} | {cell(lab.str.startswith('ranging'))} | "
                 f"{cell(lab.str.endswith('up'))} | {cell(lab.str.endswith('down'))} |")

    L += ["", "## Buy-and-hold gold reference (same period)", "",
          "| Year | Gold change |", "|---|---:|"]
    prev = first_close
    for y, close in yearly_close.items():
        L.append(f"| {y} | {close / prev - 1:+.1%} |")
        prev = close
    L.append(f"| **2022–2025** | **{yearly_close.iloc[-1] / first_close - 1:+.1%}** (first close of 2022 to last close of 2025) |")
    L += ["", "Monthly R per strategy (base) is in `e2_2_monthly_r.csv`; trades in `e2_2_trades_*.csv`; C1 totals per seed in "
          "`e2_2_c1_total_r_by_seed.csv`."]
    pd.DataFrame({n: S[(n, "base")]["monthly"] for n in STRATS}).to_csv(OUT / "e2_2_monthly_r.csv")
    (OUT / "e2_2_main_comparison.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
