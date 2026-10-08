"""Phase E3-1 — build and verify (docs/EXPERIMENT_3_SPEC.md §7). No performance numbers.

  * day boundary: the broker's D1 bars must equal H1 bars grouped by broker day (New York 17:00)
  * independent sanity check: signals and trades recomputed by src/exp3/sanity.py must match the engine
  * future-scramble test, 20 random cut times, on the whole portfolio (every market at once)
  * market availability, history start dates and the cost table -> results/exp3/e3_1_build_report.md

Run first:  .venv/Scripts/python -m src.exp3.pull_data
Then:       .venv/Scripts/python -m src.exp3.run_e3_1
"""
import json
import time

import numpy as np
import pandas as pd

from src.exp2.engine import trades_frame
from src.exp2.run_e2_1 import scramble_after
from src.exp3 import sanity
from src.exp3.data import WINDOW_END, WINDOW_START, build_market, load_frames, load_specs, make_engine, strategy
from src.exp3.markets import RESULTS, SPECS_PATH
from src.timeutils import utc_to_server

N_CUTS, CUT_SEED = 20, 31


def run_market(spec, d1, h1):
    m = build_market(d1, h1, spec["point"])
    return make_engine(spec, m).run(strategy(m))


def day_boundary_check(d1, h1):
    """Share of D1 bars whose OHLC equals the H1 bars of the same broker (server) day."""
    day = utc_to_server(h1.time_utc).dt.date.to_numpy()
    g = h1.groupby(day)
    agg = pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(), "close": g.close.last()})
    d1_day = utc_to_server(d1.time_utc).dt.date.to_numpy()
    ref = agg.reindex(d1_day)
    same = np.isclose(ref[["open", "high", "low", "close"]].to_numpy(),
                      d1[["open", "high", "low", "close"]].to_numpy(), rtol=0, atol=1e-9).all(axis=1)
    weekend = pd.Series(pd.to_datetime(d1_day)).dt.dayofweek.isin([5, 6]).sum()
    return int(same.sum()), len(d1), d1_day[~same], int(weekend)


def independent_check(spec, d1, h1, res):
    point = spec["point"]
    t_open = d1.time_utc.dt.tz_convert(None).to_numpy().astype("datetime64[ns]").astype(np.int64)
    h1_t = h1.time_utc.dt.tz_convert(None).to_numpy().astype("datetime64[ns]").astype(np.int64)
    trades, sig = sanity.simulate(d1, h1_t, h1.open.to_numpy(), h1.high.to_numpy(), h1.low.to_numpy(),
                                  h1.spread_used.to_numpy() * point, t_open, d1.spread_used.to_numpy() * point)
    eng = trades_frame(res)
    t_close = t_open + 24 * 3600 * 10**9
    sig_at = dict(zip(t_close.tolist(), sig.tolist()))
    eng_signals = [(t, d[0]) for t, kind, d, _ in res.decisions if kind == "signal"]
    signals_ok = all(sig_at.get(t) == d for t, d in eng_signals)
    same, worst, stops_ok = sanity.compare(eng, trades, tol=10 * point)
    return {"engine_trades": len(eng), "independent_trades": len(trades), "identical": same,
            "signals_checked": len(eng_signals), "signals_agree": signals_ok, "worst_stop_gap": worst,
            "stops_ok": stops_ok,
            "pass": len(eng) == len(trades) == same and signals_ok and stops_ok}


def leak_test(specs, frames, base, n_cuts=N_CUTS, seed=CUT_SEED):
    """Future-scramble test: per market, n_cuts random cut times inside its own history; every decision
    before the cut must be unchanged when all its data after the cut is shuffled."""
    rng = np.random.default_rng(seed)
    ok = {sym: 0 for sym in base}
    before_n = {sym: [] for sym in base}
    changed = {sym: [] for sym in base}
    for c in range(n_cuts):
        for s in specs:
            sym = s["symbol"]
            h1 = frames[sym][1]
            cut = pd.Timestamp(int(rng.integers(h1.time_utc.iloc[0].value, h1.time_utc.iloc[-1].value)), tz="UTC")
            d1, h1 = (scramble_after(f, cut, rng) for f in frames[sym])
            scr = run_market(s, d1, h1)
            b = sorted((d for d in base[sym].decisions if d[0] <= cut.value), key=str)
            b2 = sorted((d for d in scr.decisions if d[0] <= cut.value), key=str)
            ok[sym] += b == b2
            before_n[sym].append(len(b))
            changed[sym].append(len(set(map(str, base[sym].decisions)) ^ set(map(str, scr.decisions))))
            assert all(seen <= when for when, _, _, seen in scr.decisions)
    return ok, before_n, changed


