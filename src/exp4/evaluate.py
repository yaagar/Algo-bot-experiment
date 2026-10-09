"""Experiment 4 scoring (spec §7-§8, Change Log v1.3).

  * R = $50 full-size risk; a trade's R = its net $ / 50 (forecast sizing included). Expectancy = mean.
  * Trades belong to their trading day (all trades are intraday) and that day's regime (v1.3 e).
  * C1: Experiment 2's run_c1 (same entry, stop distance, exit time; coin-flip direction), each trade
    scaled by the real trade's forecast size. Metric = portfolio total R, 1,000 seeds (v1.3 b).
  * Deflated Sharpe (Bailey & López de Prado), on daily portfolio R over every trading day, no-trade
    days = 0 (v1.3 d): V = max(variance of daily Sharpe across the 10 Exp 4 configurations, sampling
    variance of the main Sharpe incl. skew/kurtosis); N from the trial ledger.
"""
import math
from statistics import NormalDist

import numpy as np
import pandas as pd

from src.exp2.c1 import run_c1
from src.exp2.engine import trades_frame

R_USD = 50.0
EULER_GAMMA = 0.5772156649015329
PHI = NormalDist()


def add_r(trades, days):
    """R per trade, its trading day (Timestamp) and regime label."""
    t = trades.copy()
    t["r"] = t.net_usd / R_USD
    t["day"] = [days[i] for i in t.info_day_idx]
    t["regime"] = np.where(t.info_efficiency >= 0.30, "trending", "ranging")
    return t


def stats(t):
    return {"trades": len(t), "expectancy": float(t.r.mean()) if len(t) else 0.0, "total_r": float(t.r.sum())}


def c1_total_r(engine, trades, seeds):
    """Portfolio-ready C1 total R per seed for one market (sizes from the real trades)."""
    size = dict(zip(trades.signal_ns, trades.info_size))
    out = np.empty(len(seeds))
    for k, seed in enumerate(seeds):
        c = trades_frame(run_c1(engine, trades, seed))
        out[k] = (c.net_r * c.signal_ns.map(size)).sum() if len(c) else 0.0   # net_r of a full-size trade x size
    return out


def daily_returns(trades, all_days):
    return trades.groupby("day").r.sum().reindex(all_days, fill_value=0.0).to_numpy()


def sharpe(x):
    sd = x.std(ddof=1)
    return float(x.mean() / sd) if sd > 0 else 0.0


def moments(x):
    z = (x - x.mean()) / x.std(ddof=0)
    return float((z ** 3).mean()), float((z ** 4).mean())          # skewness, kurtosis (normal = 3)


def deflated_sharpe(main_daily, config_sharpes, n_trials):
    sr, T = sharpe(main_daily), len(main_daily)
    g3, g4 = moments(main_daily)
    denom = 1 - g3 * sr + (g4 - 1) / 4 * sr ** 2
    v_cross = float(np.var(config_sharpes, ddof=1))
    v_sample = denom / (T - 1)
    V = max(v_cross, v_sample)
    sr0 = math.sqrt(V) * ((1 - EULER_GAMMA) * PHI.inv_cdf(1 - 1 / n_trials)
                          + EULER_GAMMA * PHI.inv_cdf(1 - 1 / (n_trials * math.e)))
    dsr = PHI.cdf((sr - sr0) * math.sqrt(T - 1) / math.sqrt(denom))
    return {"sharpe_daily": sr, "days": T, "skew": g3, "kurtosis": g4, "V_cross": v_cross, "V_sampling": v_sample,
            "V": V, "V_term": "cross-config" if v_cross >= v_sample else "sampling", "SR0": sr0, "N": n_trials, "dsr": dsr}
