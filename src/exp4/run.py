"""Experiment 4 runner — one config-driven entry point for every phase (spec §10).

  .venv/Scripts/python -m src.exp4.run e4_1      build checks: leak test, independent rebuild, hand-check export

E4-1 (no performance numbers): on the development period (2022-2025) for both markets,
  1. future-scramble leak test, 20 cuts per market: shuffle every bar after a random time T,
     re-run the full system; every decision at or before T (each bar's scores, gates and F,
     every signal, fill, block and exit) must be identical;
  2. the independent rebuild (src/exp4/rebuild.py) must match the engine's table on every bar;
  3. 5 trades per market for Yash's hand-check, with UTC and server times and the four scores.
Later phases add their steps here, driven by config/exp4.yaml variants — no new runner scripts.
"""
import sys

import numpy as np
import pandas as pd

from src.exp4.data import RESULTS, build_market, load_config, load_events, load_frames, period
from src.exp4.rebuild import compare, rebuild
from src.exp4.system import run_market
from src.leak_test import decisions_until, scramble_after
from src.timeutils import utc_to_server

MARKETS = ("Gold", "US500")


def scramble_test(cfg, name, m1, h1, events, n_cuts=20, seed=4):
    mcfg = cfg["markets"][name]
    base = run_market(build_market(name, mcfg, m1, h1), cfg, events)[0]
    rng = np.random.default_rng(seed)
    t0, t1 = m1.time_utc.min().value, m1.time_utc.max().value
    rows = []
    for _ in range(n_cuts):
        cut = pd.Timestamp(int(rng.integers(t0, t1)), tz="UTC")
        m1s = scramble_after(m1, cut, rng)
        h1s = scramble_after(h1, cut, rng) if h1 is not None else None
        scr = run_market(build_market(name, mcfg, m1s, h1s), cfg, events)[0]
        before_base, before_scr = decisions_until(base, cut.value), decisions_until(scr, cut.value)
        rows.append({"market": name, "cut_utc": cut, "decisions_before_cut": len(before_base),
                     "identical_before_cut": before_base == before_scr,
                     "decisions_changed_after_cut": len(set(base.decisions) ^ set(scr.decisions))})
    return pd.DataFrame(rows)


def handcheck(trades, table, n=5):
    """n trades spread evenly through the period, with everything needed to re-derive them by hand."""
    pick = trades.iloc[np.linspace(0, len(trades) - 1, n).round().astype(int)].copy()
    out = pd.DataFrame({"market": pick.market, "direction": pick.direction})
    for c in ("signal", "entry", "exit"):
        utc = pd.to_datetime(pick[f"{c}_ns"], utc=True)
        out[f"{c}_utc"] = utc.dt.strftime("%Y-%m-%d %H:%M")
        out[f"{c}_server"] = utc_to_server(utc).dt.strftime("%Y-%m-%d %H:%M").values
    for s in ("A", "B", "C", "D"):
        out[f"score_{s}"] = pick[f"info_{s}"].round(4)
    out["F"] = pick.info_F.round(4)
    out["efficiency"] = pick.info_efficiency.round(4)
    out["shock_ratio"] = pick.info_shock_ratio.round(3)
    out["risk_fraction_of_R"] = pick.info_size.round(4)
    out["atr14_h1"] = pick.info_atr14.round(4)
    for c in ("entry_price", "entry_spread", "stop", "stop_distance", "lots", "exit_price"):
        out[c] = pick[c].round(5)
    out["exit_reason"] = pick.exit_reason
    return out


def e4_1():
    cfg = load_config()
    events = load_events()
    start, end = period(cfg, "development")
    leak, rebuild_rows, checks = [], [], []
    for name in MARKETS:
        mcfg = cfg["markets"][name]
        m1, h1 = load_frames(mcfg, start, end)
        mk = build_market(name, mcfg, m1, h1)
        _, table, trades = run_market(mk, cfg, events)
        print(f"{name}: running leak test ...", flush=True)
        leak.append(scramble_test(cfg, name, m1, h1, events))
        print(f"{name}: independent rebuild ...", flush=True)
        rep = compare(table, rebuild(mcfg, cfg, m1, h1))
        rebuild_rows.append({"market": name, **{k: v for k, v in rep.items() if k != "max_abs_diff"},
                             **{f"max_diff_{k}": v for k, v in rep.get("max_abs_diff", {}).items()}})
        checks.append(handcheck(trades, table))
    RESULTS.mkdir(parents=True, exist_ok=True)
    leak = pd.concat(leak, ignore_index=True)
    leak.to_csv(RESULTS / "e4_1_leak_test.csv", index=False)
    rb = pd.DataFrame(rebuild_rows)
    rb.to_csv(RESULTS / "e4_1_rebuild_check.csv", index=False)
    pd.concat(checks, ignore_index=True).to_csv(RESULTS / "handcheck_5_trades_per_market.csv", index=False)
    summary = leak.groupby("market").agg(cuts=("identical_before_cut", "size"),
                                         identical=("identical_before_cut", "sum"),
                                         min_changed_after=("decisions_changed_after_cut", "min"))
    print(summary.to_string())
    print(rb.to_string())
    return summary, rb


if __name__ == "__main__":
    {"e4_1": e4_1}[sys.argv[1]]()
