"""Experiment 7 E7-2 scoring (spec v1.0 §5). Written and committed before any E7-2 result.

Plain English: run the base rules (M1) once on 2019-2025, then the 1,000-seed controls, the cost
stresses, the 6 robustness variants and the M2 walk-forward, and score every dev criterion:
  * expectancy = mean net R per trade; a year is positive if its total net R > 0 (London entry year);
  * "beats X% of C" = share of seeds whose expectancy is below M1's;
  * Deflated Sharpe on daily net R (London entry date; every London weekday with gold M1 data counts,
    no-trade days = 0), cross-configuration variance from the 7 full-period configurations
    (M1 + 6 variants; M2 covers fewer years and is judged separately), N = ledger N;
  * 1.5x spread criterion = expectancy > 0 with 1.5x spread; +1 tick slippage and both together are
    reported alongside;
  * M2: label win = net R > 0; compared with M1 on 2021-2025 only; adoption needs M1 PASS, higher
    expectancy than M1 on 2021-2025 and >= 100 trades.
Information only: $ figures at $50 per R on a $10k account.
"""
import numpy as np
import pandas as pd

from src.exp4.evaluate import deflated_sharpe, sharpe
from src.exp7 import controls, meta
from src.exp7.system import run_system

LONDON = "Europe/London"


def add_days(trades):
    t = trades.copy()
    entry = t.entry_utc.dt.tz_convert(LONDON)
    t["year"], t["hour"], t["day"] = entry.dt.year, entry.dt.hour, entry.dt.tz_localize(None).dt.normalize()
    t["month"] = entry.dt.tz_localize(None).dt.to_period("M")
    t["win"] = t.net_r > 0
    return t


def trading_days(data):
    d = data.m1_df.time_utc.dt.tz_convert(LONDON).dt.tz_localize(None).dt.normalize().unique()
    d = pd.DatetimeIndex(d)
    return d[d.dayofweek < 5]


def daily_r(trades, days):
    return trades.groupby("day").net_r.sum().reindex(days, fill_value=0.0).to_numpy()


def summary(t):
    return {"trades": len(t), "win_rate": float(t.win.mean()) if len(t) else np.nan,
            "expectancy": float(t.net_r.mean()) if len(t) else np.nan, "total_r": float(t.net_r.sum())}


def per_group(t, key):
    return {k: summary(g) for k, g in t.groupby(key)}


def control_expectancies(fn, seeds):
    return np.array([fn(s).net_r.mean() for s in range(seeds)])


def money(t, months, risk_usd, account=10_000.0):
    usd = t.net_r * risk_usd
    by_month = usd.groupby(t.month).sum().reindex(months, fill_value=0.0)
    by_day = usd.groupby(t.day).sum()
    equity = account + usd.groupby(t.exit_utc).sum().sort_index().cumsum()
    peak = np.maximum.accumulate(np.r_[account, equity.to_numpy()])
    dd = float((peak - np.r_[account, equity.to_numpy()]).max())
    return {"avg_usd_per_month": float(by_month.mean()), "pct_months_profitable": float((by_month > 0).mean()),
            "worst_day_usd": float(by_day.min()), "worst_month_usd": float(by_month.min()),
            "max_drawdown_usd": dd, "max_drawdown_pct": dd / account}


