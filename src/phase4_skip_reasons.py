"""Phase 4 diagnostic: WHY did Bot A skip days in the holdout? (read-only)

Re-executes the Phase 4 holdout runs (same code, base costs, kill switch on),
checks the trade counts are identical to the official run, and tallies the
decision log: skipped boxes, no breakout, news blackout, size below minimum.
Changes nothing and adds no result to the verdict.

Run:  .venv/Scripts/python -m src.phase4_skip_reasons
"""
import json
from collections import Counter

import numpy as np
import pandas as pd

from src.backtest import Events, bot_a_chooser, build_days, load_bars, run
from src.calendar_events import OUT as CALENDAR_PATH
from src.config import PROJECT_ROOT, load_settings
from src.run_phase3 import TFS, account_from, cost_cases
from src.run_phase4 import OUT, london_window
from src.strategy_asian import Params, compute_box

OFFICIAL_TRADES = {"M15": 62, "H1": 49}   # Phase 4 results, commit 619f640


def main():
    settings = load_settings()
    symbol = settings["mt5"]["symbol"]
    meta = json.loads((PROJECT_ROOT / "data" / "raw" / f"{symbol}_metadata.json").read_text())
    period = settings["periods"]["holdout"]
    start, end = london_window(period["start"], period["end"])
    m1 = load_bars(symbol, "M1", start, end, end)
    events = Events(pd.read_parquet(CALENDAR_PATH).time_utc)
    p, acct = Params.from_settings(settings), account_from(settings, meta)

    L = ["# Phase 4 diagnostic — why holdout days had no trade (read-only)", "",
         "Same holdout code and data as the official run, base costs, kill switch on. Changes nothing.", ""]
    for tf, tf_min in TFS.items():
        days = build_days(m1, load_bars(symbol, tf, start, end, end), meta["point"])
        res = run(days, bot_a_chooser(tf_min), p, cost_cases(settings)["base"], acct, events)
        assert len(res.trades) == OFFICIAL_TRADES[tf], f"{tf}: {len(res.trades)} trades, official {OFFICIAL_TRADES[tf]}"
        outcome = Counter()
        for _, kind, _, detail, _ in res.decisions:
            if kind == "box" and isinstance(detail, str):
                outcome[f"box skipped: {detail}"] += 1
            elif kind in ("no trade", "blocked"):
                outcome[f"{kind}: {detail}"] += 1
        outcome["TRADED"] = len(res.trades)

        # stop distance needed vs the $50 / 0.01-lot limit: R above $50 cannot be sized
        heights = []
        for d in days:
            box, _ = compute_box(d.m1_min, d.m1_h, d.m1_l, d.m1_s, p)
            if box:
                heights.append(box.height)
        heights = np.array(heights)
        L += [f"## {tf}", "", f"Weekdays in holdout: {len(days)}", "", "| Outcome | Days |", "|---|---:|"]
        L += [f"| {k} | {v} |" for k, v in outcome.most_common()]
        L += ["", f"Valid boxes: {len(heights)}. Box height: median ${np.median(heights):.2f}, "
                  f"{(heights > 50).mean():.0%} wider than $50 (a breakout from such a box needs a stop over $50, "
                  f"i.e. under 0.01 lots at $50 risk).", ""]
        print(f"{tf}: trade count matches official ({len(res.trades)}).", dict(outcome.most_common()))
    (OUT / "skip_reasons.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("written results/phase4/skip_reasons.md")


if __name__ == "__main__":
    main()
