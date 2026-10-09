"""Experiment 4 runner — one config-driven entry point for every phase (spec §10).

  .venv/Scripts/python -m src.exp4.run e4_1      build checks: leak test, independent rebuild, hand-check export
  .venv/Scripts/python -m src.exp4.run e4_2      development run (2022-2025) + 2026 information run

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

from src.exp4.data import RESULTS, build_market, load_config, load_events, load_frames, period, variant_config
from src.exp4.evaluate import add_r, c1_total_r, daily_returns, deflated_sharpe, sharpe, stats
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


def spread_pick(frame, n):
    return frame.iloc[np.linspace(0, len(frame) - 1, n).round().astype(int)] if len(frame) >= n else frame


def handcheck(trades, gates_cfg, n=5, n_ranging=2):
    """n trades spread evenly through the period, at least n_ranging of them on RANGING days
    (efficiency < 0.30, F = D), with everything needed to re-derive them by hand."""
    ranging = trades.info_efficiency < gates_cfg["efficiency_trend"]
    first = spread_pick(trades[ranging], n_ranging)
    pick = pd.concat([first, spread_pick(trades[~ranging], n - len(first))]).sort_values("signal_ns").copy()
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
        checks.append(handcheck(trades, cfg["gates"]))
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


N_TRIALS = 69                    # results/trial_ledger.md: N = max(69, 50)
C1_SEEDS = range(1000)
ROBUSTNESS = ("entry_0.20", "entry_0.40", "stop_1.0", "stop_2.0")


def run_portfolio(mks, cfg, events, **costs):
    """Run every market; (trades with R/day/regime, {market: engine Result})."""
    out, res = [], {}
    for name, mk in mks.items():
        r, _, tr = run_market(mk, cfg, events, **costs)
        res[name] = r
        if len(tr):
            out.append(add_r(tr, mk.days))
    return pd.concat(out, ignore_index=True), res


def e4_2():
    """Spec §7-§8 with Change Log v1.3. Writes everything to results/exp4/; prints nothing about results."""
    cfg = load_config()
    events = load_events()
    start, end = period(cfg, "development")
    mks = {n: build_market(n, cfg["markets"][n], *load_frames(cfg["markets"][n], start, end)) for n in MARKETS}
    all_days = sorted(set().union(*(mk.days for mk in mks.values())))

    runs = {}
    for v in cfg["variants"]:
        runs[v] = run_portfolio(mks, variant_config(cfg, v), events)
        print(f"ran {v}", flush=True)
    main, main_res = runs["main"]
    stress, _ = run_portfolio(mks, variant_config(cfg, "main"), events, spread_mult=1.5, commission_mult=2.0, slippage_ticks=1)

    c1 = sum(c1_total_r(main_res[n].engine, main[main.market == n], C1_SEEDS) for n in MARKETS)
    print("C1 done", flush=True)
    daily = {v: daily_returns(t, all_days) for v, (t, _) in runs.items()}
    dsr = deflated_sharpe(daily["main"], [sharpe(x) for x in daily.values()], N_TRIALS)

    s_main = stats(main)
    years = main.groupby(main.day.dt.year).r.agg(["size", "sum"]).reindex([2022, 2023, 2024, 2025], fill_value=0)
    beats = float((s_main["total_r"] > c1).mean())
    rob = {v: stats(runs[v][0]) for v in ROBUSTNESS}
    s_stress = stats(stress)
    verdict = [
        ("Trades (portfolio)", s_main["trades"], ">= 200", s_main["trades"] >= 200),
        ("Expectancy (R/trade)", round(s_main["expectancy"], 4), ">= +0.10", s_main["expectancy"] >= 0.10),
        ("Years with positive total R", int((years["sum"] > 0).sum()), ">= 3 of 4", (years["sum"] > 0).sum() >= 3),
        ("Worst year total R", round(float(years["sum"].min()), 2), ">= -10", years["sum"].min() >= -10),
        ("Beats % of C1 (portfolio total R)", round(100 * beats, 1), ">= 95%", beats >= 0.95),
        ("Deflated Sharpe probability", round(dsr["dsr"], 4), ">= 0.95", dsr["dsr"] >= 0.95),
        ("Stress expectancy (1.5x spread, 2x comm, +1 tick)", round(s_stress["expectancy"], 4), "> 0", s_stress["expectancy"] > 0),
        ("Worst robustness expectancy", round(min(r["expectancy"] for r in rob.values()), 4), "> 0",
         min(r["expectancy"] for r in rob.values()) > 0),
    ]
    passed = all(v[3] for v in verdict)

    # 2026 information only (main config, its own warm-up inside 2026)
    s26, e26 = period(cfg, "recent_info")
    mk26 = {n: build_market(n, cfg["markets"][n], *load_frames(cfg["markets"][n], s26, e26)) for n in MARKETS}
    info26, _ = run_portfolio(mk26, variant_config(cfg, "main"), events)

    RESULTS.mkdir(parents=True, exist_ok=True)
    main.drop(columns=[c for c in main.columns if c.endswith("_utc")]).to_csv(RESULTS / "e4_2_trades_main.csv", index=False)
    info26.drop(columns=[c for c in info26.columns if c.endswith("_utc")]).to_csv(RESULTS / "e4_2_trades_2026_info.csv", index=False)
    pd.DataFrame({"seed": list(C1_SEEDS), "c1_total_r": c1}).to_csv(RESULTS / "e4_2_c1_total_r_by_seed.csv", index=False)
    pd.DataFrame({"day": all_days, **{v: x for v, x in daily.items()}}).to_csv(RESULTS / "e4_2_daily_r_by_config.csv", index=False)

    f = lambda x: f"{x:+.3f}"
    lines = ["## Verdict (spec §8 development criteria)", "", "| Criterion | Value | Threshold | Result |", "|---|---:|---|---|"]
    lines += [f"| {n} | {v} | {th} | {'PASS' if ok else 'FAIL'} |" for n, v, th, ok in verdict]
    lines += [f"| **Overall** | | all must pass | **{'PASS' if passed else 'FAIL'}** |", "",
              f"Deflated Sharpe: daily Sharpe {dsr['sharpe_daily']:.4f} over {dsr['days']} days, skew {dsr['skew']:.2f}, "
              f"kurtosis {dsr['kurtosis']:.2f}; V = {dsr['V']:.3e} (cross-config {dsr['V_cross']:.3e}, sampling "
              f"{dsr['V_sampling']:.3e}; **{dsr['V_term']} term won**); SR0 = {dsr['SR0']:.4f}; N = {dsr['N']}. "
              f"C1 median total R {np.median(c1):+.1f}.", "",
              "## Per year (main, base costs)", "", "| Year | Trades | Total R |", "|---|---:|---:|"]
    lines += [f"| {y} | {int(r['size'])} | {f(r['sum'])} |" for y, r in years.iterrows()]
    lines += ["", "## Per regime of the entry day (main, base costs)", "", "| Regime | Trades | Expectancy (R) | Total R |", "|---|---:|---:|---:|"]
    for g in ("trending", "ranging"):
        st = stats(main[main.regime == g])
        lines.append(f"| {g} | {st['trades']} | {f(st['expectancy'])} | {f(st['total_r'])} |")
    lines += ["", "## Ablation and robustness (information only, base costs)", "", "| Configuration | Trades | Expectancy (R) | Total R |", "|---|---:|---:|---:|"]
    for v, (t, _) in runs.items():
        st = stats(t)
        lines.append(f"| {v} | {st['trades']} | {f(st['expectancy'])} | {f(st['total_r'])} |")
    lines.append(f"| main, cost stress | {s_stress['trades']} | {f(s_stress['expectancy'])} | {f(s_stress['total_r'])} |")
    st = stats(info26)
    lines += ["", f"**2026 information only** ({s26.date()} → latest data, main config): {st['trades']} trades, "
              f"expectancy {f(st['expectancy'])}R, total {f(st['total_r'])}R."]
    (RESULTS / "e4_2_tables.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("written", RESULTS / "e4_2_tables.md")


if __name__ == "__main__":
    {"e4_1": e4_1, "e4_2": e4_2}[sys.argv[1]]()