def evaluate(data, cfg, n_trials, seeds=None):
    seeds = seeds or cfg["seeds"]
    res, trades, setups = run_system(data, cfg)
    t = add_days(trades)
    days = trading_days(data)
    p = cfg["periods"]["development"]
    months = pd.period_range(p["start"], pd.Timestamp(p["end"]) - pd.Timedelta(days=1), freq="M")
    out = {"m1": summary(t), "setups": len(setups), "skipped_in_trade": res.skipped_in_trade,
           "per_year": per_group(t, "year"), "per_direction": per_group(t, "direction"), "per_hour": per_group(t, "hour"),
           "exit_reasons": t.exit_reason.value_counts(normalize=True).to_dict()}

    eligible = controls.trend_bars(data, cfg)
    c1 = control_expectancies(lambda s: controls.c1(data, trades, cfg, s), seeds)
    c2 = control_expectancies(lambda s: controls.c2(data, trades, cfg, s, eligible), seeds)
    exp = out["m1"]["expectancy"]
    out["c1"] = {"beats_pct": float((c1 < exp).mean()), "median": float(np.median(c1)), "p95": float(np.percentile(c1, 95))}
    out["c2"] = {"beats_pct": float((c2 < exp).mean()), "median": float(np.median(c2)), "p90": float(np.percentile(c2, 90))}

    stress = {}
    for name, sm, slip in (("spread_1.5x", 1.5, 0), ("slippage_1tick", 1.0, 1), ("spread_1.5x_and_1tick", 1.5, 1)):
        stress[name] = summary(add_days(run_system(data, cfg, spread_mult=sm, slippage_ticks=slip, setups=setups)[1]))
    out["stress"] = stress

    variants, sharpes = {}, [sharpe(daily_r(t, days))]
    for name, override in cfg["variants"].items():
        vt = add_days(run_system(data, {**cfg, **override})[1])
        variants[name] = summary(vt)
        sharpes.append(sharpe(daily_r(vt, days)))
    out["variants"] = variants
    out["dsr"] = deflated_sharpe(daily_r(t, days), sharpes, n_trials)

    early = t[t.year <= 2024]
    out["idea_source_2019_2024"] = summary(early)

    crit = {
        "trades >= 150": (len(t), len(t) >= 150),
        "expectancy >= +0.10R": (exp, exp >= 0.10),
        "positive years >= 5 of 7": (sum(v["total_r"] > 0 for v in out["per_year"].values()),
                                     sum(v["total_r"] > 0 for v in out["per_year"].values()) >= 5),
        "beats >= 95% of C1": (out["c1"]["beats_pct"], out["c1"]["beats_pct"] >= 0.95),
        "beats >= 90% of C2": (out["c2"]["beats_pct"], out["c2"]["beats_pct"] >= 0.90),
        "Deflated Sharpe >= 0.95": (out["dsr"]["dsr"], out["dsr"]["dsr"] >= 0.95),
        "expectancy > 0 at 1.5x spread": (stress["spread_1.5x"]["expectancy"], stress["spread_1.5x"]["expectancy"] > 0),
        "no variant expectancy <= 0": (min(v["expectancy"] for v in variants.values()),
                                       all(v["expectancy"] > 0 for v in variants.values())),
        "2019-2024 expectancy >= +0.05R": (out["idea_source_2019_2024"]["expectancy"],
                                           out["idea_source_2019_2024"]["expectancy"] >= 0.05),
    }
    out["criteria"] = {k: {"value": v, "pass": bool(ok)} for k, (v, ok) in crit.items()}
    out["m1_verdict"] = "PASS" if all(ok for _, ok in crit.values()) else "FAIL"

    prob = meta.walk_forward(t, t.win.astype(int), cfg)
    yrs = (t.year >= cfg["m2"]["first_year"]) & (t.year <= cfg["m2"]["last_year"])
    keep = meta.keep(prob, cfg) & yrs
    m1_late, m2, skipped = t[yrs], t[keep], t[yrs & ~keep]
    out["m2"] = {"m1_2021_2025": summary(m1_late), "m2_2021_2025": summary(m2),
                 "m1_per_year": per_group(m1_late, "year"), "m2_per_year": per_group(m2, "year"),
                 "skipped": summary(skipped), "no_prediction_in_window": int(prob[yrs].isna().sum())}
    out["m2"]["adopted"] = bool(out["m1_verdict"] == "PASS" and len(m2) >= 100
                                and out["m2"]["m2_2021_2025"]["expectancy"] > out["m2"]["m1_2021_2025"]["expectancy"])
    out["money_info"] = money(t, months, cfg["risk_usd"])
    return out, t


# --- E7-2-TS: exit variant M1-TS (spec v1.1 section 6), written before any M1-TS result ----------------

