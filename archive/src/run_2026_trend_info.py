"""INFORMATION ONLY: A vs A + with-trend on the 2026 holdout period (spec v1.4 §12, 4c note).

2026 has already been seen, so this can neither confirm nor reject the filter.
Same Phase 4 code and settings (kill switch on), M15 and H1, three cost cases.
Reads 2026-01-01 -> 2026-09-30, plus Nov-Dec 2025 (development data) only to give
the trend filter its first 20 completed daily closes. Never reads 2010-2021.

Run:  .venv/Scripts/python -m src.run_2026_trend_info
"""
import json

import pandas as pd

from src import metrics
from src.backtest import Events, bot_a_chooser, build_days, load_bars, run, trades_frame
from src.calendar_events import OUT as CALENDAR_PATH
from src.config import PROJECT_ROOT, load_settings
from src.filters import daily_closes, trend_up_tags, with_trend_chooser
from src.run_phase3 import TFS, account_from, cost_cases, fmt_money
from src.run_phase4 import london_window
from src.strategy_asian import Params

OUT = PROJECT_ROOT / "results" / "phase4" / "with_trend_2026_information_only.md"
PHASE4_BASE = {"M15": (62, 572), "H1": (49, 534)}     # Phase 4 official A, base costs (trades, rounded net $)
CASES = ["base", "spread x1.5", "commission 0.0025%"]
BOTS = ["A", "A + with-trend"]
TREND_HISTORY_FROM = pd.Timestamp("2025-11-01", tz="UTC")


def main():
    settings = load_settings()
    symbol = settings["mt5"]["symbol"]
    meta = json.loads((PROJECT_ROOT / "data" / "raw" / f"{symbol}_metadata.json").read_text())
    period = settings["periods"]["holdout"]
    start, end = london_window(period["start"], period["end"])
    m1 = load_bars(symbol, "M1", start, end, end)
    history = load_bars(symbol, "M1", TREND_HISTORY_FROM, start, start)
    closes = daily_closes(pd.concat([history, m1], ignore_index=True))
    events = Events(pd.read_parquet(CALENDAR_PATH).time_utc)
    p, acct, costs = Params.from_settings(settings), account_from(settings, meta), cost_cases(settings)
    months = metrics.all_months(period["start"], period["end"])

    res = {}
    for tf, tf_min in TFS.items():
        days = build_days(m1, load_bars(symbol, tf, start, end, end), meta["point"])
        trend = trend_up_tags([d.date for d in days], closes).to_dict()
        choosers = {"A": bot_a_chooser(tf_min), "A + with-trend": with_trend_chooser(bot_a_chooser(tf_min), trend)}
        for bot, chooser in choosers.items():
            for case in CASES:
                t = trades_frame(run(days, chooser, p, costs[case], acct, events))
                s = metrics.summarize(t, months, acct.initial_balance)
                s["exp_r_net"] = float((t.net_pnl / (t.stop_distance * t.lots * meta["contract_size"])).mean()) \
                    if len(t) else float("nan")
                res[(tf, bot, case)] = s
        a = res[(tf, "A", "base")]
        assert (a["trades"], round(a["net_profit"])) == PHASE4_BASE[tf], f"{tf}: A does not reproduce Phase 4"
        print(f"{tf}: plain A reproduces Phase 4 ({a['trades']} trades, {fmt_money(a['net_profit'])}).")

    L = ["# INFORMATION ONLY — A vs A + with-trend on the 2026 holdout period (Jan–Sep)", "",
         "**Not a verdict.** 2026 was already seen in Phase 4, so it can neither confirm nor reject the filter "
         "(spec §12, 4c). Same Phase 4 code and settings: kill switch on, real spreads. Plain A reproduces the "
         "Phase 4 numbers exactly. Expectancy in R = net P&L ÷ the trade's initial risk in $.", ""]
    for tf in TFS:
        L += [f"## {tf}", "", "| Metric | " + " | ".join(f"{b} — {c}" for c in CASES for b in BOTS) + " |",
              "|---|" + "---:|" * (len(CASES) * len(BOTS))]
        cols = [res[(tf, b, c)] for c in CASES for b in BOTS]
        row = lambda name, f: L.append(f"| {name} | " + " | ".join(f(s) for s in cols) + " |")
        row("Trades", lambda s: f"{s['trades']}")
        row("Win rate", lambda s: f"{s['win_rate']:.1%}")
        row("Expectancy / trade ($)", lambda s: f"${s['expectancy_usd']:+.2f}")
        row("**Expectancy / trade (R, net)**", lambda s: f"**{s['exp_r_net']:+.3f}R**")
        row("Net profit", lambda s: fmt_money(s["net_profit"]))
        row("Average month", lambda s: fmt_money(s["avg_month"]))
        row("% months profitable", lambda s: f"{s['pct_months_profitable']:.0%}")
        row("Fewest profitable in a 6-month window", lambda s: f"{s['min_profitable_in_6m_window']} / 6")
        row("Worst month", lambda s: f"{fmt_money(s['worst_month'])} ({s['worst_month_label']})")
        row("Max drawdown", lambda s: f"{fmt_money(s['max_dd_usd'])} ({s['max_dd_pct']:.1%})")
        row("FTMO breach", lambda s: "no" if not s["ftmo_breached"] else "YES")
        row("FTMO-flagged exits", lambda s: f"{s['ftmo_flagged_exits']}")
        L += ["", "Monthly net P&L:", "", "| Month | " + " | ".join(f"{b} — {c}" for c in CASES for b in BOTS) + " |",
              "|---|" + "---:|" * (len(CASES) * len(BOTS))]
        for mth in cols[0]["monthly"].index:
            L.append(f"| {mth} | " + " | ".join(fmt_money(s["monthly"][mth]) for s in cols) + " |")
        L.append("")
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    for tf in TFS:
        for b in BOTS:
            s = res[(tf, b, "base")]
            print(f"{tf:3} {b:15} base: {s['trades']:3} trades, net {fmt_money(s['net_profit']):>6}, "
                  f"{s['exp_r_net']:+.3f}R, max DD {fmt_money(s['max_dd_usd'])}, worst month {fmt_money(s['worst_month'])}")
    print(f"written {OUT.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
