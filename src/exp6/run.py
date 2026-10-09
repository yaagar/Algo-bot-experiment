"""Experiment 6 runner — one config-driven entry point (spec §10, config/exp6.yaml).

  .venv/Scripts/python -m src.exp6.run screen     locked swap table + §3 cost screen (no returns)
  .venv/Scripts/python -m src.exp6.run e6_1       build checks: leak test, rebuild, hand-check, mechanics (no returns)
"""
import json
import sys

import numpy as np
import pandas as pd

from src.data_access import read_prices
from src.exp6 import data, engine
from src.exp6.c1 import c1_forecasts
from src.exp6.costs import PROCESSED, RESULTS, load_config, locked_swaps, screen
from src.exp6.rebuild import rebuild
from src.leak_test import decisions_until

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
    (RESULTS / "e6_0_swaps_locked.json").write_text(swaps.to_json(orient="records", indent=1), encoding="utf-8")
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


def scramble_after(frame, cut, rng):
    """Shuffle every bar after `cut` (prices move to other timestamps; the future becomes nonsense)."""
    out = frame.copy()
    after = np.flatnonzero((out.time_utc > cut).to_numpy())
    cols = ["open", "high", "low", "close"]
    out.loc[after, cols] = out.loc[rng.permutation(after), cols].to_numpy()
    return out


def leak_test(cfg, frames, n_cuts=20, seed=6):
    """Future-scramble test on the full system: every decision, fill, equity and breach at or before
    the cut must be identical when all markets' later bars are shuffled."""
    base, _ = engine.run(data.load_universe(cfg, "gate", frames), cfg)
    t0 = min(f.time_utc.min() for f in frames.values()).value
    t1 = max(f.time_utc.max() for f in frames.values()).value
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(n_cuts):
        cut = pd.Timestamp(int(rng.integers(t0, t1)), tz="UTC")
        scr = {s: scramble_after(f, cut, rng) for s, f in frames.items()}
        res, _ = engine.run(data.load_universe(cfg, "gate", scr), cfg)
        b, s_ = decisions_until(base, cut.value), decisions_until(res, cut.value)
        rows.append({"cut_utc": cut, "decisions_before_cut": len(b), "identical_before_cut": b == s_,
                     "decisions_changed_after_cut": len(set(base.decisions) ^ set(res.decisions))})
    return pd.DataFrame(rows)


def max_diff(a, b):
    return float(np.nanmax(np.abs(np.asarray(a, float) - np.asarray(b, float))))


def rebuild_check(cfg, frames, u, res):
    """Independent rebuild vs engine: per broker day (f, targets, positions, equity) and per Prague day."""
    last_day = pd.Timestamp(max(m.days[-1] for m in u.markets)).date()
    rd, rf, rftmo = rebuild(cfg, frames, RESULTS, last_day)
    ed = pd.DataFrame(res.daily)
    syms = [m.symbol for m in u.markets]
    dec = pd.DataFrame([d for d in res.decisions if d[1] == "dec"], columns=["t", "k", "sym", "f", "target", "new"])
    new_e = dec.pivot(index="t", columns="sym", values="new")[syms].to_numpy()
    fe = pd.DataFrame(res.fills)
    eng = res.limits.days
    common = sorted(set(eng) & set(rftmo))
    minimum = lambda days, d: np.nan if days[d]["min_equity"] is None else days[d]["min_equity"]
    eng_breaches = sorted({(str(pd.Timestamp(b[0], tz="UTC").tz_convert("Europe/Prague").date()), b[1]) for b in res.limits.breaches})
    reb_breaches = sorted({(str(d), r) for d in common for r in rftmo[d]["breaches"]})
    return {
        "days_engine": len(ed), "days_rebuild": len(rd),
        "same_days": bool((pd.to_datetime(ed.day).dt.date.to_numpy() == rd.day.to_numpy()).all()),
        "max_diff_forecast_f": max_diff(ed[[f"f_{s}" for s in syms]], rd[[f"f_{s}" for s in syms]]),
        "max_diff_target_lots": max_diff(ed[[f"target_{s}" for s in syms]], rd[[f"target_{s}" for s in syms]]),
        "max_diff_position_lots_6dp": max_diff(new_e, np.round(rd[[f"new_{s}" for s in syms]].to_numpy(), 6)),
        "max_diff_equity_at_close_usd": max_diff(ed.equity, rd.equity),
        "fills_engine": len(fe), "fills_rebuild": len(rf),
        "max_diff_fill_price": max_diff(fe.price, rf.price) if len(fe) == len(rf) else None,
        "prague_days_engine": len(eng), "prague_days_rebuild": len(rftmo),
        "max_diff_ftmo_start_balance_usd": max_diff([eng[d]["start_balance"] for d in common], [rftmo[d]["start_balance"] for d in common]),
        "max_diff_ftmo_min_equity_usd": max_diff([minimum(eng, d) for d in common], [minimum(rftmo, d) for d in common]),
        "ftmo_breach_days_identical": eng_breaches == reb_breaches,
    }