def main():
    t0 = time.time()
    specs = load_specs()
    meta = json.loads(SPECS_PATH.read_text(encoding="utf-8"))
    frames = {s["symbol"]: load_frames(s) for s in specs}
    for d1, h1 in frames.values():
        assert d1.time_utc.min() >= WINDOW_START and h1.time_utc.max() < WINDOW_END
    base = {s["symbol"]: run_market(s, *frames[s["symbol"]]) for s in specs}
    RESULTS.mkdir(parents=True, exist_ok=True)

    L = ["# Phase E3-1 — data and build (no performance numbers)", "",
         f"Broker: {meta['broker']} ({meta['server']}), pulled {meta['pulled_at_utc'][:16]} UTC. "
         f"Window {WINDOW_START:%Y-%m-%d} → 2026-09-30, read through `src/data_access.py`; nothing before 2022 loaded.", "",
         "## Market availability and history", "",
         "| Market | Broker symbol | First daily bar (UTC) | Daily bars in window |", "|---|---|---|---:|"]
    for s in specs:
        d1 = frames[s["symbol"]][0]
        L.append(f"| {s['market']} | {s['symbol']} | {d1.time_utc.iloc[0]:%Y-%m-%d} | {len(d1)} |")
    for name in meta["not_available"]:
        L.append(f"| {name} | not offered | — | — |")

    L += ["", "## Costs and swap (recorded from MT5 `symbol_info`)", "",
          "Spread estimate = 75th percentile of real spread on the first H1 bar of each broker day (the daily-bar open). "
          "Used wherever the broker recorded 0. Swap = current values applied to all history (estimate).", "",
          "| Symbol | Contract | Min lot / step | Commission per side | Open-hour spread p75 (price) | Real spreads from | "
          "Daily bars with estimated spread | Swap long / short (%/yr) | Triple swap |",
          "|---|---:|---|---|---:|---|---:|---|---|"]
    for s in specs:
        comm = (f"{s['commission_pct_per_side']}% of notional" if s["commission_pct_per_side"]
                else f"${s['commission_per_lot_usd_per_side']:.2f}/lot" if s["commission_per_lot_usd_per_side"] else "$0")
        triple = s["triple_swap_day"] + ("" if s["triple_swap_day_from_broker"]
                                         else f" (broker field {s['swap_rollover3days_field']} = invalid; provisional)")
        L.append(f"| {s['symbol']} | {s['contract_size']:g} | {s['volume_min']:g} / {s['volume_step']:g} | {comm} | "
                 f"{s['open_hour_p75_points'] * s['point']:.{s['digits']}f} | {s['real_spreads_from_utc'][:10]} | "
                 f"{s['d1_bars_estimated_pct']}% | {s['swap_long_pct_per_year']} / {s['swap_short_pct_per_year']} | {triple} |")

    L += ["", "## Day boundary (broker D1 = H1 grouped by broker day, New York 17:00)", ""]
    for s in specs:
        same, n, diff, weekend = day_boundary_check(*frames[s["symbol"]])
        L.append(f"- {s['symbol']}: {same} / {n} daily bars identical; weekend-dated bars: {weekend}"
                 + (f"; differing days: {', '.join(map(str, diff[:5]))}" if len(diff) else ""))

    L += ["", "## Independent sanity check (src/exp3/sanity.py, no shared code)", "",
          "| Symbol | Engine trades | Independent trades | Identical (entry, direction, exit, reason) | "
          "Engine signals agreeing | Worst stop difference | Pass |", "|---|---:|---:|---:|---|---:|---|"]
    for s in specs:
        c = independent_check(s, *frames[s["symbol"]], base[s["symbol"]])
        L.append(f"| {s['symbol']} | {c['engine_trades']} | {c['independent_trades']} | {c['identical']} | "
                 f"{c['signals_checked']} / {c['signals_checked'] if c['signals_agree'] else 'NOT all'} | "
                 f"{c['worst_stop_gap']:.2e} | {'yes' if c['pass'] else '**NO**'} |")
    print(f"checks done ({time.time() - t0:.0f}s)")

    ok, before_n, changed = leak_test(specs, frames, base)
    L += ["", f"## Future-scramble test (portfolio, {N_CUTS} random cut times per market inside its own history, "
          "all its data after the cut shuffled)",
          "", "| Symbol | Cuts with every decision before the cut identical | Decisions before the cut (min / median) | "
          "Decisions changed after the cut (min / median) |", "|---|---:|---|---|"]
    for sym in base:
        L.append(f"| {sym} | **{ok[sym]} / {N_CUTS}** | {min(before_n[sym])} / {int(np.median(before_n[sym]))} | "
                 f"{min(changed[sym])} / {int(np.median(changed[sym]))} |")
    L.append("\nEvery decision is also checked to be logged with data no newer than its decision time.")
    L += ["", "## Notes and open questions for Yash", "",
          "- Germany 40 and Japan 225 are not offered by this broker: skipped (spec §3).",
          "- EURUSD, USDJPY, AUDUSD history starts 2025-05-19 on this broker (MT5 returns nothing earlier; "
          "max-bars is unlimited). They miss 2022-2024 entirely. Spec §3 says skip a market with 'too little "
          "history' but does not define it — Yash to decide before E3-2.",
          "- Commission: FX $2.50/lot/side and gold 0.0007% confirmed from deals on Yash's trial account. MT5 "
          "`symbol_info` has no commission field; oil and indices have no trial deals, so spec values are used unverified.",
          "- Triple swap: only USOIL gives a valid day (Friday). The others read 7 (invalid), as gold did in "
          "Experiment 2; Wednesday is used provisionally (Experiment 2 clarification 3) — Yash to confirm.",
          "- USDJPY P&L, commission and swap are computed in JPY (its profit currency); results in R are unaffected. "
          "The $ conversion for FTMO sizing is an E3-2 task.",
          "- Fills: entries and 20-day exits at the daily open, paying that day's open-hour spread; stops are checked "
          "on H1 bars (longs on bid lows, shorts on ask highs; a gap through the stop fills at the open)."]
    (RESULTS / "e3_1_build_report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"done ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
