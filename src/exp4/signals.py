"""Experiment 4 signals A-D, regime gate, shock gate and the combined forecast (spec §3-§5).

Plain English: at every closed H1 bar we compute four raw signal values, turn each into a score
in [-1, +1] by dividing by twice its recent spread (std over the previous 60 trading days), switch
some scores off depending on whether the market has been trending or ranging, and average the
scores still allowed into one forecast F (Change Log v1.2: trending (A+B+C)/3, ranging D). Everything at bar i uses only bars that have CLOSED by bar i's close.

  A  quiet-range breakout: how far the close is outside today's early range, in range heights
  B  intraday momentum: return from yesterday's flat time to the end of today's first window hour
  C  short-term trend: (close - SMA20 of finished H4 closes) / ATR20(H4)
  D  mean reversion: -(close - SMA20 of H1 closes) / ATR14(H1)

σ samples (Change Log v1.1 item 2): every H1 close where the signal is active in the previous
60 trading days (B: one value per day). Fewer than 60 earlier trading days -> score 0.
"""
import warnings

import numpy as np
import pandas as pd

from src.exp2.market import atr, sma

SIGNALS = ("A", "B", "C", "D")


def price_at(m1, t_ns):
    """Last traded price before time t: the close of the last M1 bar that opened before t."""
    j = int(np.searchsorted(m1.t, t_ns, "left")) - 1
    return m1.c[j] if j >= 0 else np.nan


def daily_sigma(samples_by_day, n_days):
    """σ for day k = std (ddof 1) of all samples from days k-n .. k-1; NaN until n earlier days exist."""
    sigma = np.full(len(samples_by_day), np.nan)
    for k in range(n_days, len(samples_by_day)):
        x = np.concatenate(samples_by_day[k - n_days:k])
        if len(x) > 1:
            sigma[k] = x.std(ddof=1)
    return sigma


def per_day(values, active, day_idx, n_days):
    out = [np.empty(0)] * n_days
    keep = active & (day_idx >= 0)
    for k, grp in pd.Series(values[keep]).groupby(day_idx[keep]):
        out[k] = grp.to_numpy()
    return out


def to_score(raw, active, sigma_bar, mult):
    with np.errstate(divide="ignore", invalid="ignore"):
        s = np.clip(raw / (mult * sigma_bar), -1.0, 1.0)
    return np.where(active & (sigma_bar > 0) & np.isfinite(s), s, 0.0)


def range_levels(mk):
    """Today's quiet-range high/low from M1 bars inside [range start, range end)."""
    rc, m1 = mk.cfg["range"], mk.m1
    hi, lo = np.full(len(mk.days), np.nan), np.full(len(mk.days), np.nan)
    for k, d in enumerate(mk.days):
        a = int(np.searchsorted(m1.t, mk.clock.at(d, rc["start"]), "left"))
        b = int(np.searchsorted(m1.t, mk.clock.at(d, rc["end"]), "left"))
        if b > a:
            hi[k], lo[k] = m1.h[a:b].max(), m1.l[a:b].min()
    return hi, lo


def momentum_by_day(mk):
    """Signal B's raw value per day: price at today's b_to / price at the previous trading day's b_from - 1."""
    out = np.full(len(mk.days), np.nan)
    for k in range(1, len(mk.days)):
        p0 = price_at(mk.m1, mk.clock.at(mk.days[k - 1], mk.cfg["b_from"]))
        p1 = price_at(mk.m1, mk.clock.at(mk.days[k], mk.cfg["b_to"]))
        out[k] = p1 / p0 - 1
    return out


def efficiency_by_day(daily_close, n):
    """Kaufman efficiency for day k from completed days only: |C[k-1]-C[k-1-n]| / sum |daily changes|."""
    eff = np.full(len(daily_close), np.nan)
    for k in range(n + 1, len(daily_close)):
        win = daily_close[k - 1 - n:k]
        path = np.abs(np.diff(win)).sum()
        if path > 0:
            eff[k] = abs(win[-1] - win[0]) / path
    return eff


def shock_ratio(h1, n_days, n_total_days):
    """Today's average H1 range so far / median of the same quantity, at the same time of day,
    over the previous n trading days (Change Log v1.1 item 3). NaN until n earlier days exist."""
    day_idx, m = h1.day_idx.to_numpy(), h1.m.to_numpy()
    rng = (h1.high - h1.low).to_numpy()
    in_day = day_idx >= 0
    so_far = np.full(len(h1), np.nan)
    so_far[in_day] = pd.Series(rng[in_day]).groupby(day_idx[in_day]).transform(
        lambda x: x.expanding().mean()).to_numpy()
    slots = np.unique(m[in_day])
    table = np.full((n_total_days, len(slots)), np.nan)        # day x time-of-day -> average range so far
    for k, grp in pd.DataFrame({"m": m[in_day], "v": so_far[in_day]}).groupby(day_idx[in_day]):
        j = np.searchsorted(grp.m.to_numpy(), slots, "right") - 1
        table[k] = np.where(j >= 0, grp.v.to_numpy()[np.maximum(j, 0)], np.nan)
    base = np.full_like(table, np.nan)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)        # all-NaN slot -> NaN baseline (gate closed)
        for k in range(n_days, n_total_days):
            base[k] = np.nanmedian(table[k - n_days:k], axis=0)
    ratio = np.full(len(h1), np.nan)
    slot_of = np.searchsorted(slots, m[in_day])
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio[in_day] = so_far[in_day] / base[day_idx[in_day], slot_of]
    return ratio


