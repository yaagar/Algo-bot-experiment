"""Experiment 4 trading rules on top of the Experiment 2 engine (spec §2, §5).

Plain English: at each H1 close inside the entry window, if we are flat, the forecast |F| is at
least 0.30, the shock gate is open, fewer than 3 trades were opened today and no USD news event is
within 5 minutes, we enter in the direction of F at the next bar's open. Risk = min(1, |F|/0.60) R,
stop = 1.5 x ATR(14, H1) from the fill. We exit at the next open after an H1 close where F flips
sign or |F| < 0.10, when the stop is hit (M1 bars, stop wins ties), or at the flat-by time.

The engine (fills, spread, M1 stop checks, forced exits, costs) is Experiment 2's, unchanged.
E4Engine only adds two things around its fill step: risk scaled by forecast strength, and a
refusal to fill after the day's flat-by time (a data gap could otherwise push a fill to the next day).
"""
from collections import defaultdict

import numpy as np

from src.exp2.engine import Costs, Engine, Order, Swap, trades_frame
from src.exp4.signals import SIGNALS, compute

NO_SWAP = Swap(0.0, 0.0)          # intraday, flat every day (spec §6)


class E4Engine(Engine):
    def __init__(self, *args, on_fill=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.on_fill = on_fill

    def open_position(self, order, fill_ns, bid, spread, res):
        if fill_ns >= order.time_exit_ns:
            return self._block(res, fill_ns, "fill at/after flat-by")
        pos = super().open_position(order, fill_ns, bid, spread, res)
        if pos is not None:
            pos.lots *= order.info["size"]          # risk = size x R; results stay in R of that trade
            if self.on_fill:
                self.on_fill(order)
        return pos


class E4Strategy:
    """Signal/exit callbacks for Engine.run, reading the precomputed forecast table."""

    def __init__(self, mk, table, cfg, events):
        tc = cfg["trading"]
        self.bars = mk.h1
        self.table = table
        self.F = table.F.to_numpy()
        self.t_close = table.t_close.to_numpy()
        self.day = table.day_idx.to_numpy()
        self.window, self.shock_ok = table.in_window.to_numpy(), table.shock_ok.to_numpy()
        self.atr = table.atr14.to_numpy()
        self.flat_ns = np.array([mk.clock.at(d, mk.cfg["flat_by"]) for d in mk.days], dtype=np.int64)
        self.tc, self.events = tc, events
        self.fills_today = defaultdict(int)
        cols = ["F"] + [f"score_{s}" for s in SIGNALS]
        vals = np.round(table[cols].to_numpy(), 9)
        flags = table[["trending", "ranging", "shock_ok", "in_window"]].to_numpy()
        # every bar's forecast is a logged decision, so the leak test compares them all
        self.decisions = [(int(t), "forecast", tuple(v) + tuple(bool(x) for x in f), int(t))
                          for t, v, f in zip(self.t_close, vals, flags)]

    def count_fill(self, order):
        self.fills_today[order.info["day_idx"]] += 1

    def signal(self, i):
        f, d, tc = self.F[i], self.day[i], self.tc
        if not (self.window[i] and abs(f) >= tc["entry_threshold"] and self.shock_ok[i]):
            return None
        if self.fills_today[d] >= tc["max_entries_per_day"] or self.events.within(self.t_close[i], tc["news_blackout_min"]):
            return None
        if not self.atr[i] > 0:
            return None
        direction = 1 if f > 0 else -1
        dist = tc["stop_atr"] * self.atr[i]
        row = self.table.iloc[i]
        info = {"day_idx": int(d), "size": min(1.0, abs(f) / tc["full_size_forecast"]), "F": f, "atr14": self.atr[i],
                **{s: row[f"score_{s}"] for s in SIGNALS},
                "efficiency": row.efficiency, "shock_ratio": row.shock_ratio}
        return Order(direction, int(self.t_close[i]), lambda price, spread: price - direction * dist,
                     time_exit_ns=int(self.flat_ns[d]), info=info)

    def exit_signal(self, i, pos):
        f = self.F[i]
        return np.sign(f) != pos.order.direction or abs(f) < self.tc["exit_threshold"]


def run_market(mk, cfg, events, spread_mult=1.0, commission_mult=1.0):
    """Run one market. Returns (engine Result, forecast table, trades DataFrame)."""
    table = compute(mk, cfg)
    strat = E4Strategy(mk, table, cfg, events)
    costs = Costs(spread_mult, mk.cfg["commission_pct_per_side"] * commission_mult)
    engine = E4Engine(mk.m1, events, costs, NO_SWAP, risk_usd=cfg["trading"]["risk_usd"],
                      contract=mk.cfg["contract_size"], blackout_min=cfg["trading"]["news_blackout_min"],
                      weekend_rule=False, on_fill=strat.count_fill)
    res = engine.run(strat)
    trades = trades_frame(res)
    if len(trades):
        trades.insert(0, "market", mk.name)
        trades["r_of_full_R"] = trades.net_r * trades.info_size    # result in units of the full R
        trades["ftmo_flagged_exit"] = [events.within(t, cfg["trading"]["ftmo_flag_min"]) for t in trades.exit_ns]
    return res, table, trades
