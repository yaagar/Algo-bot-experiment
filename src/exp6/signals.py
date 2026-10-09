"""Experiment 6 signal (spec §4) and sizing (spec §5, Change Log v1.1 b, v1.3).

Signal, per market at each broker-day close: s_L = sign(close_today - close_L_days_ago) for
L in {21, 63, 252} trading days of that market; forecast f = mean of the signs. A market trades only
once 252 earlier closes and 60 daily changes exist inside the period (variants with one lookback use
the same warm-up, so every variant trades the same days). Long-only benchmark: f = +1 when tradeable.

Sizing at each close (all past-only):
  unit lots  = daily $ budget / (σ60 of daily price changes x USD per price unit per lot)
  budget     = target_vol x capital / √252 x 1/(active classes) x 1/(tradeable markets in the class)
  desired    = f x unit
  scaler     = target daily $ vol / √(x' Σ x), Σ = 60-day covariance of daily $ changes per lot;
               capped at 2.0 and so that margin (Σ |lots x notional| / 30) <= equity
  buffer     = trade only if |target - current| > buffer x full unit (unit x scaler, |f| = 1)
"""
import numpy as np
import pandas as pd

WARMUP = 252


def market_signals(m, lookbacks, vol_days=60, long_only=False):
    """DataFrame over the market's own broker days: signs, f, σ60 of daily price changes, tradeable."""
    c = m.day_close
    n = len(c)
    out = pd.DataFrame({"day": m.days, "close": c})
    tradeable = np.arange(n) >= max(WARMUP, vol_days)
    for L in (21, 63, 252):
        s = np.full(n, np.nan)
        if n > L:
            s[L:] = np.sign(c[L:] - c[:-L])
        out[f"s_{L}"] = s
    f = out[[f"s_{L}" for L in lookbacks]].mean(axis=1).to_numpy()
    if long_only:
        f = np.ones(n)
    out["f"] = np.where(tradeable, f, 0.0)
    dc = np.r_[np.nan, np.diff(c)]
    out["sigma"] = pd.Series(dc).rolling(vol_days, min_periods=vol_days).std(ddof=1).to_numpy()
    out["tradeable"] = tradeable & np.isfinite(out.sigma.to_numpy()) & (out.sigma.to_numpy() > 0)
    return out


def class_budgets(groups, tradeable):
    """Share of the daily risk budget per market: 1/(active groups) x 1/(tradeable markets in its group)."""
    groups = np.asarray(groups)
    share = np.zeros(len(groups))
    active = sorted({g for g, t in zip(groups, tradeable) if t})
    for g in active:
        members = (groups == g) & tradeable
        share[members] = 1.0 / len(active) / members.sum()
    return share


def size_targets(f, sigma, usd_ppu, notional, groups, tradeable, cov, equity, sc):
    """Target lots per market (fractional), full units after scaling, and the scaler used."""
    daily_budget = sc["target_vol"] * sc["capital"] / np.sqrt(252)
    share = class_budgets(groups, tradeable)
    with np.errstate(divide="ignore", invalid="ignore"):
        unit = np.where(tradeable, daily_budget * share / (sigma * usd_ppu), 0.0)
    desired = f * unit
    port_sd = float(np.sqrt(max(desired @ cov @ desired, 0.0)))
    scaler = min(daily_budget / port_sd, sc["max_scaler"]) if port_sd > 0 else 0.0
    margin_per_scaler = float(np.sum(np.abs(desired) * notional)) / sc["leverage"]
    if margin_per_scaler > 0:
        scaler = min(scaler, equity / margin_per_scaler)
    return desired * scaler, unit * scaler, scaler


def apply_buffer(current, target, full_unit, buffer):
    """New position per market: the target if the change is bigger than buffer x full unit, else unchanged.
    A market with no full unit (not tradeable) is closed if it still holds anything."""
    out = current.copy()
    for i in range(len(current)):
        if full_unit[i] <= 0:
            out[i] = 0.0 if current[i] != 0 else current[i]
        elif abs(target[i] - current[i]) > buffer * full_unit[i]:
            out[i] = target[i]
    return out