def forecast(out, use, gated):
    """Change Log v1.2: F = average of the signals in use that the regime gate allows —
    trending (A+B+C)/3, ranging D; ablation = that one signal / 1; no gates = all four / 4.
    An allowed signal not yet active today still counts, as 0. Zeroes the disallowed scores in `out`."""
    total, count = np.zeros(len(out)), np.zeros(len(out))
    for s in SIGNALS:
        keep = np.full(len(out), s in use)
        if gated:
            keep &= (out.ranging if s == "D" else out.trending).to_numpy()
        out[f"score_{s}"] = np.where(keep, out[f"score_{s}"], 0.0)
        total += out[f"score_{s}"].to_numpy()
        count += keep
    return np.where(count > 0, total / np.maximum(count, 1), 0.0)


def compute(mk, cfg):
    """One row per H1 bar: raw values, scores, gates and the forecast F. Honours the variant keys
    use_signals (ablation) and use_gates (False = no regime gate and no shock gate)."""
    sc, gc, mc = cfg["signals"], cfg["gates"], mk.cfg
    h1, clk, nd = mk.h1, mk.clock, len(mk.days)
    c, hi, lo = h1.close.to_numpy(), h1.high.to_numpy(), h1.low.to_numpy()
    day_idx, m = h1.day_idx.to_numpy(), h1.m.to_numpy()
    in_day = day_idx >= 0
    di = np.where(in_day, day_idx, 0)
    m_flat = clk.minute(mc["flat_by"])
    raw, active = {}, {}

    # A: quiet-range breakout, active from range end to flat-by
    rh, rl = range_levels(mk)
    H, L = np.where(in_day, rh[di], np.nan), np.where(in_day, rl[di], np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        height = H - L
        raw["A"] = np.where(c > H, (c - H) / height, np.where(c < L, (c - L) / height, 0.0))
    active["A"] = in_day & (m >= clk.minute(mc["range"]["end"])) & (m <= m_flat) & (height > 0)

    # B: intraday momentum, fixed for the day once set at b_to
    b_day = momentum_by_day(mk)
    raw["B"] = np.where(in_day, b_day[di], np.nan)
    active["B"] = in_day & (m >= clk.minute(mc["b_to"])) & (m <= m_flat) & np.isfinite(raw["B"])

    # C: trend vs finished H4 bars
    h4 = mk.h4
    h4_sma = sma(h4.close.to_numpy(), sc["c_sma"])
    h4_atr = atr(h4.high.to_numpy(), h4.low.to_numpy(), h4.close.to_numpy(), sc["c_atr"])
    j = np.searchsorted(h4.t_close.to_numpy(), h1.t_close.to_numpy(), "right") - 1
    ok = j >= 0
    jj = np.maximum(j, 0)
    with np.errstate(divide="ignore", invalid="ignore"):
        raw["C"] = np.where(ok, (c - h4_sma[jj]) / h4_atr[jj], np.nan)
    active["C"] = in_day & np.isfinite(raw["C"])

    # D: mean reversion on H1
    atr14 = atr(hi, lo, c, sc["d_atr"])
    with np.errstate(divide="ignore", invalid="ignore"):
        raw["D"] = -(c - sma(c, sc["d_sma"])) / atr14
    active["D"] = in_day & np.isfinite(raw["D"])

    out = pd.DataFrame({"t_close": h1.t_close.to_numpy(), "day_idx": day_idx, "m": m, "atr14": atr14})
    for s in SIGNALS:
        if s == "B":
            samples = [np.array([v]) if np.isfinite(v) else np.empty(0) for v in b_day]
        else:
            samples = per_day(raw[s], active[s], day_idx, nd)
        sigma = daily_sigma(samples, sc["sigma_days"])
        out[f"raw_{s}"] = np.where(active[s], raw[s], np.nan)
        out[f"score_{s}"] = to_score(raw[s], active[s], np.where(in_day, sigma[di], np.nan), sc["sigma_mult"])

    # regime gate (completed trading days only) and shock gate
    daily_close = h1[in_day].groupby("day_idx").close.last().reindex(range(nd)).to_numpy()
    eff = efficiency_by_day(daily_close, gc["efficiency_days"])
    out["efficiency"] = np.where(in_day, eff[di], np.nan)
    out["trending"] = out.efficiency >= gc["efficiency_trend"]
    out["ranging"] = out.efficiency < gc["efficiency_trend"]          # NaN -> neither: all signals off
    out["shock_ratio"] = shock_ratio(h1, gc["shock_days"], nd)
    out["shock_ok"] = out.shock_ratio <= gc["shock_mult"]             # NaN -> no entries

    gated = cfg.get("use_gates", True)
    out["F"] = forecast(out, set(cfg.get("use_signals", SIGNALS)), gated)
    if not gated:
        out["shock_ok"] = True
    out["in_window"] = in_day & (m >= clk.minute(mc["window"]["start"])) & (m < clk.minute(mc["window"]["end"]))
    return out
