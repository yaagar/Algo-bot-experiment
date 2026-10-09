"""Experiment 7 runner (spec v1.0). Phase e7_1 = build & verify: no outcomes are printed or saved.

    .venv/Scripts/python -m src.exp7.run e7_1

E7-0 (counts, spec v0.9 / v0.10) ran from earlier versions of this file; see git history.
"""
import json
import sys

import numpy as np
import pandas as pd
import yaml

from src.backtest import Events
from src.config import PROJECT_ROOT
from src.data_access import PROCESSED, read_prices, read_usd_events
from src.exp7 import controls, meta, rebuild
from src.exp7.system import Exp7Data, entry_view, run_system
from src.timeutils import utc_to_server

CONFIG_PATH = PROJECT_ROOT / "config" / "exp7.yaml"
RESULTS = PROJECT_ROOT / "results" / "exp7"
COLS = ["time_utc", "open", "high", "low", "close"]


def load_config():
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def load(cfg, period="development"):
    """M1 + broker H1 + USD events + spread model for the period, through the data lock (grant exp7)."""
    p = cfg["periods"][period]
    start, end = (pd.Timestamp(p[k], tz="UTC") for k in ("start", "end"))
    read = lambda tf, f: read_prices(cfg["symbol"], tf, start, end, columns=COLS, path=PROCESSED / f,
                                     grant=cfg["data_grant"]).reset_index(drop=True)
    events = Events(read_usd_events(start, end, grant=cfg["data_grant"]))
    return Exp7Data(read("M1", cfg["m1_file"]), read("H1", cfg["h1_file"]), events, tick_spread_frac(cfg))


def tick_spread_frac(cfg):
    table = json.loads((PROJECT_ROOT / cfg["tick_spread_frac"]).read_text())
    return np.array([np.nan if x is None else x for x in table["p75_frac_by_server_hour"]])


# --- E7-1 checks (no outcomes printed or saved) ----------------------------------------------------

def scrambled(data, cut, seed):
    """Copy of the data with every bar from `cut` on shuffled (and shifted +$50): the future is garbage."""
    rng = np.random.default_rng(seed)
    out = []
    for df in (data.m1_df, data.h1):
        df = df.copy()
        after = np.flatnonzero((df.time_utc >= cut).to_numpy())
        perm = rng.permutation(after)
        for col in ("open", "high", "low", "close"):
            values = df[col].to_numpy(copy=True)
            values[after] = values[perm] + 50.0
            df[col] = values
        out.append(df)
    return Exp7Data(out[0], out[1], data.events, data.spread_frac)


def leak_test(data, cfg, trades, n_cuts=20):
    """Future-scramble test: for each cut, every trade that closed before the cut must be identical,
    and every trade entered before the cut must have the same entry, side, stop and target.
    Outcome fields are compared in code only; only pass/fail is reported."""
    t0, t1 = data.m1_df.time_utc.iloc[[0, -1]]
    cuts = [(t0 + (t1 - t0) * (k + 1) / (n_cuts + 1)).floor("1h") for k in range(n_cuts)]
    passed, changed_after = 0, 0
    for k, cut in enumerate(cuts):
        other = run_system(scrambled(data, cut, seed=k), cfg)[1]
        c = cut.value
        closed = lambda t: t[t.exit_ns < c].reset_index(drop=True)
        entered = lambda t: entry_view(t[t.entry_ns < c]).reset_index(drop=True)
        later = lambda t: entry_view(t[t.entry_ns >= c]).reset_index(drop=True)
        changed_after += not later(trades).equals(later(other))      # the scramble must bite
        try:
            pd.testing.assert_frame_equal(closed(trades), closed(other))
            pd.testing.assert_frame_equal(entered(trades), entered(other))
            passed += 1
        except AssertionError:
            pass
    return {"cuts": n_cuts, "passed": passed, "cuts_where_later_trades_changed": changed_after, "first_cut": str(cuts[0]), "last_cut": str(cuts[-1])}


def rebuild_check(data, cfg, trades):
    rb = rebuild.setups_and_trades(data.m1_df, data.h1, pd.to_datetime(data.events.t, utc=True),
                                   PROJECT_ROOT / cfg["tick_spread_frac"], cfg)
    eng = pd.DataFrame({"entry_ns": trades.entry_ns, "direction": np.where(trades.direction == "LONG", 1, -1),
                        "stop": trades.stop, "target": trades.target})
    m = eng.merge(rb, on=["entry_ns", "direction"], how="outer", suffixes=("", "_rb"), indicator=True)
    both = m[m._merge == "both"]
    return {"engine_trades": len(eng), "rebuild_trades": len(rb), "matched_time_and_side": len(both),
            "only_engine": int((m._merge == "left_only").sum()), "only_rebuild": int((m._merge == "right_only").sum()),
            "max_stop_diff": float((both.stop - both.stop_rb).abs().max()) if len(both) else None,
            "max_target_diff": float((both.target - both.target_rb).abs().max()) if len(both) else None}