def handcheck(u, res, sig, n=10):
    """n position changes spread through the period, with what is needed to re-derive them (no P&L)."""
    fl = pd.DataFrame(res.fills)
    pick = fl.iloc[np.linspace(0, len(fl) - 1, n).round().astype(int)]
    idx = {m.symbol: i for i, m in enumerate(u.markets)}
    rows = []
    for r in pick.itertuples():
        s = sig[idx[r.symbol]]
        row = s.iloc[int(np.searchsorted(s.day.to_numpy(), np.datetime64(r.decision_day), "right")) - 1]
        utc = pd.Timestamp(int(r.t), tz="UTC")
        server = utc.tz_convert("America/New_York").tz_localize(None) + pd.Timedelta(hours=7)
        rows.append({"symbol": r.symbol, "decision_day_server": str(pd.Timestamp(r.decision_day).date()),
                     "fill_utc": utc.strftime("%Y-%m-%d %H:%M"), "fill_server": server.strftime("%Y-%m-%d %H:%M"),
                     "f": round(row.f, 4), "s_21": row.s_21, "s_63": row.s_63, "s_252": row.s_252,
                     "lots_before": round(r.lots_before, 6), "lots_after": round(r.lots_after, 6),
                     "bid_open": r.bid_open, "fill_price": round(r.price, 8), "spread_charged": r.spread,
                     "commission_usd": round(r.commission_usd, 4),
                     "swap_accrued_on_position_usd": round(r.swap_accrued_before, 4)})
    return pd.DataFrame(rows)


def mechanics(cfg, u, res, sig):
    """Per market: position changes per year, average holding days, % of days at each forecast level,
    min-lot skips the FTMO sizes would have; plus peak margin use (margin / equity at 1:30)."""
    fl = pd.DataFrame(res.fills)
    fl["year"] = pd.to_datetime(fl.t, utc=True).dt.year
    base = cfg["sizing"]["capital"] * cfg["sizing"]["target_vol"]
    scale = {f"${s['capital']:,}@{int(s['target_vol'] * 100)}%": s["capital"] * s["target_vol"] / base
             for s in cfg["sizing"]["ftmo_sizes"]}
    rows = []
    for i, m in enumerate(u.markets):
        g = fl[fl.symbol == m.symbol].sort_values("t")
        holds, start, prev = [], None, 0.0
        for r in g.itertuples():
            if prev != 0 and start is not None and (r.lots_after == 0 or np.sign(r.lots_after) != np.sign(prev)):
                holds.append((r.t - start) / 86400e9)
                start = None
            if r.lots_after != 0 and (prev == 0 or np.sign(r.lots_after) != np.sign(prev)):
                start = r.t
            prev = r.lots_after
        s = sig[i][sig[i].tradeable]
        row = {"symbol": m.symbol, "class": cfg["classes"][m.cls],
               "changes_per_year": round(g.groupby("year").size().reindex(range(2023, 2026), fill_value=0).mean(), 1),
               "avg_holding_days": round(float(np.mean(holds)), 1) if holds else None,
               **{f"pct_days_f={lv}": round(100 * float(np.isclose(s.f, v).mean()), 1)
                  for lv, v in (("-1", -1), ("-1/3", -1 / 3), ("0", 0), ("+1/3", 1 / 3), ("+1", 1))}}
        held = g[g.lots_after != 0]
        for name, k in scale.items():
            row[f"minlot_skips {name}"] = f"{int((np.abs(held.lots_after * k) < m.volume_min).sum())}/{len(held)}"
        rows.append(row)
    d = pd.DataFrame(res.daily)
    return pd.DataFrame(rows), float((d.margin_used / d.equity).max())


def e6_1():
    cfg = data.load_config()
    frames = data.load_frames(cfg, "gate")
    u = data.load_universe(cfg, "gate", frames)
    res, sig = engine.run(u, cfg)
    print("leak test ...", flush=True)
    leak = leak_test(cfg, frames)
    print("rebuild ...", flush=True)
    rb = rebuild_check(cfg, frames, u, res)
    hc = handcheck(u, res, sig)
    mech, peak = mechanics(cfg, u, res, sig)
    symbols = [m.symbol for m in u.markets]
    c1 = []                                                         # smoke test only: 3 seeds, no results
    for seed in range(3):
        f_c1 = c1_forecasts(sig, symbols, seed)
        r1, _ = engine.run(u, cfg, f_override=f_c1)
        c1.append({"seed": seed, "fills": len(r1.fills),
                   "days_sign_flipped": sum(int((np.sign(f_c1[s]) != np.sign(sig[i].f.to_numpy())).sum()) for i, s in enumerate(symbols)),
                   "same_magnitudes": all(np.allclose(np.abs(f_c1[s]), np.abs(sig[i].f)) for i, s in enumerate(symbols))})
    variants = {v: len(engine.run(u, data.variant_config(cfg, v))[0].fills) for v in cfg["variants"]}
    leak.to_csv(RESULTS / "e6_1_leak_test.csv", index=False)
    (RESULTS / "e6_1_rebuild_check.json").write_text(json.dumps(rb, indent=1), encoding="utf-8")
    hc.to_csv(RESULTS / "e6_1_handcheck_10_position_changes.csv", index=False)
    mech.to_csv(RESULTS / "e6_1_mechanics.csv", index=False)
    summary = {"leak_cuts": len(leak), "leak_identical": int(leak.identical_before_cut.sum()),
               "leak_min_changed_after": int(leak.decisions_changed_after_cut.min()),
               "peak_margin_use_pct_of_equity": round(100 * peak, 2), "c1_smoke": c1, "variant_fills": variants}
    (RESULTS / "e6_1_summary.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
    print(json.dumps(summary, default=str))
    print(json.dumps(rb))


if __name__ == "__main__":
    {"screen": run_screen, "e6_1": e6_1}[sys.argv[1]]()
