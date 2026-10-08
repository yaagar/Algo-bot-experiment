"""Phase E2-3 — combination (docs/EXPERIMENT_2_SPEC.md §6 and Change Log), 2022-2025, base costs.

No strategy passed §7, so (spec §6) the combination of the two least-correlated strategies
with positive expectancy is run, INFORMATION ONLY; plus the extra information-only run of
S1 + S3 + S5 recorded in the Change Log before running. One account, netting, first
signal wins, skipped signals counted per strategy.

Run:  .venv/Scripts/python -m src.exp2.run_e2_3
"""
import itertools
import json

import numpy as np
import pandas as pd

from src.backtest import Events, dev_window, holdout_start
from src.calendar_events import OUT as CALENDAR_PATH
from src.config import PROJECT_ROOT, load_settings
from src.exp2.combo import run_combo
from src.exp2.engine import trades_frame
from src.exp2.market import build_market, load_frames
from src.exp2.regime import classify_months
from src.exp2.run_e2_1 import make_engine
from src.exp2.run_e2_2 import MONTHS, YEARS, build, run_one, stats

OUT = PROJECT_ROOT / "results" / "exp2"
FIVE = ["S1 H1", "S2", "S3", "S4", "S5"]
PRIORITY = ["S1 H1", "S2", "S3", "S4", "S5"]      # tie order on one account (Change Log: S1, S3, S5)
RISK = 50.0


def main():
    settings = load_settings()
    symbol = settings["mt5"]["symbol"]
    point = json.loads((PROJECT_ROOT / "data" / "raw" / f"{symbol}_metadata.json").read_text())["point"]
    start, end = dev_window(settings)
    assert end <= holdout_start(settings)
    market = build_market(*load_frames(symbol, start, end), point)
    events = Events(pd.read_parquet(CALENDAR_PATH).time_utc)
    eng = make_engine(settings, market, events)

    alone = {n: run_one(eng, build(n, market, events), n) for n in FIVE}
    S = {n: stats(t) for n, t in alone.items()}

    # combination engine must reproduce each strategy alone exactly
    for n in FIVE:
        co = trades_frame(run_combo(eng, {n: build(n, market, events)}))
        assert len(co) == len(alone[n]) and (co.entry_ns.values == alone[n].entry_ns.values).all() \
            and np.allclose(co.net_r.values, alone[n].net_r.values, rtol=0, atol=1e-9), f"combo-of-one differs for {n}"

    monthly = pd.DataFrame({n: S[n]["monthly"] for n in FIVE})
    corr = monthly.corr()
    positive = [n for n in FIVE if S[n]["exp"] > 0]
    pairs = sorted(itertools.combinations(positive, 2), key=lambda p: corr.loc[p[0], p[1]])
    pair = pairs[0]
    combos = {f"{pair[0]} + {pair[1]} (least-correlated pair)": list(pair),
              "S1 H1 + S3 + S5 (all positive)": ["S1 H1", "S3", "S5"]}
    combo_res = {}
    for label, members in combos.items():
        ordered = [n for n in PRIORITY if n in members]
        r = run_combo(eng, {n: build(n, market, events) for n in ordered})
        t = trades_frame(r)
        combo_res[label] = (t, stats(t), r.skipped_by_strategy)
        t.to_csv(OUT / f"e2_3_trades_{'_'.join(m.replace(' ', '') for m in ordered)}.csv", index=False)
    write_report(S, corr, positive, pairs, combos, combo_res, classify_months(market.days))


def write_report(S, corr, positive, pairs, combos, combo_res, reg):
    L = ["# Experiment 2 — E2-3 combinations, 2022–2025 (INFORMATION ONLY)", "",
         "No strategy passed the §7 \"promising\" test in E2-2, so no combination can be judged \"better\". Spec §6 then asks for "
         "the **two least-correlated strategies with positive expectancy**, information only; the **S1 + S3 + S5** run was added "
         "by Yash and recorded in the Change Log before running. One account, one position at a time, first signal wins "
         "(busy from signal to close; same-time events: exits, fills, then signals; ties S1, S3, S5). Base costs. $ = R × $50 "
         "(fractional size, every accepted signal traded). The combination engine reproduces every strategy's standalone run "
         "exactly when given that strategy alone (checked in this run).", ""]

    L += ["## Correlation of monthly R (2022–2025, standalone runs)", "",
          "| | " + " | ".join(FIVE) + " |", "|---|" + "---:|" * len(FIVE)]
    for a in FIVE:
        L.append(f"| **{a}** | " + " | ".join("—" if a == b else f"{corr.loc[a, b]:+.2f}" for b in FIVE) + " |")
    L += ["", f"Positive expectancy (E2-2): {', '.join(positive)}. Pairs by correlation: " +
          "; ".join(f"{p[0]} + {p[1]} {corr.loc[p[0], p[1]]:+.2f}" for p in pairs) +
          f". **Least-correlated pair: {pairs[0][0]} + {pairs[0][1]}.**", ""]

    cols = [(n, S[n], None) for n in ("S1 H1", "S3", "S5")] + [(lab, cr[1], cr[2]) for lab, cr in combo_res.items()]
    L += ["## Side by side, base costs", "",
          "| | Trades | Total R | Total $ | Expectancy | % months profitable | Max drawdown | Worst month | Signals skipped (netting) |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    for name, s, skipped in cols:
        sk = "—" if skipped is None else ", ".join(f"{k}: {v}" for k, v in skipped.items())
        L.append(f"| {name} | {s['n']} | {s['total']:+.1f}R | ${s['total'] * RISK:+,.0f} | {s['exp']:+.3f}R | "
                 f"{s['pct_months']:.0%} | {s['dd']:.1f}R (${s['dd'] * RISK:,.0f}) | {s['worst_month']:+.1f}R "
                 f"(${s['worst_month'] * RISK:+,.0f}) | {sk} |")

    L += ["", "Inside each combination — trades and R by strategy:", ""]
    for label, (t, s, skipped) in combo_res.items():
        g = t.groupby("strategy").net_r.agg(["count", "sum", "mean"])
        L.append(f"- **{label}:** " + "; ".join(f"{k} {int(r['count'])} trades, {r['sum']:+.1f}R ({r['mean']:+.3f}R/trade)"
                                                 for k, r in g.iterrows()))

    L += ["", "## Per year, base costs (trades / total R / $)", "",
          "| | " + " | ".join(map(str, YEARS)) + " |", "|---|" + "---|" * len(YEARS)]
    for name, s, _ in cols:
        L.append(f"| {name} | " + " | ".join(f"{s['years'][y][0]} / {s['years'][y][1]:+.1f}R / ${s['years'][y][1] * RISK:+,.0f}"
                                            for y in YEARS) + " |")

    lab = reg.regime.reindex(MONTHS)
    L += ["", "## Regime table — total R per month type, base costs", "",
          "| | Trending up | Trending down | Ranging up | Ranging down | All trending | All ranging |", "|---|---:|---:|---:|---:|---:|---:|"]
    for name, s, _ in cols:
        m = s["monthly"]
        cell = lambda mask: f"{m[mask.values].sum():+.1f}R"
        L.append(f"| {name} | " + " | ".join(cell(lab == k) for k in ("trending up", "trending down", "ranging up", "ranging down"))
                 + f" | {cell(lab.str.startswith('trending'))} | {cell(lab.str.startswith('ranging'))} |")
    L += ["", f"Months: " + ", ".join(f"{k} {v}" for k, v in reg.regime.value_counts().items()) + "."]
    (OUT / "e2_3_combinations.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("written results/exp2/e2_3_combinations.md")


if __name__ == "__main__":
    main()