def controls_smoke(data, cfg, trades, seeds=(0, 1, 2)):
    """3 seeds each: checks the controls are built right. Counts and entry facts only, no outcomes."""
    eligible = controls.trend_bars(data, cfg)
    out = {"c2_eligible_bars": len(eligible[0])}
    real_dist = np.sort(trades.stop_distance.to_numpy())
    for name in ("C1", "C2"):
        rows = []
        for s in seeds:
            t = controls.c1(data, trades, cfg, s) if name == "C1" else controls.c2(data, trades, cfg, s, eligible)
            row = {"seed": s, "trades": len(t), "longs": int((t.direction == "LONG").sum()),
                   "stop_dist_match": bool(np.allclose(np.sort(t.stop_distance.to_numpy()), real_dist))}
            if name == "C1":
                row["same_entry_times"] = bool(np.array_equal(np.sort(t.entry_ns), np.sort(trades.entry_ns)))
            else:
                hour = t.entry_utc.dt.tz_convert("Europe/London").dt.hour
                row["entries_in_hours"] = bool(((hour >= 7) & (hour < 20)).all())
            rows.append(row)
        out[name] = rows
    return out


def m2_smoke(cfg, seed=0):
    """M2 on SYNTHETIC trades only (no real outcomes): it must learn a planted signal, use only past
    trades and start predicting in 2021."""
    rng = np.random.default_rng(seed)
    n = 600
    days = pd.to_timedelta(np.sort(rng.uniform(0, 7 * 365, n)), unit="D")
    entry = pd.Series(pd.Timestamp("2019-01-02 10:00", tz="UTC") + days)
    t = pd.DataFrame({"entry_utc": entry, "exit_utc": entry + pd.Timedelta(hours=3),
                      "info_tstat": rng.normal(3, 1, n), "info_box_high": 10 + rng.uniform(0.5, 2, n),
                      "info_box_low": 10.0, "info_atr_h1": 1.0, "info_box_bars": rng.integers(6, 20, n),
                      "entry_price": rng.uniform(1300, 2000, n), "stop_distance": rng.uniform(3, 8, n)})
    label = pd.Series((rng.uniform(size=n) < 1 / (1 + np.exp(-(t.info_tstat - 3) * 1.5))).astype(int))
    prob = meta.walk_forward(t, label, cfg)
    year = t.entry_utc.dt.year
    has = prob.notna()
    return {"synthetic_trades": n, "first_year_predicted": int(year[has].min()),
            "no_prediction_before_2021": bool(prob[year < 2021].isna().all()),
            "probs_in_0_1": bool(prob[has].between(0, 1).all()),
            "corr_prob_vs_planted_input": round(float(np.corrcoef(prob[has], t.info_tstat[has])[0, 1]), 2),
            "kept_at_threshold": int(meta.keep(prob, cfg).sum()), "predicted": int(has.sum())}


def handcheck(trades, k=10, seed=7):
    """10 trades, entry side only (no exit, no P&L)."""
    e = entry_view(trades.sample(k, random_state=seed).sort_values("entry_ns"))
    utc = lambda x: pd.to_datetime(x, utc=True)
    fmt = lambda t: t.dt.strftime("%Y-%m-%d %H:%M").to_numpy()
    return pd.DataFrame({
        "signal_utc": fmt(utc(e.signal_ns)), "signal_server": fmt(utc_to_server(utc(e.signal_ns))),
        "entry_utc": fmt(utc(e.entry_ns)), "entry_server": fmt(utc_to_server(utc(e.entry_ns))),
        "side": e.direction.to_numpy(), "box_high": e.info_box_high.round(3).to_numpy(),
        "box_low": e.info_box_low.round(3).to_numpy(), "box_mid": e.info_box_mid.round(4).to_numpy(),
        "box_bars": e.info_box_bars.to_numpy(), "trend_tstat": e.info_tstat.round(2).to_numpy(),
        "entry_bid": e.entry_bid.round(3).to_numpy(), "spread_charged": e.entry_spread.round(3).to_numpy(),
        "entry": e.entry_price.round(3).to_numpy(), "stop": e.stop.round(3).to_numpy(),
        "stop_dist": e.stop_distance.round(3).to_numpy(), "target_2R": e.target.round(3).to_numpy()})


def mechanics(res, trades, setups):
    e = entry_view(trades)
    london = pd.to_datetime(e.entry_ns, utc=True).dt.tz_convert("Europe/London")
    by_year = lambda mask: {int(y): int(v) for y, v in london[mask].dt.year.value_counts().sort_index().items()}
    return {"setups": len(setups), "trades": len(e), "skipped_in_trade": res.skipped_in_trade,
            "engine_blocked": res.blocked, "long_per_year": by_year(e.direction == "LONG"),
            "short_per_year": by_year(e.direction == "SHORT"),
            "entries_per_london_hour": {int(h): int(v) for h, v in london.dt.hour.value_counts().sort_index().items()},
            "median_stop_usd": round(float(e.stop_distance.median()), 2)}


def run_e7_1(cfg):
    """Build & verify (spec §4). Prints and saves only entry-side facts and pass/fail checks."""
    data = load(cfg)
    res, trades, setups = run_system(data, cfg)
    report = {"mechanics": mechanics(res, trades, setups), "rebuild": rebuild_check(data, cfg, trades),
              "controls_smoke": controls_smoke(data, cfg, trades), "m2_smoke_synthetic": m2_smoke(cfg),
              "leak_test": leak_test(data, cfg, trades)}
    RESULTS.mkdir(parents=True, exist_ok=True)
    handcheck(trades).to_csv(RESULTS / "e7_1_handcheck_10_trades.csv", index=False)
    (RESULTS / "e7_1_checks.json").write_text(json.dumps(report, indent=1, default=str))
    print(json.dumps(report, indent=1, default=str))


PHASES = {"e7_1": run_e7_1}

if __name__ == "__main__":
    phase = sys.argv[1] if len(sys.argv) > 1 else ""
    if phase not in PHASES:
        sys.exit(f"Phases: {list(PHASES)}")
    PHASES[phase](load_config())
