"""Monthly market regime (spec §5): trending vs ranging, up vs down.

From broker-day closes (2022+ only):
  efficiency = |month's net change| / sum of |daily changes| within the month.
Above the median month of the period = "trending", otherwise "ranging"; the sign of the
net change gives "up" / "down". The first broker day of the data has no previous close, so
its change is not counted (no reaching into 2021).
This is a description of the market used to break down results; it never feeds a trade decision.
"""
import pandas as pd


def classify_months(days):
    closes = days.close.copy()
    closes.index = pd.to_datetime(closes.index)
    change = closes.diff().dropna()
    month = change.index.to_period("M")
    g = change.groupby(month)
    out = pd.DataFrame({"net_change": g.sum(), "path": g.apply(lambda x: x.abs().sum())})
    out["efficiency"] = out.net_change.abs() / out.path
    median = out.efficiency.median()
    out["trend"] = (out.efficiency > median).map({True: "trending", False: "ranging"})
    out["direction"] = (out.net_change > 0).map({True: "up", False: "down"})
    out["regime"] = out.trend + " " + out.direction
    out.attrs["median_efficiency"] = float(median)
    return out
