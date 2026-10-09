"""Experiment 6 costs: the locked swap table and the §3 cost screen. No returns are computed here.

Swap lock (Change Log v1.1 f): both snapshots (Exp 3, 2026-10-08 18:23 UTC; E6-0, 2026-10-09 02:10 UTC)
use swap_mode 5 = annual % of the current price, so a changed value is a changed RATE, not a unit
difference. Where the two snapshots differ, the more costly value per side is locked; elsewhere the
E6-0 value. $ per 1 lot per night = rate/100/360 x price x (USD per 1.0 price move per lot), at the
latest close.

Cost screen (spec §3), per unit of the instrument, all in price units:
  cost_ratio  = (p75 spread at 10:00 New York in 2026 recorded data + 2 x commission) / median ATR(20) 2022-2025
  carry_ratio = worst-side swap per night x 365 / (std of daily price changes 2022-2025 x sqrt(252))
Exclude if cost_ratio > 0.10 or carry_ratio > 0.30, or if under 3 years of daily history in 2022-2025.
Price level for % swaps and % commission: the mean close over 2022-2025 (the period of the volatility).
"""
import json

import numpy as np
import pandas as pd
import yaml

from src.config import PROJECT_ROOT
from src.data_access import read_prices
from src.exp2.market import atr
from src.timeutils import utc_to_server

CONFIG_PATH = PROJECT_ROOT / "config" / "exp6.yaml"
PROCESSED = PROJECT_ROOT / "data" / "processed" / "exp6"
RESULTS = PROJECT_ROOT / "results" / "exp6"
COLS = ["time_utc", "open", "high", "low", "close"]


def load_config():
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def daily_bars(symbol, cls, start, end):
    """Broker-day (New York 17:00) bars. FX: rebuilt from MetaQuotes H1 (its own D1 follows European DST)."""
    if cls != "FX":
        return read_prices(symbol, "D1", start, end, columns=COLS, path=PROCESSED / f"{symbol}_D1.parquet")
    pair = symbol.replace(".sim", "")
    h1 = read_prices(pair, "H1", start, end, columns=COLS, path=PROCESSED / "metaquotes" / f"{pair}_H1.parquet")
    day = utc_to_server(h1.time_utc).dt.date
    g = h1.groupby(day.values, sort=True)
    d = pd.DataFrame({"time_utc": g.time_utc.first(), "open": g.open.first(), "high": g.high.max(),
                      "low": g.low.min(), "close": g.close.last()}).reset_index(names="server_date")
    return d[pd.to_datetime(d.server_date).dt.dayofweek < 5].reset_index(drop=True)


def locked_swaps(symbols, exp3_specs, latest_close):
    rows = []
    e3 = {m["symbol"]: m for m in exp3_specs}
    for s in symbols.rename(columns={"class": "asset_class"}).itertuples():
        long_, short_, source = s.swap_long, s.swap_short, "E6-0 snapshot"
        if s.symbol in e3:
            l3, s3 = e3[s.symbol]["swap_long_pct_per_year"], e3[s.symbol]["swap_short_pct_per_year"]
            if (l3, s3) != (long_, short_):
                long_, short_ = min(long_, l3), min(short_, s3)            # more costly = more negative
                source = "costlier of Exp 3 / E6-0 per side"
        px, tvps = latest_close.get(s.symbol, np.nan), s.tick_value_now / s.tick_size
        per_night = lambda pct: pct / 100 / 360 * px * tvps
        rows.append({"symbol": s.symbol, "class": s.asset_class, "swap_mode": s.swap_mode,
                     "swap_long_pct": long_, "swap_short_pct": short_, "source": source,
                     "price_used": px, "usd_per_lot_night_long": per_night(long_),
                     "usd_per_lot_night_short": per_night(short_)})
    return pd.DataFrame(rows)


def commission_per_unit(cls, cfg, price, tvps, contract):
    """One side's commission per 1 unit of the instrument, in price units."""
    c = cfg["commission"][cls]
    if "usd_per_lot" in c:
        return c["usd_per_lot"] / tvps                      # $ per lot -> price units per lot-equivalent
    return c["pct"] / 100 * price


def screen(cfg, symbols, swaps, start, end):
    sc = cfg["screen"]
    rows = []
    for s in symbols.rename(columns={"class": "asset_class"}).itertuples():
        d = daily_bars(s.symbol, s.asset_class, start, end)
        years = (d.time_utc.max() - d.time_utc.min()).days / 365.25 if len(d) else 0.0
        h, l, c = d.high.to_numpy(), d.low.to_numpy(), d.close.to_numpy()
        med_atr = float(np.nanmedian(atr(h, l, c, sc["atr_days"]))) if len(d) > sc["atr_days"] else np.nan
        vol_ann = float(np.diff(c).std(ddof=1) * np.sqrt(252)) if len(d) > 2 else np.nan
        px = float(c.mean()) if len(d) else np.nan
        tvps = s.tick_value_now / s.tick_size
        comm = commission_per_unit(s.asset_class, cfg, px, tvps, s.contract_size)
        sw = swaps.set_index("symbol").loc[s.symbol]
        worst = max(-sw.swap_long_pct, -sw.swap_short_pct, 0.0)
        carry = worst / 100 / cfg["swap_days_per_year"] * px * 365
        cost_ratio = (s.spread_p75_price_10ny_2026 + 2 * comm) / med_atr
        carry_ratio = carry / vol_ann
        ok_hist = years >= sc["min_history_years"]
        included = ok_hist and cost_ratio <= sc["max_cost_ratio"] and carry_ratio <= sc["max_carry_ratio"]
        rows.append({"symbol": s.symbol, "class": s.asset_class, "history_years": round(years, 2),
                     "spread_p75_10ny_2026": s.spread_p75_price_10ny_2026, "commission_per_unit_side": comm,
                     "median_atr20": med_atr, "cost_ratio": cost_ratio, "worst_swap_pct": worst,
                     "annual_vol_price": vol_ann, "carry_ratio": carry_ratio, "included": included,
                     "reason": "" if included else ", ".join(
                         r for r, bad in (("history < 3y", not ok_hist), ("no 2026 spread at 10:00 NY", np.isnan(cost_ratio)),
                                          ("cost_ratio", cost_ratio > sc["max_cost_ratio"]),
                                          ("carry_ratio", carry_ratio > sc["max_carry_ratio"])) if bad)})
    return pd.DataFrame(rows)