def evaluate_ts(data, cfg, n_trials, seeds=None):
    """Same scoring as `evaluate` for M1-TS: controls with the M1-TS exit, its 4 variants (DSR
    cross-variance from M1-TS + 4 variants), the 1.5x spread criterion, the 2019-2024-only check.
    Adds exit-type shares and average win / loss (R). No M2."""
    from src.exp7.trailing import run_ts_system
    seeds = seeds or cfg["seeds"]
    res, trades, setups, _ = run_ts_system(data, cfg)
    t = add_days(trades)
    days = trading_days(data)
    p = cfg["periods"]["development"]
    months = pd.period_range(p["start"], pd.Timestamp(p["end"]) - pd.Timedelta(days=1), freq="M")
    out = {"m1_ts": summary(t), "setups": len(setups), "skipped_in_trade": res.skipped_in_trade,
           "per_year": per_group(t, "year"), "per_direction": per_group(t, "direction"),
           "exit_types": t.exit_type.value_counts(normalize=True).to_dict(),
           "avg_win_r": float(t.net_r[t.win].mean()), "avg_loss_r": float(t.net_r[~t.win].mean())}

    eligible = controls.trend_bars(data, cfg)
    c1 = control_expectancies(lambda s: controls.c1_ts(data, trades, cfg, s), seeds)
    c2 = control_expectancies(lambda s: controls.c2_ts(data, trades, cfg, s, eligible), seeds)
    exp = out["m1_ts"]["expectancy"]
    out["c1"] = {"beats_pct": float((c1 < exp).mean()), "median": float(np.median(c1)), "p95": float(np.percentile(c1, 95))}
    out["c2"] = {"beats_pct": float((c2 < exp).mean()), "median": float(np.median(c2)), "p90": float(np.percentile(c2, 90))}

    stress = {}
    for name, sm, slip in (("spread_1.5x", 1.5, 0), ("slippage_1tick", 1.0, 1), ("spread_1.5x_and_1tick", 1.5, 1)):
        stress[name] = summary(add_days(run_ts_system(data, cfg, spread_mult=sm, slippage_ticks=slip, setups=setups)[1]))
    out["stress"] = stress

    variants, sharpes = {}, [sharpe(daily_r(t, days))]
    for name, override in cfg["ts_variants"].items():
        vt = add_days(run_ts_system(data, {**cfg, "ts": {**cfg["ts"], **override}}, setups=setups)[1])
        variants[name] = summary(vt)
        sharpes.append(sharpe(daily_r(vt, days)))
    out["variants"] = variants
    out["dsr"] = deflated_sharpe(daily_r(t, days), sharpes, n_trials)
    out["idea_source_2019_2024"] = summary(t[t.year <= 2024])

    pos_years = sum(v["total_r"] > 0 for v in out["per_year"].values())
    crit = {
        "trades >= 150": (len(t), len(t) >= 150),
        "expectancy >= +0.10R": (exp, exp >= 0.10),
        "positive years >= 5 of 7": (pos_years, pos_years >= 5),
        "beats >= 95% of C1": (out["c1"]["beats_pct"], out["c1"]["beats_pct"] >= 0.95),
        "beats >= 90% of C2": (out["c2"]["beats_pct"], out["c2"]["beats_pct"] >= 0.90),
        "Deflated Sharpe >= 0.95": (out["dsr"]["dsr"], out["dsr"]["dsr"] >= 0.95),
        "expectancy > 0 at 1.5x spread": (stress["spread_1.5x"]["expectancy"], stress["spread_1.5x"]["expectancy"] > 0),
        "no variant expectancy <= 0": (min(v["expectancy"] for v in variants.values()),
                                       all(v["expectancy"] > 0 for v in variants.values())),
        "2019-2024 expectancy >= +0.05R": (out["idea_source_2019_2024"]["expectancy"],
                                           out["idea_source_2019_2024"]["expectancy"] >= 0.05),
    }
    out["criteria"] = {k: {"value": v, "pass": bool(ok)} for k, (v, ok) in crit.items()}
    out["verdict"] = "PASS" if all(ok for _, ok in crit.values()) else "FAIL"
    out["money_info"] = money(t, months, cfg["risk_usd"])
    return out, t
