"""Experiment 7 trading system (spec v1.0 §2-§3): the E7-0 setups traded on the Exp 2/4 engine.

Plain-English flow:
  1. pattern.scan() finds every qualifying breakout (decided at an M15 close, past data only).
  2. The engine walks the M15 bars. At a qualifying bar's close, if we are flat, we send an order;
     it fills at the next M15 open (longs pay the spread). If a trade is open, the setup is skipped
     and counted (one position at a time).
  3. The stop is placed from the actual fill (box midpoint, >= 1 ATR(M15), round-$10 rule), the
     target is 2R from the fill, and M1 bars decide the exit: stop / target (stop wins a tie) or
     20:00 London. Risk is $50 = 1R with fractional lots; commission both sides; no swap (flat daily).
Spread everywhere = 2026 tick-p75 fraction of price for that broker hour x the bar's open.
The engine (fills, M1 walk, costs) is Exp 2's via Exp 4's E4Engine (slippage stress, flat-by guard).
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.backtest import Events
from src.exp2.engine import Costs, Order, london_ns, trades_frame
from src.exp2.market import M1, to_ns
from src.exp4.system import NO_SWAP, E4Engine
from src.exp7.pattern import M15, h1_context, m15_from_m1, place_stop, scan
from src.timeutils import LONDON, utc_to_server


@dataclass
class Exp7Data:
    m1_df: pd.DataFrame        # broker M1 bars (UTC, bid)
    h1: pd.DataFrame           # broker H1 bars
    events: Events
    spread_frac: np.ndarray    # 24 fractions of price, by broker-server hour

    def __post_init__(self):
        self.m15 = m15_from_m1(self.m1_df)
        self.m1 = M1(to_ns(self.m1_df.time_utc), *(self.m1_df[k].to_numpy(float) for k in ("open", "high", "low", "close")),
                     self.spread(self.m1_df))

    def spread(self, bars):
        """Modelled spread ($) for each bar: fraction for its broker hour x its open."""
        return self.spread_frac[utc_to_server(bars.time_utc).dt.hour.to_numpy()] * bars.open.to_numpy(float)


def time_exit_ns(fill_ns, hhmm):
    """hh:mm London on the London date of the fill."""
    day = pd.Timestamp(int(fill_ns), tz="UTC").tz_convert(LONDON).date()
    return london_ns(day, int(hhmm[:2]) * 60 + int(hhmm[3:]))


class Exp7Strategy:
    """Feeds the engine one order per qualifying setup; never exits early (stop / 2R / 20:00 only)."""

    def __init__(self, data, setups, cfg):
        b = data.m15
        t_open = to_ns(b.time_utc)
        self.bars = pd.DataFrame({"t_open": t_open, "t_close": t_open + M15.value,
                                  "open": b.open.to_numpy(float), "spread": data.spread(b)})
        self.cfg = cfg
        self.setups = {int(r.bar): r for r in setups.itertuples()}

    def signal(self, i):
        r = self.setups.get(i)
        if r is None:
            return None
        d, mid, atr, cfg = int(r.direction), r.box_mid, r.atr_m15, self.cfg
        fill_ns = int(self.bars.t_open.iat[i + 1])
        return Order(direction=d, signal_ns=int(self.bars.t_close.iat[i]),
                     stop_rule=lambda price, spread: place_stop(price, mid, atr, d, cfg),
                     target_r=cfg["target_r"], time_exit_ns=time_exit_ns(fill_ns, cfg["time_exit_london"]),
                     info={"size": 1.0, "bar": i, "tstat": r.tstat, "atr_h1": r.atr_h1, "box_high": r.box_high,
                           "box_low": r.box_low, "box_mid": mid, "box_bars": r.box_bars,
                           "time_exit_ns": time_exit_ns(fill_ns, cfg["time_exit_london"])})

    def exit_signal(self, i, pos):
        return False


def make_engine(data, cfg, spread_mult=1.0, slippage_ticks=0):
    costs = Costs(spread_mult, cfg["commission_pct_per_side"])
    return E4Engine(data.m1, data.events, costs, NO_SWAP, risk_usd=cfg["risk_usd"], contract=cfg["contract_size"],
                    blackout_min=cfg["news_blackout_min"], weekend_rule=False, slippage=slippage_ticks * cfg["tick_size"])


def find_setups(data, cfg):
    cands = scan(data.m15, h1_context(data.h1, cfg), data.events, data.spread_frac, cfg)
    return cands, cands[cands.qualifies].reset_index(drop=True)


def run_system(data, cfg, spread_mult=1.0, slippage_ticks=0, setups=None):
    """Trade the setups. Returns (engine Result, trades DataFrame, setups).
    The trades frame holds outcome columns: callers must not print or inspect them during build (§4)."""
    if setups is None:
        setups = find_setups(data, cfg)[1]
    engine = make_engine(data, cfg, spread_mult, slippage_ticks)
    res = engine.run(Exp7Strategy(data, setups, cfg))
    res.engine = engine
    return res, trades_frame(res), setups


# --- what may be shown during the build: everything decided at or before the fill ------------------

ENTRY_COLUMNS = ["direction", "signal_ns", "entry_ns", "entry_price", "entry_bid", "entry_spread", "stop", "target",
                 "stop_distance", "lots"]


def entry_view(trades):
    """Trades without any exit or outcome field (build discipline, spec §4)."""
    keep = ENTRY_COLUMNS + [c for c in trades.columns if c.startswith("info_")]
    return trades[[c for c in keep if c in trades.columns]].copy()
