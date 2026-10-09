"""Experiment 7 runner. Phase e7_0 = pattern count only (spec §4): no exits, no P&L, no R outcomes.

    .venv/Scripts/python -m src.exp7.run e7_0
"""
import json
import sys

import numpy as np
import pandas as pd
import yaml

from src.backtest import Events
from src.config import PROJECT_ROOT
from src.data_access import PROCESSED, read_prices, read_usd_events
from src.exp7.pattern import REASONS, h1_context, m15_from_m1, scan

CONFIG_PATH = PROJECT_ROOT / "config" / "exp7.yaml"
RESULTS = PROJECT_ROOT / "results" / "exp7"
COLS = ["time_utc", "open", "high", "low", "close"]


def load_config():
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def load(cfg, period="development"):
    """(M15 from M1, broker H1, USD events) for the period, through the data lock (grant exp7)."""
    p = cfg["periods"][period]
    start, end = (pd.Timestamp(p[k], tz="UTC") for k in ("start", "end"))
    read = lambda tf, f: read_prices(cfg["symbol"], tf, start, end, columns=COLS, path=PROCESSED / f,
                                     grant=cfg["data_grant"]).reset_index(drop=True)
    events = Events(read_usd_events(start, end, grant=cfg["data_grant"]))
    return m15_from_m1(read("M1", cfg["m1_file"])), read("H1", cfg["h1_file"]), events


def tick_spread_frac(cfg):
    table = json.loads((PROJECT_ROOT / cfg["tick_spread_frac"]).read_text())
    return np.array([np.nan if x is None else x for x in table["p75_frac_by_server_hour"]])


def summarise(cands, period):
    """Counts only (spec §4 E7-0)."""
    q = cands[cands.qualifies].copy()
    fill = q.fill_time_utc.dt.tz_convert(None)
    months = pd.period_range(period["start"], pd.Timestamp(period["end"]) - pd.Timedelta(days=1), freq="M")
    per_month = fill.dt.to_period("M").value_counts().reindex(months, fill_value=0)
    boxed = cands[~cands.x_no_box]
    pct = lambda x: [float(np.percentile(q.stop_dist, x))]
    return {
        "candidates": len(cands),
        "qualifying": len(q),
        "per_year": {int(y): int(v) for y, v in fill.dt.year.value_counts().sort_index().items()},
        "idea_source_split": {"2019-2024": int((fill.dt.year <= 2024).sum()), "2025": int((fill.dt.year == 2025).sum())},
        "per_direction": {"long": int((q.direction > 0).sum()), "short": int((q.direction < 0).sum())},
        "per_month": {"median": float(per_month.median()), "min": int(per_month.min()), "max": int(per_month.max()),
                      "months_with_zero": int((per_month == 0).sum())},
        "days_with_setup": int(fill.dt.normalize().nunique()),
        "first_block": {r: int((cands.first_block == r).sum()) for r in REASONS},
        "fails_rule": {r: int(cands[f"x_{r}"].sum()) for r in REASONS},
        "box_rules_base": len(boxed),
        "stop_dist_usd": {"median": float(q.stop_dist.median()) if len(q) else None,
                          "p25": pct(25)[0] if len(q) else None, "p75": pct(75)[0] if len(q) else None},
        "spread_over_stop_median": float((q.spread / q.stop_dist).median()) if len(q) else None,
        "target_kind_pct": {k: round(100 * v / len(q), 1) for k, v in q.target_kind.value_counts().items()} if len(q) else {},
    }


def run_e7_0(cfg):
    m15, h1, events = load(cfg)
    cands = scan(m15, h1_context(h1, cfg), events, tick_spread_frac(cfg), cfg)
    s = summarise(cands, cfg["periods"]["development"])
    RESULTS.mkdir(parents=True, exist_ok=True)
    tag = f"e7_0_v{cfg['spec_version']}"                                  # v0.9 files stay as they were
    cands.to_csv(RESULTS / f"{tag}_candidates.csv", index=False)         # setups and blocks only, no outcomes
    (RESULTS / f"{tag}_counts.json").write_text(json.dumps(s, indent=1))
    print(json.dumps(s, indent=1))


if __name__ == "__main__":
    phase = sys.argv[1] if len(sys.argv) > 1 else "e7_0"
    if phase != "e7_0":
        sys.exit("Only e7_0 may run under spec v0.10 (draft).")
    run_e7_0(load_config())
