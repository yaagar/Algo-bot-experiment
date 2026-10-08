"""Load one Experiment 3 market and build its engine, reusing Experiment 2's code.

Each market is run on its own (spec §2: markets are independent, one position each):
  * strategy bars = broker D1 bars (broker day = New York 17:00 to 17:00, checked in E3-1);
  * the engine's intraday price path (stop checks, rollover prices) = H1 bars, which go in the
    slot Experiment 2 used for M1 bars;
  * swing account: no Friday close, no Friday cutoff, no news blackout (spec §2).
All bars are read through src/data_access.py (2022+ only), window 2022-01-01 to 2026-09-30.
"""
import json
from datetime import datetime, timezone

import pandas as pd

from src.backtest import Events
from src.data_access import read_prices
from src.exp2.engine import Costs, Engine, Swap
from src.exp2.market import Market, bar_frame, m1_arrays
from src.exp2.strategies import S3Donchian
from src.exp3.markets import BY_NAME, PROCESSED, SPECS_PATH

WINDOW_START = pd.Timestamp("2022-01-01", tz="UTC")
WINDOW_END = pd.Timestamp("2026-10-01", tz="UTC")       # exclusive: window ends 2026-09-30 (spec §4)
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
NO_EVENTS = Events([])                                  # no news blackout on a daily swing system
BAR_COLS = ["time_utc", "open", "high", "low", "close", "spread_used", "spread_estimated"]


def load_specs():
    return json.loads(SPECS_PATH.read_text(encoding="utf-8"))["markets"]


def load_frames(spec, start=WINDOW_START, end=WINDOW_END):
    """(D1, H1) bar frames for whole broker days inside [start, end).

    A broker day opens at 17:00 New York the evening before, so the day labelled 1 October opens
    on 30 September (UTC). Only days that have CLOSED by `end` are kept, and H1 bars stop there too."""
    folder = PROCESSED / spec.get("data_dir", "")     # FX: "spliced" (MetaQuotes before 2025-05-21, Change Log v1.1)
    d1, h1 = (read_prices(spec["symbol"], tf, start, end, columns=BAR_COLS,
                          path=folder / f"{spec['symbol']}_{tf}.parquet").reset_index(drop=True)
              for tf in ("D1", "H1"))
    d1 = d1[d1.time_utc + pd.Timedelta(days=1) <= end].reset_index(drop=True)
    last_close = d1.time_utc.iloc[-1] + pd.Timedelta(days=1)
    return d1, h1[h1.time_utc < last_close].reset_index(drop=True)


def build_market(d1, h1, point):
    return Market(m1_arrays(h1, point), {"D1": bar_frame(d1, 24 * 60, point)}, None)


def quote_per_usd(spec):
    """P&L-currency units per US dollar at a given price of this market."""
    if spec["currency_profit"] == "USD":
        return lambda price: 1.0
    if spec["currency_base"] == "USD":            # e.g. USDJPY: 1 USD = price JPY
        return lambda price: price
    raise ValueError(f"no USD conversion for {spec['symbol']}")


def make_engine(spec, market, risk=50.0, spread_mult=1.0, commission_mult=1.0, swap_charge_mult=1.0):
    """Results are in R; risk only scales the fractional lot size. Multipliers = spec §5.3 stresses.
    The swap stress multiplies swap CHARGES (negative rates) only; swap credits are left unchanged."""
    costs = Costs(spread_mult, spec["commission_pct_per_side"] * commission_mult,
                  spec["commission_per_lot_usd_per_side"] * commission_mult)
    charge = lambda rate: rate * swap_charge_mult if rate < 0 else rate
    swap = Swap(charge(spec["swap_long_pct_per_year"]), charge(spec["swap_short_pct_per_year"]), 360,
                WEEKDAYS.index(BY_NAME[spec["market"]].triple_swap_day))
    return Engine(market.m1, NO_EVENTS, costs, swap, risk_usd=risk, contract=spec["contract_size"],
                  weekend_rule=False, quote_per_usd=quote_per_usd(spec))


def strategy(market):
    """Spec §2: Donchian 55/20 (Turtle System 2) on daily bars — Experiment 2's S3 code."""
    return S3Donchian(market, channel=55, exit_channel=20, tf="D1")
