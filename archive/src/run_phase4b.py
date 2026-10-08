"""Phase 4b — filter discovery (information only), spec v1.4 §12.

Development period 2022-2025 only, base costs, kill switch OFF. Every Bot A
trade (M15 and H1) is tagged (src/filters.py) and the report shows expectancy
and P&L per tag per year, the 2026 long/short split (from the Phase 4 trade
files, information only), and whether each pre-chosen candidate filter passes
the rule: it must improve expectancy in >= 3 of the 4 years. Nothing is adopted
here; Yash decides. 2010-2021 is reserved for Phase 4c and is not loaded.

Run:  .venv/Scripts/python -m src.run_phase4b
"""
import dataclasses
import json

import pandas as pd

from src.backtest import Events, bot_a_chooser, build_days, dev_window, holdout_start, load_bars, run, trades_frame
from src.calendar_events import OUT as CALENDAR_PATH
from src.config import PROJECT_ROOT, load_settings
from src.filters import CANDIDATES, tag_trades
from src.run_phase3 import TFS, account_from, cost_cases
from src.strategy_asian import Params

OUT = PROJECT_ROOT / "results" / "phase4b"
PHASE4 = PROJECT_ROOT / "results" / "phase4"
YEARS = [2022, 2023, 2024, 2025]
REQUIRED_YEARS = 3


def stats(t):
    return {"n": len(t), "exp": t.net_pnl.mean() if len(t) else float("nan"), "pnl": t.net_pnl.sum()}


def cell(s):
    return "–" if s["n"] == 0 else f"{s['n']} / ${s['exp']:+.2f} / ${s['pnl']:+,.0f}"


def evaluate_filter(t, column, keep):
    """Per year: expectancy of kept trades vs all trades with a known tag."""
    known = t[t[column].notna()]
    rows = []
    for y in YEARS:
        all_y = known[known.year == y]
        kept = all_y[all_y[column] == keep]
        base, k = stats(all_y), stats(kept)
        improved = k["n"] > 0 and k["exp"] > base["exp"]
        rows.append({"year": y, "all": base, "kept": k, "improved": improved})
    n_better = sum(r["improved"] for r in rows)
    return rows, n_better, n_better >= REQUIRED_YEARS, len(t) - len(known)


def main():
    settings = load_settings()
    symbol = settings["mt5"]["symbol"]
    meta = json.loads((PROJECT_ROOT / "data" / "raw" / f"{symbol}_metadata.json").read_text())
    start, end = dev_window(settings)
    m1 = load_bars(symbol, "M1", start, end, holdout_start(settings))
    assert m1.time_utc.min() >= start            # nothing from 2010-2021
    calendar = pd.read_parquet(CALENDAR_PATH)
    events = Events(calendar.time_utc)
    p = Params.from_settings(settings)
    no_kill = dataclasses.replace(account_from(settings, meta), kill_switch_dd=float("inf"))
    OUT.mkdir(parents=True, exist_ok=True)

    L = ["# Phase 4b — filter discovery (INFORMATION ONLY)", "",
         "Development period 2022–2025, base costs, kill switch off. Tag definitions: `src/filters.py` "
         "(fixed before any result was seen). Cells: **trades / expectancy per trade / total P&L**.", "",
         "Rule (§12): a filter counts as helpful only if it improves expectancy in **≥ 3 of 4 years** "
         "(median split, no threshold search). Adopt at most two; **Yash decides**. Nothing is adopted here.", ""]
    verdicts = []
    for tf, tf_min in TFS.items():
        days = build_days(m1, load_bars(symbol, tf, start, end, holdout_start(settings)), meta["point"])
        a = trades_frame(run(days, bot_a_chooser(tf_min), p, cost_cases(settings)["base"], no_kill, events))
        t = tag_trades(a, m1, calendar)
        t.to_csv(OUT / f"tagged_trades_A_{tf}.csv", index=False)

        L += [f"## {tf}", "", "| Tag | " + " | ".join(map(str, YEARS)) + " | all years |",
              "|---|" + "---|" * (len(YEARS) + 1)]
        def tag_row(label, mask):
            sub = t[mask]
            L.append(f"| {label} | " + " | ".join(cell(stats(sub[sub.year == y])) for y in YEARS)
                     + f" | {cell(stats(sub))} |")
        tag_row("**All trades**", t.net_pnl.notna())
        tag_row("Long", t.direction == "LONG")
        tag_row("Short", t.direction == "SHORT")
        tag_row("Narrow box", t.narrow_box == True)
        tag_row("Wide box", t.narrow_box == False)
        tag_row("Box tag unknown (no 20-day history)", t.narrow_box.isna())
        tag_row("With trend", t.with_trend == True)
        tag_row("Against trend", t.with_trend == False)
        tag_row("Trend tag unknown", t.with_trend.isna())
        tag_row("FOMC/CPI/NFP day", t.event_day == True)
        tag_row("Other days", t.event_day == False)

        L += ["", "By quarter (trades / expectancy / P&L):", "", "| Quarter | Result |", "|---|---|"]
        for q, g in t.groupby("quarter"):
            L.append(f"| {q} | {cell(stats(g))} |")

        L += ["", f"### Candidate filters — {tf}", "",
              "| Filter | " + " | ".join(f"{y}: all → kept" for y in YEARS) + " | Years improved | Passes rule? |",
              "|---|" + "---|" * len(YEARS) + "---|---|"]
        for name, (col, keep) in CANDIDATES.items():
            rows, n_better, passes, unknown = evaluate_filter(t, col, keep)
            cells = [f"${r['all']['exp']:+.2f} → ${r['kept']['exp']:+.2f} ({r['kept']['n']}) {'✅' if r['improved'] else '❌'}"
                     for r in rows]
            L.append(f"| {name} | " + " | ".join(cells) + f" | {n_better} / 4 | **{'YES' if passes else 'no'}** |")
            verdicts.append((tf, name, n_better, passes, unknown))
        L.append("")

    # 2026 long/short split — information only, from the Phase 4 official trade files
    L += ["## 2026 holdout long/short split (INFORMATION ONLY — may not be used to choose filters)", "",
          "From the Phase 4 official run (base costs). Cells: trades / expectancy / P&L.", "",
          "| TF | Long | Short |", "|---|---|---|"]
    for tf in TFS:
        h = pd.read_csv(PHASE4 / f"trades_A_{tf}_holdout.csv")
        L.append(f"| {tf} | {cell(stats(h[h.direction == 'LONG']))} | {cell(stats(h[h.direction == 'SHORT']))} |")

    L += ["", "## Summary — which candidate filters pass the ≥ 3-of-4-years rule", "",
          "| TF | Filter | Years improved | Passes? | Trades without a tag (excluded from that filter's test) |",
          "|---|---|---:|---|---:|"]
    L += [f"| {tf} | {name} | {n} / 4 | **{'YES' if ok else 'no'}** | {unk} |" for tf, name, n, ok, unk in verdicts]
    (OUT / "phase4b_filter_discovery.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    for tf, name, n, ok, _ in verdicts:
        print(f"{tf:3} {name:24} improved {n}/4 years -> {'PASSES' if ok else 'does not pass'}")


if __name__ == "__main__":
    main()
