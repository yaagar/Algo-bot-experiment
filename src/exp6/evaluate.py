"""Experiment 6 scoring (spec §7-§8, Change Log v1.5).

Daily return = change in equity at the broker-day close / capital, every broker day from the first
tradeable day (v1.5 a). Sharpe = annualised mean / std of daily returns (x √252). Max drawdown in %
of capital. Costs (v1.5 c): spread paid (the spread on every buy, plus slippage on every fill in the
stress) + commission + net swap paid; gross profit = net profit + costs.
"""
import numpy as np
import pandas as pd

from src.exp4.evaluate import deflated_sharpe


def daily_returns(daily, capital, first_day):
    d = pd.DataFrame(daily)
    ret = d.equity.diff().fillna(d.equity.iloc[0] - capital) / capital
    keep = pd.to_datetime(d.day) >= pd.Timestamp(first_day)
    return pd.Series(ret[keep].to_numpy(), index=pd.to_datetime(d.day[keep]))


def sharpe_ann(r):
    sd = r.std(ddof=1)
    return float(r.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0


def max_drawdown_pct(r):
    eq = r.cumsum()
    return float((np.maximum.accumulate(np.r_[0.0, eq.to_numpy()])[1:] - eq.to_numpy()).max() * 100)


def summary(r):
    return {"net_sharpe": sharpe_ann(r), "net_return_pct": float(r.sum() * 100), "max_dd_pct": max_drawdown_pct(r)}


def cost_breakdown(daily, fills, symbols, capital):
    """$ per market: net, spread (+ slippage), commission, swap (negative = paid)."""
    last = pd.DataFrame(daily).iloc[-1]
    f = pd.DataFrame(fills)
    buy = (f.lots_after - f.lots_before) > 0
    f["spread_cost"] = np.where(buy, (f.lots_after - f.lots_before) * f.spread, 0.0) * f.usd_ppu \
        + (f.lots_after - f.lots_before).abs() * f.slippage * f.usd_ppu
    spread = f.groupby("symbol").spread_cost.sum()
    rows = [{"symbol": s, "net": last[f"net_{s}"], "spread": float(spread.get(s, 0.0)),
             "commission": last[f"comm_{s}"], "swap": last[f"swap_{s}"]} for s in symbols]
    out = pd.DataFrame(rows)
    out["gross"] = out.net + out.spread + out.commission - out.swap
    return out


def dsr(main_r, config_rs, n_trials):
    daily_sharpes = [float(r.mean() / r.std(ddof=1)) for r in config_rs]
    return deflated_sharpe(main_r.to_numpy(), daily_sharpes, n_trials)
