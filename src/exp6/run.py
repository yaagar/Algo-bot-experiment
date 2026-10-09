"""Experiment 6 runner — one config-driven entry point (spec §10, config/exp6.yaml).

  .venv/Scripts/python -m src.exp6.run screen     locked swap table + §3 cost screen (no returns)
"""
import json
import sys

import pandas as pd

from src.data_access import read_prices
from src.exp6.costs import PROCESSED, RESULTS, load_config, locked_swaps, screen

EXP3_SPECS = RESULTS.parent / "exp3" / "market_specs.json"


def latest_closes(symbols):
    out = {}
    for s in symbols:
        d = read_prices(s, "D1", pd.Timestamp("2026-01-01", tz="UTC"), None, columns=["time_utc", "close"],
                        path=PROCESSED / f"{s}_D1.parquet")
        out[s] = float(d.close.iloc[-1])
    return out


def fx_with_full_coverage(cfg):
    """Change Log v1.1 (a): MetaQuotes FX pairs covering all of 2022-2025 with no hole > 5 days."""
    cov = pd.DataFrame(json.loads((RESULTS / "e6_0_metaquotes_fx_coverage.json").read_text(encoding="utf-8")))
    max_gap = cfg["screen"]["fx_full_coverage_max_gap_days"] * 24
    ok = (cov.offered.fillna(False).astype(bool) & (pd.to_datetime(cov.H1_first_utc, utc=True) <= pd.Timestamp("2022-01-04", tz="UTC"))
          & (pd.to_datetime(cov.H1_last_utc, utc=True) >= pd.Timestamp("2025-12-31", tz="UTC"))
          & (cov.H1_largest_gap_h <= max_gap))
    cov["full_coverage"] = ok
    cov.to_csv(RESULTS / "e6_0_metaquotes_fx_coverage.csv", index=False)
    return {p + ".sim" for p in cov.pair[ok]}


def run_screen():
    cfg = load_config()
    syms = pd.DataFrame(json.loads((RESULTS / "e6_0_symbols.json").read_text(encoding="utf-8"))["symbols"])
    syms = syms[syms["class"] != "Crypto"].reset_index(drop=True)
    fx_ok = fx_with_full_coverage(cfg)
    swaps = locked_swaps(syms, json.loads(EXP3_SPECS.read_text(encoding="utf-8"))["markets"],
                         latest_closes(syms.symbol))
    swaps.to_csv(RESULTS / "e6_0_swaps_locked.csv", index=False)
    candidates = syms[(syms["class"] != "FX") | syms.symbol.isin(fx_ok)].reset_index(drop=True)
    start, end = (pd.Timestamp(x, tz="UTC") for x in (cfg["periods"]["gate"]["start"], cfg["periods"]["gate"]["end"]))
    ticks = json.loads((RESULTS / "e6_0_tick_spreads.json").read_text(encoding="utf-8"))["symbols"]
    res = screen(cfg, candidates, swaps, start, end, ticks)
    excluded_fx = sorted(set(syms.symbol[syms["class"] == "FX"]) - fx_ok)
    res.to_csv(RESULTS / "e6_0_cost_screen.csv", index=False)
    group = res.assign(group=res["class"].map(cfg["classes"])).groupby("group").included.agg(["sum", "size"])
    print(res[["symbol", "class", "cost_ratio", "carry_ratio", "included", "reason"]].round(4).to_string())
    print(group.to_string())
    print("FX excluded for MetaQuotes coverage:", excluded_fx)
    n = int(res.included.sum())
    stop = n < cfg["screen"]["min_markets"] or (group["sum"] == 0).any()
    print(f"markets passing: {n}; STOP: {stop}")


if __name__ == "__main__":
    {"screen": run_screen}[sys.argv[1]]()
